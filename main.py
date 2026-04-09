import asyncio
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config.accounts import accounts
from Core.browser import BaseBrowser
from projects.test import TestProject

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def run_account(account: dict):
    browser = BaseBrowser(account)
    try:
        browser.launch_chrome()
        await browser.connect()
        await browser.run_project(TestProject)
    except Exception as e:
        logger.error(f"[{account['name']}] Fatal error: {e}")
    finally:
        await browser.close()


async def main():
    active_accounts = [a for a in accounts if a.get("status") == "active"]
    for account in active_accounts:
        await run_account(account)


if __name__ == "__main__":
    asyncio.run(main())
