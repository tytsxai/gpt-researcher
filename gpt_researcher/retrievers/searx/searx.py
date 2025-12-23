import os
import json
import requests
from typing import List, Dict
from urllib.parse import urljoin


class SearxSearch():
    """
    SearxNG API 检索器
    """
    def __init__(self, query: str, query_domains=None):
        """
        初始化 SearxSearch 对象
        Args:
            query: 搜索查询字符串
        """
        self.query = query
        self.query_domains = query_domains or None
        self.base_url = self.get_searxng_url()

    def get_searxng_url(self) -> str:
        """
        从环境变量中获取 SearxNG 实例 URL
        Returns:
            str: SearxNG 实例的基础 URL
        """
        try:
            base_url = os.environ["SEARX_URL"]
            if not base_url.endswith('/'):
                base_url += '/'
            return base_url
        except KeyError:
            raise Exception(
                "未找到 SearxNG URL。请设置 SEARX_URL 环境变量。"
                "可在 https://searx.space/ 查找公共实例。"
            )

    def search(self, max_results: int = 10) -> List[Dict[str, str]]:
        """
        使用 SearxNG API 搜索查询
        Args:
            max_results: 返回结果的最大数量
        Returns:
            包含搜索结果的字典列表
        """
        search_url = urljoin(self.base_url, "search")
        # TODO: 添加对查询域名的支持
        params = {
            # 搜索查询。
            'q': self.query,
            # 结果输出格式，需要在 searxng 配置中启用。
            'format': 'json'
        }

        try:
            response = requests.get(
                search_url,
                params=params,
                headers={'Accept': 'application/json'}
            )
            response.raise_for_status()
            results = response.json()

            # 规范化结果以匹配预期格式
            search_response = []
            for result in results.get('results', [])[:max_results]:
                search_response.append({
                    "href": result.get('url', ''),
                    "body": result.get('content', '')
                })

            return search_response

        except requests.exceptions.RequestException as e:
            raise Exception(f"查询 SearxNG 出错：{str(e)}")
        except json.JSONDecodeError:
            raise Exception("解析 SearxNG 响应出错")
