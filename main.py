"""CLI entry point for 591 自動上架.

Examples:
  # 1) 先產生 Excel 範本，填好物件資料
  python main.py template

  # 2) 用 Excel 資料，乾跑模式（填好表單但不送出，你自己確認後手動送出）
  python main.py post --source excel --file data/listings.xlsx

  # 3) 確認沒問題後，加 --publish 讓程式自動送出
  python main.py post --source excel --file data/listings.xlsx --publish

  # 4) 從公司內網 KEIS 系統抓案件資料直接上架（只能在公司電腦跑）
  python main.py post --source keis --publish
"""
import argparse
from pathlib import Path

from src.excel_source import create_template, load_listings
from src.house591_poster import post_listing


def cmd_template(args):
    path = Path(args.file)
    path.parent.mkdir(parents=True, exist_ok=True)
    create_template(path)
    print(f"已建立範本：{path}\n請打開填入物件資料（photos 欄位用分號 ; 分隔多張照片路徑）。")


def cmd_post(args):
    if args.source == "excel":
        if not args.file:
            raise SystemExit("請用 --file 指定 Excel 檔案路徑")
        listings = load_listings(args.file)
    elif args.source == "keis":
        from src.keis_scraper import fetch_listings
        listings = fetch_listings(headless=args.headless)
    else:
        raise SystemExit(f"未知的資料來源: {args.source}")

    print(f"共讀到 {len(listings)} 筆物件。")
    for listing in listings:
        post_listing(listing, publish=args.publish, headless=args.headless)


def main():
    parser = argparse.ArgumentParser(description="591 賣屋自動上架工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_template = sub.add_parser("template", help="產生 Excel 物件資料範本")
    p_template.add_argument("--file", default="data/listings_template.xlsx")
    p_template.set_defaults(func=cmd_template)

    p_post = sub.add_parser("post", help="讀取物件資料並上架到 591")
    p_post.add_argument("--source", choices=["excel", "keis"], required=True)
    p_post.add_argument("--file", help="Excel 檔案路徑（--source excel 時必填）")
    p_post.add_argument("--publish", action="store_true",
                         help="自動點擊最終送出（預設只填表單，停在確認頁）")
    p_post.add_argument("--headless", action="store_true",
                         help="不顯示瀏覽器視窗（首次使用/需手動登入時不建議開啟）")
    p_post.set_defaults(func=cmd_post)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
