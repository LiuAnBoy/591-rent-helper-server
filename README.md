# 591 租屋爬蟲通知系統

自動爬取 591 租屋網新物件，根據訂閱條件比對後推播 Telegram 通知。

## 功能特色

- 自動定時爬取 591 租屋列表
- 支援多條件訂閱篩選（區域、價格、坪數、格局等）
- Telegram 即時推播通知
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

1. **啟動** → 立即執行一次爬蟲
2. **爬取** → 從 591 抓取最新物件列表
3. **比對** → 根據 Redis 中的訂閱條件進行匹配
4. **推播** → 符合條件的物件發送 Telegram 通知
5. **排程** → 根據時段設定下次爬取時間
   - 白天 (08:00-01:00)：每 15 分鐘
   - 夜間 (01:00-08:00)：每 2 小時

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
docker-compose up -d postgres redis

# 執行 migrations
./deploy.sh migrate

# 啟動 API 服務
uv run uvicorn src.api.main:app --reload
```

---

## 環境變數

| 變數                             | 說明                 | 預設值    |
| -------------------------------- | -------------------- | --------- |
| `PG_HOST`                        | PostgreSQL 主機      | localhost |
| `PG_PORT`                        | PostgreSQL 埠號      | 5432      |
| `PG_USER`                        | PostgreSQL 使用者    | postgres  |
| `PG_PASSWORD`                    | PostgreSQL 密碼      | postgres  |
| `PG_DATABASE`                    | PostgreSQL 資料庫    | rent591   |
| `REDIS_HOST`                     | Redis 主機           | localhost |
| `REDIS_PORT`                     | Redis 埠號           | 6379      |
| `APP_PORT`                       | API 服務埠號         | 8000      |
| `TELEGRAM_BOT_TOKEN`             | Telegram Bot Token   | -         |
| `TELEGRAM_WEBHOOK_URL`           | Telegram Webhook URL | -         |
| `JWT_SECRET`                     | JWT 密鑰             | -         |
| `CRAWLER_INTERVAL_MINUTES`       | 白天爬取間隔（分鐘） | 15        |
| `CRAWLER_NIGHT_INTERVAL_MINUTES` | 夜間爬取間隔（分鐘） | 60        |
| `CRAWLER_NIGHT_START_HOUR`       | 夜間開始時間         | 1         |
| `CRAWLER_NIGHT_END_HOUR`         | 夜間結束時間         | 8         |

---

## Telegram Bot 指令

| 指令             | 別名   | 說明         |
| ---------------- | ------ | ------------ |
| `/start`         | -      | 開始使用     |
| `/help`          | `幫助` | 顯示使用說明 |
| `/bind <綁定碼>` | -      | 綁定帳號     |
| `/status`        | -      | 查看綁定狀態 |
| `/list`          | `清單` | 查看訂閱清單 |

> 中文指令不需要加 `/`，直接輸入即可（例如：`幫助`、`清單`）

---

## API 文件

詳細 API 說明請參考 [docs/API.md](docs/API.md)

### 快速參考

| 模組         | 端點                  | 說明           |
| ------------ | --------------------- | -------------- |
| 認證         | `POST /auth/register` | 註冊帳號       |
|              | `POST /auth/login`    | 登入           |
| 使用者       | `GET /users/me`       | 取得個人資料   |
| 訂閱         | `GET /subscriptions`  | 列出所有訂閱   |
|              | `POST /subscriptions` | 新增訂閱       |
|              | `PATCH .../toggle`    | 啟用/停用訂閱  |
| 綁定         | `GET /bindings`       | 列出所有綁定   |
|              | `POST .../bind-code`  | 產生綁定碼     |
| Webhook      | `POST .../setup`      | 設定 Webhook   |
| 健康檢查     | `GET /health`         | 健康檢查       |

---

## 訂閱條件參考

| 條件     | 欄位              | 類型    | 說明                                   |
| -------- | ----------------- | ------- | -------------------------------------- |
| 區域     | `region`          | int     | 1=台北市, 3=新北市                     |
| 區段     | `section`         | int[]   | 區域代碼陣列                           |
| 類型     | `kind`            | int[]   | 1=整層, 2=獨立套房, 3=分租套房, 4=雅房 |
| 最低租金 | `price_min`       | int     | 價格下限                               |
| 最高租金 | `price_max`       | int     | 價格上限                               |
| 最小坪數 | `area_min`        | float   | 坪數下限                               |
| 最大坪數 | `area_max`        | float   | 坪數上限                               |
| 格局     | `layout`          | int[]   | 1=1房, 2=2房, 3=3房, 4=4房以上         |
| 樓層     | `floor`           | str[]   | "1_1", "2_6", "6_12", "13_"            |
| 特色     | `features`        | str[]   | near_subway, pet, cook, lift 等        |
| 設備     | `options`         | str[]   | cold, washer, icebox 等                |
| 排除頂加 | `exclude_rooftop` | bool    | 排除頂樓加蓋                           |
| 性別限制 | `gender`          | str     | boy=限男, girl=限女, null=不限         |
| 需可養寵 | `pet_required`    | bool    | 需要可養寵物                           |

詳細選項代碼請參考 [docs/OPTIONS.md](docs/OPTIONS.md)

---

## 專案結構

```
591-crawler/
├── config/
│   └── settings.py              # 應用程式設定
├── migrations/
│   └── init.sql                 # 資料庫初始化
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
│   │   │   ├── help.py          # /help 指令
│   │   │   ├── bind.py          # /bind 指令
│   │   │   ├── status.py        # /status 指令
│   │   │   └── list.py          # /list 指令
│   │   └── telegram/            # Telegram 實作
│   │       ├── bot.py           # Bot 封裝
│   │       ├── handler.py       # 訊息處理
│   │       └── formatter.py     # 訊息格式化
│   ├── connections/
│   │   ├── postgres.py          # PostgreSQL 連線
│   │   └── redis.py             # Redis 連線
│   ├── crawler/
│   │   ├── rent591.py           # 591 列表爬蟲
│   │   └── object_detail.py     # 物件詳情爬蟲
│   ├── jobs/
│   │   ├── scheduler.py         # 排程器
│   │   ├── checker.py           # 物件比對
│   │   ├── broadcaster.py       # 推播通知
│   │   └── parser.py            # 資料解析
│   ├── modules/
│   │   ├── users/               # 使用者模組
│   │   ├── subscriptions/       # 訂閱模組
│   │   ├── bindings/            # 綁定模組
│   │   └── objects/             # 物件模組
│   └── utils/
│       └── mappings.py          # 常數對照表
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
├── init.sql              # 初始化（必須）
├── 002_add_feature.sql   # 新功能
└── 003_fix_something.sql # 修正
```

### 執行 Migration

```bash
./deploy.sh migrate
```

腳本會自動追蹤已執行的 migrations，只執行新的。

---

## License

MIT
