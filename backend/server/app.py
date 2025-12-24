import json
import os
from typing import Dict, List, Any
import time
import logging
import sys
import warnings
import uuid
from datetime import datetime, timezone
import tempfile

# Suppress Pydantic V2 migration warnings
warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, File, UploadFile, BackgroundTasks, HTTPException, Depends
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict

# Add the parent directory to sys.path to make sure we can import from server
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from server.websocket_manager import WebSocketManager
from server.server_utils import (
    get_config_dict, sanitize_filename,
    update_environment_variables, handle_file_upload, handle_file_deletion,
    execute_multi_agents, handle_websocket_communication
)

from server.websocket_manager import run_agent
from utils import write_md_to_word, write_md_to_pdf
from gpt_researcher.utils.enum import Tone, ReportType, ReportSource
from gpt_researcher.config.variables.default import DEFAULT_CONFIG
from chat.chat import ChatAgentWithMemory

# MongoDB services removed - no database persistence needed

# Setup logging
logger = logging.getLogger(__name__)

# Don't override parent logger settings
logger.propagate = True

# Silence uvicorn reload logs
logging.getLogger("uvicorn.supervisors.ChangeReload").setLevel(logging.WARNING)

START_TIME = time.time()

def _env_truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def _parse_env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]

def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"Invalid int for {name}: {raw}. Using default {default}.")
        return default

def _get_api_key() -> str | None:
    return os.getenv("API_KEY") or None

def require_api_key(request: Request) -> None:
    expected = _get_api_key()
    if not expected:
        return
    provided = request.headers.get("X-API-Key")
    if not provided:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided = auth_header[7:]
    if provided != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

def _get_runtime_retrievers() -> List[str]:
    retriever_env = os.getenv("RETRIEVER") or DEFAULT_CONFIG.get("RETRIEVER", "tavily")
    return [r.strip() for r in retriever_env.split(",") if r.strip()]

def _parse_provider(value: str | None, default_value: str | None) -> str | None:
    raw = value or default_value
    if not raw:
        return None
    return raw.split(":", 1)[0] if ":" in raw else raw

def _collect_env_issues() -> List[str]:
    issues: List[str] = []
    retriever_requirements = {
        "tavily": ["TAVILY_API_KEY"],
        "serpapi": ["SERPAPI_API_KEY"],
        "serper": ["SERPER_API_KEY"],
        "searchapi": ["SEARCHAPI_API_KEY"],
        "google": ["GOOGLE_API_KEY", "GOOGLE_CX_KEY"],
        "bing": ["BING_API_KEY"],
        "searx": ["SEARX_URL"],
        "exa": ["EXA_API_KEY"],
    }

    for retriever in _get_runtime_retrievers():
        required = retriever_requirements.get(retriever, [])
        for key in required:
            if not os.getenv(key):
                issues.append(f"Missing {key} for retriever '{retriever}'.")

    default_fast_llm = DEFAULT_CONFIG.get("FAST_LLM")
    default_smart_llm = DEFAULT_CONFIG.get("SMART_LLM")
    default_strategic_llm = DEFAULT_CONFIG.get("STRATEGIC_LLM")
    default_embedding = DEFAULT_CONFIG.get("EMBEDDING")

    providers = {
        _parse_provider(os.getenv("FAST_LLM"), default_fast_llm),
        _parse_provider(os.getenv("SMART_LLM"), default_smart_llm),
        _parse_provider(os.getenv("STRATEGIC_LLM"), default_strategic_llm),
        _parse_provider(os.getenv("EMBEDDING"), default_embedding),
        os.getenv("LLM_PROVIDER"),
    }

    provider_requirements = {
        "openai": ["OPENAI_API_KEY"],
        "ollama": ["OLLAMA_BASE_URL"],
        "openrouter": ["OPENROUTER_API_KEY"],
        "vllm_openai": ["VLLM_OPENAI_API_KEY", "VLLM_OPENAI_API_BASE"],
        "dashscope": ["DASHSCOPE_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY"],
        "aimlapi": ["AIMLAPI_API_KEY"],
    }

    for provider in {p for p in providers if p}:
        required = provider_requirements.get(provider, [])
        for key in required:
            if not os.getenv(key):
                issues.append(f"Missing {key} for LLM/embedding provider '{provider}'.")

    extra_required = _parse_env_list("REQUIRED_ENV", [])
    for key in extra_required:
        if not os.getenv(key):
            issues.append(f"Missing required env '{key}'.")

    return issues

