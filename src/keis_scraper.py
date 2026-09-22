"""Scraper for the KEIS (凱璿/永慶) internal case-management system.

IMPORTANT — this only works when run from a machine on your company
network / VPN, since keis.kshouse.com.tw is an internal (內網) site.

You drive the browser: log in and navigate to whichever case's 詳情頁
you want to post, however you normally would (click 案件管理 → 案件查詢
→ the case). The script doesn't try to detect login state or find case
links itself — it just waits for you to press Enter in this terminal
once you're looking at the page you want scraped, then reads whatever
page is currently open.

The field selectors in scrape_case() are best-effort placeholders based
on a real screenshot of one case, but will likely need small adjustments
for other case layouts — if a field comes out empty, tell me and send
the relevant bit of the page's HTML (right-click the field → 檢查 →
copy outerHTML) and I'll fix the selector.
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
SEL_CASE_TITLE = "h1, .case-title"
SEL_PHOTO_DOWNLOAD_LINK = "a:has-text('下載'), a[href*='/photo']"
# ----------------------------------------------------------------------


def download_case_photos(page: Page, dest_dir: Path) -> list[str]:
    """Download every photo attached to the current case detail page."""
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


def scrape_case(page: Page, photo_dir: Path) -> Listing:
    """Read whatever case detail page is currently open into a Listing.

    NOTE: field extraction assumes a simple label→value layout. If a
    field comes out wrong or empty, send me the page's HTML for that
    field and I'll swap in an exact selector.
    """
    page.wait_for_load_state("networkidle")

    def field_text(label: str, default: str = "") -> str:
        try:
            row = page.locator(f"text={label}").first
            value = row.locator("xpath=following-sibling::*[1]").first
            return value.inner_text(timeout=2000).strip()
        except Exception:
            return default

    photos = download_case_photos(page, photo_dir)

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


def pick_and_scrape_cases(headless: bool = False) -> list[Listing]:
    """Open KEIS and let you manually drive to each case you want to post.

    You log in and click through to a case's 詳情頁 yourself; the script
    waits for you to press Enter here, then scrapes whatever page is
    currently open. Repeat for as many cases as you want in one run.
    """
    photo_dir = Path(__file__).resolve().parent.parent / "downloads" / "photos"
    listings = []

    with sync_playwright() as p:
        context, page = auth.open_context(p, SESSION_NAME, headless=headless)
        page.goto(f"{BASE_URL}/internal-properties")

        while True:
            input(
                "\n請在瀏覽器視窗中登入 KEIS（如果還沒登入），"
                "在「案件管理 → 圖片下載」頁面點到你要上架那筆案件的「詳情」，"
                "準備好之後回到這裡按 Enter 繼續..."
            )
            try:
                listing = scrape_case(page, photo_dir)
                listings.append(listing)
                print(f"[keis] 已抓取：{listing.title}（{len(listing.photos)} 張照片）")
            except Exception as e:
                print(f"[keis] 抓取這筆案件時發生錯誤：{e}")
                print("[keis] 如果欄位抓錯或抓不到，把這頁的網址跟哪個欄位有問題告訴我。")

            more = input("還要選下一筆案件嗎？(y/n，直接按 Enter 視為 n)：").strip().lower()
            if more != "y":
                break

        auth.save_session(context, SESSION_NAME)
        context.close()

    return listings
