import logging
import subprocess
import sys
import time
from pathlib import Path

import asyncio
from playwright.async_api import async_playwright, BrowserContext, Page

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
CHROME_ACCOUNTS_DIR = CONFIG_DIR / "chrome_accounts"
PROJECTS_DIR = BASE_DIR / "projects"
LOGS_DIR = BASE_DIR / "logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "browser.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class BaseBrowser:
    def __init__(self, account: dict):
        self.account = account
        self.name = account["name"]
        self.profile_dir = CHROME_ACCOUNTS_DIR / account["profile_directory"]
        self.debugging_port = account["debugging_port"]
        self.chrome_process = None
        self.playwright = None
        self.browser = None
        self.context: BrowserContext = None
        self.page: Page = None

    def launch_chrome(self, extensions=None):
        try:
            logger.info(f"[{self.name}] Launching Chrome on port {self.debugging_port}")
            self.profile_dir.mkdir(parents=True, exist_ok=True)

            chrome_path = self._find_chrome()
            if not chrome_path:
                raise FileNotFoundError("Chrome executable not found")

            # Добавляем аргументы для расширений
            args = [
                chrome_path,
                f"--remote-debugging-port={self.debugging_port}",
                f"--user-data-dir={self.profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
            ]

            # Если переданы расширения, добавляем их в аргументы
            if extensions:
                for ext_path in extensions:
                    args.extend(["--load-extension", str(ext_path)])

            self.chrome_process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info(
                f"[{self.name}] Chrome launched (PID: {self.chrome_process.pid})"
            )
            time.sleep(3)
        except Exception as e:
            logger.error(f"[{self.name}] Failed to launch Chrome: {e}")
            raise

    def _find_chrome(self):
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for p in paths:
            if Path(p).exists():
                return p
        return None

    async def connect(self, extensions=None):
        try:
            logger.info(
                f"[{self.name}] Connecting to Chrome on port {self.debugging_port}"
            )
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(
                f"http://localhost:{self.debugging_port}"
            )

            # Создаем новый контекст с расширениями
            context_options = {}
            if extensions:
                context_options["extensions"] = [str(ext) for ext in extensions]

            self.context = (
                await self.browser.new_context(**context_options)
                if not self.browser.contexts
                else self.browser.contexts[0]
            )
            
            # Если контекст уже существует, но нужно добавить расширения
            if self.browser.contexts and extensions:
                for ctx in self.browser.contexts:
                    await ctx.add_init_script(
                        f"window.__extensions__ = {json.dumps([str(e) for e in extensions])}"
                    )

            self.page = await self.context.new_page()
            logger.info(f"[{self.name}] Connected successfully")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to connect to Chrome: {e}")
            raise

    async def run_project(self, project_class):
        try:
            project = project_class(self.context, self.page, self.account)
            logger.info(f"[{self.name}] Running project: {project.__class__.__name__}")
            await project.run()
            logger.info(f"[{self.name}] Project completed successfully")
        except Exception as e:
            logger.error(f"[{self.name}] Project error: {e}")
            raise

    async def close(self):
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            if self.chrome_process:
                self.chrome_process.terminate()
                self.chrome_process.wait(timeout=5)
            logger.info(f"[{self.name}] Browser closed")
        except Exception as e:
            logger.error(f"[{self.name}] Error closing browser: {e}")
