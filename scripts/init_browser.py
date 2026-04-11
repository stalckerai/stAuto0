import asyncio
import sys
import os
import zipfile
import requests
from pathlib import Path
import json
from urllib.parse import quote

from playwright.async_api import async_playwright, BrowserContext, Page


class ExtensionInstaller:
    def __init__(self, context: BrowserContext):
        self.context = context
self.page = None

    async def setup(self):
        """Подготовка страницы для установки расширений"""
        self.page = await self.context.new_page()
        await self.page.goto("chrome://extensions/")

    async def enable_dev_mode(self):
        """Включение режима разработчика"""
try:
            # Клик по элементу включения режима разработчика
            toggle_element = await self.page.wait_for_selector(
                'xpath=/html/body/extensions-manager//extensions-toolbar//cr-toolbar/div/cr-toggle',
                timeout=10000
            )
            if toggle_element:
awaittoggle_element.click()
                print("Режим разработчика включен")
        except Exception as e:
            print(f"Не удалось включить режим разработчика: {e}")

    async def download_crx(self, extension_id: str, output_path: str):
        """Скачивает.crx файл расширения по ID из Chrome Web Store"""
        url = f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=98.0.4758.96&acceptformat=crx2,crx3&x=id%3D{extension_id}%26installsource%3Dondemand%26uc"
        print(f"Скачиваем расширение: {url}")

        try:
            response = requests.get(url, allow_redirects=True, timeout=30)
            if response.status_code == 200:
with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"Файл сохранен: {output_path}")
                return True
            else:
                print(f"Ошибка загрузки: статус {response.status_code}")
                return False
        except Exception ase:
print(f"Ошибка при загрузке расширения {extension_id}: {e}")
            return False

    async def install_extension(self, extension_url: str, extension_name: str):
        """Скачивает и устанавливает расширение по URL"""
        crx_path = Path("extensions") / f"{extension_name}.crx"
        if not crx_path.exists() or crx_path.stat().st_size == 0:
            # Скачиваем через URL
            print(f"Скачиваем {extension_name} по ссылке {extension_url}")
            response = requests.get(
f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=98.0.4758.96&acceptformat=crx2,crx3&x=id%3D{extension_id}%26installsource%3Dondemand%26uc"
         if response.status_code == 200:
                with open(crx_path, 'wb') as f:
                    f.write(response.content)
                    print(f"Файл {crx_path} загружен")
            else:
                print(f"Не удалось скачать {extension_name} по ссылке {extension_url}")
return False

        print(f"Устанавливаем {extension_name} из {crx_path}")
        await self.page.goto("chrome://extensions")

        # Загружаем файл
        await self.page.set_input_files("input[type=file]", str(crx_path))
        print("Файл загружен")

# Ждем кнопки установки
        try:
            install_button = await self.page.wait_for_selector(
                '//button[span[text()="Install"]',
                timeout=10000
            )
            if install_button:
                print("Нажимаем кнопку установки")
               awaitinstall_button.click()
                await asyncio.sleep(3)
                return True
        except:
            print("Кнопка установки не найдена")
            return False
        return False

    async def check_extension_installed(self, extension_name: str):
        """Проверка наличия расширения"""
        try:
awaitself.page.goto("chrome://extensions/")
            # Ищем расширение по имени
            extensions = await self.page.query_selector_all('div[role="checkbox"]')
            for ext in extensions:
                ext_text = await ext.inner_text()
                if extension_name.lower() in ext_text.lower():
returnTrue
return False
        except Exception as e:
            print(f"Ошибка проверки расширения {extension_name}: {e}")
            return False

    async def run(self):
        """Основной процесс установки расширений"""
        await self.setup()
        await self.enable_dev_mode()

       # УстановкаWebRTC Control
        if not await self.check_extension_installed("WebRTC Control"):
            print("Установка WebRTC Control...")
            await self.install_extension(
                "https://chromewebstore.google.com/detail/webrtc-control/fjkmabmdepjfammlpliljpnbhleegehm",
"webrtc-control"
            )

        # Установка Zerion Wallet
        if not await self.check_extension_installed("Zerion Wallet"):
            print("Установка Zerion Wallet...")
            await self.install_extension(
                "https://chromewebstore.google.com/detail/zerion-wallet-crypto-defi/klghhnkeealcohjjanjjdaeeggmfmlpl",
                "zerion-wallet"
            )

        print("Установка расширений завершена")


async def main():
    """Точка входа"""
    import sys
    import ossys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from Core.browser import BaseBrowser
    from playwright.async_api import async_playwright
    from pathlib import Path
    import json
    import requests

    # Пути к файлам
    extensions_dir = Path("extensions")
    extensions_dir.mkdir(exist_ok=True)

    webrtc_path = extensions_dir / "webrtc-control.crx"
    zerion_path = extensions_dir / "zerion-wallet.crx"

    # Загрузка аккаунта
    with open('config/accounts.py', 'r')asf:
        exec(f.read(), globals())

    account = accounts[0]  # Берем первый активный аккаунт

    async with async_playwright() as p:
        browser = BaseBrowser(account)
        browser.launch_chrome(extensions=[webrtc_path, zerion_path])
        await browser.connect()
        installer = ExtensionInstaller(browser.context)
        await installer.run()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())