def _check_path_writable(path: str) -> str | None:
    try:
        os.makedirs(path, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
    except Exception as exc:
        return f"Path not writable: {path} ({exc})"
    return None

# Models


class ResearchRequest(BaseModel):
    task: str
    report_type: str
    report_source: str
    tone: str
    headers: dict | None = None
    repo_name: str
    branch_name: str
    generate_in_background: bool = True


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")  # Allow extra fields in the request
    
    report: str
    messages: List[Dict[str, Any]]

def _validate_research_request(research_request: ResearchRequest) -> None:
    if not research_request.task:
        raise HTTPException(status_code=400, detail="task is required")

    valid_report_types = {rt.value for rt in ReportType} | {"multi_agents"}
    if research_request.report_type not in valid_report_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report_type. Expected one of: {', '.join(sorted(valid_report_types))}",
        )

    valid_report_sources = {rs.value for rs in ReportSource}
    if research_request.report_source not in valid_report_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report_source. Expected one of: {', '.join(sorted(valid_report_sources))}",
        )

    if research_request.tone not in Tone.__members__:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tone. Expected one of: {', '.join(sorted(Tone.__members__.keys()))}",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs(DOC_PATH, exist_ok=True)
    app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
    
    # Mount frontend static files
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
    if os.path.exists(frontend_path):
        app.mount("/site", StaticFiles(directory=frontend_path), name="frontend")
        logger.debug(f"Frontend mounted from: {frontend_path}")
        
        # Also mount the static directory directly for assets referenced as /static/
        static_path = os.path.join(frontend_path, "static")
        if os.path.exists(static_path):
            app.mount("/static", StaticFiles(directory=static_path), name="static")
            logger.debug(f"Static assets mounted from: {static_path}")
    else:
        logger.warning(f"Frontend directory not found: {frontend_path}")
    
    # Validate environment for readiness
    env_issues = _collect_env_issues()
    if env_issues:
        for issue in env_issues:
            logger.warning(f"Readiness check: {issue}")
        if _env_truthy("STRICT_ENV", False):
            raise RuntimeError("Environment validation failed. Set STRICT_ENV=false to bypass.")

    logger.info("GPT Researcher API 已就绪 - 本地模式（无数据库持久化）")
    yield
    # Shutdown
    logger.info("研究 API 正在关闭")

# App initialization
app = FastAPI(lifespan=lifespan)

# Configure allowed origins for CORS
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://app.gptr.dev",
]
CORS_ALLOWED_ORIGINS = _parse_env_list("CORS_ALLOW_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
CORS_ALLOW_CREDENTIALS = _env_truthy("CORS_ALLOW_CREDENTIALS", False)
if "*" in CORS_ALLOWED_ORIGINS and CORS_ALLOW_CREDENTIALS:
    logger.warning("CORS_ALLOW_ORIGINS includes '*' with credentials enabled; disabling credentials.")
    CORS_ALLOW_CREDENTIALS = False

# Standard JSON response - no custom MongoDB encoding needed

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use default JSON response class

# WebSocket manager
manager = WebSocketManager()

# Constants
DOC_PATH = os.getenv("DOC_PATH", "./my-docs")
MAX_UPLOAD_MB = _parse_int_env("MAX_UPLOAD_MB", 25)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
REQUEST_LOGGING = _env_truthy("REQUEST_LOGGING", True)

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    start = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = int((time.time() - start) * 1000)
        logger.exception(
            f"Unhandled error {request.method} {request.url.path} {duration_ms}ms request_id={request_id}"
        )
        raise exc
    duration_ms = int((time.time() - start) * 1000)
    if REQUEST_LOGGING:
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} {duration_ms}ms request_id={request_id}"
        )
    response.headers["X-Request-Id"] = request_id
    return response

@app.get("/healthz")
async def health_check():
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": int(time.time() - START_TIME),
    }

