"""Prepares a 591 賣屋 listing for you to paste in manually.

591 blocks the automated browser Playwright launches — confirmed by
testing: the same login page that loads fine in your everyday browser
stays blank in the one this script opens. That looks like anti-bot
protection on 591's side, and this script does not try to disguise
itself or bypass it, even for your own account.

So instead of automatically filling in 591's form, this turns a
scraped Listing into a clean, ready-to-copy summary (also saved to a
text file) and tells you where its photos are, so pasting everything
into 591 — in your normal browser — is quick.
"""
from pathlib import Path

from .models import Listing

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "downloads" / "listings"


def format_summary(listing: Listing) -> str:
    lines = [
        f"標題：{listing.title}",
        f"地址：{listing.city}{listing.district}{listing.address}",
        f"物件類型：{listing.house_type or '（無資料，請自行選擇）'}",
        f"總價：{listing.total_price_wan} 萬",
        f"主建物坪數：{listing.main_building_ping} 坪",
        f"權狀總坪數：{listing.total_ping} 坪",
    ]
    if listing.land_ping:
        lines.append(f"土地坪數：{listing.land_ping} 坪")
    lines += [
        f"格局：{listing.rooms} 房 {listing.living_rooms} 廳 {listing.bathrooms} 衛",
        f"樓層：{listing.floor} / {listing.total_floors} 樓",
        f"屋齡：{listing.age_years} 年",
        f"車位：{listing.parking or '（無資料）'}",
        f"朝向：{listing.facing or '（無資料）'}",
        "",
        "物件描述：",
        listing.description or "（無）",
        "",
        f"聯絡人：{listing.contact_name}",
        f"聯絡電話：{listing.contact_phone}",
        "",
        f"照片（共 {len(listing.photos)} 張）存放於：",
        str(Path(listing.photos[0]).parent) if listing.photos else "（沒有照片）",
    ]
    return "\n".join(lines)


def output_listing(listing: Listing) -> Path:
    """Print + save a copy-paste-ready summary. Doesn't touch 591 at all."""
    problems = listing.validate()
    if problems:
        print(f"[591] 提醒：《{listing.title}》這筆資料可能不完整：")
        for p in problems:
            print(f"  - {p}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_name = listing.extra.get("合約編號") or listing.title or "listing"
    safe_name = "".join(c for c in raw_name if c not in '\\/:*?"<>|').strip() or "listing"
    out_path = OUTPUT_DIR / f"{safe_name}.txt"

    summary = format_summary(listing)
    out_path.write_text(summary, encoding="utf-8")

    print(f"\n===== 591 上架資料：{listing.title} =====")
    print(summary)
    print(f"===== 以上內容已存成檔案：{out_path} =====\n")
    return out_path
