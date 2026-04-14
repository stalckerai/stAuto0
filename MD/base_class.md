Создай в папке Core базовый класс для работы с playwright
Задачи класса - запустить аккаунт хрома, настройки аккаунтов лежат
в
файле config/accounts.py путь к профилям хрома - в папке config/chrome_accounts
подключится к нему по отадочному порту
далее вызвать у проектка метод run
проекты будут лежать в папке projects
какждый проект это отдельный класс, в проект надо передать context что бы проект мог сам 
управлять страницей

Для теста создай проекто test.py который будет открывать какую-нибудть легковесную страницу, ждать 5 секунд
и закрывать браузер

Нужно корректно обрабатывать все ошибки, запуск браузера, подключение к нему, создание объекта проекта и вызов
метода run нужно оберунть все в обработчик try  и писать логи что бы я мог их прочитить и что бы
ты мог их прочитать и исправить если нужно

---

## Выполнено

### Созданные файлы
- `Core/__init__.py`
- `Core/browser.py` — базовый класс `BaseBrowser`
- `projects/__init__.py`
- `projects/test.py` — тестовый проект `TestProject`
- `main.py` — точка входа

### Архитектура

**`BaseBrowser` (Core/browser.py):**
- `__init__(account)` — инициализация из словаря аккаунта (читает `name`, `profile_directory`, `debugging_port`)
- `launch_chrome(extensions=None)` — запуск Chrome с флагами `--remote-debugging-port` и `--user-data-dir`, поддержка загрузки расширений через аргумент `--load-extension`
- `connect(extensions=None)` — подключение через Playwright CDP (`connect_over_cdp`), создание контекста с расширениями
- `run_project(project_class)` — создание экземпляра проекта, передача `context`, `page`, `account`, вызов `run()`
- `close()` — закрытие page, context, browser, playwright, завершение процесса Chrome

**`BaseProject` (projects/test.py):**
- Базовый класс с `__init__(context, page, account)`
- Абстрактный метод `run()` — переопределяется в наследниках
- `TestProject` — открывает `https://httpbin.org/get`, ждёт 5 секунд, закрывается

**`main.py`:**
- Читает `config.accounts`, фильтрует по `status == 'active'`
- Для каждого аккаунта: запуск Chrome → подключение → запуск проекта → закрытие
- Все операции обёрнуты в `try/except/finally`
- Логи дублируются в консоль и `logs/browser.log`

### Логирование
Формат: `%(asctime)s [%(levelname)s] %(message)s`
Файл логов: `logs/browser.log`

### Запуск
```bash
pip install playwright
playwright install chromium
python main.py
```

### Обновления
- Добавлена поддержка загрузки расширений через аргументы командной строки и Playwright context options
- Методы `launch_chrome()` и `connect()` теперь принимают опциональный параметр `extensions`