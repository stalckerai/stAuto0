import json
import logging
import subprocess
import sys
import time
import shutil
from pathlib import Path

import asyncio
from playwright.async_api import async_playwright, BrowserContext, Page, Browser

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
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None

    async def launch_chrome(self, extensions=None):
        """Запускает Chrome через subprocess с отладочным портом"""
        try:
            logger.info(f"[{self.name}] Launching Chrome browser on port {self.debugging_port}")

            # Определяем путь к Chrome
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            ]

            chrome_path = None
            for path in chrome_paths:
                expanded = Path(path).expanduser()
                if expanded.exists():
                    chrome_path = str(expanded)
                    break

            if not chrome_path:
                raise FileNotFoundError("Chrome executable not found in standard locations")

            logger.info(f"[{self.name}] Chrome path: {chrome_path}")

            # Формируем аргументы
            args = [
                chrome_path,
                f"--remote-debugging-port={self.debugging_port}",
                f"--user-data-dir={self.profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
            ]

            # Добавляем расширения если указаны
            if extensions:
                extensions_str = ",".join([str(e) for e in extensions])
                args.append(f"--load-extension={extensions_str}")
                logger.info(f"[{self.name}] Loading extensions: {extensions_str}")

            logger.info(f"[{self.name}] Starting Chrome process")
            self.chrome_process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Ждём пока браузер запустится
            logger.info(f"[{self.name}] Waiting for Chrome to start...")
            await asyncio.sleep(5)

            logger.info(f"[{self.name}] Chrome launched successfully")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to launch Chrome: {e}", exc_info=True)
            raise

    async def connect(self):
        """Подключается к запущенному Chrome через CDP"""
        try:
            logger.info(f"[{self.name}] Connecting to Chrome via CDP on port {self.debugging_port}")

            self.playwright = await async_playwright().start()
            logger.info(f"[{self.name}] Playwright driver started")

            cdp_url = f"http://localhost:{self.debugging_port}"
            logger.info(f"[{self.name}] CDP URL: {cdp_url}")
            self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url, timeout=30000)
            logger.info(f"[{self.name}] Connected to browser")

            # Берём первый контекст (по умолчанию у подключенного браузера он один)
            if self.browser.contexts:
                self.context = self.browser.contexts[0]
            else:
                self.context = await self.browser.new_context()

            # Получаем или создаём страницу
            if self.context.pages:
                self.page = self.context.pages[0]
                logger.info(f"[{self.name}] Using existing page")
            else:
                self.page = await self.context.new_page()
                logger.info(f"[{self.name}] Created new page")

            logger.info(f"[{self.name}] Connected to Chrome successfully")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to connect to Chrome: {e}", exc_info=True)
            raise

    async def launch(self, extensions=None):
        """Полный запуск: launch_chrome + connect"""
        await self.launch_chrome(extensions)
        await self.connect()

    async def run_project(self, project_class):
        """Создаёт экземпляр проекта и вызывает его метод run"""
        try:
            project = project_class(self.context, self.page, self.account)
            logger.info(f"[{self.name}] Running project: {project.__class__.__name__}")
            await project.run()
            logger.info(f"[{self.name}] Project completed successfully")
        except Exception as e:
            logger.error(f"[{self.name}] Project error: {e}", exc_info=True)
            raise

    async def close(self):
        """Закрывает все ресурсы"""
        try:
            if self.page:
                try:
                    await self.page.close()
                except Exception:
                    pass
                logger.info(f"[{self.name}] Page closed")

            if self.context:
                try:
                    await self.context.close()
                except Exception:
                    pass
                logger.info(f"[{self.name}] Context closed")

            if self.browser:
                try:
                    await self.browser.close()
                except Exception:
                    pass
                logger.info(f"[{self.name}] Browser disconnected")

            if self.playwright:
                await self.playwright.stop()
                logger.info(f"[{self.name}] Playwright stopped")

            if self.chrome_process:
                logger.info(f"[{self.name}] Terminating Chrome process")
                self.chrome_process.terminate()
                try:
                    self.chrome_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"[{self.name}] Chrome didn't close gracefully, killing")
                    self.chrome_process.kill()
                    self.chrome_process.wait()

            logger.info(f"[{self.name}] All resources closed")
        except Exception as e:
            logger.error(f"[{self.name}] Error closing browser: {e}", exc_info=True)
