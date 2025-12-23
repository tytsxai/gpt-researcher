import json
import re
import json_repair
import logging
from ..utils.llm import create_chat_completion
from ..prompts import PromptFamily

logger = logging.getLogger(__name__)

async def choose_agent(
    query,
    cfg,
    parent_query=None,
    cost_callback: callable = None,
    headers=None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
):
    """
    自动选择代理
    参数:
        parent_query: 在某些情况下，研究会针对主查询的子主题进行。
            parent_query 让代理了解主要上下文以便更好推理。
        query: 原始查询
        cfg: 配置
        cost_callback: 计算 LLM 成本的回调
        prompt_family: 提示词家族

    返回:
        agent: 代理名称
        agent_role_prompt: 代理角色提示词
    """
    query = f"{parent_query} - {query}" if parent_query else f"{query}"
    response = None  # Initialize response to ensure it's defined

    try:
        response = await create_chat_completion(
            model=cfg.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{prompt_family.auto_agent_instructions()}"},
                {"role": "user", "content": f"任务: {query}"},
            ],
            temperature=0.15,
            llm_provider=cfg.smart_llm_provider,
            llm_kwargs=cfg.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )

        agent_dict = json.loads(response)
        return agent_dict["server"], agent_dict["agent_role_prompt"]

    except Exception as e:
        return await handle_json_error(response)


async def handle_json_error(response):
    try:
        agent_dict = json_repair.loads(response)
        if agent_dict.get("server") and agent_dict.get("agent_role_prompt"):
            return agent_dict["server"], agent_dict["agent_role_prompt"]
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.warning(
            f"使用 json_repair 解析代理 JSON 失败: {error_type}: {error_msg}",
            exc_info=True
        )
        if response:
            logger.debug(f"无法解析的 LLM 响应: {response[:500]}...")

    json_string = extract_json_with_regex(response)
    if json_string:
        try:
            json_data = json.loads(json_string)
            return json_data["server"], json_data["agent_role_prompt"]
        except json.JSONDecodeError as e:
            logger.warning(
                f"从正则提取中解码 JSON 失败: {str(e)}",
                exc_info=True
            )

    logger.info("在 LLM 响应中未找到有效 JSON。回退到默认代理。")
    return "默认代理", (
        "你是一名具备批判性思维的人工智能研究助理。你的唯一目的就是基于给定文本撰写写作精良、"
        "广受好评、客观且结构化的报告。"
    )


def extract_json_with_regex(response):
    json_match = re.search(r"{.*?}", response, re.DOTALL)
    if json_match:
        return json_match.group(0)
    return None
