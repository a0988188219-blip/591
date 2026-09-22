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
SEL_CASE_ROW_LINK = "a[href*='/case/']"  # a row/link in the 案件查詢 list
SEL_CASE_TITLE = "h1, .case-title"
SEL_CASE_FIELD_TABLE = "table, dl"  # detail fields are often in a table or <dl>
SEL_PHOTO_DOWNLOAD_LINK = "a:has-text('下載'), a[href*='/photo']"
# ----------------------------------------------------------------------


def is_logged_in(page: Page) -> bool:
    """Logged in = the KEIS nav bar title is visible (confirmed from a real
    screenshot of the logged-in dashboard) and the URL isn't a login page."""
    try:
        if "login" in page.url.lower():
            return False
        return page.get_by_text("KEIS凱璿業務系統").first.is_visible(timeout=1000)
    except Exception:
        return False


def login(page: Page) -> None:
    page.goto(BASE_URL)
    page.wait_for_timeout(1000)
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

    ok = auth.wait_for_manual_login(
        page,
        is_logged_in,
        prompt="請在瀏覽器視窗中手動登入 KEIS 內部系統。",
        timeout_s=1800,
    )
    if not ok:
        raise RuntimeError("KEIS 登入逾時，請重新執行程式再試一次。")


def list_cases(page: Page) -> list[dict]:
    """Go to 案件查詢 (體系案件列表) and collect {title, url} for every case row."""
    page.goto(f"{BASE_URL}/case")
    page.wait_for_load_state("networkidle")
    links = page.locator(SEL_CASE_ROW_LINK).all()
    cases = []
    for link in links:
        href = link.get_attribute("href")
        if not href:
            continue
        url = href if href.startswith("http") else f"{BASE_URL}{href}"
        title = link.inner_text().strip() or url
        cases.append({"title": title, "url": url})
    return cases


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


def prompt_case_selection(cases: list[dict]) -> list[dict]:
    """Print a numbered list of cases and ask which ones to post to 591."""
    if not cases:
        print("[keis] 案件管理裡沒有找到任何案件。")
        return []

    print("\n在 KEIS 案件管理裡找到以下案件：")
    for i, case in enumerate(cases, start=1):
        print(f"  {i}. {case['title']}")

    raw = input(
        "\n請輸入要上架到 591 的案件編號（例如 1 或 1,3,5），"
        "或輸入 all 選全部，直接按 Enter 取消：\n> "
    ).strip()

    if not raw:
        return []
    if raw.lower() == "all":
        return cases

    selected = []
    for part in raw.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        idx = int(part) - 1
        if 0 <= idx < len(cases):
            selected.append(cases[idx])
    return selected


def choose_and_fetch_listings(headless: bool = False, chooser=prompt_case_selection) -> list[Listing]:
    """Log into KEIS, let you pick which case(s) to post, and scrape them.

    `chooser(cases) -> selected_cases` defaults to an interactive CLI
    prompt so you never accidentally push every case in the system to 591.
    """
    photo_dir = Path(__file__).resolve().parent.parent / "downloads" / "photos"

    with sync_playwright() as p:
        context, page = auth.open_context(p, SESSION_NAME, headless=headless)
        login(page)
        auth.save_session(context, SESSION_NAME)

        cases = list_cases(page)
        selected = chooser(cases)
        if not selected:
            print("[keis] 沒有選擇任何案件，結束。")
            context.close()
            return []

        print(f"[keis] 已選 {len(selected)} 筆案件，開始抓取資料與照片...")
        listings = []
        for case in selected:
            try:
                listings.append(scrape_case(page, case["url"], photo_dir))
                print(f"[keis] 已抓取：{case['title']}")
            except Exception as e:
                print(f"[keis] 抓取失敗 {case['title']}: {e}")

        context.close()
        return listings
