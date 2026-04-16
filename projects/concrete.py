import asyncio
import logging
import os
from pathlib import Path

from projects.base import BaseProject

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / "tmp"


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

    # =============================================================================
    # UNREGULAR TASK: Paragraph article + Concrete URL submission
    # =============================================================================

    async def _login_paragraph(self):
        """
        Логин на Paragraph.com через Zerion Wallet.

        Шаги:
        1. Клик "Continue with a wallet" (Privy модал)
        2. Поиск "Zerion" → клик по <span class="sc-hEkkVl hPdPOi">Zerion</span>
        3. Обработка popup через click_confirm
        4. Reload страницы для обнаружения кошелька Privy
        """
        logger.info(f"[{self.account['name']}] Paragraph login: checking current URL")
        current_url = self.page.url
        need_login = "login=true" in current_url

        if not need_login:
            logger.info(f"[{self.account['name']}] Already logged in")
            return

        # Ждём Privy модал
        logger.info(f"[{self.account['name']}] Waiting for Privy modal")
        await asyncio.sleep(5)

        # Шаг 1: Continue with a wallet
        logger.info(f"[{self.account['name']}] Searching for 'Continue with a wallet'")
        continue_btn = self.page.get_by_text("Continue with a wallet")
        try:
            if await continue_btn.is_visible(timeout=10000):
                await continue_btn.click()
                logger.info(f"[{self.account['name']}] 'Continue with a wallet' clicked")
            else:
                logger.warning(f"[{self.account['name']}] 'Continue with a wallet' not found")
                return
        except Exception as e:
            logger.warning(f"[{self.account['name']}] Click failed: {e}")
            return

        # Ждём появления списка кошельков
        await asyncio.sleep(3)

        # Шаг 2: Поле поиска + ввод "Zerion"
        logger.info(f"[{self.account['name']}] Searching for Zerion in wallet list")
        try:
            search_input = self.page.locator("input[placeholder*='Search through']")
            await search_input.wait_for(state="visible", timeout=10000)
            await search_input.click()
            await search_input.fill("Zerion")
            await asyncio.sleep(3)
            logger.info(f"[{self.account['name']}] 'Zerion' typed in search")
        except Exception as e:
            logger.warning(f"[{self.account['name']}] Search input failed: {e}")
            return

        # Шаг 3: Клик по <span class="sc-hEkkVl hPdPOi">Zerion</span> → popup
        logger.info(f"[{self.account['name']}] Clicking Zerion span with expect_popup")
        try:
            zerion_span = self.page.locator("span.sc-hEkkVl.hPdPOi").first
            if await zerion_span.is_visible(timeout=5000):
                async with self.context.expect_page(timeout=10000) as popup_info:
                    await zerion_span.click()
                popup = await popup_info.value
                logger.info(f"[{self.account['name']}] Zerion popup caught")
                await self.browser.click_confirm(popup)
            else:
                logger.warning(f"[{self.account['name']}] Zerion span not visible")
        except Exception as e:
            logger.warning(f"[{self.account['name']}] Zerion click/popup failed: {e}")
            return

        # Шаг 4: Reload чтобы Privy обнаружил подключённый кошелёк
        await asyncio.sleep(5)
        logger.info(f"[{self.account['name']}] Reloading page so Privy detects wallet...")
        try:
            await self.page.reload(wait_until="load", timeout=30000)
            await asyncio.sleep(5)
            logger.info(f"[{self.account['name']}] Page reloaded: {self.page.url}")
        except Exception as e:
            logger.warning(f"[{self.account['name']}] Reload failed: {e}")

        # Шаг 5: Пост-логин кнопка (если есть)
        try:
            post_login_btn = await self.page.query_selector(
                'xpath=/html/body/div[2]/div/div[1]/div/div[2]/div[3]/button/div'
            )
            if post_login_btn:
                logger.info(f"[{self.account['name']}] Post-login button found, clicking")
                await post_login_btn.click()
                await asyncio.sleep(5)
        except Exception as e:
            logger.info(f"[{self.account['name']}] Post-login button check skipped: {e}")

        logger.info(f"[{self.account['name']}] Paragraph login completed")

    async def _unregular_paragraph_task(self):
        """
        Нерегулярная задача: публикация статьи на Paragraph + отправка URL в Concrete.

        Каждая часть работает в своей НОВОЙ вкладке:
        1. Paragraph tab — логин + публикация
        2. Concrete tab — отправка URL
        """
        logger.info(f"[{self.account['name']}] ===== Starting unregular paragraph task =====")

        # === Создаём НОВУЮ вкладку для Paragraph ===
        paragraph_page = await self.context.new_page()
        logger.info(f"[{self.account['name']}] New tab created for Paragraph")

        # --- Шаг 1: Переход на /home и логин (до 3 попыток) ---
        logger.info(f"[{self.account['name']}] Navigating to paragraph.com/home")
        await paragraph_page.goto(
            "https://paragraph.com/home",
            wait_until="load",
            timeout=60000
        )
        await asyncio.sleep(5)
        logger.info(f"[{self.account['name']}] Page loaded: {paragraph_page.url}")

        # Проверяем нужен ли логин
        async def _check_need_login(page) -> bool:
            try:
                btn = page.get_by_text("Sign in")
                return await btn.is_visible(timeout=3000)
            except Exception:
                return False

        # Логинимся (до 3 попыток)
        login_success = False
        for attempt in range(1, 4):
            need_login = await _check_need_login(paragraph_page)
            if not need_login:
                logger.info(f"[{self.account['name']}] Already logged in")
                login_success = True
                break

            logger.info(f"[{self.account['name']}] Attempt {attempt}/3: 'Sign in' found, logging in...")
            await paragraph_page.goto(
                "https://paragraph.com/?login=true",
                wait_until="load",
                timeout=30000
            )
            await asyncio.sleep(3)

            original_page = self.page
            self.page = paragraph_page
            await self._login_paragraph()
            self.page = original_page
            await asyncio.sleep(5)
            logger.info(f"[{self.account['name']}] After login, URL: {paragraph_page.url}")

            # Возвращаемся на /home
            await paragraph_page.goto(
                "https://paragraph.com/home",
                wait_until="load",
                timeout=30000
            )
            await asyncio.sleep(5)

            # Проверяем результат
            if not await _check_need_login(paragraph_page):
                logger.info(f"[{self.account['name']}] Login successful on attempt {attempt}")
                login_success = True
                break
            else:
                logger.warning(f"[{self.account['name']}] Login attempt {attempt} failed, 'Sign in' still visible")

        if not login_success:
            logger.error(f"[{self.account['name']}] Failed to login after 3 attempts")
            await paragraph_page.close()
            return False

        # --- Шаг 2: Клик по кнопке создания статьи ---
        logger.info(f"[{self.account['name']}] Clicking new article button")
        try:
            new_article_btn = await paragraph_page.query_selector(
                'xpath=/html/body/div[2]/div/div[1]/div/div[2]/div[3]/button'
            )
            if new_article_btn:
                btn_text = await new_article_btn.text_content()
                logger.info(f"[{self.account['name']}] Button text: '{btn_text.strip()}'")
                await new_article_btn.click()
                await asyncio.sleep(8)
                # Проверяем что перешли на редактор
                if "/editor/" in paragraph_page.url:
                    logger.info(f"[{self.account['name']}] Navigated to editor: {paragraph_page.url}")
                else:
                    logger.info(f"[{self.account['name']}] Still on {paragraph_page.url} after click, waiting...")
                    await asyncio.sleep(5)
                    # Фолбэк: ищем ссылку на редактор
                    if "/editor/" not in paragraph_page.url:
                        try:
                            editor_link = paragraph_page.locator("a[href*='/editor/']").first
                            if await editor_link.is_visible(timeout=3000):
                                await editor_link.click()
                                await asyncio.sleep(8)
                        except Exception:
                            pass
            else:
                logger.warning(f"[{self.account['name']}] New article button not found")
        except Exception as e:
            logger.warning(f"[{self.account['name']}] Button click failed: {e}")

        # Ждём загрузки редактора
        await asyncio.sleep(8)

        # Диагностика
        logger.info(f"[{self.account['name']}] Current URL: {paragraph_page.url}")
        has_editor = await paragraph_page.locator("textarea[data-editor-field='title']").count()
        logger.info(f"[{self.account['name']}] Editor textarea found: {has_editor}")

        # --- Шаг 3: Чтение статьи ---
        article_file = TMP_DIR / f"{self.account['name']}.txt"
        if not article_file.exists():
            logger.error(f"[{self.account['name']}] Article file not found: {article_file}")
            await paragraph_page.close()
            return False

        with open(article_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) < 2:
            logger.error(f"[{self.account['name']}] Article file must have at least 2 lines")
            await paragraph_page.close()
            return False

        title = lines[0].strip()
        article_text = "".join(lines[1:]).strip()
        logger.info(f"[{self.account['name']}] Title: {title[:50]}... | Text: {len(article_text)} chars")

        # --- Шаг 4: Вставка заголовка ---
        logger.info(f"[{self.account['name']}] Inserting title")
        try:
            title_textarea = paragraph_page.locator("textarea[data-editor-field='title']")
            await title_textarea.wait_for(state="visible", timeout=15000)
            await title_textarea.click()
            await title_textarea.fill(title)
        except Exception as e:
            logger.error(f"[{self.account['name']}] Title insert failed: {e}")
            await paragraph_page.close()
            return False

        await asyncio.sleep(2)

        # --- Шаг 5: Вставка текста статьи ---
        logger.info(f"[{self.account['name']}] Inserting article text")
        editor_p = await paragraph_page.query_selector('//*[@id="paragraph-tiptap-editor"]/p')
        if editor_p:
            await paragraph_page.click('//*[@id="paragraph-tiptap-editor"]/p')
            await asyncio.sleep(1)
            escaped_text = article_text.replace('\\', '\\\\').replace('`', '\\`').replace('\n', '\\n').replace('\r', '')
            await paragraph_page.evaluate(f"""
                const editor = document.getElementById('paragraph-tiptap-editor');
                if (editor) {{
                    const p = editor.querySelector('p');
                    if (p) {{ p.textContent = `{escaped_text}`; }}
                }}
            """)
        else:
            try:
                editable = paragraph_page.locator('[contenteditable="true"]').first
                await editable.wait_for(state="visible", timeout=10000)
                await editable.click()
                await editable.fill(article_text)
            except Exception as e:
                logger.error(f"[{self.account['name']}] Text insert failed: {e}")
                await paragraph_page.close()
                return False

        await asyncio.sleep(2)

        # --- Шаг 6: Publish ---
        for btn_name in ["Continue", "Publish"]:
            logger.info(f"[{self.account['name']}] Clicking '{btn_name}'")
            btn = paragraph_page.get_by_role("button", name=btn_name)
            try:
                if await btn.is_visible(timeout=10000):
                    await btn.click()
                    await asyncio.sleep(5 if btn_name == "Continue" else 7)
            except Exception:
                logger.warning(f"[{self.account['name']}] '{btn_name}' not found")

        # --- Шаг 7: Копирование URL статьи ---
        article_url = None
        for selector in [
            lambda p: p.query_selector('input[readonly][value*="paragraph"]'),
            lambda p: p.query_selector('input[value*="paragraph.com"]'),
        ]:
            try:
                url_input = await selector(paragraph_page)
                if url_input:
                    article_url = await url_input.get_attribute("value")
                    break
            except Exception:
                pass

        if not article_url:
            article_url = paragraph_page.url
        logger.info(f"[{self.account['name']}] Article URL: {article_url}")

        # Закрываем Paragraph tab
        await paragraph_page.close()

        # === Создаём НОВУЮ вкладку для Concrete submission ===
        concrete_page = await self.context.new_page()
        logger.info(f"[{self.account['name']}] New tab created for Concrete submission")

        # --- Шаг 8: Переход на Concrete ---
        await concrete_page.goto(
            "https://points.concrete.xyz/home",
            wait_until="domcontentloaded",
            timeout=30000
        )
        await asyncio.sleep(3)

        # Логин если нужен
        connect_btn = await concrete_page.query_selector(
            "xpath=/html/body/div[2]/nav/div[1]/div/div[2]/button/span"
        )
        if connect_btn:
            logger.info(f"[{self.account['name']}] Logging in on Concrete")
            await connect_btn.click()
            await self._login()
            await asyncio.sleep(3)
        else:
            logger.info(f"[{self.account['name']}] Already logged in on Concrete")

        # --- Шаг 9: Вставка URL и Submit ---
        try:
            url_input = concrete_page.locator('input[id="url"][type="url"]')
            await url_input.wait_for(state="visible", timeout=10000)
            await url_input.click()
            await url_input.fill(article_url)
        except Exception as e:
            logger.error(f"[{self.account['name']}] URL insert failed: {e}")
            await concrete_page.close()
            return False

        await asyncio.sleep(2)

        submit_btn = concrete_page.get_by_role("button", name="Submit URL")
        try:
            if await submit_btn.is_visible(timeout=10000):
                await submit_btn.click()
        except Exception:
            pass

        # --- Шаг 10: Проверка результата ---
        await asyncio.sleep(5)

        # Ищем Close или любую кнопку подтверждения
        for btn_name in ["Close", "Done", "Success"]:
            btn = concrete_page.get_by_role("button", name=btn_name)
            try:
                if await btn.is_visible(timeout=5000):
                    logger.info(f"[{self.account['name']}] '{btn_name}' found — task completed!")
                    await concrete_page.close()
                    return True
            except Exception:
                pass

        # Фолбэк: проверяем URL не изменился (значит submission прошла)
        logger.info(f"[{self.account['name']}] No confirmation button, checking page state...")
        await asyncio.sleep(3)

        # Ищем любой текст успеха
        success_texts = ["submitted", "success", "completed", "approved"]
        for text in success_texts:
            try:
                if await concrete_page.get_by_text(text, exact=False).is_visible(timeout=2000):
                    logger.info(f"[{self.account['name']}] Success text '{text}' found!")
                    await concrete_page.close()
                    return True
            except Exception:
                pass

        logger.warning(f"[{self.account['name']}] Could not confirm submission")
        await concrete_page.close()
        return False
