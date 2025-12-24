#!/usr/bin/env python3
"""
GPT-Researcher Backend Server Startup Script

Run this to start the research API server.
"""

import uvicorn
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    # Load repo root .env (so running this script directly works)
    repo_root = Path(backend_dir).parent
    load_dotenv(dotenv_path=repo_root / ".env", override=False)

    # Change to backend directory
    os.chdir(backend_dir)
    
    def _env_truthy(name: str, default: bool = False) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = _env_truthy("RELOAD", False)
    log_level = os.getenv("LOG_LEVEL", os.getenv("LOGGING_LEVEL", "info")).lower()

    # Start the server
    uvicorn.run(
        "server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )

