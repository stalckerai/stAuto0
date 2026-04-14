import asyncio
import logging

from projects.base import BaseProject

logger = logging.getLogger(__name__)


class ConcreteProject(BaseProject):
    # --- Override virtual methods ---

    def _get_page_name(self) -> str:
        return "Concrete points"

    @classmethod
    def _use_new_tab(cls) -> bool:
        """Concrete работает в НОВОМ табе"""
        return True

    def _get_start_url(self) -> str:
        return "https://points.concrete.xyz/profile"

    def _get_max_attempts(self) -> int:
        return 3

    async def _check_done(self, page=None) -> bool:
        """Проверяет, выполнена ли задача (найдена одна из кнопок завершения)"""
        p = page or self.page
        buttons = [
            ("Back to your progress", p.get_by_role("button", name="Back to your progress", exact=True)),
            ("Claimed", p.get_by_role("button", name="Claimed", exact=True)),
            ("Checked-in", p.get_by_role("button", name="Checked-in", exact=True)),
        ]

        for name, btn in buttons:
            try:
                if await btn.is_visible(timeout=2000):
                    logger.info(f"[{self.account['name']}] Found '{name}' — task already done")
                    return True
            except Exception:
                pass
        return False

    async def _login(self):
        """Логин в Concrete — выбор Zerion"""
        logger.info(f"[{self.account['name']}] Login: searching for Zerion button")

        zerion_btn_selector = "xpath=/html/body/div[4]/div/div/div[2]/div/div/div/div/div[1]/div[2]/div[2]/div/button/div/div/div[2]"
        zerion_btn = await self.page.query_selector(zerion_btn_selector)

        if zerion_btn:
            logger.info(f"[{self.account['name']}] Zerion button found, clicking with expect_popup")
            await asyncio.sleep(1)

            try:
                async with self.context.expect_page(timeout=5000) as popup_info:
                    await zerion_btn.click()
                popup = await popup_info.value
                logger.info(f"[{self.account['name']}] Popup caught via context.expect_page, URL: {popup.url}")
                await self.browser.click_confirm(popup)
            except Exception as e:
                logger.warning(f"[{self.account['name']}] No popup after Zerion click: {e}")
        else:
            logger.info(f"[{self.account['name']}] Zerion button not found, skipping to confirm button")

        # Ищем кнопку confirm и обрабатываем через popup
        await asyncio.sleep(3)
        confirm_btn_selector = "xpath=/html/body/div[4]/div/div/div[2]/div/div/div/div/div[2]/div[2]/button[1]/div"
        confirm_btn = await self.page.query_selector(confirm_btn_selector)

        if confirm_btn:
            logger.info(f"[{self.account['name']}] Confirm button found after Zerion, clicking with expect_popup")
            try:
                async with self.context.expect_page(timeout=5000) as popup_info:
                    await confirm_btn.click()
                popup = await popup_info.value
                logger.info(f"[{self.account['name']}] Confirm popup caught, URL: {popup.url}")
                await self.browser.click_confirm(popup)
            except Exception as e:
                logger.warning(f"[{self.account['name']}] No popup after confirm click: {e}")
        else:
            logger.info(f"[{self.account['name']}] Confirm button not found after Zerion")

    async def _setup_referral(self):
        """
        Переход на leaderboard и ввод реферального кода.

        НЕ вызывается автоматически — предназначена для ручного вызова.
        """
        # Шаг 2: Переход на leaderboard и ввод реферального кода
        logger.info(f"[{self.account['name']}] Navigating to leaderboard")
        await self.page.goto(
            "https://points.concrete.xyz/leaderboard",
            wait_until="domcontentloaded",
            timeout=30000
        )
        await asyncio.sleep(5)

        # Вводим реферальный код
        logger.info(f"[{self.account['name']}] Entering referral code")
        referral_input = self.page.get_by_placeholder("Enter referral code")
        try:
            await referral_input.wait_for(state="visible", timeout=10000)
            await referral_input.fill("42e0ff07", timeout=5000)
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"[{self.account['name']}] Referral code input not found: {e}")

        # Нажимаем Apply Code
        logger.info(f"[{self.account['name']}] Clicking Apply Code")
        apply_btn = self.page.get_by_role("button", name="Apply Code", exact=True)
        try:
            await apply_btn.wait_for(state="visible", timeout=10000)
            await apply_btn.click()
            await asyncio.sleep(5)
        except Exception as e:
            logger.warning(f"[{self.account['name']}] Apply Code button not found: {e}")

    async def _process(self) -> bool:
        """Одна попытка выполнения задачи. Возвращает True если всё ок."""
        # Шаг 1: Проверяем наличие кнопки Connect
        connect_btn_selector = "xpath=/html/body/div[2]/nav/div[1]/div/div[2]/button/span"
        connect_btn = await self.page.query_selector(connect_btn_selector)

        if connect_btn:
            logger.info(f"[{self.account['name']}] Connect button found — need to login")
            await connect_btn.click()
            await self._login()
        else:
            logger.info(f"[{self.account['name']}] Connect button not found — already logged in")

        # Проверяем — может уже всё выполнено
        if await self._check_done():
            logger.info(f"[{self.account['name']}] Task already completed, skipping")
            return True

        # === referral code отключён, код сохранён в _setup_referral() ===

        # Шаг 3: Переход на profile
        logger.info(f"[{self.account['name']}] Navigating to profile")
        await self.page.goto(
            "https://points.concrete.xyz/profile",
            wait_until="domcontentloaded",
            timeout=30000
        )
        await asyncio.sleep(5)

        # Шаг 4: Ищем Claim или Check-in
        claim_btn = self.page.get_by_role("button", name="Claim", exact=True)
        checkin_btn = self.page.get_by_role("button", name="Check-in", exact=True)

        found_claim = False
        found_checkin = False

        try:
            found_claim = await claim_btn.is_visible(timeout=3000)
        except Exception:
            pass

        try:
            found_checkin = await checkin_btn.is_visible(timeout=3000)
        except Exception:
            pass

        if found_checkin:
            logger.info(f"[{self.account['name']}] Check-in button found, clicking")
            await checkin_btn.click()
        elif found_claim:
            logger.info(f"[{self.account['name']}] Claim button found, clicking")
            await claim_btn.click()
        else:
            logger.warning(f"[{self.account['name']}] Neither Check-in nor Claim found")

        await asyncio.sleep(5)

        # Шаг 5: Проверяем выполнение
        if await self._check_done():
            logger.info(f"[{self.account['name']}] Task completed successfully")
            return True
        else:
            logger.warning(f"[{self.account['name']}] Task may not be completed")
            return False
