"""
Отладочный скрипт: открывает Zerion extension popup и показывает его структуру.
"""
import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.accounts import accounts
from Core.browser import BaseBrowser


async def main():
    account_name = sys.argv[1] if len(sys.argv) > 1 else "auto_001"
    account = next((a for a in accounts if a["name"] == account_name), None)
    if not account:
        print(f"Account '{account_name}' not found")
        sys.exit(1)

    browser = BaseBrowser(account)
    try:
        await browser.launch()
        await browser.login_zerion()

        # Открываем Zerion extension popup
        pages = browser.context.pages
        zerion_popup = None
        for p in pages:
            if "extension" in p.url.lower():
                zerion_popup = p
                break

        if not zerion_popup:
            print("Zerion popup not found!")
            return

        print(f"Zerion popup URL: {zerion_popup.url}")
        await asyncio.sleep(3)

        # Скриншот Zerion overview
        screenshot_file = BASE_DIR / "tmp" / "zerion_overview.png"
        await zerion_popup.screenshot(path=str(screenshot_file))
        print(f"Zerion screenshot: {screenshot_file}")

        # Ищем все кнопки и ссылки
        buttons = await zerion_popup.query_selector_all("button")
        print(f"\nFound {len(buttons)} button(s):")
        for i, btn in enumerate(buttons):
            text = (await btn.text_content()).strip()[:40]
            print(f"  [{i}] '{text}'")

        links = await zerion_popup.query_selector_all("a")
        print(f"\nFound {len(links)} link(s):")
        for i, link in enumerate(links):
            text = (await link.text_content()).strip()[:40]
            href = await link.get_attribute("href")
            print(f"  [{i}] '{text}' -> {href}")

        inputs = await zerion_popup.query_selector_all("input")
        print(f"\nFound {len(inputs)} input(s):")
        for i, inp in enumerate(inputs):
            ph = await inp.get_attribute("placeholder")
            tp = await inp.get_attribute("type")
            print(f"  [{i}] type='{tp}', placeholder='{ph}'")

        # Ищем элементы с data-testid или role
        roles = await zerion_popup.evaluate("""() => {
            const els = document.querySelectorAll('[data-testid], [aria-label], [role="tab"], [role="button"]');
            return Array.from(els).map(e => ({
                tag: e.tagName,
                text: e.textContent?.trim()?.substring(0, 40),
                role: e.getAttribute('role'),
                testid: e.getAttribute('data-testid'),
                aria: e.getAttribute('aria-label'),
            }));
        }""")
        print(f"\nFound {len(roles)} role/testid element(s):")
        for i, el in enumerate(roles):
            print(f"  [{i}] {el}")

    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
