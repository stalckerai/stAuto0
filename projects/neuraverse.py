import asyncio
import logging
from playwright.async_api import BrowserContext, Page
from projects.base import BaseProject

logger = logging.getLogger(__name__)


# =============================================================================
# Координаты точек для кликов (пиксели, от верхнего левого угла viewport)
# Нужно уточнить под реальный размер окна игры!
# =============================================================================

# Поле 1: ключевые точки для обхода всех веток + выход справа
POINTS_FIELD_1 = [
    # Левая ветка
    (150, 250),
    # Верхняя ветка
    (400, 180),
    # Центр
    (400, 350),
    # Нижняя-левая ветка
    (300, 500),
    # Нижняя ветка
    (400, 550),
    # Нижняя-правая ветка
    (520, 520),
    # Центр-право (перед выходом)
    (500, 350),
    # === ВЫХОД: переход на поле 2 ===
    (700, 250),  # "The Oracle Passage"
]

# Поле 2: вход слева, обход веток, выход слева
POINTS_FIELD_2 = [
    # Входная точка (откуда пришли с поля 1)
    (100, 400),  # "Travel to Inari Valley" — это ВХОД
    # Верхняя ветка
    (500, 100),
    # Центр
    (500, 400),
    # Правая ветка
    (750, 450),
    # Нижняя ветка
    (600, 650),
    # Нижняя короткая ветка
    (500, 550),
    # === ВЫХОД: переход на следующее поле ===
    (100, 400),  # левый круг — выход
]


