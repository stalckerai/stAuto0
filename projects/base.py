import asyncio
import logging
from playwright.async_api import BrowserContext, Page

logger = logging.getLogger(__name__)


class BaseProject:
    def __init__(self, context: BrowserContext, page: Page, account: dict, browser=None):
        self.context = context
        self.page = page
        self.account = account
        self.browser = browser

    async def run(self):
        """Запускает процесс с повторными попытками"""
        try:
            logger.info(f"[{self.account['name']}] Opening {self._get_page_name()} page")
            await self.page.goto(
                self._get_start_url(),
                wait_until="domcontentloaded",
                timeout=30000
            )

            logger.info(f"[{self.account['name']}] Waiting 5 seconds for page to load")
            await asyncio.sleep(5)

            max_attempts = self._get_max_attempts()
            for attempt in range(1, max_attempts + 1):
                logger.info(f"[{self.account['name']}] Attempt {attempt}/{max_attempts}")
                success = await self._process()
                if success:
                    logger.info(f"[{self.account['name']}] Task completed on attempt {attempt}")
                    return

                if attempt < max_attempts:
                    logger.info(f"[{self.account['name']}] Not done yet, retrying...")
                    await self.page.goto(
                        self._get_start_url(),
                        wait_until="domcontentloaded",
                        timeout=30000
                    )
                    await asyncio.sleep(5)

            logger.warning(f"[{self.account['name']}] Task not completed after {max_attempts} attempts")

        except Exception as e:
            logger.error(f"[{self.account['name']}] Project error: {e}", exc_info=True)
            raise

    # --- Virtual methods ---

    def _get_page_name(self) -> str:
        return "project"

    def _get_start_url(self) -> str:
        return "about:blank"

    def _get_max_attempts(self) -> int:
        return 3

    @classmethod
    def _use_new_tab(cls) -> bool:
        """
        Если True — проект работает в НОВОМ табе.
        Если False — проект использует существующий таб.

        По умолчанию: True (каждый проект в своём табе).
        """
        return True

    async def _check_done(self, page=None) -> bool:
        return False

    async def _login(self):
        pass

    async def _process(self) -> bool:
        return True
