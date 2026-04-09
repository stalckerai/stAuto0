import asyncio
import os
import zipfile
from pathlib import Path
import json

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
                await toggle_element.click()
                print("Режим разработчика включен")
        except Exception as e:
            print(f"Не удалось включить режим разработчика: {e}")

    async def install_extension(self, extension_url: str):
        """Установка расширения из Chrome Web Store с обработкой .crx файлов"""
        try:
            print(f"Скачиваем расширение: {extension_url}")
            await self.page.goto(extension_url)

            # Ищем кнопку загрузки и нажимаем её
            download_button = await self.page.wait_for_selector(
                'button[aria-label*="Add to Chrome"]',
                timeout=10000
            )
            if download_button:
                print("Нажимаем на кнопку установки")
                await download_button.click()

                # Ждем скачивания (расширение скачивается в папку Downloads)
                print("Ждем завершения скачивания...")
                await asyncio.sleep(5)

            # Проверяем, есть ли скачанный файл
            downloads_dir = Path.home() / "Downloads"
            crx_files = list(downloads_dir.glob("*.crx"))
            if not crx_files:
                print("Файл .crx не найден в папке Downloads")
                return

            # Берем последний скачанный файл
            crx_file = max(crx_files, key=os.path.getctime)
            output_dir = Path("extensions")
            output_dir.mkdir(exist_ok=True)

            print(f"Распаковываем расширение из {crx_file}")

            # Пробуем распаковать как zip
            try:
                with zipfile.ZipFile(str(crx_file), 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                    print("Успешно распаковано")
                    return
            except zipfile.BadZipfile:
                print("Ошибка: .crx файл имеет бинарный заголовок")
                # Удаляем бинарный заголовок и пробуем снова
                with open(str(crx_file), 'rb') as f:
                    data = f.read()

                # Проверяем, есть ли бинарный заголовок PK\x03\x04
                if data[:4] == b'PK\x03\x04':
                    print("Файл уже в правильном формате")
                    with zipfile.ZipFile(str(crx_file), 'r') as zip_ref:
                        zip_ref.extractall(output_dir)
                    return
                else:
                    # Пробуем удалить первые несколько байт
                    output_data = data[10:]
                    temp_crx_path = str(output_dir / "temp.crx")
                    with open(temp_crx_path, 'wb') as f:
                        f.write(output_data)

                    try:
                        with zipfile.ZipFile(temp_crx_path, 'r') as zip_ref:
                            zip_ref.extractall(output_dir)
                        print("Успешно распаковано после удаления заголовка")
                    except Exception as e:
                        print(f"Ошибка при распаковке: {e}")

        except Exception as e:
            print(f"Ошибка при установке расширения {extension_url}: {e}")

    async def check_extension_installed(self, extension_name: str):
        """Проверка наличия расширения"""
        try:
            await self.page.goto("chrome://extensions/")
            # Ищем расширение по имени
            extensions = await self.page.query_selector_all('div[role="checkbox"]')
            for ext in extensions:
                ext_text = await ext.inner_text()
                if extension_name.lower() in ext_text.lower():
                    return True
            return False
        except Exception as e:
            print(f"Ошибка проверки расширения {extension_name}: {e}")
            return False

    async def run(self):
        """Основной процесс установки расширений"""
        await self.setup()

        # Установка WebRTC Control
        if not await self.check_extension_installed("WebRTC Control"):
            print("Установка WebRTC Control...")
            await self.install_extension(
                "https://chromewebstore.google.com/detail/webrtc-control/fjkmabmdepjfammlpliljpnbhleegehm")

        # Установка Zerion Wallet
        if not await self.check_extension_installed("Zerion Wallet"):
            print("Установка Zerion Wallet...")
            await self.install_extension(
                "https://chromewebstore.google.com/detail/zerion-wallet-crypto-defi/klghhnkeealcohjjanjjdaeeggmfmlpl")

        print("Установка расширений завершена")


async def main():
    """Точка входа"""
    from Core.browser import BaseBrowser

    # Загрузка аккаунта
    with open('config/accounts.py', 'r') as f:
        exec(f.read(), globals())

    account = accounts[0]  # Берем первый активный аккаунт

    browser = BaseBrowser(account)
    await browser.launch_chrome()
    await browser.connect()

    installer = ExtensionInstaller(browser.context)
    await installer.run()

    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())