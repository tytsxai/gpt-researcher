"""
MCP 工具选择模块

使用 LLM 分析进行智能工具选择。
"""
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class MCPToolSelector:
    """
    使用 LLM 分析进行 MCP 工具的智能选择。

    负责：
    - 使用 LLM 分析可用工具
    - 为查询选择最相关的工具
    - 提供回退选择机制
    """

    def __init__(self, cfg, researcher=None):
        """
        初始化工具选择器。

        Args:
            cfg: 包含 LLM 设置的配置对象
            researcher: 用于成本跟踪的研究者实例
        """
        self.cfg = cfg
        self.researcher = researcher

    async def select_relevant_tools(self, query: str, all_tools: List, max_tools: int = 3) -> List:
        """
        使用 LLM 为研究查询选择最相关的工具。

        Args:
            query: 研究查询
            all_tools: 所有可用工具列表
            max_tools: 选择工具的最大数量（默认：3）

        Returns:
            List: 与查询最相关的已选工具
        """
        if not all_tools:
            return []

        if len(all_tools) < max_tools:
            max_tools = len(all_tools)
            
        logger.info(f"使用大模型从 {len(all_tools)} 个工具中选择最相关的 {max_tools} 个")
        
        # 为 LLM 分析创建工具描述
        tools_info = []
        for i, tool in enumerate(all_tools):
            tool_info = {
                "index": i,
                "name": tool.name,
                "description": tool.description or "暂无描述"
            }
            tools_info.append(tool_info)
        
        # 在此处导入以避免循环依赖
        from ..prompts import PromptFamily
        
        # 创建智能工具选择提示词
        prompt = PromptFamily.generate_mcp_tool_selection_prompt(query, tools_info, max_tools)

        try:
            # 调用 LLM 进行工具选择
            response = await self._call_llm_for_tool_selection(prompt)
            
            if not response:
                logger.warning("大模型未返回工具选择结果，使用回退方案")
                return self._fallback_tool_selection(all_tools, max_tools)
            
            # 记录 LLM 响应预览以便调试
            response_preview = response[:500] + "..." if len(response) > 500 else response
            logger.debug(f"大模型工具选择响应: {response_preview}")
            
            # 解析 LLM 响应
            try:
                selection_result = json.loads(response)
            except json.JSONDecodeError:
                # 尝试从响应中提取 JSON
                import re
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    try:
                        selection_result = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        logger.warning("无法解析提取的 JSON，使用回退方案")
                        return self._fallback_tool_selection(all_tools, max_tools)
                else:
                    logger.warning("大模型响应中未找到 JSON，使用回退方案")
                    return self._fallback_tool_selection(all_tools, max_tools)
            
            selected_tools = []
            
            # 处理已选择的工具
            for tool_selection in selection_result.get("selected_tools", []):
                tool_index = tool_selection.get("index")
                tool_name = tool_selection.get("name", "")
                reason = tool_selection.get("reason", "")
                relevance_score = tool_selection.get("relevance_score", 0)
                
                if tool_index is not None and 0 <= tool_index < len(all_tools):
                    selected_tools.append(all_tools[tool_index])
                    logger.info(f"已选择工具 '{tool_name}'（评分: {relevance_score}）：{reason}")
            
            if len(selected_tools) == 0:
                logger.warning("大模型未选择任何工具，使用回退选择")
                return self._fallback_tool_selection(all_tools, max_tools)
            
            # 记录整体选择理由
            selection_reasoning = selection_result.get("selection_reasoning", "未提供理由")
            logger.info(f"大模型选择策略: {selection_reasoning}")
            
            logger.info(f"大模型为研究选择了 {len(selected_tools)} 个工具")
            return selected_tools
            
        except Exception as e:
            logger.error(f"大模型工具选择出错: {e}")
            logger.warning("回退到基于模式的选择")
            return self._fallback_tool_selection(all_tools, max_tools)

    async def _call_llm_for_tool_selection(self, prompt: str) -> str:
        """
        使用现有的 create_chat_completion 调用 LLM 进行工具选择。

        Args:
            prompt (str): 发送给 LLM 的提示词。

        Returns:
            str: 生成的文本响应。
        """
        if not self.cfg:
            logger.warning("没有可用于大模型调用的配置")
            return ""
            
        try:
            from ..utils.llm import create_chat_completion
            
            # 创建 LLM 消息
            messages = [{"role": "user", "content": prompt}]
            
            # 使用战略 LLM 进行工具选择（需要更复杂的推理）
            result = await create_chat_completion(
                model=self.cfg.strategic_llm_model,
                messages=messages,
                temperature=0.0,  # 低温度以保证工具选择一致性
                llm_provider=self.cfg.strategic_llm_provider,
                llm_kwargs=self.cfg.llm_kwargs,
                cost_callback=self.researcher.add_costs if self.researcher and hasattr(self.researcher, 'add_costs') else None,
            )
            return result
        except Exception as e:
            logger.error(f"调用大模型进行工具选择出错: {e}")
            return ""

    def _fallback_tool_selection(self, all_tools: List, max_tools: int) -> List:
        """
        当 LLM 选择失败时，使用模式匹配进行工具回退选择。

        Args:
            all_tools: 所有可用工具列表
            max_tools: 选择工具的最大数量

        Returns:
            List: 已选择的工具
        """
        # 定义与研究相关的工具模式
        research_patterns = [
            'search', 'get', 'read', 'fetch', 'find', 'list', 'query', 
            'lookup', 'retrieve', 'browse', 'view', 'show', 'describe'
        ]
        
        scored_tools = []
        
        for tool in all_tools:
            tool_name = tool.name.lower()
            tool_description = (tool.description or "").lower()
            
            # 基于模式匹配计算相关性评分
            score = 0
            for pattern in research_patterns:
                if pattern in tool_name:
                    score += 3
                if pattern in tool_description:
                    score += 1
            
            if score > 0:
                scored_tools.append((tool, score))
        
        # 按评分排序并取前几个工具
        scored_tools.sort(key=lambda x: x[1], reverse=True)
        selected_tools = [tool for tool, score in scored_tools[:max_tools]]
        
        for i, (tool, score) in enumerate(scored_tools[:max_tools]):
            logger.info(f"回退选择工具 {i+1}: {tool.name}（评分: {score}）")
        
        return selected_tools 
