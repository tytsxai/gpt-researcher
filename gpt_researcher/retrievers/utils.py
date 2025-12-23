import importlib.util
import logging
import os
import sys

logger = logging.getLogger(__name__)

async def stream_output(log_type, step, content, websocket=None, with_data=False, data=None):
    """
    将输出流式发送到客户端。
    
    参数:
        log_type (str): 日志类型
        step (str): 当前执行的步骤
        content (str): 要流式发送的内容
        websocket: 要发送到的 websocket
        with_data (bool): 是否包含数据
        data: 要附带的额外数据
    """
    if websocket:
        try:
            if with_data:
                await websocket.send_json({
                    "type": log_type,
                    "step": step,
                    "content": content,
                    "data": data
                })
            else:
                await websocket.send_json({
                    "type": log_type,
                    "step": step,
                    "content": content
                })
        except Exception as e:
            logger.error(f"流式输出错误: {e}")

def check_pkg(pkg: str) -> None:
    """
    检查包是否已安装，未安装则抛出错误。
    
    参数:
        pkg (str): 包名
    
    抛出:
        ImportError: 未安装包时抛出
    """
    if not importlib.util.find_spec(pkg):
        pkg_kebab = pkg.replace("_", "-")
        raise ImportError(
            f"无法导入 {pkg_kebab}。请使用以下命令安装："
            f"`pip install -U {pkg_kebab}`"
        )

# 回退时可用的检索器
VALID_RETRIEVERS = [
    "tavily",
    "custom",
    "duckduckgo",
    "searchapi",
    "serper",
    "serpapi",
    "google",
    "searx",
    "bing",
    "arxiv",
    "semantic_scholar",
    "pubmed_central",
    "exa",
    "mcp",
    "mock"
]

def get_all_retriever_names():
    """
    获取所有可用的检索器名称
    :return: 所有可用检索器名称的列表
    :rtype: list
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 获取当前目录下的所有条目
        all_items = os.listdir(current_dir)
        
        # 仅保留目录，排除 __pycache__
        retrievers = [
            item for item in all_items 
            if os.path.isdir(os.path.join(current_dir, item)) and not item.startswith('__')
        ]
        
        return retrievers
    except Exception as e:
        logger.error(f"获取检索器列表时出错: {e}")
        return VALID_RETRIEVERS
