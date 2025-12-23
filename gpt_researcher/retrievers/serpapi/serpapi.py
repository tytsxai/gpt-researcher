# SerpApi 检索器

# 依赖库
import os
import requests
import urllib.parse


class SerpApiSearch():
    """
    SerpApi 检索器
    """
    def __init__(self, query, query_domains=None):
        """
        初始化 SerpApiSearch 对象
        Args:
            query:
        """
        self.query = query
        self.query_domains = query_domains or None
        self.api_key = self.get_api_key()

    def get_api_key(self):
        """
        获取 SerpApi API 密钥
        Returns:

        """
        try:
            api_key = os.environ["SERPAPI_API_KEY"]
        except:
            raise Exception("未找到 SerpApi API 密钥。请设置 SERPAPI_API_KEY 环境变量。"
                            "可在 https://serpapi.com/ 获取密钥。")
        return api_key

    def search(self, max_results=7):
        """
        搜索查询
        Returns:

        """
        print("SerpApiSearch：正在使用查询 {0} 进行搜索...".format(self.query))
        """使用 SerpApi 进行通用互联网搜索查询。"""

        url = "https://serpapi.com/search.json"

        search_query = self.query
        if self.query_domains:
            # 将 site:domain1 OR site:domain2 OR ... 添加到搜索查询
            search_query += " site:" + " OR site:".join(self.query_domains)

        params = {
            "q": search_query,
            "api_key": self.api_key
        }
        encoded_url = url + "?" + urllib.parse.urlencode(params)
        search_response = []
        try:
            response = requests.get(encoded_url, timeout=10)
            if response.status_code == 200:
                search_results = response.json()
                if search_results:
                    results = search_results["organic_results"]
                    results_processed = 0
                    for result in results:
                        # 跳过 YouTube 结果
                        if "youtube.com" in result["link"]:
                            continue
                        if results_processed >= max_results:
                            break
                        search_result = {
                            "title": result["title"],
                            "href": result["link"],
                            "body": result["snippet"],
                        }
                        search_response.append(search_result)
                        results_processed += 1
        except Exception as e:
            print(f"错误：{e}。获取来源失败，返回空结果。")
            search_response = []

        return search_response
