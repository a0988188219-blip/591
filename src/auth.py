"""Shared browser-session helper.

You log in manually, once, in the browser window the script opens. The
session is saved to disk under .auth/<name>.json and reused on future
runs, so you don't need to log in every time. The script never tries to
detect or wait for login state itself — it waits for you to press Enter
when you're ready (see keis_scraper.py / house591_poster.py), since that
turned out far more reliable than guessing at page state on a site we
can't inspect ahead of time.
"""
from pathlib import Path

from playwright.sync_api import BrowserContext, Page

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
