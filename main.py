"""CLI entry point for 591 自動上架.

Examples:
  # 最常用：登入 KEIS，挑一筆案件，抓資料跟照片，填進 591 表單（乾跑，不自動送出）
  python main.py post

  # 確認表單沒問題後，加 --publish 讓程式自動送出
  python main.py post --publish

  # 備用：改用 Excel 表格當資料來源（不需要連 KEIS）
  python main.py template
  python main.py post --source excel --file data/listings.xlsx
"""
import argparse

from src.house591_poster import post_listing


def cmd_template(args):
    from pathlib import Path
    from src.excel_source import create_template

    path = Path(args.file)
    path.parent.mkdir(parents=True, exist_ok=True)
    create_template(path)
    print(f"已建立範本：{path}\n請打開填入物件資料（photos 欄位用分號 ; 分隔多張照片路徑）。")


def cmd_post(args):
    if args.source == "keis":
        from src.keis_scraper import pick_and_scrape_cases
        listings = pick_and_scrape_cases(headless=args.headless)
    elif args.source == "excel":
        from src.excel_source import load_listings
        if not args.file:
            raise SystemExit("請用 --file 指定 Excel 檔案路徑")
        listings = load_listings(args.file)
    else:
        raise SystemExit(f"未知的資料來源: {args.source}")

    if not listings:
        print("沒有物件資料可以上架。")
        return

    print(f"共 {len(listings)} 筆物件準備上架到 591。")
    for listing in listings:
        post_listing(listing, publish=args.publish, headless=args.headless)


def main():
    parser = argparse.ArgumentParser(description="591 賣屋自動上架工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_template = sub.add_parser("template", help="（備用）產生 Excel 物件資料範本")
    p_template.add_argument("--file", default="data/listings_template.xlsx")
    p_template.set_defaults(func=cmd_template)

    p_post = sub.add_parser("post", help="讀取物件資料並上架到 591")
    p_post.add_argument("--source", choices=["keis", "excel"], default="keis",
                         help="資料來源，預設從 KEIS 內網系統登入抓取")
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
