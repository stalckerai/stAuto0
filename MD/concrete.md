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

## Методы

### `_check_done(page=None) -> bool`

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
