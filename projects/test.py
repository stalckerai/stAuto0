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
            await self.page.goto("https://httpbin.org/get")
            logger.info(f"[{self.account['name']}] Page loaded, waiting 5 seconds")
            await asyncio.sleep(5)
            logger.info(f"[{self.account['name']}] Test project finished")
        except Exception as e:
            logger.error(f"[{self.account['name']}] TestProject error: {e}")
            raise
