from typing import Dict, Any, Callable
from ..utils.logger import get_formatted_logger

logger = get_formatted_logger()


async def stream_output(
    type, content, output, websocket=None, output_log=True, metadata=None
):
    """
    向 websocket 流式输出
    参数:
        type:
        content:
        output:

    返回:
        无
    """
    if (not websocket or output_log) and type != "images":
        try:
            logger.info(f"{output}")
        except UnicodeEncodeError:
        # 方案 1：用占位符替换有问题的字符
            logger.error(output.encode(
                'cp1252', errors='replace').decode('cp1252'))

    if websocket:
        await websocket.send_json(
            {"type": type, "content": content,
                "output": output, "metadata": metadata}
        )


async def safe_send_json(websocket: Any, data: Dict[str, Any]) -> None:
    """
    安全地通过 WebSocket 连接发送 JSON 数据。

    参数:
        websocket (WebSocket): 用于发送数据的 WebSocket 连接。
        data (Dict[str, Any]): 要发送的 JSON 数据。

    返回:
        无
    """
    try:
        await websocket.send_json(data)
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(
            f"通过 WebSocket 发送 JSON 时出错: {error_type}: {error_msg}",
            exc_info=True
        )
        # 检查常见 WebSocket 错误并提供有用的上下文
        if "closed" in error_msg.lower() or "connection" in error_msg.lower():
            logger.warning("WebSocket 连接似乎已关闭。客户端可能已断开连接。")
        elif "timeout" in error_msg.lower():
            logger.warning("WebSocket 发送操作超时。客户端可能无响应。")


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str
) -> float:
    """
    根据 token 数量和所用模型计算 API 使用成本。

    参数:
        prompt_tokens (int): 提示词中的 token 数量。
        completion_tokens (int): 补全中的 token 数量。
        model (str): 用于 API 调用的模型。

    返回:
        float: 计算得到的成本（美元）。
    """
    # 定义不同模型每 1k token 的成本
    costs = {
        "gpt-3.5-turbo": 0.002,
        "gpt-4": 0.03,
        "gpt-4-32k": 0.06,
        "gpt-4o": 0.00001,
        "gpt-4o-mini": 0.000001,
        "o3-mini": 0.0000005,
        # 如有需要，可在此添加更多模型及其成本
    }

    model = model.lower()
    if model not in costs:
        logger.warning(
            f"未知模型: {model}。成本计算可能不准确。")
        return 0.0001 # 若模型未知，则使用默认平均成本

    cost_per_1k = costs[model]
    total_tokens = prompt_tokens + completion_tokens
    return (total_tokens / 1000) * cost_per_1k


def format_token_count(count: int) -> str:
    """
    使用逗号格式化 token 数量以提升可读性。

    参数:
        count (int): 要格式化的 token 数量。

    返回:
        str: 格式化后的 token 数量。
    """
    return f"{count:,}"


async def update_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    websocket: Any
) -> None:
    """
    通过 WebSocket 更新并发送成本信息。

    参数:
        prompt_tokens (int): 提示词中的 token 数量。
        completion_tokens (int): 补全中的 token 数量。
        model (str): 用于 API 调用的模型。
        websocket (WebSocket): 用于发送数据的 WebSocket 连接。

    返回:
        无
    """
    cost = calculate_cost(prompt_tokens, completion_tokens, model)
    total_tokens = prompt_tokens + completion_tokens

    await safe_send_json(websocket, {
        "type": "cost",
        "data": {
            "total_tokens": format_token_count(total_tokens),
            "prompt_tokens": format_token_count(prompt_tokens),
            "completion_tokens": format_token_count(completion_tokens),
            "total_cost": f"${cost:.4f}"
        }
    })


def create_cost_callback(websocket: Any) -> Callable:
    """
    创建用于更新成本的回调函数。

    参数:
        websocket (WebSocket): 用于发送数据的 WebSocket 连接。

    返回:
        Callable: 可用于更新成本的回调函数。
    """
    async def cost_callback(
        prompt_tokens: int,
        completion_tokens: int,
        model: str
    ) -> None:
        await update_cost(prompt_tokens, completion_tokens, model, websocket)

    return cost_callback
