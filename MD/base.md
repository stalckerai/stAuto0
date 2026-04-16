# stAuto0 — Автоматизация браузерных аккаунтов

## Описание

Фреймворк для автоматизации работы с множеством профилей Google Chrome через Playwright. Каждый профиль — изолированный аккаунт с собственным user-data-dir, отладочным портом и набором данных (кошельки, email и т.д.).

## Архитектура

```
stAuto0/
├── Core/
│   ├── __init__.py
│   └── browser.py          # Базовый класс BaseBrowser
├── projects/
│   ├── __init__.py
│   ├── base.py             # Базовый класс BaseProject
│   ├── test.py             # Тестовый проект
│   └── concrete.py         # Проект Concrete (реферальный код + check-in)
├── scripts/
│   ├── create_wallets.py   # Генерация аккаунтов, мнемоник, адресов
│   ├── run_account.py      # Запуск одного аккаунта с пустой страницей
│   ├── init_wallet4browser.py  # Инициализация Zerion Wallet
│   └── proxy_checker.py    # Проверка прокси из списка
├── config/
│   ├── __init__.py
│   ├── accounts.py         # Конфигурация аккаунтов (генерируется)
│   ├── auto_sids.py        # Сид-фразы (генерируется)
│   ├── proxy.txt           # Список прокси для проверки
│   ├── proxy.py            # Рабочие прокси (генерируется)
│   └── chrome_accounts/    # Профили Chrome (user-data-dir)
│       └── auto_001/
│       └── auto_002/
│       └── ...
├── logs/
│   └── browser.log         # Логи выполнения
└── main.py                 # Точка входа — массовый запуск проектов
```

---

## Core — BaseBrowser

**Файл:** `Core/browser.py`

Базовый класс для управления жизненным циклом Chrome-профиля.

### Принцип работы

1. **`launch_chrome(extensions=None)`** — запуск Chrome через `subprocess.Popen`
   - Флаги: `--remote-debugging-port`, `--user-data-dir`, `--no-first-run`, `--disable-session-crashed-bubble`, `--disable-features=SessionCrashedBubble,Translate`
   - Опционально: `--load-extension` для загрузки распакованных расширений
   - Ожидание запуска: 5 секунд
   - Перед запуском: сброс `Local State.exited_cleanly`, `Preferences.session.exit_type`, удаление `Last Session/Last Tabs` (чтобы Chrome не показывал диалог восстановления)

2. **`connect()`** — подключение через Playwright CDP
   - `playwright.chromium.connect_over_cdp("http://localhost:{port}")`
   - Берёт существующий контекст или создаёт новый
   - Получает первую доступную страницу
   - Вызывает `page.bring_to_front()` для вывода окна Chrome на передний план

3. **`launch(extensions=None)`** — обёртка: `launch_chrome()` + `connect()`

4. **`login_zerion(password=None)`** — логин в Zerion Wallet (вызывается для каждого аккаунта)
   - Открывает страницу логина расширения
   - Вводит пароль из конфига аккаунта
   - Нажимает «Unlock»
   - Ждёт 7 сек, закрывает страницу

5. **`click_confirm(page, depth=0)`** — обработка popup'ов кошелька
   - Кликает на переданную страницу (popup)
   - Ищет «Disable and Continue» → если нет → последняя кнопка
   - Ловит следующий popup через `context.expect_page()`
   - Рекурсивно обрабатывает цепочку (макс. глубина 5)

6. **`run_project(project_class)`** — создание проекта и вызов `run()`
   - Передаёт: `context`, `page`, `account`, `self` (browser)

7. **`close()`** — закрытие с таймаутами:
   - Каждое закрытие обёрнуто в `asyncio.wait_for(timeout=5)`
   - Порядок: page → context → browser → playwright → Chrome process
   - После `browser.close()`: ожидание завершения chrome_process (10 сек) → terminate если завис
   - При таймауте — предупреждение в лог и продолжение

---

## Защита от зависаний (main.py)

