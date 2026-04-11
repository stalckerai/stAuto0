import asyncio
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.accounts import accounts
from Core.browser import BaseBrowser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    # Определяем аккаунт из аргумента или берём первый
    account_name = sys.argv[1] if len(sys.argv) > 1 else None

    if account_name:
        account = next((a for a in accounts if a["name"] == account_name), None)
        if not account:
            logger.error(f"Account '{account_name}' not found")
            sys.exit(1)
    else:
        account = accounts[0]
        logger.info(f"No account specified, using first: {account['name']}")

    logger.info(f"Launching account: {account['name']}")

    browser = BaseBrowser(account)
    try:
        await browser.launch()

        # Переходим на пустую страницу
        await browser.page.goto("about:blank", wait_until="domcontentloaded", timeout=10000)
        logger.info(f"[{account['name']}] Opened about:blank")

        logger.info(f"[{account['name']}] Browser is running and will remain open")
        logger.info(f"[{account['name']}] Debugging port: {browser.debugging_port}")
        logger.info(f"[{account['name']}] Press Ctrl+C to close")

        # Держим процесс живым
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info(f"[{account['name']}] Interrupted by user")
    except Exception as e:
        logger.error(f"[{account['name']}] Fatal error: {e}", exc_info=True)
    finally:
        await browser.close()
        logger.info(f"[{account['name']}] Browser closed")


if __name__ == "__main__":
    asyncio.run(main())
