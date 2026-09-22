"""快速測試：這個網站在自動化瀏覽器裡打不打得開。
用法：python scripts/test_site.py https://www.rakuya.com.tw/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "https://www.rakuya.com.tw/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    print(f"正在打開：{url}")
    page.goto(url, timeout=30000)
    page.wait_for_timeout(3000)
    print(f"網頁標題：{page.title()}")
    print(f"目前網址：{page.url}")
    out = Path(__file__).resolve().parent.parent / "downloads" / "test_screenshot.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out))
    print(f"已存截圖：{out}")
    input("看完瀏覽器畫面後，回這裡按 Enter 結束...")
    browser.close()
