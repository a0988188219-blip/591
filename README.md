# 591 賣屋自動上架工具

用 Excel 表格或公司內部系統(KEIS)的物件資料，自動幫你把「賣屋」物件填進 591 的刊登表單、上傳照片，並可選擇自動送出。

## 設計上的安全考量（請先讀）

- **不會自動破解或略過驗證碼/簡訊驗證**。跳出驗證步驟時程式會暫停，等你在跳出的瀏覽器視窗手動完成。
- **預設不會真的送出刊登**（乾跑模式）：表單填好、照片上傳好後停在確認頁，你自己檢查沒問題再手動按送出；要讓程式自動送出，需明確加上 `--publish`。
- **帳密不會寫進程式碼或存進 git**：只從本機 `.env` 讀取（`.gitignore` 已排除），或者用「記住登入」模式（見下方）完全不用輸入密碼給程式。
- **KEIS 是公司內網系統，只能在公司電腦（連公司網路）執行**，雲端環境連不到。

## 安裝（在公司電腦上執行）

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

`.env` 有兩種用法，選一種就好：

- **不填帳密**（建議）：第一次執行時瀏覽器會跳出來，你自己手動登入 591 / KEIS 一次，之後程式會記住登入狀態（存在 `.auth/` 資料夾），下次不用再登入。
- **填帳密**：程式會自動幫你打帳號密碼（遇到驗證碼還是要你手動完成）。

## 使用方式

### 方式一：Excel 資料來源（不依賴內網，最穩定）

```bash
# 1. 產生範本
python main.py template

# 2. 打開 data/listings_template.xlsx 填入物件資料
#    photos 欄位放照片的本機路徑，多張用分號 ; 分隔

# 3. 乾跑：填好表單、上傳照片，但不送出，你自己確認
python main.py post --source excel --file data/listings_template.xlsx

# 4. 確認沒問題後，自動送出
python main.py post --source excel --file data/listings_template.xlsx --publish
```

### 方式二：直接從 KEIS 內網系統抓案件資料上架

**只能在公司電腦（連得到 keis.kshouse.com.tw）執行：**

```bash
python main.py post --source keis --publish
```

程式會登入 KEIS → 進「案件管理」→ 逐筆抓案件資料與照片 → 自動上架到 591。

## 目前狀態：選擇器需要你幫忙校正

我沒辦法從目前的雲端環境連到 `keis.kshouse.com.tw` 或 `591.com.tw`（網路權限擋掉了），所以：

- `src/keis_scraper.py` 和 `src/house591_poster.py` 裡的欄位選擇器（`SEL_...` 開頭的常數）是根據一般網站常見寫法猜的，**很可能跟實際頁面對不上**。
- 你在公司電腦第一次執行時，用 `--headless` **不要**加（預設就是有視窗），親眼看程式跑到哪裡卡住。
- 卡住時，把當下的錯誤訊息，或是在瀏覽器按 F12 開發者工具、對著卡住的欄位按右鍵「檢查」複製一段 HTML，回饋給我，我就能把對應的 `SEL_...` 改成正確的值。

這是最後一哩路，通常抓 2-3 個真實案例校正一輪就會穩定下來。

## 專案結構

```
main.py                CLI 入口
src/models.py           物件資料結構 (Listing)
src/excel_source.py     從 Excel 讀取物件資料 / 產生範本
src/keis_scraper.py     登入 KEIS 內網、抓案件資料與照片
src/house591_poster.py  登入 591、填表單、上傳照片、送出刊登
src/auth.py             瀏覽器登入狀態管理（記住登入 / 等待手動登入）
data/                   Excel 資料檔案（不會進 git）
.auth/                  儲存的登入 session（不會進 git）
downloads/              從 KEIS 下載的照片（不會進 git）
```
