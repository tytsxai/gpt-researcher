# GPT-Researcher 全面汉化开发计划

## 项目概述
将 gpt-researcher 项目全面汉化，包括前端UI、后端提示词、错误信息和文档。

## 汉化范围
- **前端UI**: Next.js 组件中的所有用户可见文本
- **后端提示词**: LLM 系统提示词
- **错误信息**: 日志和错误提示
- **配置文件**: 注释和说明文本

## 任务分解 (25个并行任务)

### 前端UI组件 (TASK-001 ~ TASK-009)

#### TASK-001: ResearchBlocks核心组件
- **文件范围**: `frontend/nextjs/components/ResearchBlocks/Report.tsx`, `Sources.tsx`, `LogsSection.tsx`, `ImageSection.tsx`, `AccessReport.tsx`
- **依赖**: 无
- **测试**: `cd frontend/nextjs && npm run build`

#### TASK-002: ResearchBlocks交互组件
- **文件范围**: `frontend/nextjs/components/ResearchBlocks/ChatInterface.tsx`, `ChatResponse.tsx`, `Question.tsx`
- **依赖**: 无
- **测试**: `cd frontend/nextjs && npm run build`

#### TASK-003: ResearchBlocks元素组件
- **文件范围**: `frontend/nextjs/components/ResearchBlocks/elements/InputArea.tsx`, `ChatInput.tsx`, `SubQuestions.tsx`, `SourceCard.tsx`, `LogMessage.tsx`
- **依赖**: 无
- **测试**: `cd frontend/nextjs && npm run build`

#### TASK-004: Task组件
- **文件范围**: `frontend/nextjs/components/Task/Report.tsx`, `AgentLogs.tsx`, `Accordion.tsx`, `DomainFilter.tsx`, `ResearchForm.tsx`
- **依赖**: 无
- **测试**: `cd frontend/nextjs && npm run build`

#### TASK-005: Settings组件
- **文件范围**: `frontend/nextjs/components/Settings/Modal.tsx`, `LayoutSelector.tsx`, `ToneSelector.tsx`, `MCPSelector.tsx`, `FileUpload.tsx`, `ChatBox.tsx`
- **依赖**: 无
- **测试**: `cd frontend/nextjs && npm run build`

#### TASK-006: Mobile组件
- **文件范围**: `frontend/nextjs/components/mobile/MobileChatPanel.tsx`, `MobileResearchContent.tsx`, `MobileHomeScreen.tsx`
- **依赖**: 无
- **测试**: `cd frontend/nextjs && npm run build`

#### TASK-007: Research组件
- **文件范围**: `frontend/nextjs/components/research/ResearchPanel.tsx`, `CopilotPanel.tsx`, `CopilotResearchContent.tsx`, `NotFoundContent.tsx`, `ResearchContent.tsx`
- **依赖**: 无
- **测试**: `cd frontend/nextjs && npm run build`

#### TASK-008: 布局和图片组件
- **文件范围**: `frontend/nextjs/components/layouts/CopilotLayout.tsx`, `MobileLayout.tsx`, `ResearchPageLayout.tsx`, `frontend/nextjs/components/Images/ImagesAlbum.tsx`, `ImageModal.tsx`
- **依赖**: 无
- **测试**: `cd frontend/nextjs && npm run build`

#### TASK-009: 顶层组件和页面
- **文件范围**: `frontend/nextjs/components/Header.tsx`, `Footer.tsx`, `Hero.tsx`, `HumanFeedback.tsx`, `SimilarTopics.tsx`, `ResearchSidebar.tsx`, `frontend/nextjs/app/page.tsx`, `layout.tsx`, `research/[id]/page.tsx`
- **依赖**: 无
- **测试**: `cd frontend/nextjs && npm run build`

### 后端提示词 (TASK-010 ~ TASK-011)

#### TASK-010: 核心提示词汉化
- **文件范围**: `gpt_researcher/prompts.py`
- **依赖**: 无
- **测试**: `python -c "from gpt_researcher.prompts import *; print('OK')"`

#### TASK-011: 示例提示词汉化
- **文件范围**: `docs/docs/examples/custom_prompt.py`
- **依赖**: 无
- **测试**: 无

### CLI和入口 (TASK-012)

#### TASK-012: CLI和主入口汉化
- **文件范围**: `cli.py`, `main.py`
- **依赖**: 无
- **测试**: `python cli.py --help`

### 后端服务 (TASK-013 ~ TASK-015)

