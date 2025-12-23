"""
基于 MCP 的研究检索器

使用模型上下文协议（MCP）工具进行智能研究的检索器。
该检索器采用两阶段方法：
1. 工具选择：LLM 从所有可用 MCP 工具中选择 2-3 个最相关的工具
2. 研究执行：LLM 使用所选工具进行智能研究
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    HAS_MCP_ADAPTERS = True
except ImportError:
    HAS_MCP_ADAPTERS = False

from ...mcp.client import MCPClientManager
from ...mcp.tool_selector import MCPToolSelector
from ...mcp.research import MCPResearchSkill
from ...mcp.streaming import MCPStreamer

logger = logging.getLogger(__name__)


class MCPRetriever:
    """
    用于 GPT Researcher 的模型上下文协议（MCP）检索器。
    
    该检索器采用两阶段方法：
    1. 工具选择：LLM 从所有可用 MCP 工具中选择 2-3 个最相关的工具
    2. 研究执行：绑定工具的 LLM 进行智能研究
    
    相比调用所有工具，这种方式更高效，并能提供更有针对性的研究结果。
    
    该检索器需要 researcher 实例以访问：
    - mcp_configs: MCP 服务器配置列表
    - cfg: 包含 LLM 设置和参数的配置对象
    - add_costs: 用于跟踪研究成本的方法
    """

    def __init__(
        self, 
        query: str, 
        headers: Optional[Dict[str, str]] = None,
        query_domains: Optional[List[str]] = None,
        websocket=None,
        researcher=None,
        **kwargs
    ):
        """
        初始化 MCP 检索器。
        
        参数:
            query (str): 搜索查询字符串。
            headers (dict, optional): 包含 MCP 配置的请求头。
            query_domains (list, optional): 要搜索的域名列表（在 MCP 中未使用）。
            websocket: 用于流式日志的 WebSocket。
            researcher: 包含 mcp_configs 与 cfg 的 Researcher 实例。
            **kwargs: 其他参数（用于兼容）。
        """
        self.query = query
        self.headers = headers or {}
        self.query_domains = query_domains or []
        self.websocket = websocket
        self.researcher = researcher
        
        # 从 researcher 实例中提取 mcp_configs 和配置
        self.mcp_configs = self._get_mcp_configs()
        self.cfg = self._get_config()
        
        # 初始化模块化组件
        self.client_manager = MCPClientManager(self.mcp_configs)
        self.tool_selector = MCPToolSelector(self.cfg, self.researcher)
        self.mcp_researcher = MCPResearchSkill(self.cfg, self.researcher)
        self.streamer = MCPStreamer(self.websocket)
        
        # 初始化缓存
        self._all_tools_cache = None
        
        # 记录初始化日志
        if self.mcp_configs:
            self.streamer.stream_log_sync(f"🔧 正在初始化 MCP 检索器，查询：{self.query}")
            self.streamer.stream_log_sync(f"🔧 找到 {len(self.mcp_configs)} 个 MCP 服务器配置")
        else:
            logger.error("未找到 MCP 服务器配置。检索将在搜索时失败。")
            self.streamer.stream_log_sync("❌ 严重错误：未找到 MCP 服务器配置。请检查文档。")

    def _get_mcp_configs(self) -> List[Dict[str, Any]]:
        """
        从 researcher 实例获取 MCP 配置。
        
        返回:
            List[Dict[str, Any]]: MCP 服务器配置列表。
        """
        if self.researcher and hasattr(self.researcher, 'mcp_configs'):
            return self.researcher.mcp_configs or []
        return []

    def _get_config(self):
        """
        从 researcher 实例获取配置。
        
        返回:
            Config: 包含 LLM 设置的配置对象。
        """
        if self.researcher and hasattr(self.researcher, 'cfg'):
            return self.researcher.cfg
        
        # 如果没有配置，这是致命错误
        logger.error("researcher 实例中未找到配置。MCPRetriever 需要包含 cfg 属性的 researcher 实例。")
        raise ValueError("MCPRetriever 需要包含 LLM 配置的 cfg 属性的 researcher 实例")

    async def search_async(self, max_results: int = 10) -> List[Dict[str, str]]:
        """
        使用 MCP 工具以智能两阶段方式执行异步搜索。
        
        参数:
            max_results: 返回结果的最大数量。
            
        返回:
            List[Dict[str, str]]: 搜索结果。
        """
        # 检查是否有服务器配置
        if not self.mcp_configs:
            error_msg = "没有可用的 MCP 服务器配置。请为 GPTResearcher 提供 mcp_configs 参数。"
            logger.error(error_msg)
            await self.streamer.stream_error("没有服务器配置，MCP 检索器无法继续。")
            return []  # 返回空结果以允许研究继续
            
        # 记录日志以便调试集成流程
        logger.info(f"MCPRetriever.search_async 被调用，查询：{self.query}")
            
        try:
            # 阶段 1：获取所有可用工具
            await self.streamer.stream_stage_start("阶段 1", "获取所有可用的 MCP 工具")
            all_tools = await self._get_all_tools()
            
            if not all_tools:
                await self.streamer.stream_warning("没有可用的 MCP 工具，跳过 MCP 研究")
                return []
            
            # 阶段 2：选择最相关的工具
            await self.streamer.stream_stage_start("阶段 2", "选择最相关的工具")
            selected_tools = await self.tool_selector.select_relevant_tools(self.query, all_tools, max_tools=3)
            
            if not selected_tools:
                await self.streamer.stream_warning("未选择到相关工具，跳过 MCP 研究")
                return []
            
            # 阶段 3：使用所选工具开展研究
            await self.streamer.stream_stage_start("阶段 3", "使用所选工具开展研究")
            results = await self.mcp_researcher.conduct_research_with_tools(self.query, selected_tools)
            
            # 限制结果数量
            if len(results) > max_results:
                logger.info(f"将 {len(results)} 条 MCP 结果限制为 {max_results}")
                results = results[:max_results]
            
            # 记录结果摘要与内容样本
            logger.info(f"MCPRetriever 返回 {len(results)} 条结果")
            
            # 计算摘要所需的总内容长度
            total_content_length = sum(len(result.get("body", "")) for result in results)
            await self.streamer.stream_research_results(len(results), total_content_length)
            
            # 记录详细内容样本以便调试
            if results:
                # 展示前几条结果的样本
                for i, result in enumerate(results[:3]):  # 展示前 3 条结果
                    title = result.get("title", "无标题")
                    url = result.get("href", "无 URL")
                    content = result.get("body", "")
                    content_length = len(content)
                    content_sample = content[:400] + "..." if len(content) > 400 else content
                    
                    logger.debug(f"结果 {i+1}/{len(results)}：'{title}'")
                    logger.debug(f"URL：{url}")
                    logger.debug(f"内容（{content_length:,} 字符）：{content_sample}")
                    
                if len(results) > 3:
                    remaining_results = len(results) - 3
                    remaining_content = sum(len(result.get("body", "")) for result in results[3:])
                    logger.debug(f"... 以及另外 {remaining_results} 条结果（{remaining_content:,} 字符）")
                    
            return results
            
        except Exception as e:
            logger.error(f"MCP 搜索出错：{e}")
            await self.streamer.stream_error(f"MCP 搜索出错：{str(e)}")
            return []
        finally:
            # 搜索完成后确保清理客户端
            try:
                await self.client_manager.close_client()
            except Exception as e:
                logger.error(f"客户端清理时出错：{e}")

    def search(self, max_results: int = 10) -> List[Dict[str, str]]:
        """
        使用 MCP 工具以智能两阶段方式执行搜索。
        
        这是 GPT Researcher 需要的同步接口。
        该方法封装了异步的 search_async。
        
        参数:
            max_results: 返回结果的最大数量。
            
        返回:
            List[Dict[str, str]]: 搜索结果。
        """
        # 检查是否有服务器配置
        if not self.mcp_configs:
            error_msg = "没有可用的 MCP 服务器配置。请为 GPTResearcher 提供 mcp_configs 参数。"
            logger.error(error_msg)
            self.streamer.stream_log_sync("❌ 没有服务器配置，MCP 检索器无法继续。")
            return []  # 返回空结果以允许研究继续
            
        # 记录日志以便调试集成流程
        logger.info(f"MCPRetriever.search 被调用，查询：{self.query}")
        
        try:
            # 妥善处理异步与同步边界
            try:
                # 尝试获取当前事件循环
                loop = asyncio.get_running_loop()
                # 若在异步上下文，需要调度协程
                # 这里有些复杂：创建任务并让其运行
                import concurrent.futures
                import threading
                
                # 在独立线程中创建新的事件循环
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result = new_loop.run_until_complete(self.search_async(max_results))
                        return result
                    finally:
                        # 针对 MCP 连接的增强清理流程
                        try:
                            # 取消所有待处理任务并设置超时
                            pending = asyncio.all_tasks(new_loop)
                            for task in pending:
                                task.cancel()
                            
                            # 等待取消任务完成，并设置超时
                            if pending:
                                try:
                                    new_loop.run_until_complete(
                                        asyncio.wait_for(
                                            asyncio.gather(*pending, return_exceptions=True),
                                            timeout=5.0  # 清理超时 5 秒
                                        )
                                    )
                                except asyncio.TimeoutError:
                                    logger.debug("任务清理超时，继续执行...")
                                except Exception:
                                    pass  # 忽略其他清理错误
                        except Exception:
                            pass  # 忽略清理错误
                        finally:
                            try:
                                # 给事件循环一点时间完成最终清理
                                import time
                                time.sleep(0.1)
                                
                                # 强制垃圾回收以清理残余引用
                                import gc
                                gc.collect()
                                
                                # 给 HTTP 客户端额外时间完成清理
                                time.sleep(0.2)
                                
                                # 关闭事件循环
                                if not new_loop.is_closed():
                                    new_loop.close()
                            except Exception:
                                pass  # 忽略关闭错误
                
                # 在线程池中运行以避免阻塞主事件循环
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    results = future.result(timeout=300)  # 5 分钟超时
                    
            except RuntimeError:
                # 没有运行中的事件循环，直接运行
                results = asyncio.run(self.search_async(max_results))
            
            return results
            
        except Exception as e:
            logger.error(f"MCP 搜索出错：{e}")
            self.streamer.stream_log_sync(f"❌ MCP 搜索出错：{str(e)}")
            # 返回空结果以允许研究继续
            return []

    async def _get_all_tools(self) -> List:
        """
        从 MCP 服务器获取所有可用工具。
        
        返回:
            List: 所有可用的 MCP 工具
        """
        if self._all_tools_cache is not None:
            return self._all_tools_cache
            
        try:
            all_tools = await self.client_manager.get_all_tools()
            
            if all_tools:
                await self.streamer.stream_log(f"📋 从 MCP 服务器加载了 {len(all_tools)} 个工具")
                self._all_tools_cache = all_tools
                return all_tools
            else:
                await self.streamer.stream_warning("MCP 服务器没有可用工具")
                return []
                
        except Exception as e:
            logger.error(f"获取 MCP 工具时出错：{e}")
            await self.streamer.stream_error(f"获取 MCP 工具时出错：{str(e)}")
            return []
