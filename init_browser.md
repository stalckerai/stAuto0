Создай скрипт scripts/init_browser.py
Для работы с расширениями используй код проекта.

Нужно уставновить и настроить расширения.
переходит на страницу
chrome://extensions/
и включаем режим разработчика
нужно кликнуть по элементу
xpath=/html/body/extensions-manager//extensions-toolbar//cr-toolbar/div/cr-toggle
мы включили режим разработчика, далее будем устанавливать расширения

Первое расширение:
перейти на страницу chrome://extensions/ и проверить есть там текст WebRTC Control
если есть то переходим к установке следующего
если нет то устанавливаем расширение
https://chromewebstore.google.com/detail/webrtc-control/fjkmabmdepjfammlpliljpnbhleegehm
Напрямую из магазина установить нельзя — нужно сначала скачать .crx файл, затем загрузить его.
Шаг 2 — Распаковать .crx (Chrome требует распакованный формат)
Некоторые .crx имеют бинарный заголовок перед zip-частью. Если zipfile выдаёт ошибку реши эту проблему

Второе расширение по так же как и первое
на странице chrome://extensions/ идем текст Zerion Wallet: если он есть то ничего не делаем, 
если нет то устанавливаем по аналогии с первым
https://chromewebstore.google.com/detail/zerion-wallet-crypto-defi/klghhnkeealcohjjanjjdaeeggmfmlpl

добавь в код запука браузера код для что бы браузер запускался с этими расширениями
