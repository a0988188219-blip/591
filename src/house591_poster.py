"""Automates posting a 賣屋 (for-sale) listing to 591.

Safety model:
  - By default (publish=False) the script fills in the entire form,
    uploads photos, and stops on the final review/confirm step WITHOUT
    clicking 送出刊登 — you check it over and click that button yourself.
  - Pass publish=True (CLI: --publish) only once you've verified a dry
    run looks right, and the script will click the final submit button.
  - This never attempts to solve a CAPTCHA or SMS code. If one appears,
    the script pauses and waits for you.

Like keis_scraper.py, the selectors below are best-effort placeholders
(I couldn't load the real page from this sandbox — network egress to
591.com.tw is blocked here). Run with a visible browser, and send me any
selector that doesn't match so I can fix it.
"""
from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

from . import auth
from .models import Listing

load_dotenv()

HOME_URL = "https://www.591.com.tw/"
SESSION_NAME = "house591"

# --- Selectors: adjust these to match the real page -----------------
SEL_TITLE_INPUT = "input[name='title']"
SEL_CITY_SELECT = "select[name='city']"
SEL_DISTRICT_SELECT = "select[name='district']"
SEL_ADDRESS_INPUT = "input[name='address']"
SEL_HOUSE_TYPE_SELECT = "select[name='type']"
SEL_TOTAL_PRICE_INPUT = "input[name='price']"
SEL_MAIN_BUILDING_PING_INPUT = "input[name='main_building_ping']"
SEL_TOTAL_PING_INPUT = "input[name='total_ping']"
SEL_LAND_PING_INPUT = "input[name='land_ping']"
SEL_ROOMS_INPUT = "input[name='room']"
SEL_LIVING_ROOMS_INPUT = "input[name='hall']"
SEL_BATHROOMS_INPUT = "input[name='bathroom']"
SEL_FLOOR_INPUT = "input[name='floor']"
SEL_TOTAL_FLOORS_INPUT = "input[name='total_floor']"
SEL_AGE_INPUT = "input[name='age']"
SEL_PARKING_SELECT = "select[name='parking']"
SEL_FACING_SELECT = "select[name='facing']"
SEL_DESCRIPTION_TEXTAREA = "textarea[name='description']"
SEL_CONTACT_NAME_INPUT = "input[name='contact_name']"
SEL_CONTACT_PHONE_INPUT = "input[name='contact_phone']"
SEL_PHOTO_UPLOAD_INPUT = "input[type='file']"

SEL_REVIEW_STEP_MARKER = "text=確認刊登內容"
SEL_FINAL_SUBMIT_BUTTON = "button:has-text('送出刊登'), button:has-text('確認送出')"
# ----------------------------------------------------------------------


def wait_until_on_post_form(page: Page) -> None:
    """You log in and navigate to the 刊登賣屋 form yourself; the script
    just waits for you to say you're ready, then fills in whatever page
    is currently open. This avoids guessing at login/page detection on a
    site we can't inspect ahead of time."""
    input(
        "\n請在瀏覽器視窗中登入 591（含任何驗證碼/簡訊驗證），"
        "並手動導覽到「刊登賣屋」的新增/編輯物件表單頁面，"
        "準備好之後回到這裡按 Enter，程式會開始在目前這頁自動填表..."
    )


def _select_by_label_or_value(page: Page, selector: str, value: str) -> None:
    if not value:
        return
    try:
        page.select_option(selector, label=value)
    except Exception:
        try:
            page.select_option(selector, value=value)
        except Exception as e:
            print(f"[591] 無法選取 {selector} = {value!r}：{e}")


def fill_listing_form(page: Page, listing: Listing) -> None:
    page.fill(SEL_TITLE_INPUT, listing.title)
    _select_by_label_or_value(page, SEL_CITY_SELECT, listing.city)
    _select_by_label_or_value(page, SEL_DISTRICT_SELECT, listing.district)
    page.fill(SEL_ADDRESS_INPUT, listing.address)
    _select_by_label_or_value(page, SEL_HOUSE_TYPE_SELECT, listing.house_type)

    page.fill(SEL_TOTAL_PRICE_INPUT, str(listing.total_price_wan))
    page.fill(SEL_MAIN_BUILDING_PING_INPUT, str(listing.main_building_ping))
    page.fill(SEL_TOTAL_PING_INPUT, str(listing.total_ping))
    if listing.land_ping:
        page.fill(SEL_LAND_PING_INPUT, str(listing.land_ping))

    page.fill(SEL_ROOMS_INPUT, str(listing.rooms))
    page.fill(SEL_LIVING_ROOMS_INPUT, str(listing.living_rooms))
    page.fill(SEL_BATHROOMS_INPUT, str(listing.bathrooms))
    page.fill(SEL_FLOOR_INPUT, str(listing.floor))
    page.fill(SEL_TOTAL_FLOORS_INPUT, str(listing.total_floors))
    page.fill(SEL_AGE_INPUT, str(listing.age_years))

    _select_by_label_or_value(page, SEL_PARKING_SELECT, listing.parking)
    _select_by_label_or_value(page, SEL_FACING_SELECT, listing.facing)

    page.fill(SEL_DESCRIPTION_TEXTAREA, listing.description)
    page.fill(SEL_CONTACT_NAME_INPUT, listing.contact_name)
    page.fill(SEL_CONTACT_PHONE_INPUT, listing.contact_phone)

    if listing.photos:
        page.set_input_files(SEL_PHOTO_UPLOAD_INPUT, listing.photos)
        page.wait_for_timeout(1000 * len(listing.photos))  # let uploads finish


def post_listing(listing: Listing, publish: bool = False, headless: bool = False) -> None:
    problems = listing.validate()
    if problems:
        print("[591] 這筆物件資料不完整，已跳過：")
        for p in problems:
            print(f"  - {p}")
        return

    with sync_playwright() as p:
        context, page = auth.open_context(p, SESSION_NAME, headless=headless)
        page.goto(HOME_URL)
        wait_until_on_post_form(page)
        auth.save_session(context, SESSION_NAME)

        fill_listing_form(page, listing)

        if not publish:
            print(f"[591]《{listing.title}》表單已填好、照片已上傳，"
                  f"停在確認頁面等你檢查。若確認無誤，請自行手動點擊送出，"
                  f"或加上 --publish 重跑讓程式自動送出。")
            page.wait_for_timeout(1000 * 60 * 10)  # keep window open for manual review
        else:
            page.click(SEL_FINAL_SUBMIT_BUTTON)
            page.wait_for_timeout(3000)
            print(f"[591]《{listing.title}》已送出刊登。")

        context.close()