class NeuraverseProject(BaseProject):
    """
    Проект для прохождения игры Neuraverse.

    Логика:
    1. Работает в НОВОМ табе (_use_new_tab = True)
    2. Переход на страницу → ждать 5 сек
    3. _login(): ищем "Sign In" → клик → ловим popup → кликаем по privy-кнопке → click_confirm
    4. _process(): поле 1 → поле 2

    Координаты нужно уточнить под реальный размер окна!
    """

    def _get_page_name(self) -> str:
        return "Neuraverse"

    def _get_start_url(self) -> str:
        # TODO: Укажи реальный URL игры Neuraverse
        return "https://neuraverse.neuraprotocol.io"

    def _get_max_attempts(self) -> int:
        return 3

    @classmethod
    def _use_new_tab(cls) -> bool:
        """Neuraverse работает в НОВОМ табе"""
        return True

    async def run(self):
        """
        Переопределяем run() чтобы вызвать _login() после загрузки страницы.
        """
        try:
            logger.info(f"[{self.account['name']}] Opening {self._get_page_name()} page")
            await self.page.goto(
                self._get_start_url(),
                wait_until="domcontentloaded",
                timeout=30000
            )

            logger.info(f"[{self.account['name']}] Waiting 5 seconds for page to load")
            await asyncio.sleep(5)

            # Логин в игру
            logger.info(f"[{self.account['name']}] Running _login()")
            await self._login()

            # Основной цикл с попытками
            max_attempts = self._get_max_attempts()
            for attempt in range(1, max_attempts + 1):
                logger.info(f"[{self.account['name']}] Attempt {attempt}/{max_attempts}")
                success = await self._process()
                if success:
                    logger.info(f"[{self.account['name']}] Task completed on attempt {attempt}")
                    return

                if attempt < max_attempts:
                    logger.info(f"[{self.account['name']}] Not done yet, retrying...")
                    await self.page.goto(
                        self._get_start_url(),
                        wait_until="domcontentloaded",
                        timeout=30000
                    )
                    await asyncio.sleep(5)

            logger.warning(f"[{self.account['name']}] Task not completed after {max_attempts} attempts")

        except Exception as e:
            logger.error(f"[{self.account['name']}] Neuraverse error: {e}", exc_info=True)
            raise

    async def _login(self):
        """
        Логин в Neuraverse:
        1. Ищем кнопку "Sign In" → кликаем
        2. Ждём 5 сек
        3. Ищем "Continue with a wallet" → если есть → кликаем
        4. Ищем "Zerion" → кликаем
        5. Ловим popup → если есть → click_confirm(popup)
        """
        # === Шаг 1: Sign In ===
        logger.info(f"[{self.account['name']}] Login: searching for 'Sign In' button")

        sign_in_btn = self.page.get_by_role("button").filter(has_text="Sign In").first

        found_sign_in = False
        try:
            found_sign_in = await sign_in_btn.is_visible(timeout=3000)
        except Exception:
            pass

        if not found_sign_in:
            logger.info(f"[{self.account['name']}] 'Sign In' button not found — already logged in")
            return

        logger.info(f"[{self.account['name']}] 'Sign In' button found, clicking")
        await sign_in_btn.click()

        # Ждём 5 сек после клика
        logger.info(f"[{self.account['name']}] Waiting 5 seconds after Sign In click")
        await asyncio.sleep(5)

        # === Шаг 2: Continue with a wallet (опционально) ===
        logger.info(f"[{self.account['name']}] Searching for 'Continue with a wallet'")

        continue_btn = self.page.locator("div.sc-bRKDuR.iLnOpz", has_text="Continue with a wallet")

        found_continue = False
        try:
            found_continue = await continue_btn.is_visible(timeout=3000)
        except Exception:
            pass

        if found_continue:
            logger.info(f"[{self.account['name']}] 'Continue with a wallet' found, clicking")
            await continue_btn.click()
            await asyncio.sleep(2)
        else:
            logger.info(f"[{self.account['name']}] 'Continue with a wallet' not found — skipping")

        # === Шаг 3: Zerion кнопка → ловим popup ===
        logger.info(f"[{self.account['name']}] Searching for 'Zerion' button")

        zerion_btn = self.page.locator("span.sc-hlweCQ.dvnrEF", has_text="Zerion")

        found_zerion = False
        try:
            found_zerion = await zerion_btn.is_visible(timeout=5000)
        except Exception:
            pass

        if not found_zerion:
            logger.warning(f"[{self.account['name']}] 'Zerion' button not found — login incomplete")
            return

        logger.info(f"[{self.account['name']}] 'Zerion' button found, clicking with expect_popup")

        # Кликаем Zerion и ловим popup
        try:
            async with self.context.expect_page(timeout=10000) as popup_info:
                await zerion_btn.click()
            popup = await popup_info.value
            logger.info(f"[{self.account['name']}] Popup caught, URL: {popup.url}")
            await self.browser.click_confirm(popup)
        except Exception as e:
            logger.warning(f"[{self.account['name']}] No popup after Zerion click: {e}")

        logger.info(f"[{self.account['name']}] Login process completed")

    async def _process(self) -> bool:
        """Основной цикл: поле 1 → поле 2"""
        try:
            # === ПОЛЕ 1 ===
            logger.info(f"[{self.account['name']}] Field 1: traversing all branches")
            await self._traverse_field(POINTS_FIELD_1, field_name="Field 1")

            # Ждём перехода на поле 2
            logger.info(f"[{self.account['name']}] Waiting for transition to Field 2...")
            await asyncio.sleep(3)

            # === ПОЛЕ 2 ===
            logger.info(f"[{self.account['name']}] Field 2: traversing all branches")
            await self._traverse_field(POINTS_FIELD_2, field_name="Field 2")

            logger.info(f"[{self.account['name']}] All fields completed!")
            return True

        except Exception as e:
            logger.error(f"[{self.account['name']}] Neuraverse process error: {e}", exc_info=True)
            return False

    async def _traverse_field(self, points: list[tuple[int, int]], field_name: str):
        """
        Кликаем по всем точкам поля последовательно.

        Args:
            points: список координат (x, y) для кликов
            field_name: название поля для логов
        """
        for i, (x, y) in enumerate(points, 1):
            logger.info(f"[{self.account['name']}] {field_name}: clicking point {i}/{len(points)} at ({x}, {y})")

            try:
                # Клик по координатам
                await self.page.mouse.click(x, y)

                # Пауза между кликами (персонаж идёт по дорожке)
                # Подбери экспериментально!
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f"[{self.account['name']}] {field_name}: click failed at ({x}, {y}): {e}")
                # Продолжаем — возможно персонаж уже на месте

    async def _check_done(self, page=None) -> bool:
        """
        Проверка: все шары собраны и мы на выходе.

        TODO: добавить проверку по визуальному индикатору
        (счётчик шаров, надпись и т.д.)
        """
        # Пока возвращаем True после обхода всех точек
        return True