@app.get("/readyz")
async def readiness_check():
    issues = []
    env_issues = _collect_env_issues()
    issues.extend(env_issues)

    path_issue = _check_path_writable("outputs")
    if path_issue:
        issues.append(path_issue)
    path_issue = _check_path_writable(DOC_PATH)
    if path_issue:
        issues.append(path_issue)

    ready = len(issues) == 0
    return {
        "ready": ready,
        "issues": issues,
        "time": datetime.now(timezone.utc).isoformat(),
    }

# Startup event


# Lifespan events now handled in the lifespan context manager above


# Routes
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend HTML page."""
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
    index_path = os.path.join(frontend_dir, "index.html")
    
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend index.html not found")
    
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return HTMLResponse(content=content)

@app.get("/report/{research_id}")
async def read_report(request: Request, research_id: str, _: None = Depends(require_api_key)):
    docx_path = os.path.join('outputs', f"{research_id}.docx")
    if not os.path.exists(docx_path):
        return {"message": "未找到报告。"}
    return FileResponse(docx_path)


# Simplified API routes - no database persistence
@app.get("/api/reports")
async def get_all_reports(report_ids: str = None):
    """Get research reports - returns empty list since no database."""
    logger.debug("未配置数据库 - 返回空报告列表")
    return {"reports": []}


@app.get("/api/reports/{research_id}")
async def get_report_by_id(research_id: str):
    """Get a specific research report by ID - no database configured."""
    logger.debug(f"未配置数据库 - 无法检索报告 {research_id}")
    raise HTTPException(status_code=404, detail="未找到报告")


@app.post("/api/reports")
async def create_or_update_report(request: Request, _: None = Depends(require_api_key)):
    """Create or update a research report - no database persistence."""
    try:
        data = await request.json()
        research_id = data.get("id", "temp_id")
        logger.debug(f"请求创建报告 ID: {research_id} - 未配置数据库，未持久化")
        return {"success": True, "id": research_id}
    except Exception as e:
        logger.error(f"处理报告创建时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def write_report(research_request: ResearchRequest, research_id: str = None):
    try:
        tone = Tone[research_request.tone]
    except KeyError as exc:
        logger.error(f"Invalid tone: {research_request.tone}")
        raise HTTPException(status_code=400, detail="Invalid tone") from exc

    report_information = await run_agent(
        task=research_request.task,
        report_type=research_request.report_type,
        report_source=research_request.report_source,
        source_urls=[],
        document_urls=[],
        tone=tone,
        websocket=None,
        stream_output=None,
        headers=research_request.headers,
        query_domains=[],
        config_path="",
        return_researcher=True
    )

    docx_path = await write_md_to_word(report_information[0], research_id)
    pdf_path = await write_md_to_pdf(report_information[0], research_id)
    if research_request.report_type != "multi_agents":
        report, researcher = report_information
        response = {
            "research_id": research_id,
            "research_information": {
                "source_urls": researcher.get_source_urls(),
                "research_costs": researcher.get_costs(),
                "visited_urls": list(researcher.visited_urls),
                "research_images": researcher.get_research_images(),
                # "research_sources": researcher.get_research_sources(),  # Raw content of sources may be very large
            },
            "report": report,
            "docx_path": docx_path,
            "pdf_path": pdf_path
        }
    else:
        response = { "research_id": research_id, "report": "", "docx_path": docx_path, "pdf_path": pdf_path }

    return response

@app.post("/report/")
async def generate_report(
    research_request: ResearchRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
):
    _validate_research_request(research_request)
    research_id = sanitize_filename(f"task_{int(time.time())}_{research_request.task}")

    if research_request.generate_in_background:
        background_tasks.add_task(write_report, research_request=research_request, research_id=research_id)
        return {"message": "您的报告正在后台生成中，请稍后查看。",
                "research_id": research_id}
    else:
        response = await write_report(research_request, research_id)
        return response


@app.get("/files/")
async def list_files(_: None = Depends(require_api_key)):
    if not os.path.exists(DOC_PATH):
        os.makedirs(DOC_PATH, exist_ok=True)
    files = os.listdir(DOC_PATH)
    print(f"Files in {DOC_PATH}: {files}")
    return {"files": files}


@app.post("/api/multi_agents")
async def run_multi_agents(_: None = Depends(require_api_key)):
    return await execute_multi_agents(manager)


@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    _: None = Depends(require_api_key),
):
    return await handle_file_upload(file, DOC_PATH, MAX_UPLOAD_BYTES)


@app.delete("/files/{filename}")
async def delete_file(filename: str, _: None = Depends(require_api_key)):
    return await handle_file_deletion(filename, DOC_PATH)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    expected_key = _get_api_key()
    if expected_key:
        provided = websocket.headers.get("x-api-key")
        if not provided:
            auth_header = websocket.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                provided = auth_header[7:]
        if not provided:
            provided = websocket.query_params.get("api_key")
        if provided != expected_key:
            await websocket.close(code=1008)
            return
    await manager.connect(websocket)
    try:
        await handle_websocket_communication(websocket, manager)
    except WebSocketDisconnect as e:
        # Disconnect with more detailed logging about the WebSocket disconnect reason
        logger.info(f"WebSocket disconnected with code {e.code} and reason: '{e.reason}'")
        await manager.disconnect(websocket)
    except Exception as e:
        # More general exception handling
        logger.error(f"Unexpected WebSocket error: {str(e)}")
        await manager.disconnect(websocket)

@app.post("/api/chat")
async def chat(chat_request: ChatRequest, _: None = Depends(require_api_key)):
    """Process a chat request with a report and message history.

    Args:
        chat_request: ChatRequest object containing report text and message history

    Returns:
        JSON response with the assistant's message and any tool usage metadata
    """
    try:
        logger.info(f"Received chat request with {len(chat_request.messages)} messages")

        # Create chat agent with the report
        chat_agent = ChatAgentWithMemory(
            report=chat_request.report,
            config_path="default",
            headers=None
        )

        # Process the chat and get response with metadata
        response_content, tool_calls_metadata = await chat_agent.chat(chat_request.messages, None)
        logger.info(f"Got chat response of length: {len(response_content) if response_content else 0}")
        
        if tool_calls_metadata:
            logger.info(f"Tool calls used: {json.dumps(tool_calls_metadata)}")

        # Format response as a ChatMessage object with role, content, timestamp and metadata
        response_message = {
            "role": "assistant",
            "content": response_content,
            "timestamp": int(time.time() * 1000),  # Current time in milliseconds
            "metadata": {
                "tool_calls": tool_calls_metadata
            } if tool_calls_metadata else None
        }

        logger.info(f"Returning formatted response: {json.dumps(response_message)[:100]}...")
        return {"response": response_message}
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        return {"error": str(e)}

@app.post("/api/reports/{research_id}/chat")
async def research_report_chat(research_id: str, request: Request, _: None = Depends(require_api_key)):
    """Handle chat requests for a specific research report.
    Directly processes the raw request data to avoid validation errors.
    """
    try:
        # Get raw JSON data from request
        data = await request.json()
        
        # Create chat agent with the report
        chat_agent = ChatAgentWithMemory(
            report=data.get("report", ""),
            config_path="default",
            headers=None
        )

        # Process the chat and get response with metadata
        response_content, tool_calls_metadata = await chat_agent.chat(data.get("messages", []), None)
        
        if tool_calls_metadata:
            logger.info(f"Tool calls used: {json.dumps(tool_calls_metadata)}")

        # Format response as a ChatMessage object
        response_message = {
            "role": "assistant",
            "content": response_content,
            "timestamp": int(time.time() * 1000),
            "metadata": {
                "tool_calls": tool_calls_metadata
            } if tool_calls_metadata else None
        }

        return {"response": response_message}
    except Exception as e:
        logger.error(f"Error in research report chat: {str(e)}", exc_info=True)
        return {"error": str(e)}

@app.put("/api/reports/{research_id}")
async def update_report(research_id: str, request: Request, _: None = Depends(require_api_key)):
    """Update a specific research report by ID - no database configured."""
    logger.debug(f"Update requested for report {research_id} - no database configured, not persisted")
    return {"success": True, "id": research_id}

@app.delete("/api/reports/{research_id}")
async def delete_report(research_id: str, _: None = Depends(require_api_key)):
    """Delete a specific research report by ID - no database configured."""
    logger.debug(f"Delete requested for report {research_id} - no database configured, nothing to delete")
    return {"success": True, "id": research_id}
