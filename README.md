# 591 租屋爬蟲通知系統

自動爬取 591 租屋網新物件，根據訂閱條件比對後推播 Telegram 通知。

## 功能特色

- 自動定時爬取 591 租屋列表
- 支援多條件訂閱篩選（區域、價格、坪數、格局等）
- Telegram 即時推播通知
- **新增訂閱或開啟通知時，立即檢查並推播符合條件的物件**
- 平台無關的指令系統（未來可擴充 LINE、Discord）
- JWT 身份驗證
- 白天/夜間不同爬取間隔
- 一鍵部署腳本

## 系統架構

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   591 網站   │────▶│   Crawler   │────▶│  PostgreSQL │
└─────────────┘     └─────────────┘     └─────────────┘
                          │                    │
                          ▼                    ▼
                   ┌─────────────┐     ┌─────────────┐
                   │    Redis    │◀───▶│   Checker   │
                   └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │  Telegram   │
                                       └─────────────┘
```

## 執行流程

### 定時爬取流程（ETL）

```
排程器觸發
    ↓
查詢 Redis 取得有訂閱的區域
    ↓
對每個區域執行 ETL Pipeline：
    ↓
┌─────────────────────────────────────────────────────────┐
│ 1. Extract - 列表頁                                      │
│    └─ BS4 解析 → ListRawData（失敗則通知管理員）         │
│ 2. Redis 過濾                                            │
│    └─ 比對已爬取 ID，找出新物件                          │
│ 3. Extract - 詳情頁（有備援機制）                        │
│    └─ BS4 重試 → Playwright fallback → DetailRawData    │
│ 4. Combine - 合併原始資料                                │
│    └─ ListRawData + DetailRawData → CombinedRawData     │
│    └─ layout 只從 Detail 取得（含廳/衛資訊）             │
│ 5. Transform - 轉換為 DB 格式                            │
│    └─ CombinedRawData → DBReadyData                     │
│ 6. Load - 儲存                                           │
│    └─ 存入 PostgreSQL + Redis                           │
│ 7. 訂閱比對 & 推播通知                                   │
│    └─ 根據訂閱條件匹配，發送 Telegram 通知               │
└─────────────────────────────────────────────────────────┘
```

**排程設定**（可透過環境變數調整）：

- 白天：每 15 分鐘 (`CRAWLER_INTERVAL_MINUTES`)
- 夜間：每 60 分鐘 (`CRAWLER_NIGHT_INTERVAL_MINUTES`)
- 夜間時段：01:00-08:00 (`CRAWLER_NIGHT_START_HOUR`, `CRAWLER_NIGHT_END_HOUR`)

### 備援機制

| 階段       | 主要方式      | 備援方式              |
| ---------- | ------------- | --------------------- |
| 列表頁爬取 | BS4 解析      | 通知管理員（無備援）  |
| 詳情頁爬取 | BS4 解析 × 3  | Playwright 瀏覽器抓取 |

> 詳情頁會先用 BS4 嘗試最多 3 次，若仍失敗或回傳空標籤，則自動降級為 Playwright 抓取

### 即時通知流程

當用戶**新增訂閱**或**開啟通知**時，系統會立即檢查並推播：

```
新增訂閱 / 開啟通知
    ↓
檢查該區域是否有人訂閱過
    ├─ 有 → 從資料庫撈最新 10 筆該區域物件
    └─ 無 → 爬取 10 筆並存入資料庫
    ↓
比對訂閱條件
    ↓
推播符合的物件給用戶
```

---

## 快速開始（Docker 部署）

### 首次部署

```bash
# Clone 專案
git clone <repo-url>
cd 591-crawler

# 一鍵部署
./deploy.sh
```

腳本會自動：

1. 建立 `.env` 設定檔（需手動編輯）
2. 啟動 PostgreSQL、Redis、App 容器
3. 執行資料庫 migrations

### 更新部署

```bash
# 一鍵更新（自動 git pull + migration + 重啟）
./deploy.sh
```

### 部署指令

```bash
./deploy.sh           # 自動偵測（首次/更新）
./deploy.sh init      # 強制首次部署
./deploy.sh update    # 強制更新模式
./deploy.sh migrate   # 只執行 migration
```

---

## 本地開發

### 環境需求

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- uv (Python 套件管理)

### 安裝

```bash
# 安裝依賴
uv sync

# 安裝 Playwright 瀏覽器
uv run playwright install chromium
```

### 設定環境變數

```bash
cp .env.example .env
# 編輯 .env 填入設定
```

### 啟動服務

```bash
# 啟動 PostgreSQL & Redis（使用 Docker）
docker compose up -d postgres redis

# 執行 migrations
./deploy.sh migrate

# 啟動 API 服務
uv run uvicorn src.api.main:app --reload
```

### 手動測試爬蟲

```bash
# 測試列表爬蟲
python scripts/test_list_bs4.py --region 1 --limit 5
python scripts/test_list_playwright.py --region 1 --limit 5