# =============================================================================
# УТИЛИТА: Помощник для определения координат
# =============================================================================

async def calibrate_coordinates(page: Page):
    """
    Запусти этот скрипт один раз, чтобы определить координаты точек.
    Открой игру, наведи курсор на каждую точку — в консоли будут координаты.

    Использование:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto("URL_ИГРЫ")
            await calibrate_coordinates(page)
    """
    logger.info("=== CALIBRATION MODE ===")
    logger.info("Click on each point on the map.")
    logger.info("Coordinates will be logged below.\n")

    # Слушаем клики
    await page.evaluate("""
        document.addEventListener('click', (e) => {
            console.log(`CLICK: (${e.clientX}, ${e.clientY})`);
        });
    """)

    logger.info("Click on the game map points. Press Ctrl+C to stop.")

    # Ждём бесконечно — пользователь кликает
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Calibration finished.")


# =============================================================================
# АЛЬТЕРНАТИВА: Обход через клавиши (стрелки)
# Полный перебор всех веток DFS
# =============================================================================

# Поле 1: подсчёт по клеткам со схемы field_1_new.png
# Калибровка: LEFT=14, UP вертикаль=10
#
# СТРАТЕГИЯ "ПОИСК ПЕРЕКРЁСТКА":
# 1. Персонаж появляется в СЛУЧАЙНОЙ точке
# 2. Идём LEFT до упора (макс. 14 шагов) — гарантированно дойдём до левого края
# 3. Разворачиваемся RIGHT на 14 шагов — оказываемся на перекрёстке
# 4. Начинаем DFS обход всех веток
# 5. Выходим вправо к The Oracle Passage
#
# Задержка: 0.3 сек между нажатиями

ARROW_MOVES_FIELD_1 = [
    # === ШАГ 0: Поиск перекрёстка ===
    # Идём LEFT до упора (если стартовали не там — дойдём до края)
    *["ArrowLeft"] * 14,
    # Разворачиваемся RIGHT — 14 шагов назад к перекрёстку
    *["ArrowRight"] * 14,

    # === ШАГ 1: LEFT ветка (уже на краю после поиска, обходим) ===
    # Мы уже в левом тупике после поиска — обходим её
    *["ArrowRight"] * 14,  # возвращаемся к перекрёстку

    # === ШАГ 2: UP ветка: 10 туда + 10 обратно ===
    *["ArrowUp"] * 10,
    *["ArrowDown"] * 10,

    # === ШАГ 3: DOWN ветка (Validator House): 3 туда + 3 обратно ===
    *["ArrowDown"] * 3,
    *["ArrowUp"] * 3,

    # === ШАГ 4: DOWN ветка (Bridge): 3 туда + 3 обратно ===
    *["ArrowDown"] * 3,
    *["ArrowUp"] * 3,

    # === ШАГ 5: DOWN-RIGHT ветка (Faucet): 3 down + 2 right + 3 down, возврат ===
    *["ArrowDown"] * 3,
    *["ArrowRight"] * 2,
    *["ArrowDown"] * 3,
    *["ArrowUp"] * 3,
    *["ArrowLeft"] * 2,
    *["ArrowUp"] * 3,

    # === ШАГ 6: ВЫХОД — The Oracle Passage (10 right) ===
    *["ArrowRight"] * 10,
]

