from typing import Any
from colorama import Fore, Style

from gpt_researcher.utils.workers import WorkerPool
from ..scraper import Scraper
from ..config.config import Config
from ..utils.logger import get_formatted_logger

logger = get_formatted_logger()


async def scrape_urls(
    urls, cfg: Config, worker_pool: WorkerPool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    抓取这些 URL
    参数:
        urls: URL 列表
        cfg: 配置（可选）

    返回:
        tuple[list[dict[str, Any]], list[dict[str, Any]]]: 包含抓取内容和图片的元组

    """
    scraped_data = []
    images = []
    user_agent = (
        cfg.user_agent
        if cfg
        else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    try:
        scraper = Scraper(urls, user_agent, cfg.scraper, worker_pool=worker_pool)
        scraped_data = await scraper.run()
        for item in scraped_data:
            if 'image_urls' in item:
                images.extend(item['image_urls'])
    except Exception as e:
        print(f"{Fore.RED}抓取 URL 时出错: {e}{Style.RESET_ALL}")

    return scraped_data, images


async def filter_urls(urls: list[str], config: Config) -> list[str]:
    """
    根据配置设置过滤 URL。

    参数:
        urls (list[str]): 要过滤的 URL 列表。
        config (Config): 配置对象。

    返回:
        list[str]: 过滤后的 URL 列表。
    """
    filtered_urls = []
    for url in urls:
        # 在这里添加过滤逻辑
        # 例如，你可能想排除特定域名或 URL 模式
        if not any(excluded in url for excluded in config.excluded_domains):
            filtered_urls.append(url)
    return filtered_urls

async def extract_main_content(html_content: str) -> str:
    """
    从 HTML 中提取主要内容。

    参数:
        html_content (str): 原始 HTML 内容。

    返回:
        str: 提取的主要内容。
    """
    # 在这里实现内容提取逻辑
    # 这可能涉及使用 BeautifulSoup 等库或自定义解析逻辑
    # 目前先返回原始 HTML 作为占位
    return html_content

async def process_scraped_data(scraped_data: list[dict[str, Any]], config: Config) -> list[dict[str, Any]]:
    """
    处理抓取数据以提取并清理主要内容。

    参数:
        scraped_data (list[dict[str, Any]]): 包含抓取数据的字典列表。
        config (Config): 配置对象。

    返回:
        list[dict[str, Any]]: 处理后的抓取数据。
    """
    processed_data = []
    for item in scraped_data:
        if item['status'] == 'success':
            main_content = await extract_main_content(item['content'])
            processed_data.append({
                'url': item['url'],
                'content': main_content,
                'status': 'success'
            })
        else:
            processed_data.append(item)
    return processed_data
