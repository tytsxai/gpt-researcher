from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

def _env_truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

log_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
log_to_file = _env_truthy("LOG_TO_FILE", True)
log_file_max_bytes = int(os.getenv("LOG_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
log_file_backups = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))

handlers = [logging.StreamHandler()]
if log_to_file:
    handlers.append(
        RotatingFileHandler(
            "logs/app.log",
            maxBytes=log_file_max_bytes,
            backupCount=log_file_backups,
        )
    )

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
)

# Suppress verbose fontTools logging
logging.getLogger('fontTools').setLevel(logging.WARNING)
logging.getLogger('fontTools.subset').setLevel(logging.WARNING)
logging.getLogger('fontTools.ttLib').setLevel(logging.WARNING)

# Create logger instance
logger = logging.getLogger(__name__)

load_dotenv()

from backend.server.app import app

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
