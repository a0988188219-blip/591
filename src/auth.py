"""Shared browser-session helpers.

Two login strategies are supported for each site:

1. "remember session" (recommended) — you log in manually, once, in the
   browser window the script opens. The session is saved to disk under
   .auth/<name>.json and reused on future runs, so you never type a
   password into this program again.

2. "auto-fill from .env" — the script types the username/password from
   your local .env file into the login form for you. Useful if you don't
   want to keep a browser session around. If the site shows a CAPTCHA or
   SMS code, the script pauses and waits for you to finish that step by
   hand — it does not attempt to solve or bypass it.
"""
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

AUTH_DIR = Path(__file__).resolve().parent.parent / ".auth"
AUTH_DIR.mkdir(exist_ok=True)


def storage_state_path(name: str) -> Path:
    return AUTH_DIR / f"{name}.json"


def open_context(playwright, name: str, headless: bool = False) -> tuple[BrowserContext, Page]:
    """Launch a browser context, restoring a saved session for `name` if present."""
    browser = playwright.chromium.launch(headless=headless)
    state_path = storage_state_path(name)
    if state_path.exists():
        context = browser.new_context(storage_state=str(state_path))
    else:
        context = browser.new_context()
    page = context.new_page()
    return context, page


def save_session(context: BrowserContext, name: str) -> None:
    context.storage_state(path=str(storage_state_path(name)))
    print(f"[auth] 已儲存 {name} 的登入狀態到 {storage_state_path(name)}")


def wait_for_manual_login(page: Page, check_logged_in, prompt: str, timeout_s: int = 300) -> bool:
    """Poll `check_logged_in(page) -> bool` while you log in by hand in the window.

    Use this whenever a site might show a CAPTCHA / SMS code — this script
    never tries to solve those, it just waits for you.
    """
    print(f"[auth] {prompt}")
    print(f"[auth] 最多等待 {timeout_s} 秒，登入完成後程式會自動偵測並繼續。")
    import time

    waited = 0
    interval = 2
    while waited < timeout_s:
        if check_logged_in(page):
            print("[auth] 偵測到已登入，繼續執行。")
            return True
        if waited % 10 == 0:
            all_pages = page.context.pages
            print(f"[auth][診斷] 程式追蹤的分頁網址：{page.url}")
            print(f"[auth][診斷] 瀏覽器裡總共有 {len(all_pages)} 個分頁，網址分別是：")
            for i, p in enumerate(all_pages):
                marker = "← 程式追蹤的就是這個" if p == page else ""
                print(f"[auth][診斷]   分頁{i+1}：{p.url} {marker}")
        time.sleep(interval)
        waited += interval
    print("[auth] 等待逾時，仍未偵測到登入成功。")
    return False
