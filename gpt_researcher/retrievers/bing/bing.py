# Bing Search Retriever

# libraries
import os
import requests
import json
import logging


class BingSearch():
    """
    Bing Search Retriever
    """

    def __init__(self, query, query_domains=None):
        """
        Initializes the BingSearch object
        Args:
            query:
        """
        self.query = query
        self.query_domains = query_domains or None
        self.api_key = self.get_api_key()
        self.logger = logging.getLogger(__name__)

    def get_api_key(self):
        """
        Gets the Bing API key
        Returns:

        """
        try:
            api_key = os.environ["BING_API_KEY"]
        except:
            raise Exception(
                "未找到 Bing API 密钥。请设置 BING_API_KEY 环境变量。")
        return api_key

    def search(self, max_results=7) -> list[dict[str]]:
        """
        Searches the query
        Returns:

        """
        print("正在使用查询 {0} 进行搜索...".format(self.query))
        """Useful for general internet search queries using the Bing API."""

        # Search the query
        url = "https://api.bing.microsoft.com/v7.0/search"

        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        # TODO: Add support for query domains
        params = {
            "responseFilter": "Webpages",
            "q": self.query,
            "count": max_results,
            "setLang": "en-GB",
            "textDecorations": False,
            "textFormat": "HTML",
            "safeSearch": "Strict"
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Bing 搜索请求失败: {e}。返回空响应。")
            return []

        # Preprocess the results
        if resp is None:
            return []
        try:
            search_results = json.loads(resp.text)
            results = search_results["webPages"]["value"]
        except Exception as e:
            self.logger.error(
                f"解析 Bing 搜索结果时出错: {e}。返回空响应。")
            return []
        if search_results is None:
            self.logger.warning(f"未找到查询的搜索结果: {self.query}")
            return []
        search_results = []

        # Normalize the results to match the format of the other search APIs
        for result in results:
            # skip youtube results
            if "youtube.com" in result["url"]:
                continue
            search_result = {
                "title": result["name"],
                "href": result["url"],
                "body": result["snippet"],
            }
            search_results.append(search_result)

        return search_results
