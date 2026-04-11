import asyncio
import logging
from playwright.async_api import BrowserContext, Page

logger = logging.getLogger(__name__)


class BaseProject:
    def __init__(self, context: BrowserContext, page: Page, account: dict):
        self.context = context
        self.page = page
        self.account = account

    async def run(self):
        raise NotImplementedError


class TestProject(BaseProject):
    async def run(self):
        try:
            logger.info(f"[{self.account['name']}] Opening test page")
            try:
                # Пробуем открыть страницу с таймаутом и обработкой ошибок
                await self.page.goto(
                    "https://httpbin.org/get",
                    wait_until="domcontentloaded",
                    timeout=10000
                )
            except Exception as navigate_error:
                logger.warning(f"[{self.account['name']}] Failed to load httpbin, trying alternative page: {navigate_error}")
                # Если первая страница не загружается, пробуем локальную пустую страницу
                try:
                    await self.page.goto(
                        "about:blank",
                        timeout=5000
                    )
                except Exception as blank_error:
                    logger.error(f"[{self.account['name']}] Failed to load blank page: {blank_error}")
                    raise
            
            logger.info(f"[{self.account['name']}] Page loaded, waiting 5 seconds")
            await asyncio.sleep(5)
            logger.info(f"[{self.account['name']}] Test project finished")
        except Exception as e:
            logger.error(f"[{self.account['name']}] TestProject error: {e}")
            raise
