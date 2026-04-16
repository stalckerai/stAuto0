"""
Отладочный скрипт: открывает Paragraph редактор, сохраняет DOM и скриншот. Быстро, без ожидания.
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

        paragraph_page = await browser.context.new_page()

        print("Navigating to paragraph.com...")
        await paragraph_page.goto(
            "https://paragraph.com",
            wait_until="domcontentloaded",
            timeout=30000
        )
        await asyncio.sleep(5)

        # Ищем кнопку создания новой статьи
        print("Looking for new post button...")
        new_post_selectors = [
            "a[href*='/editor/']",
            "a[href*='/new']",
            "button:has-text('New')",
            "a:has-text('New')",
            "a:has-text('Write')",
            "button:has-text('Write')",
            "[role='button']:has-text('Create')",
            "a:has-text('Create')",
        ]
        for sel in new_post_selectors:
            try:
                el = paragraph_page.locator(sel).first
                if await el.is_visible(timeout=3000):
                    href = await el.get_attribute("href")
                    text = await el.text_content()
                    tag = await el.evaluate("e => e.tagName")
                    print(f"  Found: tag={tag}, text='{text.strip()[:40]}', href='{href}', selector='{sel}'")
            except:
                pass

        # Сохраняем скриншот главной страницы
        screenshot_file = BASE_DIR / "tmp" / "paragraph_home.png"
        await paragraph_page.screenshot(path=str(screenshot_file), full_page=True)
        print(f"Home screenshot: {screenshot_file}")

        # HTML главной
        html = await paragraph_page.content()
        html_file = BASE_DIR / "tmp" / "paragraph_home.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Home HTML saved: {html_file}")

        # Попробуем перейти на /editor/ijl3mRFMIzL9gjfyIBQX
        print("\nNavigating to editor URL...")
        await paragraph_page.goto(
            "https://paragraph.com/editor/ijl3mRFMIzL9gjfyIBQX",
            wait_until="domcontentloaded",
            timeout=30000
        )
        print("Waiting for editor to render...")
        await asyncio.sleep(15)

        # Скриншот редактора
        screenshot_file = BASE_DIR / "tmp" / "paragraph_editor_screenshot.png"
        await paragraph_page.screenshot(path=str(screenshot_file), full_page=True)
        print(f"Editor screenshot: {screenshot_file}")

        # HTML редактора
        html = await paragraph_page.content()
        html_file = BASE_DIR / "tmp" / "paragraph_editor.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Editor HTML saved: {html_file}")

        # Ищем все возможные элементы для заголовка
        print("\n=== [1] TEXTAREA elements ===")
        textareas = await paragraph_page.query_selector_all("textarea")
        for i, ta in enumerate(textareas):
            attrs = {}
            for attr in ["placeholder", "data-editor-field", "class", "id", "name", "aria-label"]:
                val = await ta.get_attribute(attr)
                if val:
                    attrs[attr] = val
            print(f"  [{i}] {attrs}")

        print("\n=== [2] Contenteditable elements ===")
        editables = await paragraph_page.query_selector_all("[contenteditable='true']")
        for i, el in enumerate(editables):
            tag = await el.evaluate("e => e.tagName")
            parent_info = await el.evaluate("""e => {
                const p = e.closest('[id]');
                return p ? p.tagName + '#' + p.id : e.tagName;
            }""")
            attrs = {}
            for attr in ["class", "data-placeholder", "placeholder", "role"]:
                val = await el.get_attribute(attr)
                if val:
                    attrs[attr] = val
            print(f"  [{i}] tag={tag}, parent={parent_info}, {attrs}")

        print("\n=== [3] Elements with data-editor-field ===")
        editor_fields = await paragraph_page.query_selector_all("[data-editor-field]")
        for i, ef in enumerate(editor_fields):
            tag = await ef.evaluate("e => e.tagName")
            field = await ef.get_attribute("data-editor-field")
            cls = await ef.get_attribute("class")
            print(f"  [{i}] tag={tag}, field='{field}', class='{cls}'")

        print("\n=== [4] Elements inside #paragraph-tiptap-editor ===")
        editor_children = await paragraph_page.evaluate("""() => {
            const editor = document.getElementById('paragraph-tiptap-editor');
            if (!editor) return 'EDITOR NOT FOUND';
            const children = Array.from(editor.querySelectorAll('*'));
            return children.slice(0, 20).map(c => ({
                tag: c.tagName,
                class: c.className,
                text: (c.textContent || '').substring(0, 80),
                contenteditable: c.contentEditable,
                role: c.getAttribute('role'),
                placeholder: c.getAttribute('placeholder'),
                'data-placeholder': c.getAttribute('data-placeholder'),
            }));
        }""")
        print(f"  {editor_children}")

        print("\n=== [5] First-level children of editor ===")
        first_children = await paragraph_page.evaluate("""() => {
            const editor = document.getElementById('paragraph-tiptap-editor');
            if (!editor) return 'EDITOR NOT FOUND';
            return Array.from(editor.children).map(c => ({
                tag: c.tagName,
                class: c.className,
                text: (c.textContent || '').substring(0, 100),
                contenteditable: c.contentEditable,
            }));
        }""")
        print(f"  {first_children}")

        # Пробуем вставить текст в редактор напрямую
        print("\n=== [6] Trying to find title field ===")
        # Попробуем h1
        h1_count = await paragraph_page.locator("h1").count()
        print(f"  h1 elements: {h1_count}")
        for i in range(min(h1_count, 3)):
            h1 = paragraph_page.locator("h1").nth(i)
            try:
                text = await h1.text_content()
                cls = await h1.get_attribute("class")
                print(f"  h1[{i}] text='{text[:60]}', class='{cls}'")
            except:
                print(f"  h1[{i}] <error>")

        # Попробуем [data-placeholder]
        placeholders = await paragraph_page.query_selector_all("[data-placeholder]")
        print(f"  Elements with data-placeholder: {len(placeholders)}")
        for i, el in enumerate(placeholders):
            ph = await el.get_attribute("data-placeholder")
            tag = await el.evaluate("e => e.tagName")
            print(f"  [{i}] tag={tag}, data-placeholder='{ph}'")

        print("\nDone!")

    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
