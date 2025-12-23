import json_repair

from gpt_researcher.llm_provider.generic.base import ReasoningEfforts
from ..utils.llm import create_chat_completion
from ..prompts import PromptFamily
from typing import Any, List, Dict
from ..config import Config
import logging

logger = logging.getLogger(__name__)

async def get_search_results(query: str, retriever: Any, query_domains: List[str] = None, researcher=None) -> List[Dict[str, Any]]:
    """
    获取给定查询的网页搜索结果。

    参数:
        query: 搜索查询
        retriever: 检索器实例
        query_domains: 可选的搜索域名列表
        researcher: 研究器实例（MCP 检索器需要）

    返回:
        搜索结果列表
    """
    # 检查是否为 MCP 检索器并传入 researcher 实例
    if "mcpretriever" in retriever.__name__.lower():
        search_retriever = retriever(
            query, 
            query_domains=query_domains,
            researcher=researcher  # 为 MCP 检索器传入 researcher 实例
        )
    else:
        search_retriever = retriever(query, query_domains=query_domains)
    
    return search_retriever.search()

async def generate_sub_queries(
    query: str,
    parent_query: str,
    report_type: str,
    context: List[Dict[str, Any]],
    cfg: Config,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> List[str]:
    """
    使用指定的 LLM 模型生成子查询。

    参数:
        query: 原始查询
        parent_query: 父查询
        report_type: 报告类型
        max_iterations: 最大研究迭代次数
        context: 搜索结果上下文
        cfg: 配置对象
        cost_callback: 成本计算回调
        prompt_family: 提示词家族

    返回:
        子查询列表
    """
    gen_queries_prompt = prompt_family.generate_search_queries_prompt(
        query,
        parent_query,
        report_type,
        max_iterations=cfg.max_iterations or 3,
        context=context,
    )

    try:
        response = await create_chat_completion(
            model=cfg.strategic_llm_model,
            messages=[{"role": "user", "content": gen_queries_prompt}],
            llm_provider=cfg.strategic_llm_provider,
            max_tokens=None,
            llm_kwargs=cfg.llm_kwargs,
            reasoning_effort=ReasoningEfforts.Medium.value,
            cost_callback=cost_callback,
            **kwargs
        )
    except Exception as e:
        logger.warning(f"战略 LLM 出错: {e}。使用 max_tokens={cfg.strategic_token_limit} 重试。")
        logger.warning("参见 https://github.com/assafelovic/gpt-researcher/issues/1022")
        try:
            response = await create_chat_completion(
                model=cfg.strategic_llm_model,
                messages=[{"role": "user", "content": gen_queries_prompt}],
                max_tokens=cfg.strategic_token_limit,
                llm_provider=cfg.strategic_llm_provider,
                llm_kwargs=cfg.llm_kwargs,
                cost_callback=cost_callback,
                **kwargs
            )
            logger.warning(f"使用 max_tokens={cfg.strategic_token_limit} 重试成功。")
        except Exception as e:
            logger.warning(f"使用 max_tokens={cfg.strategic_token_limit} 重试失败。")
            logger.warning(f"战略 LLM 出错: {e}。回退到智能 LLM。")
            response = await create_chat_completion(
                model=cfg.smart_llm_model,
                messages=[{"role": "user", "content": gen_queries_prompt}],
                temperature=cfg.temperature,
                max_tokens=cfg.smart_token_limit,
                llm_provider=cfg.smart_llm_provider,
                llm_kwargs=cfg.llm_kwargs,
                cost_callback=cost_callback,
                **kwargs
            )

    return json_repair.loads(response)

async def plan_research_outline(
    query: str,
    search_results: List[Dict[str, Any]],
    agent_role_prompt: str,
    cfg: Config,
    parent_query: str,
    report_type: str,
    cost_callback: callable = None,
    retriever_names: List[str] = None,
    **kwargs
) -> List[str]:
    """
    通过生成子查询来规划研究提纲。

    参数:
        query: 原始查询
        search_results: 初始搜索结果
        agent_role_prompt: 代理角色提示词
        cfg: 配置对象
        parent_query: 父查询
        report_type: 报告类型
        cost_callback: 成本计算回调
        retriever_names: 使用中的检索器名称

    返回:
        子查询列表
    """
    # 处理未提供 retriever_names 的情况
    if retriever_names is None:
        retriever_names = []
    
    # 对于 MCP 检索器，可能需要跳过子查询生成
    # 检查 MCP 是唯一检索器还是多检索器之一
    if retriever_names and ("mcp" in retriever_names or "MCPRetriever" in retriever_names):
        mcp_only = (len(retriever_names) == 1 and 
                   ("mcp" in retriever_names or "MCPRetriever" in retriever_names))
        
        if mcp_only:
            # 如果 MCP 是唯一检索器，则跳过子查询生成
            logger.info("仅使用 MCP 检索器 - 跳过子查询生成")
            # 返回原始查询以避免额外搜索迭代
            return [query]
        else:
            # 如果 MCP 是多个检索器之一，则为其他检索器生成子查询
            logger.info("与其他检索器一起使用 MCP - 为非 MCP 检索器生成子查询")

    # 为研究提纲生成子查询
    sub_queries = await generate_sub_queries(
        query,
        parent_query,
        report_type,
        search_results,
        cfg,
        cost_callback,
        **kwargs
    )

    return sub_queries