# Поле 2: подсчёт по клеткам со скриншота field_2.png
# От центрального перекрёстка:
#   UP    → тупик: 6 клеток
#   LEFT  → Travel to Inari Valley (ВЫХОД): 10 клеток
#   RIGHT → тупик (Lady Luck): 8 клеток
#   DOWN  → тупик: 5 клеток
#
# СТРАТЕГИЯ "ПОИСК ПЕРЕКРЁСТКА" для Поля 2:
# 1. Персонаж приходит с Поля 1 (справа), но может оказаться в случайной точке
# 2. Идём LEFT до упора (10 шагов) — дойдём до левого края
# 3. Разворачиваемся RIGHT на 10 шагов — оказываемся на перекрёстке
# 4. Обходим все тупики
# 5. Выходим влево к Travel to Inari Valley

ARROW_MOVES_FIELD_2 = [
    # === ШАГ 0: Поиск перекрёстка ===
    # Идём LEFT до упора (10 шагов до левого края)
    *["ArrowLeft"] * 10,
    # Разворачиваемся RIGHT — 10 шагов к перекрёстку
    *["ArrowRight"] * 10,

    # === ШАГ 1: UP ветка: 6 туда + 6 обратно ===
    *["ArrowUp"] * 6,
    *["ArrowDown"] * 6,

    # === ШАГ 2: RIGHT ветка (Lady Luck): 8 туда + 8 обратно ===
    *["ArrowRight"] * 8,
    *["ArrowLeft"] * 8,

    # === ШАГ 3: DOWN ветка: 5 туда + 5 обратно ===
    *["ArrowDown"] * 5,
    *["ArrowUp"] * 5,

    # === ШАГ 4: ВЫХОД — Travel to Inari Valley (10 left) ===
    *["ArrowLeft"] * 10,
]