### `kill_chrome_processes()`

Перед запуском каждого аккаунта:
- `taskkill /F /IM chrome.exe` — убивает все Chrome процессы
- `taskkill /F /IM node.exe` — убивает Playwright драйвер
- `time.sleep(1)` — ожидание

Это предотвращает зависание из-за фоновых процессов предыдущего аккаунта.

### Корректное закрытие Chrome

Чтобы Chrome не показывал диалог «Восстановить страницы?»:
- `Local State.exited_cleanly = True` — сброс перед запуском
- `Preferences.session.exit_type = "Normal"` — сброс перед запуском
- Удаление `Last Session`, `Last Tabs` — файлы сессий
- При закрытии: `browser.close()` через CDP → ожидание процесса → terminate только если завис

---

## Работа с popup'ами кошелька

Для взаимодействия с Zerion Wallet (и другими расширениями) используется два механизма:

### 1. `context.expect_page()` — ловля нового окна/таба

Используется когда клик по кнопке открывает новую страницу (popup расширения):

```python
async with self.context.expect_page(timeout=5000) as popup_info:
    await button.click()
popup = await popup_info.value
# popup — это объект Page, можно работать как с обычной страницей
```

### 2. `click_confirm(popup_page, depth=0)` — цепочка popup'ов

Рекурсивная функция для обработки последовательности popup'ов:

```python
# depth == 0: ищет "Disable and Continue" → если нет → .get_by_role("button").last
# depth > 0: всегда .get_by_role("button").last
# После клика пытается поймать следующий popup через context.expect_page()
await browser.click_confirm(popup_page)
```

### Пример полного флоу подключения Zerion:

```python
# 1. Клик по Zerion → ловим popup
async with self.context.expect_page(timeout=5000) as popup_info:
    await zerion_btn.click()
popup = await popup_info.value

# 2. Обрабатываем popup (кнопка "Connect" или другая)
await browser.click_confirm(popup)

# 3. Если есть confirm-кнопка — тоже через popup
async with self.context.expect_page(timeout=5000) as popup_info:
    await confirm_btn.click()
confirm_popup = await popup_info.value
await browser.click_confirm(confirm_popup)
```

---

## Projects

### BaseProject

**Файл:** `projects/base.py`

Базовый класс для всех проектов.

**Атрибуты:** `context`, `page`, `account`, `browser`

**`run()`** — общий цикл:
1. Открытие `_get_start_url()` → 5 сек
2. Цикл до `_get_max_attempts()`: вызов `_process()` → при неудаче перезагрузка страницы
3. Логирование результата

**Виртуальные методы для переопределения:**

| Метод | Описание | Default |
|---|---|---|
| `_get_page_name()` | Название проекта для логов | `"project"` |
| `_get_start_url()` | Стартовая страница | `"about:blank"` |
| `_get_max_attempts()` | Кол-во попыток | `3` |
| `_use_new_tab()` | Если `True` — проект в НОВОМ табе | `True` |
| `_check_done()` | Проверка выполнения задачи | `False` |
| `_login()` | Логин/подключение кошелька | `pass` |
| `_process() -> bool` | Основная логика. `True` = успех | `True` |

### Работа с табами

Каждый проект может работать в **существующем** или **новом** табе:

```python
class MyProject(BaseProject):
    @classmethod
    def _use_new_tab(cls) -> bool:
        return True  # Новый таб для этого проекта

class OtherProject(BaseProject):
    @classmethod
    def _use_new_tab(cls) -> bool:
        return False  # Использует существующий таб (по умолчанию)
```

**Логика `run_project()` в `BaseBrowser`:**
- Вызывает `project_class._use_new_tab()`
- Если `True` → `context.new_page()` → передаёт в проект
- Если `False` → использует `self.page`

### Создание нового проекта

```python
from projects.base import BaseProject

class MyProject(BaseProject):
    def _get_page_name(self) -> str:
        return "My Project"

    def _get_start_url(self) -> str:
        return "https://example.com"

    async def _process(self) -> bool:
        # Основная логика
        return True
```

