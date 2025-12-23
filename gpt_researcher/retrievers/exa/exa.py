import os
from ..utils import check_pkg


class ExaSearch:
    """
    Exa API 检索器
    """

    def __init__(self, query, query_domains=None):
        """
        初始化 ExaSearch 对象。
        参数:
            query: 搜索查询。
        """
        # 需要先校验，因为 exa_py 是可选依赖
        check_pkg("exa_py")
        from exa_py import Exa
        self.query = query
        self.api_key = self._retrieve_api_key()
        self.client = Exa(api_key=self.api_key)
        self.query_domains = query_domains or None

    def _retrieve_api_key(self):
        """
        从环境变量中获取 Exa API 密钥。
        返回:
            API 密钥。
        抛出:
            Exception: 未找到 API 密钥时抛出。
        """
        try:
            api_key = os.environ["EXA_API_KEY"]
        except KeyError:
            raise Exception(
                "未找到 Exa API 密钥。请设置 EXA_API_KEY 环境变量。"
                "可在 https://exa.ai/ 获取密钥。"
            )
        return api_key

    def search(
        self, max_results=10, use_autoprompt=False, search_type="neural", **filters
    ):
        """
        使用 Exa API 搜索查询。
        参数:
            max_results: 返回结果的最大数量。
            use_autoprompt: 是否使用自动提示。
            search_type: 搜索类型（例如："neural"、"keyword"）。
            **filters: 额外过滤条件（如日期范围、域名）。
        返回:
            搜索结果列表。
        """
        results = self.client.search(
            self.query,
            type=search_type,
            use_autoprompt=use_autoprompt,
            num_results=max_results,
            include_domains=self.query_domains,
            **filters
        )

        search_response = [
            {"href": result.url, "body": result.text} for result in results.results
        ]
        return search_response

    def find_similar(self, url, exclude_source_domain=False, **filters):
        """
        使用 Exa API 查找与给定 URL 相似的文档。
        参数:
            url: 用于查找相似文档的 URL。
            exclude_source_domain: 是否在结果中排除源域名。
            **filters: 额外过滤条件。
        返回:
            相似文档列表。
        """
        results = self.client.find_similar(
            url, exclude_source_domain=exclude_source_domain, **filters
        )

        similar_response = [
            {"href": result.url, "body": result.text} for result in results.results
        ]
        return similar_response

    def get_contents(self, ids, **options):
        """
        使用 Exa API 获取指定 ID 的内容。
        参数:
            ids: 要获取内容的文档 ID。
            **options: 内容检索的额外选项。
        返回:
            文档内容列表。
        """
        results = self.client.get_contents(ids, **options)

        contents_response = [
            {"id": result.id, "content": result.text} for result in results.results
        ]
        return contents_response