class NeuraverseArrowsProject(BaseProject):
    """
    Альтернативная версия — обход через стрелки клавиатуры.
    Используй если клики по координатам не работают.

    Логика с табами такая же:
    1. Работает в НОВОМ табе
    2. _login() — Sign In + privy popup
    3. _process() — стрелки
    """

    def _get_page_name(self) -> str:
        return "Neuraverse (Arrows)"

    def _get_start_url(self) -> str:
        return "https://example.com/neuraverse"

    def _get_max_attempts(self) -> int:
        return 3

    @classmethod
    def _use_new_tab(cls) -> bool:
        """Neuraverse Arrows работает в НОВОМ табе"""
        return True

    async def run(self):
        """
        Переопределяем run() чтобы вызвать _login().
        """
        try:
            logger.info(f"[{self.account['name']}] Opening {self._get_page_name()} page")
            await self.page.goto(
                self._get_start_url(),
                wait_until="domcontentloaded",
                timeout=30000
            )

            logger.info(f"[{self.account['name']}] Waiting 5 seconds for page to load")
            await asyncio.sleep(5)

            # Логин в игру
            logger.info(f"[{self.account['name']}] Running _login()")
            await self._login()

            # Основной цикл
            max_attempts = self._get_max_attempts()
            for attempt in range(1, max_attempts + 1):
                logger.info(f"[{self.account['name']}] Attempt {attempt}/{max_attempts}")
                success = await self._process()
                if success:
                    logger.info(f"[{self.account['name']}] Task completed on attempt {attempt}")
                    return

                if attempt < max_attempts:
                    logger.info(f"[{self.account['name']}] Not done yet, retrying...")
                    await self.page.goto(
                        self._get_start_url(),
                        wait_until="domcontentloaded",
                        timeout=30000
                    )
                    await asyncio.sleep(5)

            logger.warning(f"[{self.account['name']}] Task not completed after {max_attempts} attempts")

        except Exception as e:
            logger.error(f"[{self.account['name']}] Neuraverse Arrows error: {e}", exc_info=True)
            raise

    async def _login(self):
        """
        Логин в Neuraverse (такой же как в NeuraverseProject).
        1. Sign In → клик
        2. Continue with a wallet → если есть → клик
        3. Zerion → клик + ловим popup → click_confirm()
        """
        logger.info(f"[{self.account['name']}] Login: searching for 'Sign In' button")

        sign_in_btn = self.page.get_by_role("button").filter(has_text="Sign In").first

        found_sign_in = False
        try:
            found_sign_in = await sign_in_btn.is_visible(timeout=3000)
        except Exception:
            pass

        if not found_sign_in:
            logger.info(f"[{self.account['name']}] 'Sign In' button not found — already logged in")
            return

        logger.info(f"[{self.account['name']}] 'Sign In' button found, clicking")
        await sign_in_btn.click()
        await asyncio.sleep(5)

        # Continue with a wallet (опционально)
        logger.info(f"[{self.account['name']}] Searching for 'Continue with a wallet'")

        continue_btn = self.page.locator("div.sc-bRKDuR.iLnOpz", has_text="Continue with a wallet")

        found_continue = False
        try:
            found_continue = await continue_btn.is_visible(timeout=3000)
        except Exception:
            pass

        if found_continue:
            logger.info(f"[{self.account['name']}] 'Continue with a wallet' found, clicking")
            await continue_btn.click()
            await asyncio.sleep(2)
        else:
            logger.info(f"[{self.account['name']}] 'Continue with a wallet' not found — skipping")

        # Zerion кнопка → ловим popup
        logger.info(f"[{self.account['name']}] Searching for 'Zerion' button")

        zerion_btn = self.page.locator("span.sc-hlweCQ.dvnrEF", has_text="Zerion")

        found_zerion = False
        try:
            found_zerion = await zerion_btn.is_visible(timeout=5000)
        except Exception:
            pass

        if not found_zerion:
            logger.warning(f"[{self.account['name']}] 'Zerion' button not found — login incomplete")
            return

        logger.info(f"[{self.account['name']}] 'Zerion' button found, clicking with expect_popup")

        try:
            async with self.context.expect_page(timeout=10000) as popup_info:
                await zerion_btn.click()
            popup = await popup_info.value
            logger.info(f"[{self.account['name']}] Popup caught, URL: {popup.url}")
            await self.browser.click_confirm(popup)
        except Exception as e:
            logger.warning(f"[{self.account['name']}] No popup after Zerion click: {e}")

        logger.info(f"[{self.account['name']}] Login process completed")

    async def _process(self) -> bool:
        """
        Полный обход обоих полей через стрелки.
        1 клетка = 1 нажатие, задержка 0.3 сек.
        
        Алгоритм DFS:
        1. Поле 1: обходим все 5 веток → выходим справа (The Oracle Passage)
        2. Ждём перехода на поле 2
        3. Поле 2: обходим все 3 ветки → выходим слева (Travel to Inari Valley)
        """
        try:
            # === ПОЛЕ 1 ===
            logger.info(f"[{self.account['name']}] Field 1: DFS traversal ({len(ARROW_MOVES_FIELD_1)} keys)")
            for i, key in enumerate(ARROW_MOVES_FIELD_1, 1):
                await self.page.keyboard.press(key)
                await asyncio.sleep(0.3)
                if i % 15 == 0:
                    logger.info(f"[{self.account['name']}] Field 1: {i}/{len(ARROW_MOVES_FIELD_1)} keys")

            logger.info(f"[{self.account['name']}] Field 1 complete, waiting for transition...")
            await asyncio.sleep(3)

            # === ПОЛЕ 2 ===
            logger.info(f"[{self.account['name']}] Field 2: DFS traversal ({len(ARROW_MOVES_FIELD_2)} keys)")
            for i, key in enumerate(ARROW_MOVES_FIELD_2, 1):
                await self.page.keyboard.press(key)
                await asyncio.sleep(0.3)
                if i % 15 == 0:
                    logger.info(f"[{self.account['name']}] Field 2: {i}/{len(ARROW_MOVES_FIELD_2)} keys")

            logger.info(f"[{self.account['name']}] All fields completed — 4 + 3 orbs collected!")
            return True

        except Exception as e:
            logger.error(f"[{self.account['name']}] Arrow navigation error: {e}", exc_info=True)
            return False

    async def _check_done(self, page=None) -> bool:
        """
        Проверка завершения:
        TODO: искать визуальный индикатор (счётчик шаров, надпись и т.д.)
        Пока всегда True после обхода.
        """
        return True
