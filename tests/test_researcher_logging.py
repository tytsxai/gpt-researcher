import os
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_researcher_logging(monkeypatch, tmp_path):
    """Offline test: Researcher writes JSON log and returns output paths."""
    import backend.server.server_utils as su

    monkeypatch.chdir(tmp_path)

    class DummyGPTResearcher:
        def __init__(self, query, report_type=None, websocket=None, **kwargs):
            self.query = query
            self.websocket = websocket
            self.visited_urls = set()

        async def conduct_research(self):
            if self.websocket is not None:
                await self.websocket.send_json({"type": "logs", "content": "info", "output": "start"})

        async def write_report(self):
            return "dummy report"

        def get_source_urls(self):
            return []

        def get_costs(self):
            return 0.0

        def get_research_images(self):
            return []

    async def dummy_generate_report_files(report: str, filename: str):
        outputs_dir = Path("outputs")
        outputs_dir.mkdir(exist_ok=True)
        md_path = outputs_dir / f"{filename}.md"
        md_path.write_text(report, encoding="utf-8")
        return {"pdf": "", "docx": "", "md": str(md_path)}

    monkeypatch.setattr(su, "GPTResearcher", DummyGPTResearcher)
    monkeypatch.setattr(su, "generate_report_files", dummy_generate_report_files)

    researcher = su.Researcher(query="Test query", report_type="research_report")
    result = await researcher.research()

    assert "output" in result
    assert "json" in result["output"]
    assert os.path.exists(result["output"]["json"])
