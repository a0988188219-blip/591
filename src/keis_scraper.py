"""Scraper for the KEIS (凱璿/永慶) internal case-management system.

IMPORTANT — this only works when run from a machine on your company
network / VPN, since keis.kshouse.com.tw is an internal (內網) site.
It cannot be reached from a cloud sandbox.

The selectors below are best-effort placeholders — I couldn't load the
real page from this session (network egress to keis.kshouse.com.tw is
blocked here), so they will very likely need small adjustments. To fix
them:
  1. Run with --headless=False (the default) so you can see the browser.
  2. When something fails, right-click the element in question → 檢查
     (Inspect) in Chrome DevTools, copy the outer HTML, and send it to
     me — I'll update the selector here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

from . import auth
from .models import Listing

load_dotenv()

BASE_URL = os.getenv("KEIS_BASE_URL", "https://keis.kshouse.com.tw")
SESSION_NAME = "keis"

# --- Selectors: adjust these to match the real page -----------------
SEL_USERNAME_INPUT = "input[name='username'], input[name='account'], input[type='text']"
SEL_PASSWORD_INPUT = "input[name='password'], input[type='password']"
SEL_LOGIN_BUTTON = "button[type='submit'], button:has-text('登入')"
SEL_LOGGED_IN_MARKER = "text=登出, text=案件管理"  # something only visible after login
SEL_CASE_ROW_LINK = "a[href*='/case/']"  # a row/link in the 案件管理 list
SEL_CASE_TITLE = "h1, .case-title"
SEL_CASE_FIELD_TABLE = "table, dl"  # detail fields are often in a table or <dl>
SEL_PHOTO_DOWNLOAD_LINK = "a:has-text('下載'), a[href*='/photo']"
# ----------------------------------------------------------------------


def is_logged_in(page: Page) -> bool:
    try:
        return page.locator(SEL_LOGGED_IN_MARKER).first.is_visible(timeout=1000)
    except Exception:
        return False


def login(page: Page) -> None:
    page.goto(BASE_URL)
    if is_logged_in(page):
        return

    username = os.getenv("KEIS_USERNAME")
    password = os.getenv("KEIS_PASSWORD")

    if username and password:
        page.fill(SEL_USERNAME_INPUT, username)
        page.fill(SEL_PASSWORD_INPUT, password)
        page.click(SEL_LOGIN_BUTTON)
        page.wait_for_timeout(2000)
        if is_logged_in(page):
            return
        print("[keis] 自動登入後仍未偵測到成功登入，請手動完成（可能跳出驗證步驟）。")

    auth.wait_for_manual_login(
        page,
        is_logged_in,
        prompt="請在瀏覽器視窗中手動登入 KEIS 內部系統。",
    )


def list_case_urls(page: Page) -> list[str]:
    """Go to 案件管理 and collect the URL of every case row."""
    page.goto(f"{BASE_URL}/dashboard")
    page.click("text=案件管理")
    page.wait_for_load_state("networkidle")
    links = page.locator(SEL_CASE_ROW_LINK).all()
    urls = []
    for link in links:
        href = link.get_attribute("href")
        if href:
            urls.append(href if href.startswith("http") else f"{BASE_URL}{href}")
    return urls


def download_case_photos(page: Page, case_url: str, dest_dir: Path) -> list[str]:
    """Download every photo attached to a case detail page. Returns local paths."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    links = page.locator(SEL_PHOTO_DOWNLOAD_LINK).all()
    for i, link in enumerate(links):
        with page.expect_download() as dl_info:
            link.click()
        download = dl_info.value
        target = dest_dir / (download.suggested_filename or f"photo_{i}.jpg")
        download.save_as(str(target))
        saved_paths.append(str(target))

    return saved_paths


def scrape_case(page: Page, case_url: str, photo_dir: Path) -> Listing:
    """Open one case detail page and turn it into a Listing.

    NOTE: field extraction below assumes a simple label→value table/dl
    layout. Once you show me the real 案件詳情 HTML this will be swapped
    for exact selectors instead of text-matching, which is more fragile.
    """
    page.goto(case_url)
    page.wait_for_load_state("networkidle")

    def field_text(label: str, default: str = "") -> str:
        try:
            row = page.locator(f"text={label}").first
            # assume the value sits in the next sibling cell/element
            value = row.locator("xpath=following-sibling::*[1]").first
            return value.inner_text(timeout=2000).strip()
        except Exception:
            return default

    photos = download_case_photos(page, case_url, photo_dir)

    def to_float(s: str, default: float = 0.0) -> float:
        try:
            return float("".join(c for c in s if c.isdigit() or c == "."))
        except ValueError:
            return default

    def to_int(s: str, default: int = 0) -> int:
        try:
            return int("".join(c for c in s if c.isdigit()) or default)
        except ValueError:
            return default

    return Listing(
        title=field_text("案名") or page.locator(SEL_CASE_TITLE).first.inner_text(),
        city=field_text("縣市"),
        district=field_text("行政區"),
        address=field_text("地址"),
        house_type=field_text("型態"),
        total_price_wan=to_float(field_text("總價")),
        main_building_ping=to_float(field_text("主建物坪數")),
        total_ping=to_float(field_text("權狀坪數")),
        land_ping=to_float(field_text("土地坪數")) or None,
        rooms=to_int(field_text("房")),
        living_rooms=to_int(field_text("廳")),
        bathrooms=to_int(field_text("衛")),
        floor=to_int(field_text("樓層")),
        total_floors=to_int(field_text("總樓層")),
        age_years=to_float(field_text("屋齡")),
        parking=field_text("車位"),
        facing=field_text("座向"),
        description=field_text("物件描述"),
        contact_name=field_text("聯絡人") or "顏秀珊",
        contact_phone=field_text("聯絡電話") or "0913-335-182",
        photos=photos,
    )


def fetch_listings(case_urls: list[str] | None = None, headless: bool = False) -> list[Listing]:
    """Log into KEIS and scrape one or more cases into Listing objects.

    If case_urls is None, scrapes every case found in 案件管理.
    """
    photo_dir = Path(__file__).resolve().parent.parent / "downloads" / "photos"

    with sync_playwright() as p:
        context, page = auth.open_context(p, SESSION_NAME, headless=headless)
        login(page)
        auth.save_session(context, SESSION_NAME)

        urls = case_urls or list_case_urls(page)
        print(f"[keis] 找到 {len(urls)} 筆案件，開始抓取...")

        listings = []
        for url in urls:
            try:
                listings.append(scrape_case(page, url, photo_dir))
            except Exception as e:
                print(f"[keis] 抓取失敗 {url}: {e}")

        context.close()
        return listings
