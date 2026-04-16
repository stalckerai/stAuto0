import asyncio
import sys
import logging
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config.accounts import accounts
from config.active_projects import get_active_project_classes, get_all_project_names
from Core.browser import BaseBrowser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def kill_chrome_processes():
    """Убивает все зависшие процессы Chrome и Playwright"""
    import time
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "chrome.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "node.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
    time.sleep(1)


async def run_account(account: dict, login_wallet: bool = False):
    """
    Запускает браузер для аккаунта и последовательно выполняет все active проекты.
    
    Логика:
    1. Запуск Chrome + CDP подключение
    2. Логин в Zerion (если нужно) — НОВЫЙ таб
    3. Поочерёдно запускает каждый active проект — каждый в НОВОМ табе
    4. После завершения всех проектов браузер закрывается
    """
    browser = BaseBrowser(account)
    try:
        await browser.launch()

        if login_wallet:
            await browser.login_zerion()

        # Получаем список активных проектов
        active_projects = get_active_project_classes()

        if not active_projects:
            logger.warning(f"[{account['name']}] No active projects to run")
            return

        logger.info(f"[{account['name']}] Found {len(active_projects)} active project(s): {[name for name, _ in active_projects]}")

        # Запускаем каждый проект последовательно
        for project_name, project_class in active_projects:
            logger.info(f"[{account['name']}] ===== Running project: {project_name} =====")
            await browser.run_project(project_class)
            logger.info(f"[{account['name']}] ===== Project {project_name} finished =====")
            await asyncio.sleep(1)  # Пауза между проектами

    except Exception as e:
        logger.error(f"[{account['name']}] Fatal error: {e}", exc_info=True)
    finally:
        await browser.close()


async def run_unregular_paragraph(account: dict):
    """
    Запуск нерегулярной задачи: публикация статьи на Paragraph + отправка в Concrete.
    """
    from projects.concrete import ConcreteProject

    browser = BaseBrowser(account)
    try:
        await browser.launch()

        # Логин в Zerion для Concrete
        await browser.login_zerion()

        # Запускаем Concrete проект с нерегулярной задачей
        project = ConcreteProject(browser.context, browser.page, account, browser)

        # Выполняем нерегулярную задачу
        logger.info(f"[{account['name']}] ===== Running UNREGULAR paragraph task =====")
        success = await project._unregular_paragraph_task()

        if success:
            logger.info(f"[{account['name']}] Unregular task completed successfully")
        else:
            logger.warning(f"[{account['name']}] Unregular task may have failed")

    except Exception as e:
        logger.error(f"[{account['name']}] Unregular task error: {e}", exc_info=True)
    finally:
        await browser.close()


async def main():
    # Проверяем аргументы
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Тестовый режим — запускаем все аккаунты с TestProject
        from projects.test import TestProject
        active_accounts = [a for a in accounts if a.get("status") == "active"]
        logger.info(f"TEST MODE: Found {len(active_accounts)} active accounts")

        for i, account in enumerate(active_accounts):
            kill_chrome_processes()
            logger.info(f"Starting account {i+1}/{len(active_accounts)}: {account['name']}")
            login_wallet = (i == 0)
            await run_account(account, login_wallet)
            if i < len(active_accounts) - 1:
                await asyncio.sleep(3)
        return

    # Нерегулярная задача: Paragraph article + Concrete submission
    if len(sys.argv) > 1 and sys.argv[1] == "paragraph":
        account_name = sys.argv[2] if len(sys.argv) > 2 else None

        if account_name:
            # Один аккаунт
            kill_chrome_processes()
            account = next((a for a in accounts if a["name"] == account_name), None)
            if not account:
                logger.error(f"Account '{account_name}' not found")
                sys.exit(1)
            logger.info(f"Running unregular paragraph task for: {account['name']}")
            await run_unregular_paragraph(account)
        else:
            # Все аккаунты
            active_accounts = [a for a in accounts if a.get("status") == "active"]
            logger.info(f"Running unregular paragraph task for {len(active_accounts)} accounts")

            for i, account in enumerate(active_accounts):
                kill_chrome_processes()
                logger.info(f"Account {i+1}/{len(active_accounts)}: {account['name']}")
                await run_unregular_paragraph(account)
                if i < len(active_accounts) - 1:
                    await asyncio.sleep(3)
        return

    # Обычный режим — один или все аккаунты
    account_name = sys.argv[1] if len(sys.argv) > 1 else None

    # Показываем список активных проектов
    all_projects = get_all_project_names()
    logger.info(f"Available projects: {all_projects}")

    if account_name:
        kill_chrome_processes()
        account = next((a for a in accounts if a["name"] == account_name), None)
        if not account:
            logger.error(f"Account '{account_name}' not found")
            sys.exit(1)
        logger.info(f"Running active projects for: {account['name']}")
        await run_account(account, login_wallet=True)
    else:
        active_accounts = [a for a in accounts if a.get("status") == "active"]
        logger.info(f"Found {len(active_accounts)} active accounts")

        for i, account in enumerate(active_accounts):
            kill_chrome_processes()
            logger.info(f"Starting account {i+1}/{len(active_accounts)}: {account['name']}")
            await run_account(account, login_wallet=True)
            if i < len(active_accounts) - 1:
                await asyncio.sleep(3)

    logger.info("All accounts processed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
