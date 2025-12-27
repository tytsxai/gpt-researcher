import pytest
import asyncio
from pathlib import Path
import json
import logging
import pytest
from fastapi import WebSocket
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DummyWebSocket(WebSocket):
    def __init__(self):
        self.events = []
        self.scope = {}

    def __bool__(self):
        return True

    async def accept(self):
        self.scope["type"] = "websocket"
        pass
        
    async def send_json(self, event):
        logger.info(f"WebSocket received event: {event}")
        self.events.append(event)

@pytest.mark.asyncio
async def test_log_output_file():
    """Test to verify logs are properly written to output file"""
    from backend.server.server_utils import CustomLogsHandler
    
    # 1. Setup like the main app
    websocket = DummyWebSocket()
    await websocket.accept()
    
    # 2. Initialize logs handler like main app
    query = "What is the capital of France?"
    research_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(query)}"
    logs_handler = CustomLogsHandler(websocket=websocket, task=research_id)

    # 3. Emit a couple of log events
    await logs_handler.send_json({"type": "logs", "content": "info", "output": "hello"})
    await logs_handler.send_json({"type": "logs", "content": "info", "output": "world"})
    
    # 4. Verify events were captured
    logger.info(f"Events captured: {len(websocket.events)}")
    assert len(websocket.events) > 0, "No events were captured"
    
    # 5. Check output file
    output_dir = Path().joinpath(Path.cwd(), "outputs")
    output_files = list(output_dir.glob(f"task_*{research_id}*.json"))
    assert len(output_files) > 0, "No output file was created"
    
    with open(output_files[-1]) as f:
        data = json.load(f)
        assert len(data.get('events', [])) > 0, "No events in output file" 

    # Clean up the output files
    for output_file in output_files:
        output_file.unlink()
        logger.info(f"Deleted output file: {output_file}")