# 591 賣屋自動上架工具

從公司內部系統(KEIS)取得案件資料與照片，自動幫你把「賣屋」物件填進 591 的刊登表單、上傳照片，並可選擇自動送出。也支援 Excel 作為備用資料來源。

登入跟頁面導覽（KEIS 選案件、591 找到刊登表單）都是你自己手動操作，程式只接手抓資料跟填表單這兩段——因為這兩個網站的畫面沒辦法事先看到、也沒辦法可靠地用程式判斷「有沒有登入成功」，讓你自己操作反而更穩定。

不會寫程式、想直接照著步驟操作的話，請看 [SETUP.md](SETUP.md)。

## 設計上的安全考量（請先讀）

- **不會自動破解或略過驗證碼/簡訊驗證**，也不會用任何方式繞過網站的登入/安全機制。登入跟頁面導覽全部由你手動操作，程式只在你按 Enter 之後才接手。
- **預設不會真的送出刊登**（乾跑模式）：表單填好、照片上傳好後停在畫面上，你自己檢查沒問題再手動按送出；要讓程式自動送出，需明確加上 `--publish`。
- **帳密完全不會經過程式或存進任何檔案**：登入永遠是你自己在瀏覽器裡手動輸入，程式只負責記住登入後的 session（存在 `.auth/` 資料夾，已加入 `.gitignore`），下次不用重新登入。

## 安裝（在公司電腦上執行）

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## 使用方式

### 主要方式：從 KEIS 內網系統抓案件資料上架（預設）

**只能在公司電腦（連得到 keis.kshouse.com.tw）執行：**

```bash
# 乾跑：打開 KEIS → 你自己登入、點到案件詳情、按 Enter → 抓資料與照片
#      → 打開 591 → 你自己登入、導覽到刊登表單、按 Enter → 自動填表單
python main.py post

# 確認流程與資料都沒問題後，最後一步自動送出
python main.py post --publish
```

程式打開 KEIS 的「圖片下載」頁面，你自己登入、點到要上架那筆案件的詳情頁，回到終端機按 Enter，程式就抓取該案件的資料與照片；可以重複選多筆。抓完後程式打開 591，你自己登入、導覽到「刊登賣屋」表單頁，按 Enter，程式自動填表單、上傳照片。

### 備用方式：Excel 資料來源（不依賴內網）

```bash
# 1. 產生範本
python main.py template

# 2. 打開 data/listings_template.xlsx 填入物件資料
#    photos 欄位放照片的本機路徑，多張用分號 ; 分隔

# 3. 乾跑
python main.py post --source excel --file data/listings_template.xlsx

# 4. 確認沒問題後，自動送出
python main.py post --source excel --file data/listings_template.xlsx --publish
```

## 目前狀態：欄位選擇器需要你幫忙校正

我沒辦法從目前的雲端環境連到 `keis.kshouse.com.tw` 或 `591.com.tw`（網路權限擋掉了），所以：

- `src/keis_scraper.py` 裡讀取案件欄位（地址、坪數、房廳衛等）的邏輯，跟 `src/house591_poster.py` 裡填 591 表單欄位的選擇器（`SEL_...` 開頭的常數），都還是根據猜測或單一截圖寫的，**很可能跟實際頁面對不上**。
- 登入跟導覽已經改成你手動操作，程式只在「抓資料」「填表單」這兩段自動化，所以出錯時問題會更容易定位在哪個欄位。
- 某個欄位抓錯或填不進去時，把那頁的網址、以及在瀏覽器按 F12 開發者工具對著那個欄位按右鍵「檢查」複製一段 HTML，回饋給我，我就能把對應的選擇器改成正確的值。

## 專案結構

```
main.py                CLI 入口
src/models.py           物件資料結構 (Listing)
src/excel_source.py     從 Excel 讀取物件資料 / 產生範本
src/keis_scraper.py     抓 KEIS 案件詳情頁的資料與照片
src/house591_poster.py  在 591 刊登表單頁自動填表、上傳照片、送出刊登
src/auth.py             瀏覽器登入 session 記憶（存檔/還原）
data/                   Excel 資料檔案（不會進 git）
.auth/                  儲存的登入 session（不會進 git）
downloads/              從 KEIS 下載的照片（不會進 git）
```
