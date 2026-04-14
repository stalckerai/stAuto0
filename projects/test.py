import asyncio
import logging
from projects.base import BaseProject

logger = logging.getLogger(__name__)


class TestProject(BaseProject):
    def _get_page_name(self) -> str:
        return "test"

    def _get_start_url(self) -> str:
        return "https://httpbin.org/get"

    async def _process(self) -> bool:
        try:
            logger.info(f"[{self.account['name']}] Opening test page")
            await self.page.goto(
                "https://httpbin.org/get",
                wait_until="domcontentloaded",
                timeout=10000
            )
            logger.info(f"[{self.account['name']}] Page loaded, waiting 5 seconds")
            await asyncio.sleep(5)
            logger.info(f"[{self.account['name']}] Test project finished")
            return True
        except Exception as e:
            logger.error(f"[{self.account['name']}] TestProject error: {e}")
            raise
