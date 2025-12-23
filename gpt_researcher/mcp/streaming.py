"""
MCP 流式工具模块

处理 MCP 操作的 WebSocket 流式输出与日志记录。
"""
import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MCPStreamer:
    """
    处理 MCP 操作的流式输出。

    负责：
    - 将日志流式发送到 websocket
    - 同步/异步日志记录
    - 流式输出的错误处理
    """

    def __init__(self, websocket=None):
        """
        初始化 MCP 流式输出器。

        Args:
            websocket: 用于流式输出的 WebSocket
        """
        self.websocket = websocket

    async def stream_log(self, message: str, data: Any = None):
        """如可用则将日志消息流式发送到 websocket。"""
        logger.info(message)
        
        if self.websocket:
            try:
                from ..actions.utils import stream_output
                await stream_output(
                    type="logs", 
                    content="mcp_retriever", 
                    output=message, 
                    websocket=self.websocket,
                    metadata=data
                )
            except Exception as e:
                logger.error(f"流式发送日志出错: {e}")
                
    def stream_log_sync(self, message: str, data: Any = None):
        """用于同步场景的 stream_log 同步版本。"""
        logger.info(message)
        
        if self.websocket:
            try:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self.stream_log(message, data))
                    else:
                        loop.run_until_complete(self.stream_log(message, data))
                except RuntimeError:
                    logger.debug("无法流式发送日志：没有正在运行的事件循环")
            except Exception as e:
                logger.error(f"同步日志流式发送出错: {e}")

    async def stream_stage_start(self, stage: str, description: str):
        """流式输出研究阶段开始。"""
        await self.stream_log(f"🔧 {stage}: {description}")

    async def stream_stage_complete(self, stage: str, result_count: int = None):
        """流式输出研究阶段完成。"""
        if result_count is not None:
            await self.stream_log(f"✅ {stage} 完成: {result_count} 条结果")
        else:
            await self.stream_log(f"✅ {stage} 完成")

    async def stream_tool_selection(self, selected_count: int, total_count: int):
        """流式输出工具选择信息。"""
        await self.stream_log(f"🧠 使用大模型从 {total_count} 个工具中选择最相关的 {selected_count} 个")

    async def stream_tool_execution(self, tool_name: str, step: int, total: int):
        """流式输出工具执行进度。"""
        await self.stream_log(f"🔍 执行工具 {step}/{total}: {tool_name}")

    async def stream_research_results(self, result_count: int, total_chars: int = None):
        """流式输出研究结果摘要。"""
        if total_chars:
            await self.stream_log(f"✅ MCP 研究完成：获得 {result_count} 条结果（{total_chars:,} 字符）")
        else:
            await self.stream_log(f"✅ MCP 研究完成：获得 {result_count} 条结果")

    async def stream_error(self, error_msg: str):
        """流式输出错误信息。"""
        await self.stream_log(f"❌ {error_msg}")

    async def stream_warning(self, warning_msg: str):
        """流式输出警告信息。"""
        await self.stream_log(f"⚠️ {warning_msg}")

    async def stream_info(self, info_msg: str):
        """流式输出提示信息。"""
        await self.stream_log(f"ℹ️ {info_msg}")
