from typing import List, Dict, Any, Optional
import os
import xml.etree.ElementTree as ET
import requests
from typing import Any, Dict, List, Optional


class PubMedCentralSearch:
    """
    PubMed Central 全文搜索
    """

    def __init__(self, query: str, query_domains=None):
        self.base_search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.base_fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        
        # 从环境变量获取 API 密钥
        self.api_key = os.getenv('NCBI_API_KEY')
        if not self.api_key:
            print("警告：未设置 NCBI_API_KEY。请求将受到速率限制。")
        
        self.query = query
        self.db_type = os.getenv('PUBMED_DB', 'pmc')  # 默认使用 PMC 获取全文
        
        # 从环境变量获取可选参数
        self.params = self._populate_params()

    def _populate_params(self) -> Dict[str, Any]:
        """
        从以“PUBMED_ARG_”开头的环境变量中填充参数
        """
        params = {
            key[len('PUBMED_ARG_'):].lower(): value
            for key, value in os.environ.items()
            if key.startswith('PUBMED_ARG_')
        }
        
        # 若未提供则设置默认值
        params.setdefault('sort', 'relevance')
        params.setdefault('retmode', 'json')
        return params

    def _search_articles(self, max_results: int) -> Optional[List[str]]:
        """
        根据查询检索文章 ID
        """
        # 构建带全文过滤条件的搜索查询
        if self.db_type == 'pubmed':
            search_term = f"{self.query} AND (ffrft[filter] OR pmc[filter])"
        else:  # PMC 始终有全文
            search_term = self.query
        
        search_params = {
            "db": self.db_type,
            "term": search_term,
            "retmax": max_results,
            "api_key": self.api_key,
            **self.params  # 包含自定义参数
        }
        
        try:
            response = requests.get(self.base_search_url, params=search_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            id_list = data.get('esearchresult', {}).get('idlist', [])
            print(f"找到 {len(id_list)} 篇可获取全文的文章")
            return id_list
            
        except requests.RequestException as e:
            print(f"检索文章失败：{e}")
            return None

    def _fetch_full_text(self, article_id: str) -> Optional[Dict[str, str]]:
        """
        获取单篇文章的全文内容
        """
        fetch_params = {
            "db": "pmc" if self.db_type == "pmc" else "pmc",  # 始终从 PMC 获取全文
            "id": article_id,
            "rettype": "full",
            "retmode": "xml",
            "api_key": self.api_key
        }
        
        try:
            response = requests.get(self.base_fetch_url, params=fetch_params, timeout=10)
            response.raise_for_status()
            
            # 解析 XML 内容
            try:
                root = ET.fromstring(response.text)
                
                # 提取标题
                title = root.find('.//article-title')
                title_text = title.text if title is not None else ""
                
                # 提取摘要
                abstract = root.find('.//abstract')
                abstract_text = " ".join(abstract.itertext()) if abstract is not None else ""
                
                # 提取正文
                body = root.find('.//body')
                body_text = " ".join(body.itertext()) if body is not None else ""
                
                # 合并全部文本内容
                full_content = f"标题：{title_text}\n\n摘要：{abstract_text}\n\n正文：{body_text}"
                
                # 构建 URL
                if self.db_type == "pmc" or article_id.startswith("PMC"):
                    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{article_id}/"
                else:
                    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{article_id}/"
                
                return {
                    "url": url,
                    "raw_content": full_content,
                    "title": title_text  # 额外字段便于使用
                }
                
            except ET.ParseError as e:
                return None
                
        except requests.RequestException as e:
            return None

    def search(self, max_results: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        执行搜索并获取全文内容。

        :param max_results: 返回结果的最大数量
        :return: JSON 响应格式如下：
            [
              {
                "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/",
                "raw_content": "文章的全文内容..."
              },
              ...
            ]
        """
        # 步骤 1：检索文章 ID
        article_ids = self._search_articles(max_results)
        if not article_ids:
            return None
        
        # 步骤 2：获取每篇文章的全文
        results = []
        for article_id in article_ids:
            article_content = self._fetch_full_text(article_id)
            if article_content:
                results.append(article_content)
        
        return results
