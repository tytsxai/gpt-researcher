#!/usr/bin/env python3
"""MCP integration tests.

These are external integration tests that require network access, `npx`, and
provider credentials. They are skipped by default.
"""

import os
import shutil
import pytest


def _env_truthy(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require_integration_prereqs(*vars_to_check: str) -> None:
    if not _env_truthy("RUN_MCP_TESTS"):
        pytest.skip("Set RUN_MCP_TESTS=true to run MCP integration tests")
    if shutil.which("npx") is None:
        pytest.skip("npx not available")
    missing = [v for v in vars_to_check if not os.environ.get(v)]
    if missing:
        pytest.skip(f"Missing env vars: {', '.join(missing)}")


@pytest.mark.asyncio
async def test_web_search_mcp():
    _require_integration_prereqs("OPENAI_API_KEY", "TAVILY_API_KEY")

    from gpt_researcher import GPTResearcher

    mcp_configs = [
        {
            "name": "tavily",
            "command": "npx",
            "args": ["-y", "tavily-mcp@0.1.2"],
            "env": {"TAVILY_API_KEY": os.environ["TAVILY_API_KEY"]},
        }
    ]

    researcher = GPTResearcher(query="MCP test query", mcp_configs=mcp_configs)
    await researcher.conduct_research()
    report = await researcher.write_report()
    assert isinstance(report, str) and report.strip()


@pytest.mark.asyncio
async def test_github_mcp():
    _require_integration_prereqs("OPENAI_API_KEY", "GITHUB_PERSONAL_ACCESS_TOKEN")

    from gpt_researcher import GPTResearcher

    mcp_configs = [
        {
            "name": "github",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"]},
        }
    ]

    researcher = GPTResearcher(query="MCP test query", mcp_configs=mcp_configs)
    await researcher.conduct_research()
    report = await researcher.write_report()
    assert isinstance(report, str) and report.strip()
