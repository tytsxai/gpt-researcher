from contextlib import asynccontextmanager
import math
from pathlib import Path
import random
import traceback
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Dict, Literal, cast, Tuple, List
import requests
import asyncio
import logging

from ..utils import get_relevant_images, extract_title, get_text_from_soup, clean_soup


class NoDriverScraper:
    logger = logging.getLogger(__name__)
    max_browsers = 3
    browser_load_threshold = 5
    browsers: set["NoDriverScraper.Browser"] = set()
    browsers_lock = asyncio.Lock()

    @staticmethod
    def get_domain(url: str) -> str:
        domain = urlparse(url).netloc
        parts = domain.split(".")
        if len(parts) > 2:
            domain = ".".join(parts[-2:])
        return domain

    class Browser:
        def __init__(
            self,
            driver: "zendriver.Browser",
        ):
            self.driver = driver
            self.processing_count = 0
            self.has_blank_page = True
            self.allowed_requests_times = {}
            self.domain_semaphores: Dict[str, asyncio.Semaphore] = {}
            self.tab_mode = True
            self.max_scroll_percent = 500
            self.stopping = False

        async def get(self, url: str) -> "zendriver.Tab":
            self.processing_count += 1
            try:
                async with self.rate_limit_for_domain(url):
                    new_window = not self.has_blank_page
                    self.has_blank_page = False
                    if self.tab_mode:
                        return await self.driver.get(url, new_tab=new_window)
                    else:
                        return await self.driver.get(url, new_window=new_window)
            except Exception:
                self.processing_count -= 1
                raise

        async def scroll_page_to_bottom(self, page: "zendriver.Tab"):
            total_scroll_percent = 0
            while True:
                # in tab mode, we need to bring the tab to front before scrolling to load the page content properly
                if self.tab_mode:
                    await page.bring_to_front()
                scroll_percent = random.randrange(46, 97)
                total_scroll_percent += scroll_percent
                await page.scroll_down(scroll_percent)
                await self.wait_or_timeout(page, "idle", 2)
                await page.sleep(random.uniform(0.23, 0.56))

                if total_scroll_percent >= self.max_scroll_percent:
                    break

                if cast(
                    bool,
                    await page.evaluate(
                        "window.innerHeight + window.scrollY >= document.scrollingElement.scrollHeight"
                    ),
                ):
                    break

        async def wait_or_timeout(
            self,
            page: "zendriver.Tab",
            until: Literal["complete", "idle"] = "idle",
            timeout: float = 3,
        ):
            try:
                if until == "idle":
                    await asyncio.wait_for(page.wait(), timeout)
                else:
                    timeout = math.ceil(timeout)
                    await page.wait_for_ready_state(until, timeout=timeout)
            except asyncio.TimeoutError:
                NoDriverScraper.logger.debug(
                    f"等待 {until} 超时，已等待 {timeout} 秒"
                )

        async def close_page(self, page: "zendriver.Tab"):
            try:
                await page.close()
            except Exception as e:
                NoDriverScraper.logger.error(f"关闭页面失败: {e}")
            finally:
                self.processing_count -= 1

        @asynccontextmanager
        async def rate_limit_for_domain(self, url: str):
            semaphore = None
            try:
                domain = NoDriverScraper.get_domain(url)

                semaphore = self.domain_semaphores.get(domain)
                if not semaphore:
                    semaphore = asyncio.Semaphore(1)
                    self.domain_semaphores[domain] = semaphore

                was_locked = semaphore.locked()
                async with semaphore:
                    if was_locked:
                        await asyncio.sleep(random.uniform(0.6, 1.2))
                    yield

            except Exception as e:
                # Log error but don't block the request
                NoDriverScraper.logger.warning(
                    f"{url} 的限速处理出错: {str(e)}"
                )

        async def stop(self):
            if self.stopping:
                return
            self.stopping = True
            await self.driver.stop()

    @classmethod
    async def get_browser(cls, headless: bool = False) -> "NoDriverScraper.Browser":
        async def create_browser():
            try:
                global zendriver
                import zendriver
            except ImportError:
                raise ImportError(
                    "使用 NoDriverScraper 需要 zendriver 包。"
                    "请使用以下命令安装: pip install zendriver"
                )

            config = zendriver.Config(
                headless=headless,
                browser_connection_timeout=1,
            )
            driver = await zendriver.start(config)
            browser = cls.Browser(driver)
            cls.browsers.add(browser)
            return browser

        async with cls.browsers_lock:
            if len(cls.browsers) == 0:
                # No browsers available, create new one
                return await create_browser()

            # Load balancing: Get browser with lowest number of tabs
            browser = min(cls.browsers, key=lambda b: b.processing_count)

            # If all browsers are heavily loaded and we can create more
            if (
                browser.processing_count >= cls.browser_load_threshold
                and len(cls.browsers) < cls.max_browsers
            ):
                return await create_browser()

            return browser

    @classmethod
    async def release_browser(cls, browser: Browser):
        async with cls.browsers_lock:
            if browser and browser.processing_count <= 0:
                try:
                    await browser.stop()
                except Exception as e:
                    NoDriverScraper.logger.error(f"释放浏览器失败: {e}")
                finally:
                    cls.browsers.discard(browser)

    def __init__(self, url: str, session: requests.Session | None = None):
        self.url = url
        self.session = session
        self.debug = False

    async def scrape_async(self) -> Tuple[str, list[dict], str]:
        """Returns tuple of (text, image_urls, title)"""
        if not self.url:
            return (
                "未指定 URL，已取消浏览网站请求。",
                [],
                "",
            )

        browser: NoDriverScraper.Browser | None = None
        page = None
        try:
            try:
                browser = await self.get_browser()
            except ImportError as e:
                self.logger.error(f"初始化浏览器失败: {str(e)}")
                return str(e), [], ""

            page = await browser.get(self.url)
            await browser.wait_or_timeout(page, "complete", 2)
            # wait for potential redirection
            await page.sleep(random.uniform(0.3, 0.7))
            await browser.wait_or_timeout(page, "idle", 2)

            await browser.scroll_page_to_bottom(page)
            html = await page.get_content()
            soup = BeautifulSoup(html, "lxml")
            clean_soup(soup)
            text = get_text_from_soup(soup)
            image_urls = get_relevant_images(soup, self.url)
            title = extract_title(soup)

            if len(text) < 200:
                self.logger.warning(
                    f"{self.url} 的内容过短。标题: {title}，文本长度: {len(text)}，\n"
                    f"摘录: {text}。"
                )
                if self.debug:
                    screenshot_dir = Path("logs/screenshots")
                    screenshot_dir.mkdir(exist_ok=True)
                    screenshot_path = (
                        screenshot_dir
                        / f"screenshot-error-{NoDriverScraper.get_domain(self.url)}.jpeg"
                    )
                    await page.save_screenshot(screenshot_path)
                    self.logger.warning(
                        f"更多详情请查看截图: [{screenshot_path}]。"
                    )

            return text, image_urls, title
        except Exception as e:
            self.logger.error(
                f"抓取过程中发生错误: {str(e)}\n"
                "完整堆栈跟踪:\n"
                f"{traceback.format_exc()}"
            )
            return str(e), [], ""
        finally:
            try:
                if page and browser:
                    await browser.close_page(page)
                if browser:
                    await self.release_browser(browser)
            except Exception as e:
                self.logger.error(e)