### TestProject

**Файл:** `projects/test.py`

Тестовый проект — открывает `httpbin.org/get`, ждёт 5 сек.

---

## Скрипты

### `main.py` — Массовый запуск проектов

Запускает все аккаунты последовательно. **Для каждого аккаунта:**
1. Kill Chrome процессов (`taskkill`)
2. Запуск Chrome + CDP подключение
3. `login_zerion()` — ввод пароля в Zerion Wallet (НОВЫЙ таб)
4. Запуск **всех active проектов** из `config/active_projects.py`
   - Каждый active проект в **своём табе** (если `_use_new_tab() == True`)
   - Или в существующем табе (если `_use_new_tab() == False`)

**Управление проектами:** `config/active_projects.py`
```python
active_projects = {
    'concrete': 'active',       # Запускается
    'test': 'not_active',       # Пропускается
    'neuraverse': 'active',     # Запускается
}
```

```bash
python main.py              # Все аккаунты, все active проекты
python main.py auto_001     # Один аккаунт, все active проекты
```

### `scripts/run_account.py` — Запуск одного аккаунта

Открывает браузер с пустой страницей, держит открытым до `Ctrl+C`.

```bash
python scripts\run_account.py           # Первый аккаунт
python scripts\run_account.py auto_005  # Конкретный аккаунт
```

### `scripts/init_wallet4browser.py` — Инициализация Zerion Wallet

Автоматический импорт мнемонической фразы в расширение Zerion.

```bash
python scripts\init_wallet4browser.py           # Все аккаунты
python scripts\init_wallet4browser.py auto_007  # Один (браузер остаётся открытым)
```

**Проверка:** Если на странице «Session expired» — аккаунт пропускается.

### `scripts/create_wallets.py` — Генерация аккаунтов

Создаёт мнемонические фразы (BIP39, 256 bit), EVM/Solana адреса, профили Chrome.

### `scripts/proxy_checker.py` — Проверка прокси

Читает `config/proxy.txt`, проверяет каждый, рабочие сохраняет в `config/proxy.py`.

```bash
pip install aiohttp
python scripts\proxy_checker.py
```

---

## Конфигурация

### `config/accounts.py`

Генерируется `create_wallets.py`. Кортеж аккаунтов:

```python
accounts = (
    {
        'status': 'active',
        'name': 'auto_001',
        'wallet_password': 'asdfj*KK',
        'solana': 'rVZ6m3TThPJqyERosPJW9Gx4wCXvGkgFzuLa4iYuWbi',
        'evm': '0x8993eCEC73e8bb79AB95e5F3cfc1374f48D9A79E',
        'profile_directory': 'auto_001',
        'debugging_port': 9331,
    },
    ...
)
```

### `config/auto_sids.py`

Сид-фразы для импорта кошельков:

```python
accounts = {
    'auto_001': 'awake similar industry defense ...',
    ...
}
```

### `config/proxy.py`

Рабочие прокси (генерируется `proxy_checker.py`):

```python
proxies = [
    "https://47.91.65.23:3128",
    ...
]
```

---

## Логирование

- **Формат:** `%(asctime)s [%(levelname)s] %(message)s`
- **Файл:** `logs/browser_YYYY-MM-DD.log` (новый файл каждый день)
- **Пример:** `logs/browser_2026-04-13.log`
- **Уровень:** INFO

---

## Зависимости

```bash
pip install playwright aiohttp
playwright install chromium
```

---

## Запуск

```bash
# Массовый запуск Concrete (все аккаунты с login_zerion)
python main.py

# Один аккаунт
python main.py auto_001

# Массовый тест
python main.py test

# Пустой браузер для ручной работы
python scripts\run_account.py auto_001

# Инициализация кошельков
python scripts\init_wallet4browser.py

# Проверка прокси
python scripts\proxy_checker.py
```
