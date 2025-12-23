from typing import Dict, Optional, List
import json
from ..config.config import Config
from ..utils.llm import create_chat_completion
from ..actions import stream_output


class SourceCurator:
    """Ranks sources and curates data based on their relevance, credibility and reliability."""

    def __init__(self, researcher):
        self.researcher = researcher

    async def curate_sources(
        self,
        source_data: List,
        max_results: int = 10,
    ) -> List:
        """
        Rank sources based on research data and guidelines.

        Args:
            query: The research query/task
            source_data: List of source documents to rank
            max_results: Maximum number of top sources to return

        Returns:
            str: Ranked list of source URLs with reasoning
        """
        print(f"\n\n正在整理 {len(source_data)} 个来源: {source_data}")
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "research_plan",
                f"⚖️ 正在根据可信度和相关性评估和整理来源...",
                self.researcher.websocket,
            )

        response = ""
        try:
            response = await create_chat_completion(
                model=self.researcher.cfg.smart_llm_model,
                messages=[
                    {"role": "system", "content": f"{self.researcher.role}"},
                    {"role": "user", "content": self.researcher.prompt_family.curate_sources(
                        self.researcher.query, source_data, max_results)},
                ],
                temperature=0.2,
                max_tokens=8000,
                llm_provider=self.researcher.cfg.smart_llm_provider,
                llm_kwargs=self.researcher.cfg.llm_kwargs,
                cost_callback=self.researcher.add_costs,
            )

            curated_sources = json.loads(response)
            print(f"\n\n最终整理的 {len(source_data)} 个来源: {curated_sources}")

            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "research_plan",
                    f"🏅 已验证并排序前 {len(curated_sources)} 个最可靠的来源",
                    self.researcher.websocket,
                )

            return curated_sources

        except Exception as e:
            print(f"从 LLM 响应整理来源时出错: {response}")
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "research_plan",
                    f"🚫 来源验证失败: {str(e)}",
                    self.researcher.websocket,
                )
            return source_data
