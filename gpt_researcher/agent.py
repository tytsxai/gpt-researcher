from typing import Any, Optional
import json
import os

from .config import Config
from .memory import Memory
from .utils.enum import ReportSource, ReportType, Tone
from .llm_provider import GenericLLMProvider
from .prompts import get_prompt_family
from .vector_store import VectorStoreWrapper

# Research skills
from .skills.researcher import ResearchConductor
from .skills.writer import ReportGenerator
from .skills.context_manager import ContextManager
from .skills.browser import BrowserManager
from .skills.curator import SourceCurator
from .skills.deep_research import DeepResearchSkill

from .actions import (
    add_references,
    extract_headers,
    extract_sections,
    table_of_contents,
    get_search_results,
    get_retrievers,
    choose_agent
)


class GPTResearcher:
    def __init__(
        self,
        query: str,
        report_type: str = ReportType.ResearchReport.value,
        report_format: str = "markdown",
        report_source: str = ReportSource.Web.value,
        tone: Tone = Tone.Objective,
        source_urls: list[str] | None = None,
        document_urls: list[str] | None = None,
        complement_source_urls: bool = False,
        query_domains: list[str] | None = None,
        documents=None,
        vector_store=None,
        vector_store_filter=None,
        config_path=None,
        websocket=None,
        agent=None,
        role=None,
        parent_query: str = "",
        subtopics: list | None = None,
        visited_urls: set | None = None,
        verbose: bool = True,
        context=None,
        headers: dict | None = None,
        max_subtopics: int = 5,
        log_handler=None,
        prompt_family: str | None = None,
        mcp_configs: list[dict] | None = None,
        mcp_max_iterations: int | None = None,
        mcp_strategy: str | None = None,
        **kwargs
    ):
        """
        初始化 GPT Researcher 实例。
        
        Args:
            query (str): 研究查询或问题。
            report_type (str): 生成的报告类型。
            report_format (str): 报告格式（markdown、pdf 等）。
            report_source (str): 报告信息来源（web、local 等）。
            tone (Tone): 报告语气。
            source_urls (list[str], optional): 作为来源的指定 URL 列表。
            document_urls (list[str], optional): 作为来源的文档 URL 列表。
            complement_source_urls (bool): 是否使用网页搜索补充来源 URL。
            query_domains (list[str], optional): 限制搜索范围的域名列表。
            documents: 用于 LangChain 集成的文档对象。
            vector_store: 用于文档检索的向量存储。
            vector_store_filter: 向量存储查询过滤器。
            config_path: 配置文件路径。
            websocket: 用于流式输出的 WebSocket。
            agent: 预先指定的 agent 类型。
            role: 预先指定的 agent 角色。
            parent_query: 子主题报告的父查询。
            subtopics: 需要研究的子主题列表。
            visited_urls: 已访问 URL 的集合。
            verbose (bool): 是否输出详细日志。
            context: 预加载的研究上下文。
            headers (dict, optional): 请求与配置的额外 headers。
            max_subtopics (int): 最大生成子主题数量。
            log_handler: 日志事件处理器。
            prompt_family: 要使用的提示词家族。
            mcp_configs (list[dict], optional): MCP 服务器配置列表。
                每个字典可包含：
                - name (str): MCP 服务器名称
                - command (str): 启动服务器的命令
                - args (list[str]): 服务器命令参数
                - tool_name (str): 在 MCP 服务器上使用的特定工具
                - env (dict): 服务器环境变量
                - connection_url (str): WebSocket 或 HTTP 连接的 URL
                - connection_type (str): 连接类型（stdio、websocket、http）
                - connection_token (str): 远程连接的认证令牌
                
                示例：
                ```python
                mcp_configs=[{
                    "command": "python",
                    "args": ["my_mcp_server.py"],
                    "name": "search"
                }]
                ```
            mcp_strategy (str, optional): MCP 执行策略。可选项：
                - "fast"（默认）：使用原始查询运行一次 MCP，性能最佳
                - "deep"：对所有子查询运行 MCP，尽可能全面  
                - "disabled"：完全禁用 MCP，仅使用网页检索器
        """
        self.kwargs = kwargs
        self.query = query
        self.report_type = report_type
        self.cfg = Config(config_path)
        self.cfg.set_verbose(verbose)
        self.report_source = report_source if report_source else getattr(self.cfg, 'report_source', None)
        self.report_format = report_format
        self.max_subtopics = max_subtopics
        self.tone = tone if isinstance(tone, Tone) else Tone.Objective
        self.source_urls = source_urls
        self.document_urls = document_urls
        self.complement_source_urls = complement_source_urls
        self.query_domains = query_domains or []
        self.research_sources = []  # The list of scraped sources including title, content and images
        self.research_images = []  # The list of selected research images
        self.documents = documents
        self.vector_store = VectorStoreWrapper(vector_store) if vector_store else None
        self.vector_store_filter = vector_store_filter
        self.websocket = websocket
        self.agent = agent
        self.role = role
        self.parent_query = parent_query
        self.subtopics = subtopics or []
        self.visited_urls = visited_urls or set()
        self.verbose = verbose
        self.context = context or []
        self.headers = headers or {}
        self.research_costs = 0.0
        self.log_handler = log_handler
        self.prompt_family = get_prompt_family(prompt_family or self.cfg.prompt_family, self.cfg)
        
        # 若提供了 MCP 配置则进行处理
        self.mcp_configs = mcp_configs
        if mcp_configs:
            self._process_mcp_configs(mcp_configs)
        
        self.retrievers = get_retrievers(self.headers, self.cfg)
        self.memory = Memory(
            self.cfg.embedding_provider, self.cfg.embedding_model, **self.cfg.embedding_kwargs
        )
        
        # 设置默认编码为 utf-8
        self.encoding = kwargs.get('encoding', 'utf-8')
        self.kwargs.pop('encoding', None)  # 从 kwargs 中移除 encoding，避免传给 LLM 调用

        # 初始化组件
        self.research_conductor: ResearchConductor = ResearchConductor(self)
        self.report_generator: ReportGenerator = ReportGenerator(self)
        self.context_manager: ContextManager = ContextManager(self)
        self.scraper_manager: BrowserManager = BrowserManager(self)
        self.source_curator: SourceCurator = SourceCurator(self)
        self.deep_researcher: Optional[DeepResearchSkill] = None
        if report_type == ReportType.DeepResearch.value:
            self.deep_researcher = DeepResearchSkill(self)

        # 处理 MCP 策略配置（兼容旧版本）
        self.mcp_strategy = self._resolve_mcp_strategy(mcp_strategy, mcp_max_iterations)

    def _resolve_mcp_strategy(self, mcp_strategy: str | None, mcp_max_iterations: int | None) -> str:
        """
        从多个来源解析 MCP 策略并保持向后兼容。
        
        优先级：
        1. 参数 mcp_strategy（新方式）
        2. 参数 mcp_max_iterations（向后兼容）  
        3. 配置 MCP_STRATEGY
        4. 默认 "fast"
        
        Args:
            mcp_strategy: 新的策略参数
            mcp_max_iterations: 旧参数（向后兼容）
            
        Returns:
            str: 解析后的策略（"fast"、"deep" 或 "disabled"）
        """
        # 优先级 1：如果提供了 mcp_strategy 参数则使用
        if mcp_strategy is not None:
            # 支持新策略名称
            if mcp_strategy in ["fast", "deep", "disabled"]:
                return mcp_strategy
            # 兼容旧的策略名称
            elif mcp_strategy == "optimized":
                import logging
                logging.getLogger(__name__).warning("mcp_strategy 'optimized' 已弃用，请改用 'fast'")
                return "fast"
            elif mcp_strategy == "comprehensive":
                import logging
                logging.getLogger(__name__).warning("mcp_strategy 'comprehensive' 已弃用，请改用 'deep'")
                return "deep"
            else:
                import logging
                logging.getLogger(__name__).warning(f"无效的 mcp_strategy '{mcp_strategy}'，将默认使用 'fast'")
                return "fast"
        
        # 优先级 2：将 mcp_max_iterations 转换为策略（向后兼容）
        if mcp_max_iterations is not None:
            import logging
            logging.getLogger(__name__).warning("mcp_max_iterations 已弃用，请改用 mcp_strategy")
            
            if mcp_max_iterations == 0:
                return "disabled"
            elif mcp_max_iterations == 1:
                return "fast"
            elif mcp_max_iterations == -1:
                return "deep"
            else:
                # 其他数值一律按 fast 模式处理
                return "fast"
        
        # 优先级 3：使用配置项
        if hasattr(self.cfg, 'mcp_strategy'):
            config_strategy = self.cfg.mcp_strategy
            # 支持新策略名称
            if config_strategy in ["fast", "deep", "disabled"]:
                return config_strategy
            # 兼容旧的策略名称
            elif config_strategy == "optimized":
                return "fast"
            elif config_strategy == "comprehensive":
                return "deep"
            
        # 优先级 4：默认 fast
        return "fast"

    def _process_mcp_configs(self, mcp_configs: list[dict]) -> None:
        """
        从配置字典列表中处理 MCP 配置。
        
        该方法会校验 MCP 配置。仅在未通过环境变量显式配置检索器时，
        才会将 MCP 加入检索器列表。
        
        Args:
            mcp_configs (list[dict]): MCP 服务器配置字典列表。
        """
        # 检查用户是否显式设置了 RETRIEVER 环境变量
        user_set_retriever = os.getenv("RETRIEVER") is not None
        
        if not user_set_retriever:
            # 仅在用户未显式设置检索器时自动添加 MCP
            if hasattr(self.cfg, 'retrievers') and self.cfg.retrievers:
                # 如果在配置中设置了检索器（但不是通过环境变量）
                current_retrievers = set(self.cfg.retrievers.split(",")) if isinstance(self.cfg.retrievers, str) else set(self.cfg.retrievers)
                if "mcp" not in current_retrievers:
                    current_retrievers.add("mcp")
                    self.cfg.retrievers = ",".join(filter(None, current_retrievers))
            else:
                # 未配置检索器时，默认使用 mcp
                self.cfg.retrievers = "mcp"
        # 若用户显式设置了 RETRIEVER，则尊重其选择，不自动添加 MCP
        
        # 保存 mcp_configs 供 MCP 检索器使用
        self.mcp_configs = mcp_configs

    async def _log_event(self, event_type: str, **kwargs):
        """用于处理日志事件的辅助方法。"""
        if self.log_handler:
            try:
                if event_type == "tool":
                    await self.log_handler.on_tool_start(kwargs.get('tool_name', ''), **kwargs)
                elif event_type == "action":
                    await self.log_handler.on_agent_action(kwargs.get('action', ''), **kwargs)
                elif event_type == "research":
                    await self.log_handler.on_research_step(kwargs.get('step', ''), kwargs.get('details', {}))

                # 作为备用的直接日志输出
                import logging
                research_logger = logging.getLogger('research')
                research_logger.info(f"{event_type}: {json.dumps(kwargs, default=str)}")

            except Exception as e:
                import logging
                logging.getLogger('research').error(f"_log_event 出错：{e}", exc_info=True)

    async def conduct_research(self, on_progress=None):
        await self._log_event("research", step="start", details={
            "query": self.query,
            "report_type": self.report_type,
            "agent": self.agent,
            "role": self.role
        })

        # 深度研究单独处理
        if self.report_type == ReportType.DeepResearch.value and self.deep_researcher:
            return await self._handle_deep_research(on_progress)

        if not (self.agent and self.role):
            await self._log_event("action", action="choose_agent")
            # 过滤 encoding 参数，LLM API 不支持该参数
            # filtered_kwargs = {k: v for k, v in self.kwargs.items() if k != 'encoding'}
            self.agent, self.role = await choose_agent(
                query=self.query,
                cfg=self.cfg,
                parent_query=self.parent_query,
                cost_callback=self.add_costs,
                headers=self.headers,
                prompt_family=self.prompt_family,
                **self.kwargs,
                # **filtered_kwargs
            )
            await self._log_event("action", action="agent_selected", details={
                "agent": self.agent,
                "role": self.role
            })

        await self._log_event("research", step="conducting_research", details={
            "agent": self.agent,
            "role": self.role
        })
        self.context = await self.research_conductor.conduct_research()

        await self._log_event("research", step="research_completed", details={
            "context_length": len(self.context)
        })
        return self.context

    async def _handle_deep_research(self, on_progress=None):
        """处理深度研究的执行与日志记录。"""
        # 记录深度研究配置
        await self._log_event("research", step="deep_research_initialize", details={
            "type": "deep_research",
            "breadth": self.deep_researcher.breadth,
            "depth": self.deep_researcher.depth,
            "concurrency": self.deep_researcher.concurrency_limit
        })

        # 记录深度研究开始
        await self._log_event("research", step="deep_research_start", details={
            "query": self.query,
            "breadth": self.deep_researcher.breadth,
            "depth": self.deep_researcher.depth,
            "concurrency": self.deep_researcher.concurrency_limit
        })

        # 运行深度研究并获取上下文
        self.context = await self.deep_researcher.run(on_progress=on_progress)

        # 获取总研究成本
        total_costs = self.get_costs()

        # 记录深度研究完成与成本
        await self._log_event("research", step="deep_research_complete", details={
            "context_length": len(self.context),
            "visited_urls": len(self.visited_urls),
            "total_costs": total_costs
        })

        # 记录最终成本更新
        await self._log_event("research", step="cost_update", details={
            "cost": total_costs,
            "total_cost": total_costs,
            "research_type": "deep_research"
        })

        # 返回研究上下文
        return self.context

    async def write_report(self, existing_headers: list = [], relevant_written_contents: list = [], ext_context=None, custom_prompt="") -> str:
        await self._log_event("research", step="writing_report", details={
            "existing_headers": existing_headers,
            "context_source": "external" if ext_context else "internal"
        })

        report = await self.report_generator.write_report(
            existing_headers=existing_headers,
            relevant_written_contents=relevant_written_contents,
            ext_context=ext_context or self.context,
            custom_prompt=custom_prompt
        )

        await self._log_event("research", step="report_completed", details={
            "report_length": len(report)
        })
        return report

    async def write_report_conclusion(self, report_body: str) -> str:
        await self._log_event("research", step="writing_conclusion")
        conclusion = await self.report_generator.write_report_conclusion(report_body)
        await self._log_event("research", step="conclusion_completed")
        return conclusion

    async def write_introduction(self):
        await self._log_event("research", step="writing_introduction")
        intro = await self.report_generator.write_introduction()
        await self._log_event("research", step="introduction_completed")
        return intro

    async def quick_search(self, query: str, query_domains: list[str] = None) -> list[Any]:
        return await get_search_results(query, self.retrievers[0], query_domains=query_domains)

    async def get_subtopics(self):
        return await self.report_generator.get_subtopics()

    async def get_draft_section_titles(self, current_subtopic: str):
        return await self.report_generator.get_draft_section_titles(current_subtopic)

    async def get_similar_written_contents_by_draft_section_titles(
        self,
        current_subtopic: str,
        draft_section_titles: list[str],
        written_contents: list[dict],
        max_results: int = 10
    ) -> list[str]:
        return await self.context_manager.get_similar_written_contents_by_draft_section_titles(
            current_subtopic,
            draft_section_titles,
            written_contents,
            max_results
        )

    # 工具方法
    def get_research_images(self, top_k=10) -> list[dict[str, Any]]:
        return self.research_images[:top_k]

    def add_research_images(self, images: list[dict[str, Any]]) -> None:
        self.research_images.extend(images)

    def get_research_sources(self) -> list[dict[str, Any]]:
        return self.research_sources

    def add_research_sources(self, sources: list[dict[str, Any]]) -> None:
        self.research_sources.extend(sources)

    def add_references(self, report_markdown: str, visited_urls: set) -> str:
        return add_references(report_markdown, visited_urls)

    def extract_headers(self, markdown_text: str) -> list[dict]:
        return extract_headers(markdown_text)

    def extract_sections(self, markdown_text: str) -> list[dict]:
        return extract_sections(markdown_text)

    def table_of_contents(self, markdown_text: str) -> str:
        return table_of_contents(markdown_text)

    def get_source_urls(self) -> list:
        return list(self.visited_urls)

    def get_research_context(self) -> list:
        return self.context

    def get_costs(self) -> float:
        return self.research_costs

    def set_verbose(self, verbose: bool):
        self.verbose = verbose

    def add_costs(self, cost: float) -> None:
        if not isinstance(cost, (float, int)):
            raise ValueError("Cost 必须是整数或浮点数")
        self.research_costs += cost
        if self.log_handler:
            self._log_event("research", step="cost_update", details={
                "cost": cost,
                "total_cost": self.research_costs
            })
