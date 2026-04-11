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
        await browser.launch()
        await browser.run_project(TestProject)
    except Exception as e:
        logger.error(f"[{account['name']}] Fatal error: {e}", exc_info=True)
    finally:
        await browser.close()


async def main():
    active_accounts = [a for a in accounts if a.get("status") == "active"]
    logger.info(f"Found {len(active_accounts)} active accounts")
    
    for i, account in enumerate(active_accounts):
        logger.info(f"Starting account {i+1}/{len(active_accounts)}: {account['name']}")
        await run_account(account)
        
        # Задержка между профилями для стабильности
        if i < len(active_accounts) - 1:
            logger.info(f"Waiting 3 seconds before next profile...")
            await asyncio.sleep(3)
    
    logger.info("All accounts processed successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
