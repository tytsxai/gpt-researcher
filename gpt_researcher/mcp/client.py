"""
MCP 客户端管理模块

处理 MCP 客户端创建、配置转换与连接管理。
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    HAS_MCP_ADAPTERS = True
except ImportError:
    HAS_MCP_ADAPTERS = False

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    管理 MCP 客户端的生命周期与配置。

    负责：
    - 将 GPT Researcher 的 MCP 配置转换为 langchain 格式
    - 创建并管理 MultiServerMCPClient 实例
    - 处理客户端清理与资源管理
    """

    def __init__(self, mcp_configs: List[Dict[str, Any]]):
        """
        初始化 MCP 客户端管理器。

        Args:
            mcp_configs: 来自 GPT Researcher 的 MCP 服务器配置列表
        """
        self.mcp_configs = mcp_configs or []
        self._client = None
        self._client_lock = asyncio.Lock()

    def convert_configs_to_langchain_format(self) -> Dict[str, Dict[str, Any]]:
        """
        将 GPT Researcher 的 MCP 配置转换为 langchain-mcp-adapters 格式。

        Returns:
            Dict[str, Dict[str, Any]]: 供 MultiServerMCPClient 使用的服务器配置
        """
        server_configs = {}
        
        for i, config in enumerate(self.mcp_configs):
            # 生成服务器名称
            server_name = config.get("name", f"mcp_server_{i+1}")
            
            # 构建服务器配置
            server_config = {}
            
            # 如果提供了 URL，则自动检测传输类型
            connection_url = config.get("connection_url")
            if connection_url:
                if connection_url.startswith(("wss://", "ws://")):
                    server_config["transport"] = "websocket"
                    server_config["url"] = connection_url
                elif connection_url.startswith(("https://", "http://")):
                    server_config["transport"] = "streamable_http"
                    server_config["url"] = connection_url
                else:
                    # 回退到指定的 connection_type 或 stdio
                    connection_type = config.get("connection_type", "stdio")
                    server_config["transport"] = connection_type
                    if connection_type in ["websocket", "streamable_http", "http"]:
                        server_config["url"] = connection_url
            else:
                # 未提供 URL，使用 stdio（默认）或指定的 connection_type
                connection_type = config.get("connection_type", "stdio")
                server_config["transport"] = connection_type
            
            # 处理 stdio 传输配置
            if server_config.get("transport") == "stdio":
                if config.get("command"):
                    server_config["command"] = config["command"]
                    
                    # 处理 server_args
                    server_args = config.get("args", [])
                    if isinstance(server_args, str):
                        server_args = server_args.split()
                    server_config["args"] = server_args
                    
                    # 处理环境变量
                    server_env = config.get("env", {})
                    if server_env:
                        server_config["env"] = server_env
                        
            # 如有提供则添加认证信息
            if config.get("connection_token"):
                server_config["token"] = config["connection_token"]
                
            server_configs[server_name] = server_config
            
        return server_configs

    async def get_or_create_client(self) -> Optional[object]:
        """
        获取或创建 MultiServerMCPClient，并进行正确的生命周期管理。

        Returns:
            MultiServerMCPClient: 客户端实例；若创建失败则为 None
        """
        async with self._client_lock:
            if self._client is not None:
                return self._client
                
            if not HAS_MCP_ADAPTERS:
                logger.error("langchain-mcp-adapters 未安装")
                return None
                
            if not self.mcp_configs:
                logger.error("未找到 MCP 服务器配置")
                return None
                
            try:
                # 将配置转换为 langchain 格式
                server_configs = self.convert_configs_to_langchain_format()
                logger.info(f"正在为 {len(server_configs)} 个服务器创建 MCP 客户端")
                
                # 初始化 MultiServerMCPClient
                self._client = MultiServerMCPClient(server_configs)
                
                return self._client
                
            except Exception as e:
                logger.error(f"创建 MCP 客户端时出错: {e}")
                return None

    async def close_client(self):
        """
        正确关闭 MCP 客户端并清理资源。
        """
        async with self._client_lock:
            if self._client is not None:
                try:
                    # 由于 langchain-mcp-adapters 0.1.0 中的 MultiServerMCPClient
                    # 不支持上下文管理器或显式关闭方法，这里仅清除引用并交由 GC 处理
                    logger.debug("释放 MCP 客户端引用")
                except Exception as e:
                    logger.error(f"清理 MCP 客户端时出错: {e}")
                finally:
                    # 始终清除引用
                    self._client = None

    async def get_all_tools(self) -> List:
        """
        获取 MCP 服务器中所有可用工具。

        Returns:
            List: 所有可用的 MCP 工具
        """
        client = await self.get_or_create_client()
        if not client:
            return []
            
        try:
            # 从所有服务器获取工具
            all_tools = await client.get_tools()
            
            if all_tools:
                logger.info(f"从 MCP 服务器加载了 {len(all_tools)} 个工具")
                return all_tools
            else:
                logger.warning("MCP 服务器没有可用的工具")
                return []
                
        except Exception as e:
            logger.error(f"获取 MCP 工具时出错: {e}")
            return [] 
