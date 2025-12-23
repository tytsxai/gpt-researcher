"""
MCP 研究执行能力

使用选定的 MCP 工具作为技能组件来执行研究。
"""
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class MCPResearchSkill:
    """
    使用选定的 MCP 工具执行研究。

    负责：
    - 使用 LLM 与已绑定的工具执行研究
    - 将工具结果处理为标准格式
    - 管理工具执行与错误处理
    """

    def __init__(self, cfg, researcher=None):
        """
        初始化 MCP 研究技能。

        Args:
            cfg: 包含 LLM 设置的配置对象
            researcher: 用于成本跟踪的研究者实例
        """
        self.cfg = cfg
        self.researcher = researcher

    async def conduct_research_with_tools(self, query: str, selected_tools: List) -> List[Dict[str, str]]:
        """
        使用已绑定工具的 LLM 进行智能研究。

        Args:
            query: 研究查询
            selected_tools: 已选择的 MCP 工具列表

        Returns:
            List[Dict[str, str]]: 标准格式的研究结果
        """
        if not selected_tools:
            logger.warning("没有可用于研究的工具")
            return []
            
        logger.info(f"使用 {len(selected_tools)} 个已选工具进行研究")
        
        try:
            from ..llm_provider.generic.base import GenericLLMProvider
            
            # 使用配置创建 LLM 提供方
            provider_kwargs = {
                'model': self.cfg.strategic_llm_model,
                **self.cfg.llm_kwargs
            }
            
            llm_provider = GenericLLMProvider.from_provider(
                self.cfg.strategic_llm_provider, 
                **provider_kwargs
            )
            
            # 将工具绑定到 LLM
            llm_with_tools = llm_provider.llm.bind_tools(selected_tools)
            
            # 在此处导入以避免循环依赖
            from ..prompts import PromptFamily
            
            # 创建研究提示词
            research_prompt = PromptFamily.generate_mcp_research_prompt(query, selected_tools)

            # 创建消息
            messages = [{"role": "user", "content": research_prompt}]
            
            # 调用带工具的 LLM
            logger.info("大模型正在使用绑定工具进行研究...")
            response = await llm_with_tools.ainvoke(messages)
            
            # 处理工具调用与结果
            research_results = []
            
            # 检查 LLM 是否进行了工具调用
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"大模型进行了 {len(response.tool_calls)} 次工具调用")
                
                # 处理每次工具调用
                for i, tool_call in enumerate(response.tool_calls, 1):
                    tool_name = tool_call.get("name", "未知")
                    tool_args = tool_call.get("args", {})
                    
                    logger.info(f"执行工具 {i}/{len(response.tool_calls)}: {tool_name}")
                    
                    # 记录工具参数以便透明可追踪
                    if tool_args:
                        args_str = ", ".join([f"{k}={v}" for k, v in tool_args.items()])
                        logger.debug(f"工具参数: {args_str}")
                    
                    try:
                        # 通过名称查找工具
                        tool = next((t for t in selected_tools if t.name == tool_name), None)
                        if not tool:
                            logger.warning(f"未在已选工具中找到工具 {tool_name}")
                            continue
                        
                        # 执行工具
                        if hasattr(tool, 'ainvoke'):
                            result = await tool.ainvoke(tool_args)
                        elif hasattr(tool, 'invoke'):
                            result = tool.invoke(tool_args)
                        else:
                            result = await tool(tool_args) if asyncio.iscoroutinefunction(tool) else tool(tool_args)
                        
                        # 记录实际工具响应以便调试
                        if result:
                            result_preview = str(result)[:500] + "..." if len(str(result)) > 500 else str(result)
                            logger.debug(f"工具 {tool_name} 响应预览: {result_preview}")
                            
                            # 处理结果
                            formatted_results = self._process_tool_result(tool_name, result)
                            research_results.extend(formatted_results)
                            logger.info(f"工具 {tool_name} 返回了 {len(formatted_results)} 条格式化结果")
                            
                            # 记录每条格式化结果的详情
                            for j, formatted_result in enumerate(formatted_results):
                                title = formatted_result.get("title", "无标题")
                                content_preview = formatted_result.get("body", "")[:200] + "..." if len(formatted_result.get("body", "")) > 200 else formatted_result.get("body", "")
                                logger.debug(f"结果 {j+1}: '{title}' - 内容: {content_preview}")
                        else:
                            logger.warning(f"工具 {tool_name} 返回空结果")
                            
                    except Exception as e:
                        logger.error(f"执行工具 {tool_name} 时出错: {e}")
                        continue
                        
            # 同时将 LLM 自身的分析/响应作为结果
            if hasattr(response, 'content') and response.content:
                llm_analysis = {
                    "title": f"大模型分析: {query}",
                    "href": "mcp://llm_analysis",
                    "body": response.content
                }
                research_results.append(llm_analysis)
                
                # 记录 LLM 分析内容
                analysis_preview = response.content[:300] + "..." if len(response.content) > 300 else response.content
                logger.debug(f"大模型分析: {analysis_preview}")
                logger.info("已将大模型分析加入结果")
            
            logger.info(f"研究完成，共 {len(research_results)} 条结果")
            return research_results
            
        except Exception as e:
            logger.error(f"使用工具进行大模型研究时出错: {e}")
            return []

    def _process_tool_result(self, tool_name: str, result: Any) -> List[Dict[str, str]]:
        """
        将工具结果处理为搜索结果格式。

        Args:
            tool_name: 产生结果的工具名称
            result: 工具结果

        Returns:
            List[Dict[str, str]]: 格式化后的搜索结果
        """
        search_results = []
        
        try:
            # 1) 先处理带 structured_content/content 的 MCP 结果包装
            if isinstance(result, dict) and ("structured_content" in result or "content" in result):
                search_results = []
                # 优先使用 structured_content
                structured = result.get("structured_content")
                if isinstance(structured, dict):
                    items = structured.get("results")
                    if isinstance(items, list):
                        for i, item in enumerate(items):
                            if isinstance(item, dict):
                                search_results.append({
                                    "title": item.get("title", f"来自 {tool_name} 的结果 #{i+1}"),
                                    "href": item.get("href", item.get("url", f"mcp://{tool_name}/{i}")),
                                    "body": item.get("body", item.get("content", str(item)))
                                })
                    # structured 为 dict 且没有 items 数组时，视为单个结果
                    elif isinstance(structured, dict):
                        search_results.append({
                            "title": structured.get("title", f"来自 {tool_name} 的结果"),
                            "href": structured.get("href", structured.get("url", f"mcp://{tool_name}")),
                            "body": structured.get("body", structured.get("content", str(structured)))
                        })
                # 若提供 content 则回退使用（MCP 规范：{type: text, text: ...} 列表）
                if not search_results:
                    content_field = result.get("content")
                    if isinstance(content_field, list):
                        texts = []
                        for part in content_field:
                            if isinstance(part, dict):
                                if part.get("type") == "text" and isinstance(part.get("text"), str):
                                    texts.append(part["text"])
                                elif "text" in part:
                                    texts.append(str(part.get("text")))
                                else:
                                    # 未知片段，转为字符串
                                    texts.append(str(part))
                            else:
                                texts.append(str(part))
                        body_text = "\n\n".join([t for t in texts if t])
                    elif isinstance(content_field, str):
                        body_text = content_field
                    else:
                        body_text = str(result)
                    search_results.append({
                        "title": f"来自 {tool_name} 的结果",
                        "href": f"mcp://{tool_name}",
                        "body": body_text,
                    })
                return search_results

            # 2) 如果结果已是列表，逐项处理
            if isinstance(result, list):
                # 结果为列表时，逐项处理
                for i, item in enumerate(result):
                    if isinstance(item, dict):
                        # 若包含必要字段则直接使用
                        if "title" in item and ("content" in item or "body" in item):
                            search_result = {
                                "title": item.get("title", ""),
                                "href": item.get("href", item.get("url", f"mcp://{tool_name}/{i}")),
                                "body": item.get("body", item.get("content", str(item))),
                            }
                            search_results.append(search_result)
                        else:
                            # 创建带通用标题的搜索结果
                            search_result = {
                                "title": f"来自 {tool_name} 的结果",
                                "href": f"mcp://{tool_name}/{i}",
                                "body": str(item),
                            }
                            search_results.append(search_result)
            # 3) 如果结果是 dict（非 MCP 包装），作为单个搜索结果
            elif isinstance(result, dict):
                # 结果为字典时，作为单个搜索结果
                search_result = {
                    "title": result.get("title", f"来自 {tool_name} 的结果"),
                    "href": result.get("href", result.get("url", f"mcp://{tool_name}")),
                    "body": result.get("body", result.get("content", str(result))),
                }
                search_results.append(search_result)
            else:
                # 其他类型转为字符串并作为单个搜索结果
                search_result = {
                    "title": f"来自 {tool_name} 的结果",
                    "href": f"mcp://{tool_name}",
                    "body": str(result),
                }
                search_results.append(search_result)
                
        except Exception as e:
            logger.error(f"处理来自 {tool_name} 的工具结果时出错: {e}")
            # 回退：创建基础结果
            search_result = {
                "title": f"来自 {tool_name} 的结果",
                "href": f"mcp://{tool_name}",
                "body": str(result),
            }
            search_results.append(search_result)
        
        return search_results 
