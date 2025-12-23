from gpt_researcher import GPTResearcher
from backend.utils import write_md_to_pdf
import asyncio


async def main(task: str):
    # Progress callback
    def on_progress(progress):
        print(f"深度: {progress.current_depth}/{progress.total_depth}")
        print(f"广度: {progress.current_breadth}/{progress.total_breadth}")
        print(f"查询: {progress.completed_queries}/{progress.total_queries}")
        if progress.current_query:
            print(f"当前查询: {progress.current_query}")
    
    # Initialize researcher with deep research type
    researcher = GPTResearcher(
        query=task,
        report_type="deep",  # This will trigger deep research
    )
    
    # Run research with progress tracking
    print("开始深度研究...")
    context = await researcher.conduct_research(on_progress=on_progress)
    print("\n研究完成。正在生成报告...")
    
    # Generate the final report
    report = await researcher.write_report()
    await write_md_to_pdf(report, "deep_research_report")
    print(f"\n最终报告: {report}")

if __name__ == "__main__":
    query = "What are the most effective ways for beginners to start investing?"
    asyncio.run(main(query))