# 測試詳情爬蟲
python scripts/test_detail_bs4.py <object_id>
python scripts/test_detail_playwright.py <object_id>
```

---

## 環境變數

| 變數                             | 說明                                 | 預設值    |
| -------------------------------- | ------------------------------------ | --------- |
| `PG_HOST`                        | PostgreSQL 主機                      | localhost |
| `PG_PORT`                        | PostgreSQL 埠號                      | 5432      |
| `PG_USER`                        | PostgreSQL 使用者                    | postgres  |
| `PG_PASSWORD`                    | PostgreSQL 密碼                      | postgres  |
| `PG_DATABASE`                    | PostgreSQL 資料庫                    | rent591   |
| `PG_POOL_MAX`                    | PostgreSQL 連線池最大數              | 10        |
| `REDIS_HOST`                     | Redis 主機                           | localhost |
| `REDIS_PORT`                     | Redis 埠號                           | 6379      |
| `APP_PORT`                       | API 服務埠號                         | 8000      |
| `WEB_APP_URL`                    | 前台網址                             | -         |
| `TELEGRAM_BOT_TOKEN`             | Telegram Bot Token                   | -         |
| `TELEGRAM_BOT_USERNAME`          | Telegram Bot 使用者名稱              | -         |
| `TELEGRAM_WEBHOOK_URL`           | Telegram Webhook URL                 | -         |
| `TELEGRAM_ADMIN_ID`              | 管理員 ID（錯誤通知用，可選）        | -         |
| `JWT_SECRET`                     | JWT 密鑰                             | -         |
| `CRAWLER_INTERVAL_MINUTES`       | 白天爬取間隔（分鐘），間隔式排程     | 15        |
| `CRAWLER_NIGHT_INTERVAL_MINUTES` | 夜間爬取間隔（分鐘），固定時間點     | 60        |
| `CRAWLER_NIGHT_START_HOUR`       | 夜間開始時間                         | 1         |
| `CRAWLER_NIGHT_END_HOUR`         | 夜間結束時間                         | 8         |
| `CORS_ORIGINS`                   | CORS 允許來源                        | \*        |

> **排程說明**
>
> - 白天（08:00-01:00）：間隔式排程，每 X 分鐘執行一次（相對時間）
> - 夜間（01:00-08:00）：固定時間點，例如 60 分鐘 = 每小時整點執行

---

## Telegram Bot 指令

| 指令     | 別名       | 說明         |
| -------- | ---------- | ------------ |
| `/start` | -          | 開始使用     |
| -        | `幫助`     | 顯示使用說明 |
| -        | `清單`     | 查看訂閱清單 |
| -        | `指令`     | 顯示可用指令 |
| -        | `開始通知` | 恢復接收通知 |
| -        | `暫停通知` | 暫停接收通知 |

> 中文指令不需要加 `/`，直接輸入即可（例如：`幫助`、`清單`）
>
> 綁定帳號請透過 Telegram Web App 登入，點擊「開啟管理頁面」按鈕即可

---

## API 文件

詳細 API 說明請參考 [docs/API.md](docs/API.md)

### 快速參考

| 模組     | 端點                        | 說明                        |
| -------- | --------------------------- | --------------------------- |
| 認證     | `POST /auth/telegram`       | Telegram Web App 登入       |
| 使用者   | `GET /users/me`             | 取得個人資料                |
| 訂閱     | `GET /subscriptions`        | 列出所有訂閱                |
|          | `POST /subscriptions`       | 新增訂閱（含即時通知）      |
|          | `PATCH .../toggle`          | 啟用/停用訂閱               |
| 綁定     | `PATCH /bindings/telegram/toggle` | 啟用/停用通知（含即時通知） |
| 健康檢查 | `GET /health`               | 健康檢查                    |

---

## 訂閱條件參考

| 條件     | 欄位              | 類型  | 說明                                   |
| -------- | ----------------- | ----- | -------------------------------------- |
| 區域     | `region`          | int   | 1=台北市, 3=新北市                     |
| 區段     | `section`         | int[] | 區域代碼陣列                           |
| 類型     | `kind`            | int[] | 1=整層, 2=獨立套房, 3=分租套房, 4=雅房 |
| 最低租金 | `price_min`       | int   | 價格下限                               |
| 最高租金 | `price_max`       | int   | 價格上限                               |
| 最小坪數 | `area_min`        | float | 坪數下限                               |
| 最大坪數 | `area_max`        | float | 坪數上限                               |
| 格局     | `layout`          | int[] | 1=1房, 2=2房, 3=3房, 4=4房以上         |
| 建物型態 | `shape`           | int[] | 1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅   |
| 樓層     | `floor`           | str[] | "1", "2_6", "6_12", "13_"              |
| 衛浴     | `bathroom`        | int[] | 1=1衛, 2=2衛, 3=3衛, 4=4衛以上         |
| 裝潢     | `fitment`         | int[] | 99=新裝潢, 3=中檔, 4=高檔              |
| 特色     | `other`           | str[] | near_subway, pet, cook, lift 等        |
| 設備     | `options`         | str[] | cold, washer, icebox 等                |
| 排除頂加 | `exclude_rooftop` | bool  | 排除頂樓加蓋                           |
| 性別限制 | `gender`          | str   | boy=限男, girl=限女, null=不限         |
| 需可養寵 | `pet_required`    | bool  | 需要可養寵物                           |

### 比對邏輯

| 類型 | 條件 | 規則 |
| ---- | ---- | ---- |
| 範圍 | 價格、坪數、樓層 | `min ≤ obj ≤ max` |
| 列表 | 類型、區段、建物、格局、衛浴、裝潢 | `obj IN sub`（4=4以上） |
| 子集 | 特色、設備 | `sub ⊆ obj`（全部都要有） |
| 布林 | 排除頂加 | `sub=true` → `obj.is_rooftop=false` |
| 布林 | 需可養寵 | `sub=true` → `obj.pet_allowed≠false` |
| 性別 | 性別限制 | `sub=boy` → `obj=boy/all`<br>`sub=girl` → `obj=girl/all` |

詳細選項代碼請參考 [docs/OPTIONS.md](docs/OPTIONS.md)

---

## 專案結構

```
591-crawler/
├── config/
│   └── settings.py              # 應用程式設定
├── migrations/
│   ├── init.sql                 # 資料庫初始化
│   ├── 002_user_providers.sql   # 用戶 Provider 關聯
│   └── 003_instant_notify_index.sql  # 即時通知索引
├── src/
│   ├── api/
│   │   ├── main.py              # FastAPI 應用程式
│   │   ├── dependencies.py      # 依賴注入
│   │   └── routes/              # API 路由
│   ├── channels/
│   │   ├── commands/            # 平台無關的指令
│   │   │   ├── base.py          # 指令基礎類別
│   │   │   ├── registry.py      # 指令註冊表
│   │   │   ├── start.py         # /start 指令
│   │   │   ├── help.py          # 幫助 指令
│   │   │   ├── list.py          # 清單 指令
│   │   │   ├── notify.py        # 開始通知/暫停通知 指令
│   │   │   ├── status.py        # 狀態 指令
│   │   │   └── command.py       # 指令 指令
│   │   └── telegram/            # Telegram 實作
│   │       ├── bot.py           # Bot 封裝
│   │       ├── handler.py       # 訊息處理
│   │       └── formatter.py     # 訊息格式化
│   ├── connections/
│   │   ├── postgres.py          # PostgreSQL 連線
│   │   └── redis.py             # Redis 連線
│   ├── crawler/
│   │   ├── types.py                  # Raw data 型別定義
│   │   ├── combiner.py               # Raw data 合併
│   │   ├── list_fetcher.py           # 列表爬蟲（自動備援）
│   │   ├── list_fetcher_bs4.py       # BS4 列表爬取+解析
│   │   ├── list_fetcher_playwright.py # Playwright 列表爬取+解析
│   │   ├── detail_fetcher.py         # 詳情爬蟲（自動備援）
│   │   ├── detail_fetcher_bs4.py     # BS4 詳情爬取+解析
│   │   └── detail_fetcher_playwright.py # Playwright 詳情爬取+解析
│   ├── jobs/
│   │   ├── scheduler.py         # 排程器
│   │   ├── checker.py           # 物件比對
│   │   ├── broadcaster.py       # 推播通知
│   │   ├── instant_notify.py    # 即時通知
│   │   └── parser.py            # 資料解析
│   ├── middleware/
│   │   └── cors.py              # CORS 設定
│   ├── modules/
│   │   ├── users/               # 使用者模組
│   │   ├── providers/           # 登入提供者模組 & Redis 同步
│   │   ├── subscriptions/       # 訂閱模組
│   │   └── objects/             # 物件模組
│   └── utils/
│       ├── mappings.py          # 常數對照表
│       └── transformers.py      # ETL Transform 層
├── scripts/
│   ├── test_list_bs4.py         # BS4 列表爬蟲測試
│   ├── test_list_playwright.py  # Playwright 列表爬蟲測試
│   ├── test_detail_bs4.py       # BS4 詳情爬蟲測試
│   └── test_detail_playwright.py # Playwright 詳情爬蟲測試
├── docs/
│   ├── API.md                   # API 文件
│   └── OPTIONS.md               # 訂閱條件選項
├── .env.example                 # 環境變數範本
├── deploy.sh                    # 部署腳本
├── docker-compose.yml           # Docker 編排
├── Dockerfile                   # Docker 映像
└── pyproject.toml               # Python 專案設定
```

---

## Migration 管理

### 新增 Migration

在 `migrations/` 資料夾新增 SQL 檔案，命名格式：

```
migrations/
└── init.sql    # 資料庫初始化
```

### 執行 Migration

```bash
./deploy.sh migrate
```

腳本會自動追蹤已執行的 migrations，只執行新的。

---

## License

MIT
