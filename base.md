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
│   └── test.py             # Тестовый проект (BaseProject + TestProject)
├── scripts/
│   ├── create_wallets.py   # Генерация аккаунтов, мнемоник, адресов
│   ├── run_account.py      # Запуск одного аккаунта с пустой страницей
│   └── init_wallet4browser.py  # Инициализация Zerion Wallet
├── config/
│   ├── __init__.py
│   ├── accounts.py         # Конфигурация аккаунтов (генерируется)
│   ├── auto_sids.py        # Сид-фразы (генерируется)
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
   - Флаги: `--remote-debugging-port`, `--user-data-dir`, `--no-first-run`
   - Опционально: `--load-extension` для загрузки распакованных расширений
   - Ожидание запуска: 5 секунд

2. **`connect()`** — подключение через Playwright CDP
   - `playwright.chromium.connect_over_cdp("http://localhost:{port}")`
   - Берёт существующий контекст или создаёт новый
   - Получает первую доступную страницу

3. **`launch(extensions=None)`** — обёртка: `launch_chrome()` + `connect()`

4. **`login_zerion(password=None)`** — логин в Zerion Wallet
   - Открывает страницу логина расширения
   - Вводит пароль из конфига аккаунта
   - Нажимает «Unlock»
   - Ждёт 3 секунды, закрывает страницу

5. **`run_project(project_class)`** — создание проекта и вызов `run()`
   - Передаёт: `context`, `page`, `account`

6. **`close()`** — корректное закрытие: page → context → browser → playwright → Chrome process

### Пример использования

```python
from Core.browser import BaseBrowser

account = {
    "name": "auto_001",
    "profile_directory": "auto_001",
    "debugging_port": 9331,
}

browser = BaseBrowser(account)
await browser.launch()
await browser.login_zerion()
await browser.run_project(MyProject)
await browser.close()
```

---

## Projects

**Файл:** `projects/test.py`

### BaseProject

Базовый класс для всех проектов. Принимает `context`, `page`, `account`.

```python
class BaseProject:
    def __init__(self, context, page, account):
        self.context = context
        self.page = page
        self.account = account

    async def run(self):
        raise NotImplementedError
```

### TestProject

Тестовая реализация — открывает страницу, ждёт 5 сек, завершается.

---

## Скрипты

### `main.py` — Массовый запуск

Запускает все активные аккаунты (`status == "active"`) последовательно с задержкой 3 сек.

```bash
python main.py
```

### `scripts/run_account.py` — Запуск одного аккаунта

Открывает браузер с пустой страницей и держит его открытым до `Ctrl+C`.

```bash
# Первый аккаунт
python scripts\run_account.py

# Конкретный аккаунт
python scripts\run_account.py auto_005
```

### `scripts/init_wallet4browser.py` — Инициализация Zerion Wallet

Автоматический импорт мнемонической фразы в расширение Zerion для каждого аккаунта.

**Шаги:**
1. Открытие страницы импорта Zerion
2. Выбор «Use 24 word phrase»
3. Заполнение 24 слов из `config/auto_sids.py`
4. Нажатие «Import wallet»
5. Ввод пароля из `config/accounts.py`
6. Подтверждение и установка пароля

```bash
# Все аккаунты (авто-пропуск уже инициализированных)
python scripts\init_wallet4browser.py

# Один аккаунт (браузер останется открытым)
python scripts\init_wallet4browser.py auto_007
```

**Проверка:** Если на странице обнаружен текст «Session expired» — аккаунт пропускается (кошелёк уже установлен).

### `scripts/create_wallets.py` — Генерация аккаунтов

Создаёт:
- Мнемонические фразы (BIP39, 256 bit)
- EVM адреса (BIP44: m/44'/60'/0'/0/0)
- Solana адреса (BIP44: m/44'/501'/0'/0')
- Профили Chrome
- Файлы `config/accounts.py` и `config/auto_sids.py`

---

## Конфигурация

### `config/accounts.py`

Генерируется автоматически. Содержит кортеж аккаунтов:

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
    'auto_002': 'sadness method bronze april ...',
    ...
}
```

---

## Логирование

- **Формат:** `%(asctime)s [%(levelname)s] %(message)s`
- **Файл:** `logs/browser.log`
- **Уровень:** INFO

---

## Зависимости

```bash
pip install playwright
playwright install chromium
```

---

## Запуск

```bash
# Тестовый прогон всех аккаунтов
python main.py

# Запуск одного аккаунта (для отладки)
python scripts\run_account.py auto_001

# Инициализация кошельков
python scripts\init_wallet4browser.py
```