#### TASK-013: API服务器汉化
- **文件范围**: `backend/server/app.py`, `server_utils.py`, `websocket_manager.py`, `logging_config.py`
- **依赖**: 无
- **测试**: `python -c "from backend.server.app import app; print('OK')"`

#### TASK-014: 聊天和工具汉化
- **文件范围**: `backend/chat/chat.py`, `backend/utils.py`
- **依赖**: 无
- **测试**: 无

#### TASK-015: 报告类型汉化
- **文件范围**: `backend/report_type/deep_research/main.py`, `example.py`, `backend/report_type/detailed_report/detailed_report.py`
- **依赖**: 无
- **测试**: 无

### 核心库 (TASK-016 ~ TASK-020)

#### TASK-016: Agent和Actions汉化
- **文件范围**: `gpt_researcher/agent.py`, `gpt_researcher/actions/agent_creator.py`, `query_processing.py`, `report_generation.py`, `markdown_processing.py`, `utils.py`, `web_scraping.py`
- **依赖**: 无
- **测试**: `python -c "from gpt_researcher.agent import GPTResearcher; print('OK')"`

#### TASK-017: Skills汉化
- **文件范围**: `gpt_researcher/skills/curator.py`, `deep_research.py`, `researcher.py`
- **依赖**: 无
- **测试**: 无

#### TASK-018: Retrievers汉化
- **文件范围**: `gpt_researcher/retrievers/utils.py`, `google/google.py`, `bing/bing.py`, `duckduckgo/duckduckgo.py`, `serpapi/serpapi.py`, `serper/serper.py`, `tavily/tavily_search.py`, `searx/searx.py`, `searchapi/searchapi.py`, `semantic_scholar/semantic_scholar.py`, `pubmed_central/pubmed_central.py`, `custom/custom.py`
- **依赖**: 无
- **测试**: 无

#### TASK-019: Scraper汉化
- **文件范围**: `gpt_researcher/scraper/scraper.py`, `utils.py`, `firecrawl/firecrawl.py`, `tavily_extract/tavily_extract.py`, `beautiful_soup/beautiful_soup.py`, `pymupdf/pymupdf.py`, `web_base_loader/web_base_loader.py`, `browser/browser.py`, `browser/nodriver_scraper.py`
- **依赖**: 无
- **测试**: 无

#### TASK-020: MCP和工具汉化
- **文件范围**: `gpt_researcher/mcp/__init__.py`, `client.py`, `research.py`, `streaming.py`, `tool_selector.py`, `gpt_researcher/utils/logger.py`, `logging_config.py`, `tools.py`, `llm.py`
- **依赖**: 无
- **测试**: 无

### 多智能体 (TASK-021)

#### TASK-021: Multi-agents汉化
- **文件范围**: `multi_agents/main.py`, `agents/researcher.py`, `agents/human.py`, `agents/utils/views.py`, `agents/utils/llms.py`, `agents/utils/file_formats.py`
- **依赖**: 无
- **测试**: 无

### 配置文件 (TASK-022)

#### TASK-022: 配置文件汉化
- **文件范围**: `.env.example`, `docker-compose.yml`, `langgraph.json`, `gpt_researcher/config/config.py`, `variables/base.py`, `variables/default.py`
- **依赖**: 无
- **测试**: 无

### 文档 (TASK-023 ~ TASK-025)

#### TASK-023: 核心文档汉化
- **文件范围**: `README.md`, `docs/docs/welcome.md`, `docs/docs/faq.md`, `docs/docs/roadmap.md`, `docs/docs/contribute.md`
- **依赖**: 无
- **测试**: 无

#### TASK-024: 入门文档汉化
- **文件范围**: `docs/docs/gpt-researcher/getting-started/introduction.md`, `how-to-choose.md`, `getting-started.md`, `getting-started-with-docker.md`, `linux-deployment.md`, `cli.md`
- **依赖**: 无
- **测试**: 无

#### TASK-025: 功能文档汉化
- **文件范围**: `docs/docs/gpt-researcher/frontend/*.md`, `docs/docs/gpt-researcher/gptr/*.md`, `docs/docs/gpt-researcher/context/*.md`, `docs/docs/gpt-researcher/llms/*.md`
- **依赖**: 无
- **测试**: 无

## UI判定
- **needs_ui**: true
- **evidence**: `frontend/nextjs/components/*`, `frontend/nextjs/app/*`, 样式文件 `globals.css`, `markdown.css`, `Settings.css`

## 执行策略
- 所有25个任务可并行执行，无依赖关系
- UI任务(TASK-001~009)使用gemini后端
- 其他任务使用codex后端
