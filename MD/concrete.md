# Concrete Project — Автоматизация Concrete.xyz

## Описание

Проект для автоматизации ежедневного check-in на платформе **Concrete.xyz** (points.concrete.xyz). Каждый аккаунт выполняет:
1. Логин через Zerion Wallet
2. Проверка статуса check-in
3. Выполнение check-in / claim если доступно

**Файл:** `projects/concrete.py`

---

## Архитектура проекта

```python
class ConcreteProject(BaseProject):
    """Проект Concrete — daily check-in + claim"""

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
```

---

## Логин на Paragraph.com

**Метод:** `_login_paragraph()`

**Привязка:** Zerion Wallet через Privy + injected provider.

**Шаги:**

| Шаг | Действие | Описание |
|---|---|---|
| 1 | Клик "Continue with a wallet" | Privy модал, `<div class="sc-FEMpB cWABZH">` |
| 2 | Ввод "Zerion" в поиск | `input[placeholder*='Search through']` |
| 3 | Клик по `<span class="sc-hEkkVl hPdPOi">Zerion</span>` | Ловим popup через `context.expect_page()` |
| 4 | `click_confirm(popup)` | Zerion показывает диалог подписи → последняя кнопка (Sign) |
| 5 | `page.reload()` | Privy обнаруживает подключённый кошелёк |
| 6 | Пост-логин кнопка (если есть) | Закрывает модал |

Проверяет, выполнена ли задача (найдена одна из кнопок завершения).

**Ищет кнопки:**
- `"Back to your progress"`
- `"Claimed"`
- `"Checked-in"`

Если хотя бы одна видна → задача выполнена.

---

### `_login()`

Логин в Concrete через Zerion Wallet.

**Шаги:**
1. Ищет Zerion кнопку по xpath
2. Кликает → ловит popup через `context.expect_page()`
3. Обрабатывает popup через `browser.click_confirm(popup)`
4. Ищет confirm-кнопку → кликает → ловит popup → `click_confirm()`

**XPath-селекторы:**
```python
zerion_btn = 'xpath=/html/body/div[4]/.../div/button/div/div/div[2]'
confirm_btn = 'xpath=/html/body/div[4]/.../div[2]/div[2]/button[1]/div'
```

---

### `_setup_referral()` ⚠️ НЕ АКТИВНА

Переход на leaderboard и ввод реферального кода.

**НЕ вызывается автоматически** — предназначена для ручного вызова.

**Шаги:**
1. Переход на `https://points.concrete.xyz/leaderboard`
2. Ввод реферального кода `"42e0ff07"`
3. Клик по "Apply Code"

**Использование:**
```python
# В _process() или отдельно:
await self._setup_referral()
```

---

### `_process() -> bool`

Основная логика выполнения задачи.

**Шаги:**

| Шаг | Действие | Описание |
|---|---|---|
| 1 | Проверка Connect | Если есть кнопка "Connect" → клик → `_login()` |
| 2 | Проверка `_check_done()` | Если уже выполнено → возврат `True` |
| 3 | Переход на profile | `goto("https://points.concrete.xyz/profile")` |
| 4 | Поиск Claim / Check-in | Ищет кнопки, кликает найденную |
| 5 | Проверка `_check_done()` | Подтверждение выполнения |

**Логика кнопок:**
```python
# Приоритет: Check-in > Claim
if found_checkin:
    await checkin_btn.click()
elif found_claim:
    await claim_btn.click()
else:
    logger.warning("Neither Check-in nor Claim found")
```

---

## Цикл выполнения

```
run() → goto(profile) → sleep(5)
    │
    ├── for attempt in 1..3:
    │       │
    │       ├── _process()
    │       │   ├── _login() (если нужно)
    │       │   ├── _check_done() → если True → return
    │       │   ├── goto(profile)
    │       │   ├── клик Check-in / Claim
    │       │   └── _check_done() → если True → return True
    │       │
    │       └── если False → goto(profile) + retry
    │
    └── Если 3 попытки неудачны → warning
```

---

## Конфигурация

### Активация проекта

