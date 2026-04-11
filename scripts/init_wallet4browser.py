import asyncio
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.accounts import accounts
from config.auto_sids import accounts as sids
from Core.browser import BaseBrowser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "logs" / "browser.log", encoding="utf-8", mode="a"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

WALLET_URL = "chrome-extension://klghhnkeealcohjjanjjdaeeggmfmlpl/popup.8e8f209b.html?windowType=tab&appMode=onboarding#/onboarding/import/mnemonic"
WAIT = 3
WAIT_IMPORT = 5


async def click_element(page, selector: str, description: str, timeout=15000):
    """Ждёт видимости элемента и кликает"""
    logger.info(f"Waiting for element: {description}")
    element = await page.wait_for_selector(selector, state="visible", timeout=timeout)
    logger.info(f"Clicking: {description}")
    await element.click()
    await asyncio.sleep(WAIT)


async def init_wallet(account: dict, keep_open: bool = False):
    """Инициализация кошелька Zerion для одного аккаунта"""
    name = account["name"]
    sid = sids.get(name)
    password = account.get("wallet_password")

    if not sid:
        logger.error(f"[{name}] No SID found in auto_sids.py")
        return
    if not password:
        logger.error(f"[{name}] No password found in accounts.py")
        return

    words = sid.strip().split()
    logger.info(f"[{name}] Initializing wallet with {len(words)} word mnemonic")

    browser = BaseBrowser(account)
    try:
        await browser.launch()
        await asyncio.sleep(3)  # Ждём 3 сек после подключения к браузеру
        # Открываем новую страницу для chrome-extension
        browser.page = await browser.context.new_page()
        await browser.page.goto(WALLET_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(10)  # Ждём 10 сек после открытия страницы до любых действий
        logger.info(f"[{name}] Wallet page opened")

        # Проверка: если кошелек уже установлен (Session expired)
        session_expired = await browser.page.query_selector('div._uitext_tij8c_1:text("Session expired")')
        if session_expired:
            logger.info(f"[{name}] Wallet already initialized (Session expired page found), skipping")
            await asyncio.sleep(5)  # Ждём 5 сек перед закрытием чтобы JS скрипты отработали
            return

        # 1. Use 24 word phrase
        await click_element(
            browser.page,
            'div._uitext_tij8c_1:text("Use 24 word phrase")',
            "Use 24 word phrase"
        )

        # 2. Заполняем 24 слова
        for i, word in enumerate(words):
            selector = f'input#word-{i}'
            await browser.page.fill(selector, word, timeout=5000)
            logger.info(f"[{name}] Filled word {i+1}/24: {word}")
            await asyncio.sleep(0.3)

        await asyncio.sleep(WAIT)

        # 3. Import wallet
        await click_element(
            browser.page,
            'button.EyUuEa_primary:text("Import wallet")',
            "Import wallet"
        )

        # 4. Ждём 5 сек после импорта
        await asyncio.sleep(WAIT_IMPORT)

        # 5. Continue (2)
        await click_element(
            browser.page,
            'button.EyUuEa_primary:text("Continue (2)")',
            "Continue (2)"
        )

        # 6. Вводим пароль
        await browser.page.fill(
            'input#\\:r0\\:',
            password,
            timeout=5000
        )
        logger.info(f"[{name}] Password entered")
        await asyncio.sleep(WAIT)

        # 7. Confirm Password
        await click_element(
            browser.page,
            'span:text("Confirm Password")',
            "Confirm Password"
        )

        # 8. Proceed Anyway
        await click_element(
            browser.page,
            'a.EyUuEa_regular:text("Proceed Anyway")',
            "Proceed Anyway"
        )

        # 9. Вводим пароль повторно
        await browser.page.fill(
            'input[name="confirmPassword"]',
            password,
            timeout=5000
        )
        logger.info(f"[{name}] Password confirmed")
        await asyncio.sleep(WAIT)

        # 10. Set Password
        await click_element(
            browser.page,
            'button.EyUuEa_primary:text("Set Password")',
            "Set Password"
        )

        logger.info(f"[{name}] Wallet initialization completed successfully")

        if keep_open:
            logger.info(f"[{name}] Browser will remain open for inspection. Press Ctrl+C to close.")
            while True:
                await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"[{name}] Wallet init error: {e}", exc_info=True)
        if keep_open:
            logger.info(f"[{name}] Browser will remain open for inspection. Press Ctrl+C to close.")
            while True:
                await asyncio.sleep(1)
    finally:
        if not keep_open:
            await asyncio.sleep(5)  # Ждём 5 сек чтобы JS скрипты успели отработать
            await browser.close()
            logger.info(f"[{name}] Browser closed")


async def main():
    account_name = sys.argv[1] if len(sys.argv) > 1 else None
    single_mode = account_name is not None

    if account_name:
        account = next((a for a in accounts if a["name"] == account_name), None)
        if not account:
            logger.error(f"Account '{account_name}' not found")
            sys.exit(1)
        await init_wallet(account, keep_open=True)
    else:
        for i, account in enumerate(accounts):
            logger.info(f"Processing account {i+1}/{len(accounts)}: {account['name']}")
            await init_wallet(account, keep_open=False)
            if i < len(accounts) - 1:
                await asyncio.sleep(3)
        logger.info("All accounts processed")


if __name__ == "__main__":
    asyncio.run(main())
