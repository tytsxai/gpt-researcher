from typing import Any, Dict, List, Optional
import requests
import os


class CustomRetriever:
    """
    自定义 API 检索器
    """

    def __init__(self, query: str, query_domains=None):
        self.endpoint = os.getenv('RETRIEVER_ENDPOINT')
        if not self.endpoint:
            raise ValueError("未设置 RETRIEVER_ENDPOINT 环境变量")

        self.params = self._populate_params()
        self.query = query

    def _populate_params(self) -> Dict[str, Any]:
        """
        从以“RETRIEVER_ARG_”开头的环境变量中填充参数
        """
        return {
            key[len('RETRIEVER_ARG_'):].lower(): value
            for key, value in os.environ.items()
            if key.startswith('RETRIEVER_ARG_')
        }

    def search(self, max_results: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        使用自定义检索器端点执行搜索。

        :param max_results: 返回结果的最大数量（当前未使用）
        :return: JSON 响应格式如下：
            [
              {
                "url": "http://example.com/page1",
                "raw_content": "页面 1 的内容"
              },
              {
                "url": "http://example.com/page2",
                "raw_content": "页面 2 的内容"
              }
            ]
        """
        try:
            response = requests.get(
                self.endpoint,
                params={**self.params, "query": self.query},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"获取搜索结果失败：{e}")
            return None