**Файл:** `config/active_projects.py`

```python
active_projects = {
    'concrete': 'active',      # ← Запускается
    'test': 'not_active',
    'neuraverse': 'not_active',
}
```

### Реферальный код

Хардкод в `_setup_referral()`:
```python
await referral_input.fill("42e0ff07", timeout=5000)
```

---

## Логирование

**Примеры логов:**

```
[auto_001] ===== Running project: concrete =====
[auto_001] Creating NEW tab for ConcreteProject
[auto_001] Opening Concrete points page
[auto_001] Waiting 5 seconds for page to load
[auto_001] Attempt 1/3
[auto_001] Connect button not found — already logged in
[auto_001] Found 'Checked-in' — task already done
[auto_001] Task already completed, skipping
[auto_001] Task completed on attempt 1
[auto_001] ===== Project concrete finished =====
```

---

## Время выполнения

| Этап | Время |
|---|---|
| Загрузка страницы | ~1-2 сек |
| Ожидание | 5 сек |
| Проверка кнопок | ~3 сек |
| Клик Check-in | ~5 сек |
| Проверка завершения | ~2 сек |
| **Итого** | **~15-20 сек** |

---

## Зависимости

- `BaseProject` — базовый класс
- `BaseBrowser` — методы `click_confirm()`, `login_zerion()`
- `Playwright` — браузерная автоматизация

---

## Ошибки и решения

### "Neither Check-in nor Claim found"

**Причина:** Кнопки не появились за 3 сек.

**Решение:**
- Увеличить timeout в `is_visible()`
- Проверить что аккаунт залогинен
- Убедиться что check-in доступен (не каждые 24 часа)

### "Referral code input not found"

**Причина:** Поле ввода реферального кода не найдено.

**Решение:**
- Код уже применён ранее
- Страница leaderboard загружается медленно

### "No popup after Zerion click"

**Причина:** Zerion popup не появился.

**Решение:**
- Увеличить timeout в `expect_page()`
- Проверить что Zerion установлен в браузере

---

## Запуск

```bash
# Все аккаунты, Concrete
python main.py

# Один аккаунт, Concrete
python main.py auto_001
```

---

# Unregular Task — Paragraph Article + Concrete Submission

## Описание

Нерегулярная задача для публикации статьи на **Paragraph.com** и отправки URL в Concrete.xyz для получения поинтов.

**Выполняет:**
1. Логин на Paragraph.com через Zerion
2. Чтение статьи из `tmp/{account_name}.txt`
3. Публикация статьи на Paragraph
4. Копирование URL статьи
5. Переход на Concrete.xyz/home
6. Отправка URL статьи

**Метод:** `_unregular_paragraph_task()`

---

## Формат файла статьи

**Путь:** `tmp/{account_name}.txt`

**Структура:**
```
Заголовок статьи (первая строка)
Текст статьи (все остальные строки)
```

**Пример (`tmp/auto_001.txt`):**
```
My New Article About DeFi
This is the body of the article.
It can span multiple lines.
```

---

## Шаги выполнения

### 1. Логин на Paragraph.com

| Шаг | Действие | Ожидание |
|---|---|---|
| 1.1 | Переход на `https://paragraph.com` | 3 сек |
| 1.2 | Клик "Sign in" | 5 сек |
| 1.3 | Клик "Continue with a wallet" | 5 сек |
| 1.4 | Клик "Zerion" → popup → `click_confirm()` | — |
| 1.5 | Клик post-login кнопки | 5 сек |

**Селекторы:**
```python
sign_in_btn = page.get_by_role("button", name="Sign in")
continue_btn = page.locator("div.sc-FEMpB.cWABZH", has_text="Continue with a wallet")
zerion_btn = page.locator("span.sc-hEkkVl.hPdPOi", has_text="Zerion")
post_login_btn = xpath='/html/body/div[2]/div/div[1]/div/div[2]/div[3]/button/div'
```

### 2. Чтение статьи

```python
article_file = TMP_DIR / f"{account_name}.txt"
# Первая строка = заголовок
# Остальные строки = текст статьи
```

