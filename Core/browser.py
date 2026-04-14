import json
import logging
import subprocess
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime

import asyncio
from playwright.async_api import async_playwright, BrowserContext, Page, Browser

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
CHROME_ACCOUNTS_DIR = CONFIG_DIR / "chrome_accounts"
PROJECTS_DIR = BASE_DIR / "projects"
LOGS_DIR = BASE_DIR / "logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Формируем имя файла логов с датой: browser_2026-04-13.log
log_filename = f"browser_{datetime.now().strftime('%Y-%m-%d')}.log"
log_file = LOGS_DIR / log_filename

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
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

            # Сбрасываем состояние краша, не удаляя настройки
            # 1. Local State
            local_state = self.profile_dir / "Local State"
            if local_state.exists():
                try:
                    import json
                    with open(local_state, "r", encoding="utf-8") as f:
                        ls = json.load(f)
                    ls["exited_cleanly"] = True
                    with open(local_state, "w", encoding="utf-8") as f:
                        json.dump(ls, f)
                except Exception:
                    pass

            # 2. Default/Preferences — только session
            prefs_file = self.profile_dir / "Default" / "Preferences"
            if prefs_file.exists():
                try:
                    import json
                    with open(prefs_file, "r", encoding="utf-8") as f:
                        prefs = json.load(f)
                    if "exit_type" in prefs.get("session", {}):
                        prefs["session"]["exit_type"] = "Normal"
                        prefs["session"]["exited_cleanly"] = True
                    with open(prefs_file, "w", encoding="utf-8") as f:
                        json.dump(prefs, f)
                except Exception:
                    pass

            # 3. Удаляем только файлы сессий
            for crash_file in ["Last Session", "Last Tabs", "Last Session~", "Last Tabs~"]:
                crash_path = self.profile_dir / crash_file
                if crash_path.exists():
                    try:
                        crash_path.unlink()
                    except Exception:
                        pass

            # Формируем аргументы
            args = [
                chrome_path,
                f"--remote-debugging-port={self.debugging_port}",
                "--remote-allow-origins=*",
                f"--user-data-dir={self.profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-session-crashed-bubble",
                "--disable-session-crashed-notification",
                "--disable-features=SessionCrashedBubble,Translate,TranslateUI,SideSearch",
                "--disable-restore-session-state",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-hang-monitor",
                "--disable-crash-reporter",
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

            # Активируем окно Chrome
            try:
                await self.page.bring_to_front()
                logger.info(f"[{self.name}] Brought page to front")
            except Exception as e:
                logger.info(f"[{self.name}] Could not bring page to front: {e}")

            logger.info(f"[{self.name}] Connected to Chrome successfully")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to connect to Chrome: {e}", exc_info=True)
            raise

    async def launch(self, extensions=None):
        """Полный запуск: launch_chrome + connect"""
        await self.launch_chrome(extensions)
        await self.connect()

    async def login_zerion(self, password: str = None):
        """Логин в Zerion Wallet"""
        try:
            wallet_password = password or self.account.get("wallet_password")
            if not wallet_password:
                logger.warning(f"[{self.name}] No wallet password found, skipping login")
                return

            login_url = "chrome-extension://klghhnkeealcohjjanjjdaeeggmfmlpl/popup.8e8f209b.html?windowType=dialog#/login"
            logger.info(f"[{self.name}] Opening Zerion login page")

            page = await self.context.new_page()
            await page.goto(login_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)

            # Проверяем наличие поля ввода пароля
            password_field = await page.query_selector('input[name="password"][type="password"]')
            if password_field:
                logger.info(f"[{self.name}] Password field found, entering password")
                await password_field.fill(wallet_password, timeout=5000)
                await asyncio.sleep(1)

                # Нажимаем Unlock
                unlock_btn = await page.query_selector('button.EyUuEa_primary:text("Unlock")')
                if unlock_btn:
                    await unlock_btn.click()
                    logger.info(f"[{self.name}] Unlock button clicked")
                    await asyncio.sleep(7)  # Ждём 7 сек после успешного логина
                    logger.info(f"[{self.name}] Zerion login completed")
                else:
                    logger.warning(f"[{self.name}] Unlock button not found")
            else:
                logger.info(f"[{self.name}] Password field not found — wallet may already be unlocked")

            # Таб НЕ закрываем — Zerion остаётся открытым для использования
            logger.info(f"[{self.name}] Zerion login tab stays open")

        except Exception as e:
            logger.error(f"[{self.name}] Zerion login error: {e}", exc_info=True)

    async def _concrete_setup_referral(self, page):
        """
        Настройка Concrete: подключение Zerion + ввод реферального кода.
        
        НЕ вызывается автоматически — предназначена для ручного вызова.
        
        Args:
            page: объект Page, уже открытый на странице leaderboard
        """
        try:
            # Проверяем наличие кнопки Connect — если есть, значит нужно залогиниться
            connect_btn = page.get_by_role("button", name="Connect", exact=True)
            found_connect = False
            try:
                found_connect = await connect_btn.is_visible(timeout=3000)
            except Exception:
                pass

            if found_connect:
                logger.info(f"[{self.name}] Connect button found, clicking")
                await connect_btn.click()
                await asyncio.sleep(5)
                await self._connect_zerion_with_popup(page)
                logger.info(f"[{self.name}] Zerion connection completed")
                await asyncio.sleep(5)

            # Вставляем referral code — ждём появления элемента
            logger.info(f"[{self.name}] Entering referral code")
            referral_input = page.get_by_placeholder("Enter referral code")
            await referral_input.wait_for(state="visible", timeout=15000)
            await referral_input.fill("42e0ff07", timeout=5000)
            await asyncio.sleep(1)

            # Нажимаем Apply Code
            logger.info(f"[{self.name}] Clicking Apply Code")
            apply_btn = page.get_by_role("button", name="Apply Code", exact=True)
            await apply_btn.click()
            await asyncio.sleep(3)

            logger.info(f"[{self.name}] Referral code applied successfully")

        except Exception as e:
            logger.error(f"[{self.name}] Concrete referral error: {e}", exc_info=True)

    async def _concrete_setup(self):
        """Настройка Concrete: check-in/claim"""
        try:
            # Переходим на profile
            logger.info(f"[{self.name}] Navigating to Concrete profile")
            page = await self.context.new_page()
            await page.goto(
                "https://points.concrete.xyz/profile",
                wait_until="domcontentloaded",
                timeout=30000
            )
            await asyncio.sleep(5)

            # Ищем Check-in или Claim
            checkin_btn = page.get_by_role("button", name="Check-in", exact=True)
            claim_btn = page.get_by_role("button", name="Claim", exact=True)

            found_checkin = False
            try:
                found_checkin = await checkin_btn.is_visible(timeout=3000)
            except Exception:
                pass

            found_claim = False
            try:
                found_claim = await claim_btn.is_visible(timeout=3000)
            except Exception:
                pass

            if found_checkin:
                logger.info(f"[{self.name}] Check-in button found, clicking")
                await checkin_btn.click()
            elif found_claim:
                logger.info(f"[{self.name}] Claim button found, clicking")
                await claim_btn.click()
            else:
                logger.warning(f"[{self.name}] Neither Check-in nor Claim found")

            await page.close()
            logger.info(f"[{self.name}] Concrete setup completed")

        except Exception as e:
            logger.error(f"[{self.name}] Concrete setup error: {e}", exc_info=True)

    async def click_confirm(self, page, depth: int = 0):
        """
        Обрабатывает popup: ищет кнопки и кликает рекурсивно
        page — страница popup (или основная если inline modal)
        """
        logger.info(f"[{self.name}] ====== click_confirm START depth={depth} ======")

        if depth >= 5:
            logger.warning(f"[{self.name}] click_confirm: max popup depth reached (5)")
            return

        logger.info(f"[{self.name}] Step 1: waiting 1 sec before actions")
        await asyncio.sleep(1)

        # Логируем страницу
        try:
            page_url = page.url
            logger.info(f"[{self.name}] Step 2: current page URL = {page_url}")
        except Exception:
            logger.info(f"[{self.name}] Step 2: could not get page URL")

        if depth == 0:
            logger.info(f"[{self.name}] Step 3: depth=0, searching for 'Disable and Continue'")
            disable_btn = page.get_by_role("button", name="Disable and Continue", exact=True)
            found_disable = False
            try:
                found_disable = await disable_btn.is_visible(timeout=3000)
                logger.info(f"[{self.name}] Step 3a: 'Disable and Continue' visible = {found_disable}")
            except Exception as e:
                logger.info(f"[{self.name}] Step 3a: 'Disable and Continue' check error: {e}")

            if found_disable:
                logger.info(f"[{self.name}] Step 4: clicking 'Disable and Continue'")
                await disable_btn.click()
                logger.info(f"[{self.name}] Step 4a: 'Disable and Continue' clicked")
            else:
                logger.info(f"[{self.name}] Step 4: 'Disable and Continue' not found, clicking last button")
                sign_button = page.get_by_role("button").last
                try:
                    btn_text = await sign_button.inner_text(timeout=2000)
                    logger.info(f"[{self.name}] Step 4a: last button text = '{btn_text.strip()}'")
                except Exception:
                    logger.info(f"[{self.name}] Step 4a: last button text = (could not read)")
                await sign_button.click()
                logger.info(f"[{self.name}] Step 4b: last button clicked")
        else:
            logger.info(f"[{self.name}] Step 3: depth={depth}>0, clicking last button")
            sign_button = page.get_by_role("button").last
            try:
                btn_text = await sign_button.inner_text(timeout=2000)
                logger.info(f"[{self.name}] Step 3a: last button text = '{btn_text.strip()}'")
            except Exception:
                logger.info(f"[{self.name}] Step 3a: last button text = (could not read)")
            await sign_button.click()
            logger.info(f"[{self.name}] Step 3b: last button clicked")

        logger.info(f"[{self.name}] Step 5: waiting 2 sec after click")
        await asyncio.sleep(2)

        logger.info(f"[{self.name}] Step 6: trying to catch next page via context.expect_page")
        try:
            async with self.context.expect_page(timeout=5000) as popup_info:
                pass
            next_page = await popup_info.value
            try:
                page_url = next_page.url
                logger.info(f"[{self.name}] Step 6a: new page caught, URL = {page_url}")
            except Exception:
                logger.info(f"[{self.name}] Step 6a: new page caught, URL unknown")
            logger.info(f"[{self.name}] Step 7: recursive call click_confirm(depth={depth + 1})")
            await self.click_confirm(next_page, depth + 1)
        except Exception as e:
            logger.info(f"[{self.name}] Step 6a: no new page caught, exception: {e}")
            logger.info(f"[{self.name}] ====== click_confirm DONE depth={depth}, no more popups ======")

    async def _connect_zerion_with_popup(self, page):
        """
        Обрабатывает подключение Zerion: кликает кнопки и ловит popup
        """
        first_btn_path = "xpath=/html/body/div[4]/div/div/div[2]/div/div/div/div/div[1]/div[2]/div[2]/div/button/div/div/div[2]"
        confirm_btn_path = "xpath=/html/body/div[4]/div/div/div[2]/div/div/div/div/div[2]/div[2]/button[1]/div"

        first_btn = await page.query_selector(first_btn_path)
        confirm_btn = await page.query_selector(confirm_btn_path)

        async def _try_popup(btn, label="button"):
            """Кликает кнопку и пытается поймать popup"""
            logger.info(f"[{self.name}] Clicking {label}")
            await btn.click()
            await asyncio.sleep(2)

            # Пробуем window popup
            try:
                async with page.expect_popup(timeout=5000) as popup_info:
                    pass
                popup = await popup_info.value
                logger.info(f"[{self.name}] Window popup caught after {label}, URL: {popup.url}")
                await self.click_confirm(popup)
                return True
            except Exception:
                logger.info(f"[{self.name}] No window popup after {label}, treating as inline modal")

            # Нет window popup — значит inline modal на этой же странице
            # Ждём появления модалки и ищем кнопки ВНУТРИ неё через locator
            try:
                # Ищем последнюю кнопку внутри dialog через CSS
                dialog_btn = page.locator('div[role="dialog"] button').last
                btn_text = await dialog_btn.inner_text(timeout=5000)
                logger.info(f"[{self.name}] Dialog button found: '{btn_text.strip()}'")
                await dialog_btn.click()
                logger.info(f"[{self.name}] Dialog button clicked")
                return True
            except Exception as e:
                logger.info(f"[{self.name}] No dialog found: {e}")
                # Fallback: ищем на всей странице
                await self.click_confirm(page)
                return True

        if first_btn and confirm_btn:
            logger.info(f"[{self.name}] Both buttons found")
            if await _try_popup(first_btn, "first button"):
                return
            # Popup не сработал — пробуем confirm
            await _try_popup(confirm_btn, "confirm button")

        elif first_btn:
            if not await _try_popup(first_btn, "first button"):
                # Нет popup — ищем confirm
                await asyncio.sleep(2)
                confirm_btn = await page.query_selector(confirm_btn_path)
                if confirm_btn:
                    await _try_popup(confirm_btn, "confirm button")

        elif confirm_btn:
            await _try_popup(confirm_btn, "confirm button")
        else:
            logger.warning(f"[{self.name}] No Zerion buttons found after Connect")

    async def run_project(self, project_class):
        """
        Создаёт экземпляр проекта и вызывает его метод run.

        Если проект требует новый таб (_use_new_tab() == True):
        - Создаёт новый таб
        - Передаёт его в проект
        """
        try:
            # Проверяем нужен ли новый таб
            use_new_tab = getattr(project_class, '_use_new_tab', lambda: False)()

            if use_new_tab:
                logger.info(f"[{self.name}] Creating NEW tab for {project_class.__name__}")
                project_page = await self.context.new_page()
            else:
                project_page = self.page

            project = project_class(self.context, project_page, self.account, self)
            logger.info(f"[{self.name}] Running project: {project.__class__.__name__}")
            await project.run()
            logger.info(f"[{self.name}] Project completed successfully")
        except Exception as e:
            logger.error(f"[{self.name}] Project error: {e}", exc_info=True)
            raise

    async def close(self):
        """Закрывает все ресурсы с таймаутами"""
        async def _close_with_timeout(coro, name, timeout=5):
            try:
                await asyncio.wait_for(coro, timeout=timeout)
                logger.info(f"[{self.name}] {name} closed")
            except asyncio.TimeoutError:
                logger.warning(f"[{self.name}] {name} close timed out after {timeout}s")
            except Exception as e:
                logger.info(f"[{self.name}] {name} close skipped: {e}")

        try:
            if self.page:
                await _close_with_timeout(self.page.close(), "Page")

            if self.context:
                await _close_with_timeout(self.context.close(), "Context")

            if self.browser:
                # Закрываем Chrome через CDP — корректное закрытие
                try:
                    import requests
                    import json as _json
                    import websocket

                    cdp_url = f"http://localhost:{self.debugging_port}"
                    tabs = requests.get(f"{cdp_url}/json", timeout=5).json()
                    if tabs:
                        ws_url = tabs[0].get("webSocketDebuggerUrl", "")
                        if ws_url:
                            ws = websocket.create_connection(ws_url, timeout=5)
                            ws.send(_json.dumps({"id": 1, "method": "Browser.close"}))
                            ws.close()
                            logger.info(f"[{self.name}] Sent Browser.close via CDP")
                except Exception as e:
                    logger.info(f"[{self.name}] CDP Browser.close failed: {e}")

                # Ждём пока Chrome процесс завершится
                if self.chrome_process:
                    try:
                        self.chrome_process.wait(timeout=10)
                        logger.info(f"[{self.name}] Chrome process exited cleanly")
                    except subprocess.TimeoutExpired:
                        logger.warning(f"[{self.name}] Chrome didn't exit after 10s, terminating")
                        self.chrome_process.terminate()
                        self.chrome_process.wait(timeout=5)

            if self.playwright:
                await _close_with_timeout(self.playwright.stop(), "Playwright")

            logger.info(f"[{self.name}] All resources closed")
        except Exception as e:
            logger.error(f"[{self.name}] Error closing browser: {e}", exc_info=True)
