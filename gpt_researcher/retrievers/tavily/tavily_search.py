# Tavily API 检索器

# 依赖库
import os
from typing import Literal, Sequence, Optional
import requests
import json


class TavilySearch:
    """
    Tavily API 检索器
    """

    def __init__(self, query, headers=None, topic="general", query_domains=None):
        """
        初始化 TavilySearch 对象。

        Args:
            query (str): 搜索查询字符串。
            headers (dict, optional): 要包含在请求中的额外请求头。默认为 None。
            topic (str, optional): 搜索主题。默认为 "general"。
            query_domains (list, optional): 要包含在搜索中的域名列表。默认为 None。
        """
        self.query = query
        self.headers = headers or {}
        self.topic = topic
        self.base_url = "https://api.tavily.com/search"
        self.api_key = self.get_api_key()
        self.headers = {
            "Content-Type": "application/json",
        }
        self.query_domains = query_domains or None

    def get_api_key(self):
        """
        获取 Tavily API 密钥
        Returns:

        """
        api_key = self.headers.get("tavily_api_key")
        if not api_key:
            try:
                api_key = os.environ["TAVILY_API_KEY"]
            except KeyError:
                print(
                    "未找到 Tavily API 密钥，设置为空。如果您需要检索器，请设置 TAVILY_API_KEY 环境变量。"
                )
                return ""
        return api_key


    def _search(
        self,
        query: str,
        search_depth: Literal["basic", "advanced"] = "basic",
        topic: str = "general",
        days: int = 2,
        max_results: int = 10,
        include_domains: Sequence[str] = None,
        exclude_domains: Sequence[str] = None,
        include_answer: bool = False,
        include_raw_content: bool = False,
        include_images: bool = False,
        use_cache: bool = True,
    ) -> dict:
        """
        向 API 发送请求的内部搜索方法。
        """

        data = {
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "days": days,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "max_results": max_results,
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "include_images": include_images,
            "api_key": self.api_key,
            "use_cache": use_cache,
        }

        response = requests.post(
            self.base_url, data=json.dumps(data), headers=self.headers, timeout=100
        )

        if response.status_code == 200:
            return response.json()
        else:
            # 如果 HTTP 请求返回非成功状态码，则抛出 HTTPError
            response.raise_for_status()

    def search(self, max_results=10):
        """
        搜索查询
        Returns:

        """
        try:
            # 执行搜索查询
            results = self._search(
                self.query,
                search_depth="basic",
                max_results=max_results,
                topic=self.topic,
                include_domains=self.query_domains,
            )
            sources = results.get("results", [])
            if not sources:
                raise Exception("使用 Tavily API 搜索未找到结果。")
            # 返回结果
            search_response = [
                {"href": obj["url"], "body": obj["content"]} for obj in sources
            ]
        except Exception as e:
            print(f"错误：{e}。获取来源失败，返回空结果。")
            search_response = []
        return search_response
