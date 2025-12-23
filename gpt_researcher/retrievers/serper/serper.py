# Google Serper 检索器

# 依赖库
import os
import requests
import json


class SerperSearch():
    """
    支持国家、语言和日期过滤的 Google Serper 检索器
    """
    def __init__(self, query, query_domains=None, country=None, language=None, time_range=None, exclude_sites=None):
        """
        初始化 SerperSearch 对象
        Args:
            query (str): 搜索查询字符串。
            query_domains (list, optional): 需要包含在搜索中的域名列表。默认为 None。
            country (str, optional): 搜索结果的国家代码（例如：'us'、'kr'、'jp'）。默认为 None。
            language (str, optional): 搜索结果的语言代码（例如：'en'、'ko'、'ja'）。默认为 None。
            time_range (str, optional): 时间范围过滤（例如：'qdr:h'、'qdr:d'、'qdr:w'、'qdr:m'、'qdr:y'）。默认为 None。
            exclude_sites (list, optional): 要从搜索结果中排除的网站列表。默认为 None。
        """
        self.query = query
        self.query_domains = query_domains or None
        self.country = country or os.getenv("SERPER_REGION")
        self.language = language or os.getenv("SERPER_LANGUAGE")
        self.time_range = time_range or os.getenv("SERPER_TIME_RANGE")
        self.exclude_sites = exclude_sites or self._get_exclude_sites_from_env()
        self.api_key = self.get_api_key()

    def _get_exclude_sites_from_env(self):
        """
        从环境变量中获取需要排除的网站列表
        Returns:
            list: 要排除的网站列表
        """
        exclude_sites_env = os.getenv("SERPER_EXCLUDE_SITES", "")
        if exclude_sites_env:
            # 按逗号分隔并去除空白
            return [site.strip() for site in exclude_sites_env.split(",") if site.strip()]
        return []

    def get_api_key(self):
        """
        获取 Serper API 密钥
        Returns:

        """
        try:
            api_key = os.environ["SERPER_API_KEY"]
        except:
            raise Exception("未找到 Serper API 密钥。请设置 SERPER_API_KEY 环境变量。"
                            "可在 https://serper.dev/ 获取密钥。")
        return api_key

    def search(self, max_results=7):
        """
        搜索查询，并可选国家、语言和时间过滤
        Returns:
            list: 包含 title、href 和 body 的搜索结果列表
        """
        print("正在使用查询 {0} 进行搜索...".format(self.query))
        """使用 Serper API 进行通用互联网搜索查询。"""

        # 执行搜索查询（格式说明见 https://serper.dev/playground）
        url = "https://google.serper.dev/search"

        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        # 构建搜索参数
        query_with_filters = self.query

        # 使用 Google 搜索语法排除站点
        if self.exclude_sites:
            for site in self.exclude_sites:
                query_with_filters += f" -site:{site}"

        # 如果指定则添加域名过滤
        if self.query_domains:
            # 将 site:domain1 OR site:domain2 OR ... 添加到搜索查询
            domain_query = " site:" + " OR site:".join(self.query_domains)
            query_with_filters += domain_query

        search_params = {
            "q": query_with_filters,
            "num": max_results
        }

        # 添加可选参数（若存在）
        if self.country:
            search_params["gl"] = self.country  # 地理位置（国家）

        if self.language:
            search_params["hl"] = self.language  # 主语言

        if self.time_range:
            search_params["tbs"] = self.time_range  # 时间范围搜索

        data = json.dumps(search_params)

        resp = requests.request("POST", url, timeout=10, headers=headers, data=data)

        # 预处理结果
        if resp is None:
            return
        try:
            search_results = json.loads(resp.text)
        except Exception:
            return
        if search_results is None:
            return

        results = search_results.get("organic", [])
        search_results = []

        # 规范化结果以匹配其他搜索 API 的格式
        # 排除站点应已由查询参数过滤
        for result in results:
            search_result = {
                "title": result["title"],
                "href": result["link"],
                "body": result["snippet"],
            }
            search_results.append(search_result)

        return search_results
