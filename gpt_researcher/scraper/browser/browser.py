from __future__ import annotations

import traceback
import pickle
from pathlib import Path
from sys import platform
import time
import random
import string
import os

from bs4 import BeautifulSoup
from typing import Iterable, cast

from .processing.scrape_skills import (scrape_pdf_with_pymupdf,
                                       scrape_pdf_with_arxiv)

from urllib.parse import urljoin

from ..utils import get_relevant_images, extract_title, get_text_from_soup, clean_soup

FILE_DIR = Path(__file__).parent.parent

class BrowserScraper:
    def __init__(self, url: str, session=None):
        self.url = url
        self.session = session
        self.selenium_web_browser = "chrome"
        self.headless = False
        self.user_agent = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/128.0.0.0 Safari/537.36")
        self.driver = None
        self.use_browser_cookies = False
        self._import_selenium()  # Import only if used to avoid unnecessary dependencies
        self.cookie_filename = f"{self._generate_random_string(8)}.pkl"

    def scrape(self) -> tuple:
        if not self.url:
            print("未指定 URL")
            return "未指定 URL，已取消浏览网站请求。", [], ""

        try:
            self.setup_driver()
            self._visit_google_and_save_cookies()
            self._load_saved_cookies()
            self._add_header()

            text, image_urls, title = self.scrape_text_with_selenium()
            return text, image_urls, title
        except Exception as e:
            print(f"抓取过程中发生错误: {str(e)}")
            print("完整堆栈跟踪:")
            print(traceback.format_exc())
            return f"发生错误: {str(e)}\n\n堆栈跟踪:\n{traceback.format_exc()}", [], ""
        finally:
            if self.driver:
                self.driver.quit()
            self._cleanup_cookie_file()

    def _import_selenium(self):
        try:
            global webdriver, By, EC, WebDriverWait, TimeoutException, WebDriverException
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.wait import WebDriverWait
            from selenium.common.exceptions import TimeoutException, WebDriverException

            global ChromeOptions, FirefoxOptions, SafariOptions
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from selenium.webdriver.safari.options import Options as SafariOptions
        except ImportError as e:
            print(f"导入 Selenium 失败: {str(e)}")
            print("要使用 BrowserScraper，请先安装 Selenium 及其依赖项。")
            print("您可以使用 pip 安装 Selenium:")
            print("    pip install selenium")
            print("如果您使用的是虚拟环境，请确保已激活。")
            raise ImportError(
                "需要 Selenium 但未安装。请参阅上面的错误信息以获取安装说明。") from e

    def setup_driver(self) -> None:
        # print(f"Setting up {self.selenium_web_browser} driver...")

        options_available = {
            "chrome": ChromeOptions,
            "firefox": FirefoxOptions,
            "safari": SafariOptions,
        }

        options = options_available[self.selenium_web_browser]()
        options.add_argument(f"user-agent={self.user_agent}")
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--enable-javascript")

        try:
            if self.selenium_web_browser == "firefox":
                self.driver = webdriver.Firefox(options=options)
            elif self.selenium_web_browser == "safari":
                self.driver = webdriver.Safari(options=options)
            else:  # chrome
                if platform == "linux" or platform == "linux2":
                    options.add_argument("--disable-dev-shm-usage")
                    options.add_argument("--remote-debugging-port=9222")
                options.add_argument("--no-sandbox")
                options.add_experimental_option("prefs", {"download_restrictions": 3})
                self.driver = webdriver.Chrome(options=options)

            if self.use_browser_cookies:
                self._load_browser_cookies()

            # print(f"{self.selenium_web_browser.capitalize()} driver set up successfully.")
        except Exception as e:
            print(f"设置 {self.selenium_web_browser} 驱动失败: {str(e)}")
            print("完整堆栈跟踪:")
            print(traceback.format_exc())
            raise

    def _load_saved_cookies(self):
        """Load saved cookies before visiting the target URL"""
        cookie_file = Path(self.cookie_filename)
        if cookie_file.exists():
            cookies = pickle.load(open(self.cookie_filename, "rb"))
            for cookie in cookies:
                self.driver.add_cookie(cookie)
        else:
            print("未找到保存的 cookies。")

    def _load_browser_cookies(self):
        """Load cookies directly from the browser"""
        try:
            import browser_cookie3
        except ImportError:
            print(
                "未安装 browser_cookie3。请使用以下命令安装: pip install browser_cookie3"
            )
            return

        if self.selenium_web_browser == "chrome":
            cookies = browser_cookie3.chrome()
        elif self.selenium_web_browser == "firefox":
            cookies = browser_cookie3.firefox()
        else:
            print(f"{self.selenium_web_browser} 不支持加载 cookies")
            return

        for cookie in cookies:
            self.driver.add_cookie({'name': cookie.name, 'value': cookie.value, 'domain': cookie.domain})

    def _cleanup_cookie_file(self):
        """Remove the cookie file"""
        cookie_file = Path(self.cookie_filename)
        if cookie_file.exists():
            try:
                os.remove(self.cookie_filename)
            except Exception as e:
                print(f"删除 cookie 文件失败: {str(e)}")
        else:
            print("未找到要删除的 cookie 文件。")

    def _generate_random_string(self, length):
        """Generate a random string of specified length"""
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def _get_domain(self):
        """Extract domain from URL"""
        from urllib.parse import urlparse

        """Get domain from URL, removing 'www' if present"""
        domain = urlparse(self.url).netloc
        return domain[4:] if domain.startswith("www.") else domain

    def _visit_google_and_save_cookies(self):
        """Visit Google and save cookies before navigating to the target URL"""
        try:
            self.driver.get("https://www.google.com")
            time.sleep(2)  # Wait for cookies to be set

            # Save cookies to a file
            cookies = self.driver.get_cookies()
            pickle.dump(cookies, open(self.cookie_filename, "wb"))

            # print("Google cookies saved successfully.")
        except Exception as e:
            print(f"访问 Google 并保存 cookies 失败: {str(e)}")
            print("完整堆栈跟踪:")
            print(traceback.format_exc())

    def scrape_text_with_selenium(self) -> tuple:
        self.driver.get(self.url)

        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException as e:
            print("等待页面加载超时")
            print(f"完整堆栈跟踪:\n{traceback.format_exc()}")
            return "页面加载超时", [], ""

        self._scroll_to_bottom()

        if self.url.endswith(".pdf"):
            text = scrape_pdf_with_pymupdf(self.url)
            return text, [], ""
        elif "arxiv" in self.url:
            doc_num = self.url.split("/")[-1]
            text = scrape_pdf_with_arxiv(doc_num)
            return text, [], ""
        else:
            page_source = self.driver.execute_script(
                "return document.documentElement.outerHTML;"
            )
            soup = BeautifulSoup(page_source, "lxml")

            soup = clean_soup(soup)

            text = get_text_from_soup(soup)
            image_urls = get_relevant_images(soup, self.url)
            title = extract_title(soup)

        return text, image_urls, title

    def _scroll_to_bottom(self):
        """Scroll to the bottom of the page to load all content"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for content to load
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def _scroll_to_percentage(self, ratio: float) -> None:
        """Scroll to a percentage of the page"""
        if ratio < 0 or ratio > 1:
            raise ValueError("百分比应在 0 到 1 之间")
        self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {ratio});")

    def _add_header(self) -> None:
        """Add a header to the website"""
        self.driver.execute_script(open(f"{FILE_DIR}/browser/js/overlay.js", "r").read())