### 3. Вставка заголовка

```python
title_textarea = page.locator("textarea[data-editor-field='title']")
await title_textarea.fill(title)
```

### 4. Вставка текста статьи

**Способ 1:** Через xpath (основной)
```python
editor_p = await page.query_selector('//*[@id="paragraph-tiptap-editor"]/p')
await page.evaluate(f"p.textContent = `{escaped_text}`")
```

**Способ 2:** Через contenteditable (альтернативный)
```python
editable = page.locator('[contenteditable="true"]').first
await editable.fill(article_text)
```

### 5. Публикация

| Шаг | Действие | Ожидание |
|---|---|---|
| 5.1 | Клик "Continue" | 3 сек |
| 5.2 | Клик "Publish" | 7 сек |

### 6. Копирование URL

| Шаг | Действие | Ожидание |
|---|---|---|
| 6.1 | Клик по share-кнопке (radix) | 3 сек |
| 6.2 | Чтение URL из `input[readonly][value*="paragraph.com"]` | — |

### 7. Переход на Concrete.xyz

| Шаг | Действие | Ожидание |
|---|---|---|
| 7.1 | Переход на `https://points.concrete.xyz/home` | 3 сек |
| 7.2 | Логин (если нужно) | — |
| 7.3 | Вставка URL в `input[id="url"][type="url"]` | 3 сек |
| 7.4 | Клик "Submit URL" | 5 сек |
| 7.5 | Проверка кнопки "Close" → успех | — |

---

## Запуск

```bash
# Один аккаунт
python main.py paragraph auto_001

# Все аккаунты
python main.py paragraph
```

---

## Логирование

```
[auto_001] ===== Starting unregular paragraph task =====
[auto_001] Navigating to paragraph.com
[auto_001] Paragraph login: searching for 'Sign in' button
[auto_001] 'Sign in' found, clicking
[auto_001] Reading article from tmp/auto_001.txt
[auto_001] Article title: My New Article About DeFi...
[auto_001] Article text length: 245 chars
[auto_001] Title inserted
[auto_001] Article text inserted
[auto_001] 'Continue' found, clicking
[auto_001] 'Publish' found, clicking
[auto_001] Article URL copied: https://paragraph.com/@0xbad.../my-new-article
[auto_001] Navigating to concrete.xyz/home
[auto_001] Article URL inserted into concrete
[auto_001] 'Submit URL' found, clicking
[auto_001] 'Close' button found — task completed successfully!
```

---

## Подготовка файла статьи

1. Создать папку `tmp/` в корне проекта (если нет)
2. Создать файл `tmp/auto_001.txt` (имя = имя аккаунта)
3. Первая строка — заголовок
4. Остальные строки — текст статьи

**Пример структуры:**
```
stAuto0/
├── tmp/
│   ├── auto_001.txt
│   ├── auto_002.txt
│   └── ...
├── projects/
├── config/
└── main.py
```

---

## Зависимости unregular task

- Файлы статей в `tmp/{account_name}.txt`
- Zerion Wallet установлен в браузере
- Аккаунты имеют средства для публикации (если требуется)

---

## Ошибки unregular task

### "Article file not found"

**Причина:** Файл `tmp/{account_name}.txt` не существует.

**Решение:** Создать файл с правильным именем аккаунта.

### "Article file must have at least 2 lines"

**Причина:** Файл пустой или только заголовок.

**Решение:** Добавить текст статьи после заголовка.

### "Failed to insert title"

**Причина:** Поле заголовка не найдено или страница не загрузилась.

**Решение:** Увеличить timeout, проверить что пользователь залогинен.

### "Failed to insert article text"

**Причина:** Редактор не найден.

**Решение:** Проверить что редактор загрузился, попробовать альтернативный способ через contenteditable.

### "'Close' button not found"

**Причина:** Отправка URL не прошла или страница не обновилась.

**Решение:**
- Проверить что URL статьи корректный
- Убедиться что аккаунт залогинен на Concrete
- Проверить что кнопка "Submit URL" была найдена и нажата
