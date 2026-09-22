"""Scraper for the KEIS (凱璿/永慶) internal case-management system.

IMPORTANT — this only works when run from a machine on your company
network / VPN, since keis.kshouse.com.tw is an internal (內網) site.

You drive the browser: log in and open the 案件詳情 (CASE STUDY) popup
for whichever case you want to post, however you normally would (案件
管理 → 圖片下載 → 詳情). The script waits for you to press Enter once
that popup is open, then:
  1. reads every 案件詳情 field directly (label/value pairs are a fixed,
     consistent layout — confirmed from a real popup's HTML)
  2. closes the popup
  3. finds that same case's row in the list (matched by 合約編號) and
     clicks its 照片 button, which downloads a ZIP of all the photos,
     then unzips it locally
"""
import os
import re
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

from . import auth
from .models import Listing

load_dotenv()

BASE_URL = os.getenv("KEIS_BASE_URL", "https://keis.kshouse.com.tw")
SESSION_NAME = "keis"

DEFAULT_CONTACT_NAME = "顏秀珊"
DEFAULT_CONTACT_PHONE = "0913-335-182"


def _read_detail_fields(page: Page) -> dict:
    """Read every label→value pair in the open 案件詳情 popup."""
    fields = {}
    for item in page.locator(".cs-field-item").all():
        label = item.locator(".cs-field-label").inner_text().strip()
        try:
            value = item.locator(".cs-field-value").inner_text().strip()
        except Exception:
            value = ""
        fields[label] = value
    return fields


def _read_highlights(page: Page) -> str:
    """The 訴求重點 bullet points, joined into one description."""
    rows = page.locator(".cs-feature-row").all_inner_texts()
    return "\n".join(r.strip() for r in rows if r.strip())


def _clean(s: str) -> str:
    """KEIS shows '—' for an empty field — treat that as blank."""
    s = (s or "").strip()
    return "" if s in ("—", "-", "–") else s


def _to_float(s: str, default: float = 0.0) -> float:
    s = _clean(s)
    if not s:
        return default
    try:
        return float("".join(c for c in s if c.isdigit() or c == "."))
    except ValueError:
        return default


def _split_address(addr: str) -> tuple[str, str, str]:
    """'高雄市鳳山區崗山北街11巷30號' -> ('高雄市', '鳳山區', '崗山北街11巷30號')"""
    m = re.match(r"^(\S+?[市縣])(\S+?[鄉鎮市區])(.*)$", addr or "")
    if m:
        return m.group(1), m.group(2), m.group(3)
    return "", "", addr or ""


def _parse_layout(s: str) -> tuple[int, int, int]:
    """'3房2廳4衛' -> (3, 2, 4)"""
    m = re.match(r"(\d+)房(\d+)廳(\d+)衛", s or "")
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return 0, 0, 0


def _parse_floor(s: str) -> tuple[int, int]:
    """'1～2 樓（共 2 層）' -> (1, 2)　　'8F/15F' -> (8, 15)"""
    s = s or ""
    total_match = re.search(r"共\s*(\d+)\s*層", s)
    total = int(total_match.group(1)) if total_match else 0
    nums = re.findall(r"\d+", s)
    floor = int(nums[0]) if nums else 0
    if not total and len(nums) >= 2:
        total = int(nums[1])
    return floor, total


def download_case_photos(page: Page, contract_no: str, dest_dir: Path) -> list[str]:
    """Click the 照片 button for the row matching contract_no, which
    downloads a ZIP of all photos, then unzip it locally."""
    if not contract_no:
        print("[keis] 沒有合約編號，無法找到對應的照片下載按鈕。")
        return []

    dest_dir.mkdir(parents=True, exist_ok=True)
    row = page.locator(".table-row").filter(
        has=page.locator(f"code.contract-code:text-is('{contract_no}')")
    )
    photo_button = row.locator("button:has-text('照片')")

    try:
        with page.expect_download(timeout=15000) as dl_info:
            photo_button.click()
        download = dl_info.value
    except Exception as e:
        print(f"[keis] 下載照片失敗：{e}")
        return []

    zip_path = dest_dir / f"{contract_no}.zip"
    download.save_as(str(zip_path))

    extract_dir = dest_dir / contract_no
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile as e:
        print(f"[keis] 解壓縮照片失敗：{e}")
        return []
    finally:
        zip_path.unlink(missing_ok=True)

    return [str(p) for p in sorted(extract_dir.rglob("*")) if p.is_file()]


def scrape_case(page: Page, photo_dir: Path) -> Listing:
    """Read the currently-open 案件詳情 popup into a Listing, then close
    it and download that case's photos."""
    page.wait_for_selector(".cs-overlay", timeout=5000)
    fields = _read_detail_fields(page)
    description = _read_highlights(page)

    contract_no = fields.get("合約編號", "")

    page.locator(".cs-btn-close").click()
    page.wait_for_selector(".cs-overlay", state="hidden", timeout=5000)

    photos = download_case_photos(page, contract_no, photo_dir)

    city, district, address = _split_address(_clean(fields.get("物件座落", "")))
    rooms, living_rooms, bathrooms = _parse_layout(fields.get("隔局", ""))
    floor, total_floors = _parse_floor(fields.get("樓層", ""))

    land_ping = _to_float(fields.get("地坪", "")) or _to_float(fields.get("土地總坪數(整筆)", "")) or None

    return Listing(
        title=fields.get("案名", ""),
        city=city,
        district=district,
        address=address,
        house_type=re.sub(r"^[A-Za-z]\.", "", _clean(fields.get("建築型態", ""))),
        total_price_wan=_to_float(fields.get("總價款", "")),
        main_building_ping=_to_float(fields.get("主建物面積", "")),
        total_ping=_to_float(fields.get("登記面積(含車位)", "")) or _to_float(fields.get("建物面積", "")),
        land_ping=land_ping,
        rooms=rooms,
        living_rooms=living_rooms,
        bathrooms=bathrooms,
        floor=floor,
        total_floors=total_floors,
        age_years=_to_float(fields.get("屋齡", "")),
        parking=_clean(fields.get("車位類型", "")),
        facing=_clean(fields.get("朝向（落地窗／住家門）", "")),
        description=description,
        contact_name=DEFAULT_CONTACT_NAME,
        contact_phone=DEFAULT_CONTACT_PHONE,
        photos=photos,
        extra={"合約編號": contract_no},
    )


def pick_and_scrape_cases(headless: bool = False) -> list[Listing]:
    """Open KEIS and let you manually drive to each case you want to post.

    You log in and open a case's 案件詳情 popup yourself; the script waits
    for you to press Enter here, then scrapes it and downloads its photos.
    Repeat for as many cases as you want in one run.
    """
    photo_dir = Path(__file__).resolve().parent.parent / "downloads" / "photos"
    listings = []

    with sync_playwright() as p:
        context, page = auth.open_context(p, SESSION_NAME, headless=headless)
        page.goto(f"{BASE_URL}/internal-properties")

        while True:
            input(
                "\n請在瀏覽器視窗中登入 KEIS（如果還沒登入），"
                "在「案件管理 → 圖片下載」頁面點開你要上架那筆案件的「詳情」彈窗，"
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
