"""
GPT Researcher 的 MCP（Model Context Protocol）集成

本模块提供完整的 MCP 集成能力，包括：
- MCP 服务器客户端管理
- 工具选择与执行
- 使用 MCP 工具进行研究执行
- 实时更新的流式支持
"""

import logging

logger = logging.getLogger(__name__)

try:
    # 检查 langchain-mcp-adapters 是否可用
    from langchain_mcp_adapters.client import MultiServerMCPClient
    HAS_MCP_ADAPTERS = True
    logger.debug("langchain-mcp-adapters 可用")
    
    # 导入 MCP 核心组件
    from .client import MCPClientManager
    from .tool_selector import MCPToolSelector
    from .research import MCPResearchSkill
    from .streaming import MCPStreamer
    
    __all__ = [
        "MCPClientManager",
        "MCPToolSelector", 
        "MCPResearchSkill",
        "MCPStreamer",
        "HAS_MCP_ADAPTERS"
    ]
    
except ImportError as e:
    logger.warning(f"MCP 依赖不可用: {e}")
    HAS_MCP_ADAPTERS = False
    __all__ = ["HAS_MCP_ADAPTERS"]
    
except Exception as e:
    logger.error(f"导入 MCP 组件时发生意外错误: {e}")
    HAS_MCP_ADAPTERS = False
    __all__ = ["HAS_MCP_ADAPTERS"] 
