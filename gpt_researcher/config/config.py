import json
import os
import warnings
from typing import Dict, Any, List, Union, Type, get_origin, get_args

from gpt_researcher.llm_provider.generic.base import ReasoningEfforts
from .variables.default import DEFAULT_CONFIG
from .variables.base import BaseConfig


class Config:
    """GPT Researcher 的配置类。"""

    CONFIG_DIR = os.path.join(os.path.dirname(__file__), "variables")

    def __init__(self, config_path: str | None = None):
        """初始化配置类。"""
        self.config_path = config_path
        self.llm_kwargs: Dict[str, Any] = {}
        self.embedding_kwargs: Dict[str, Any] = {}

        config_to_use = self.load_config(config_path)
        self._set_attributes(config_to_use)
        self._set_embedding_attributes()
        self._set_llm_attributes()
        self._handle_deprecated_attributes()
        if config_to_use['REPORT_SOURCE'] != 'web':
          self._set_doc_path(config_to_use)

        # MCP 支持配置
        self.mcp_servers = []  # MCP 服务器配置列表
        self.mcp_allowed_root_paths = []  # MCP 服务器允许的根路径

        # 从配置中读取
        if hasattr(self, 'mcp_servers'):
            self.mcp_servers = self.mcp_servers
        if hasattr(self, 'mcp_allowed_root_paths'):
            self.mcp_allowed_root_paths = self.mcp_allowed_root_paths

    def _set_attributes(self, config: Dict[str, Any]) -> None:
        for key, value in config.items():
            env_value = os.getenv(key)
            if env_value is not None:
                value = self.convert_env_value(key, env_value, BaseConfig.__annotations__[key])
            setattr(self, key.lower(), value)

        # 处理 RETRIEVER 的默认值
        retriever_env = os.environ.get("RETRIEVER", config.get("RETRIEVER", "tavily"))
        try:
            self.retrievers = self.parse_retrievers(retriever_env)
        except ValueError as e:
            print(f"警告：{str(e)}。将默认使用 'tavily' 检索器。")
            self.retrievers = ["tavily"]

    def _set_embedding_attributes(self) -> None:
        self.embedding_provider, self.embedding_model = self.parse_embedding(
            self.embedding
        )

    def _set_llm_attributes(self) -> None:
        self.fast_llm_provider, self.fast_llm_model = self.parse_llm(self.fast_llm)
        self.smart_llm_provider, self.smart_llm_model = self.parse_llm(self.smart_llm)
        self.strategic_llm_provider, self.strategic_llm_model = self.parse_llm(self.strategic_llm)
        self.reasoning_effort = self.parse_reasoning_effort(os.getenv("REASONING_EFFORT"))

    def _handle_deprecated_attributes(self) -> None:
        if os.getenv("EMBEDDING_PROVIDER") is not None:
            warnings.warn(
                "EMBEDDING_PROVIDER 已弃用，即将移除。请使用 EMBEDDING 代替。",
                FutureWarning,
                stacklevel=2,
            )
            self.embedding_provider = (
                os.environ["EMBEDDING_PROVIDER"] or self.embedding_provider
            )

            embedding_provider = os.environ["EMBEDDING_PROVIDER"]
            if embedding_provider == "ollama":
                self.embedding_model = os.environ["OLLAMA_EMBEDDING_MODEL"]
            elif embedding_provider == "custom":
                self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "custom")
            elif embedding_provider == "openai":
                self.embedding_model = "text-embedding-3-large"
            elif embedding_provider == "azure_openai":
                self.embedding_model = "text-embedding-3-large"
            elif embedding_provider == "huggingface":
                self.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
            elif embedding_provider == "gigachat":
                self.embedding_model = "Embeddings"
            elif embedding_provider == "google_genai":
                self.embedding_model = "text-embedding-004"
            else:
                raise Exception("未找到嵌入提供者。")

        _deprecation_warning = (
            "LLM_PROVIDER、FAST_LLM_MODEL 和 SMART_LLM_MODEL 已弃用，"
            "即将移除。请使用 FAST_LLM 和 SMART_LLM 代替。"
        )
        if os.getenv("LLM_PROVIDER") is not None:
            warnings.warn(_deprecation_warning, FutureWarning, stacklevel=2)
            self.fast_llm_provider = (
                os.environ["LLM_PROVIDER"] or self.fast_llm_provider
            )
            self.smart_llm_provider = (
                os.environ["LLM_PROVIDER"] or self.smart_llm_provider
            )
        if os.getenv("FAST_LLM_MODEL") is not None:
            warnings.warn(_deprecation_warning, FutureWarning, stacklevel=2)
            self.fast_llm_model = os.environ["FAST_LLM_MODEL"] or self.fast_llm_model
        if os.getenv("SMART_LLM_MODEL") is not None:
            warnings.warn(_deprecation_warning, FutureWarning, stacklevel=2)
            self.smart_llm_model = os.environ["SMART_LLM_MODEL"] or self.smart_llm_model

    def _set_doc_path(self, config: Dict[str, Any]) -> None:
        self.doc_path = config['DOC_PATH']
        if self.doc_path:
            try:
                self.validate_doc_path()
            except Exception as e:
                print(f"警告：验证 doc_path 时出错：{str(e)}。使用默认 doc_path。")
                self.doc_path = DEFAULT_CONFIG['DOC_PATH']

    @classmethod
    def load_config(cls, config_path: str | None) -> Dict[str, Any]:
        """按名称加载配置。"""
        if config_path is None:
            return DEFAULT_CONFIG

        # config_path = os.path.join(cls.CONFIG_DIR, config_path)
        if not os.path.exists(config_path):
            if config_path and config_path != "default":
                print(f"警告：在 '{config_path}' 未找到配置。使用默认配置。")
                if not config_path.endswith(".json"):
                    print(f"你是指 '{config_path}.json' 吗？")
            return DEFAULT_CONFIG

        with open(config_path, "r") as f:
            custom_config = json.load(f)

        # 与默认配置合并以确保所有键都存在
        merged_config = DEFAULT_CONFIG.copy()
        merged_config.update(custom_config)
        return merged_config

    @classmethod
    def list_available_configs(cls) -> List[str]:
        """列出所有可用的配置名称。"""
        configs = ["default"]
        for file in os.listdir(cls.CONFIG_DIR):
            if file.endswith(".json"):
                configs.append(file[:-5])  # 移除 .json 后缀
        return configs

    def parse_retrievers(self, retriever_str: str) -> List[str]:
        """解析检索器字符串为列表并校验其有效性。"""
        from ..retrievers.utils import get_all_retriever_names
        
        retrievers = [retriever.strip()
                      for retriever in retriever_str.split(",")]
        valid_retrievers = get_all_retriever_names() or []
        invalid_retrievers = [r for r in retrievers if r not in valid_retrievers]
        if invalid_retrievers:
            raise ValueError(
                f"发现无效的检索器：{', '.join(invalid_retrievers)}。"
                f"可用选项：{', '.join(valid_retrievers)}。"
            )
        return retrievers

    @staticmethod
    def parse_llm(llm_str: str | None) -> tuple[str | None, str | None]:
        """将 llm 字符串解析为 (llm_provider, llm_model)。"""
        from gpt_researcher.llm_provider.generic.base import _SUPPORTED_PROVIDERS

        if llm_str is None:
            return None, None
        try:
            llm_provider, llm_model = llm_str.split(":", 1)
            assert llm_provider in _SUPPORTED_PROVIDERS, (
                f"不支持 {llm_provider}。\n可用的 LLM 提供方："
                + ", ".join(_SUPPORTED_PROVIDERS)
            )
            return llm_provider, llm_model
        except ValueError:
            raise ValueError(
                "请设置 SMART_LLM 或 FAST_LLM = '<llm_provider>:<llm_model>' "
                "例如 'openai:gpt-4o-mini'"
            )

    @staticmethod
    def parse_reasoning_effort(reasoning_effort_str: str | None) -> str | None:
        """解析推理强度字符串为 (reasoning_effort)。"""
        if reasoning_effort_str is None:
            return ReasoningEfforts.Medium.value
        if reasoning_effort_str not in [effort.value for effort in ReasoningEfforts]:
            raise ValueError(
                f"无效的推理强度：{reasoning_effort_str}。可用选项：{', '.join([effort.value for effort in ReasoningEfforts])}"
            )
        return reasoning_effort_str

    @staticmethod
    def parse_embedding(embedding_str: str | None) -> tuple[str | None, str | None]:
        """将 embedding 字符串解析为 (embedding_provider, embedding_model)。"""
        from gpt_researcher.memory.embeddings import _SUPPORTED_PROVIDERS

        if embedding_str is None:
            return None, None
        try:
            embedding_provider, embedding_model = embedding_str.split(":", 1)
            assert embedding_provider in _SUPPORTED_PROVIDERS, (
                f"不支持 {embedding_provider}。\n可用的 embedding 提供方："
                + ", ".join(_SUPPORTED_PROVIDERS)
            )
            return embedding_provider, embedding_model
        except ValueError:
            raise ValueError(
                "请设置 EMBEDDING = '<embedding_provider>:<embedding_model>' "
                "例如 'openai:text-embedding-3-large'"
            )

    def validate_doc_path(self):
        """确保 doc_path 路径存在。"""
        os.makedirs(self.doc_path, exist_ok=True)

    @staticmethod
    def convert_env_value(key: str, env_value: str, type_hint: Type) -> Any:
        """根据类型提示将环境变量转换为对应类型。"""
        origin = get_origin(type_hint)
        args = get_args(type_hint)

        if origin is Union:
            # 处理 Union 类型（例如 Union[str, None]）
            for arg in args:
                if arg is type(None):
                    if env_value.lower() in ("none", "null", ""):
                        return None
                else:
                    try:
                        return Config.convert_env_value(key, env_value, arg)
                    except ValueError:
                        continue
            raise ValueError(f"无法将 {env_value} 转换为 {args} 中的任意类型")

        if type_hint is bool:
            return env_value.lower() in ("true", "1", "yes", "on")
        elif type_hint is int:
            return int(env_value)
        elif type_hint is float:
            return float(env_value)
        elif type_hint in (str, Any):
            return env_value
        elif origin is list or origin is List:
            return json.loads(env_value)
        elif type_hint is dict:
            return json.loads(env_value)
        else:
            raise ValueError(f"不支持的类型 {type_hint}（key: {key}）")


    def set_verbose(self, verbose: bool) -> None:
        """设置日志详细级别。"""
        self.llm_kwargs["verbose"] = verbose

    def get_mcp_server_config(self, name: str) -> dict:
        """
        获取 MCP 服务器的配置。
        
        Args:
            name (str): 要获取配置的 MCP 服务器名称。
                
        Returns:
            dict: 服务器配置；未找到时返回空字典。
        """
        if not name or not self.mcp_servers:
            return {}
        
        for server in self.mcp_servers:
            if isinstance(server, dict) and server.get("name") == name:
                return server
            
        return {}
