# 如何新增一個租屋來源（Source）

本系統採「**來源（Source）外掛化**」架構：每個租屋網站（591、未來的 dd-room、永慶…）
是一個獨立的 `Source` 實作，收在自己的資料夾。**核心（去重 / 比對 / 儲存 / 通知）
與推播層完全來源無關**，新增來源時不需要改它們。

> 一句話總結：**新增來源 = 在 `sources/` 多一個資料夾、實作 `Source` 介面、在 registry 註冊一行。核心零改動。**

---

## 1. 三區架構（最重要的心智模型）

| 區 | 職責 | 放哪 |
|----|------|------|
| **來源區**（Source） | 抓取該網站的 list / detail，把 raw 資料**標準化**成 `DBReadyData`（含來源專屬的解析 mapping、URL 組裝、BS4/Playwright/API fallback） | `src/crawler/sources/<name>/` |
| **核心區**（來源無關） | 去重、pre-filter、比對、存 DB / Redis、通知排程 | `src/jobs/`、`src/matching/`、`src/modules/` |
| **推播區**（呈現） | 把標準化代碼轉成中文標籤後送出通知 | `src/channels/` |

**鐵則：過了 Source 邊界就全是標準化資料。** 任何 raw 型別（HTML、API JSON、該站的欄位名）
只存在於 Source 內部，核心與推播都看不到。

---

## 2. 你只需要實作這個介面

`src/crawler/base.py`：

```python
class Source(Protocol):
    key: str   # 穩定的來源代碼，例如 "591" / "ddroom"。會寫進 DBReadyData["source"]

    async def start(self) -> None: ...   # 取得資源（瀏覽器 / session）
    async def close(self) -> None: ...   # 釋放資源

    # list 階段：回傳「該區、尚未看過的、已標準化」物件（has_detail=False）
    async def fetch_list(self, region: int, max_pages: int) -> ListBatch: ...

    # detail 階段：對候選物件補詳情，回傳已標準化（has_detail=True）
    async def fetch_detail(self, items: list[DBReadyData]) -> DetailBatch: ...
```

回傳型別（也在 `base.py`）：

```python
@dataclass
class ListBatch:
    items: list[DBReadyData]   # 新的、已標準化、has_detail=False
    total_fetched: int         # 本輪抓到的總筆數（含已看過的）；0 = 第一頁抓取失敗

@dataclass
class DetailBatch:
    enriched: dict[str, DBReadyData]  # key=source_id，has_detail=True
    not_found: int                    # 404 數
    failed: int                       # 非 404 錯誤數
    failed_ids: list[str]             # 沒成功補到 detail 的 source_id
```

### 2.1 每來源爬取設定（manifest 的 `fetch_all`）

每個來源「怎麼爬」的差異寫在 manifest（`src/crawler/registry.py` 的 `SOURCES`）那一筆的
`fetch_all`：

- `fetch_all=True` — 每個新物件都補詳情（資料完整、不漏推播）。591 現在的形式。
- `fetch_all=False` — 只對「可能符合訂閱」的物件補詳情（沿用 `src/matching/pre_filter.py` 的粗篩）。

也就是你在 §3 註冊那一筆 `SourceDescriptor` 設好即可（預設 `True`）。

> **覆蓋（少用）**：若想在不改 code 的情況下臨時改某來源的 `fetch_all`，可在
> `config/settings.py` 的 `settings.sources`（預設空 `{}`，僅放覆蓋值）加一筆
> `SourceConfig`；checker 解析時「manifest 預設 + settings 覆蓋」。平常不必碰。

> 注意：鍵用的是 `Source.key`（如 `"591"`），不是資料夾名（`x591`）。

### 核心怎麼驅動你（你不用寫這段，但要知道）

`src/jobs/checker.py` 的主迴圈（全程只碰 `DBReadyData`）：

```
for source in registry.all_sources(redis):
    for region in source.regions:                  # 目前 591 由訂閱推得 active regions
        batch     = await source.fetch_list(region, MAX_PAGES)   # 你回標準化新物件
        if resolve_fetch_all(source.key):                        # manifest 預設 + settings 覆蓋（§2.1）
            candidates = batch.items                             #   全爬：每個新物件都補詳情
        else:
            candidates = pre_filter(batch.items, subs)           #   粗篩：只補可能符合訂閱的
        enriched  = await source.fetch_detail(candidates)        # 你回標準化詳情
        save(merge(batch.items, enriched)); seed_seen; match; notify
```

---

## 3. 你的輸出契約：`DBReadyData`

`src/crawler/contract.py`。**這是所有來源的共同邊界型別**，你的 `fetch_list` / `fetch_detail`
最終都要產出它。物件以 `(source, source_id)` 辨識；DB 的 UUID 主鍵由 PostgreSQL 自動產生，
應用層不碰。

| 欄位 | 型別 | 說明 / 標準化規則 |
|------|------|------|
| `source` | `str` | 你的 `key`，例如 `"ddroom"` |
| `source_id` | `str` | 該站的原生物件 id（字串） |
| `url` | `str` | 詳情頁完整網址 |
| `title` | `str` | 標題 |
| `price` | `int` | 月租金（純數字，去逗號/去額外費用） |
| `price_unit` | `str` | 通常 `"元/月"` |
| `region` | `int` | 縣市代碼（`0` = 未知） |
| `section` | `int` | 行政區代碼（`0` = 未知；核心把 0 當「不過濾」） |
| `kind` | `int` | 房型代碼（整層/獨套/分租/雅房/車位…；`0` = 未知） |
| `kind_name` | `str` | 房型中文（推播顯示用） |
| `address` | `str` | 地址 |
| `floor` | `int \| None` | 樓層（0=頂加、負數=地下） |
| `floor_str` | `str` | 樓層原字串（顯示用，例 `"3F/10F"`） |
| `total_floor` | `int \| None` | 總樓層 |
| `is_rooftop` | `bool` | 是否頂樓加蓋 |
| `layout` | `int \| None` | 房數 |
| `layout_str` | `str` | 格局原字串（例 `"2房1廳1衛"`） |
| `bathroom` | `int \| None` | 衛浴數 |
| `area` | `float \| None` | 坪數 |
| `shape` | `int \| None` | 建物型態（1公寓/2電梯大樓/3透天/4別墅） |
| `fitment` | `int \| None` | 裝潢等級代碼 |
| `gender` | `str` | 性別限制（`boy`/`girl`/`all`） |
| `pet_allowed` | `bool` | 可否養寵物 |
| `options` | `list[str]` | 設備代碼（標準化後，例 `["washer","cold"]`） |
| `other` | `list[str]` | 特色代碼（例 `["near_subway","pet"]`） |
| `tags` | `list[str]` | 原始標籤（去重） |
| `surrounding_type` | `str \| None` | 周邊交通類型（metro/bus） |
| `surrounding_desc` | `str \| None` | 周邊描述（例 `"信義安和站"`） |
| `surrounding_distance` | `int \| None` | 距離（公尺） |
| `has_detail` | `bool` | 是否已補詳情（list 階段 False、detail 階段 True） |

> **代碼對齊**：`region` / `section` / `kind` / `shape` / `fitment` / `options` / `other` 用的是
> 系統內部代碼（見 `src/utils/mappings/` 與 `docs/OPTIONS.md`）。你的來源若欄位語意不同，
> 在**你的 Source 內部**把它對應到這些代碼即可；真的對不上的代碼填 `0` / `None`，
> 系統會當「未知 → 不過濾」。中文標籤是推播時才轉，不是你的責任。

---

## 4. 目標目錄結構

```
src/crawler/
├── base.py          # Source 介面 + ListBatch/DetailBatch（共用，勿改語意）
├── contract.py      # DBReadyData（共用契約）
├── registry.py      # 來源註冊處 ← 你要加一行
├── workers.py       # 通用 worker 數計算（可重用）
└── sources/
    ├── x591/        # 591（既有，可當範本）
    └── ddroom/      # ← 你的新來源
        ├── __init__.py        # 匯出 DdRoomSource
        ├── source.py          # class DdRoomSource: 串接管線、輸出 DBReadyData
        ├── client.py          # 抓取（API client 或 fetchers + fallback）
        ├── transformers.py    # 該站 raw → DBReadyData 的轉換
        ├── mappings/          # 該站字串/代碼 → 系統代碼 的解析（若需要）
        └── raw_types.py       # 該站 raw 結構（選用）
```

> 591 用 BS4→Playwright 爬 HTML，所以拆了 list/detail fetcher + combiner。
> 若你的來源有**乾淨的 JSON API**（如 dd-room），可以簡單很多 —— 一個 `client.py`
> 直接打 API、`transformers.py` 把 JSON 轉成 `DBReadyData` 就好，**完全不需要 Playwright**。

---

## 5. 步驟

1. **建資料夾** `src/crawler/sources/<name>/`，加 `__init__.py`。
2. **實作 `source.py`**：`class <Name>Source` 滿足 `Source` 介面。
   - `key = "<name>"`
   - `fetch_list(region, max_pages)`：抓清單 → 標準化 → 回 `ListBatch`（`has_detail=False`、
     `total_fetched` 要計入所有抓到的筆數，第一頁失敗回 `total_fetched=0`）。
   - `fetch_detail(items)`：對 `items`（帶 `source_id`）補詳情 → 回 `DetailBatch`。
   - 去重/提早停這類「爬取優化」可在 Source 內自理（591 用 Redis seen-set 做提早停，
     建構子收 `redis`；若你的來源不需要可以不收）。
3. **寫 `transformers.py`**：raw → `DBReadyData`，把該站欄位對應到系統代碼。
4. **註冊**：`src/crawler/registry.py` 的 `SOURCES` manifest 加一筆 `SourceDescriptor`
   （`key` / `name` / `factory` / `fetch_all` 一處寫齊）：
   ```python
   SOURCES: list[SourceDescriptor] = [
       SourceDescriptor(
           key=X591Source.key, name="591 租屋網",
           factory=lambda redis: X591Source(redis), fetch_all=True,
       ),
       SourceDescriptor(                                          # ← 新增
           key=DdRoomSource.key, name="好房網",
           factory=lambda redis: DdRoomSource(redis), fetch_all=False,
       ),
   ]
   ```
   這一筆同時餵 crawl 驅動、爬取政策（§2.1）、`GET /sources` 與 TG 來源 label——
   其他地方零改動。
5. **測試**（見下一節）。
6. **完成** —— 不用碰 `checker.py` / `instant_notify.py` / `matcher.py` / 任何核心或推播檔。

---

## 6. 測試（照既有模式）

- **黃金輸出測試**（最重要）：準備一筆該站真實 raw（list + detail），斷言整條
  `raw → DBReadyData` 的**精確輸出**。參考 `tests/unit/crawler/test_pipeline_golden.py`。
  集合型欄位（`tags`/`options`/`other`）用集合比較避免 PYTHONHASHSEED flaky。
- **Source 生命週期測試**：`start()` 建自己的資源、`close()` 只關自己擁有的、注入的不關。
  參考 `tests/unit/crawler/test_x591_source.py`。
- 跑 `uv run pytest` 應全綠；`uv run ruff check .`、`uv run mypy src` 乾淨
  （新來源若有 Playwright/TypedDict typing 雜訊，比照 591 在 `pyproject.toml` 的
  `[[tool.mypy.overrides]]` 加模組）。

> 核心的編排（分頁、pre-filter、has_detail 合併、通知抑制、冷 region 靜默基準）已有
> characterization 測試守住（`tests/unit/jobs/`），新來源只要**輸出對的 `DBReadyData`**
> 就能正確被核心處理，不用重測核心。

---

## 7. 不要做的事

- ❌ 不要在核心（`checker` / `matcher` / `repository`）裡寫任何來源專屬的 if-else / 欄位解析。
- ❌ 不要讓 raw 型別（HTML / API JSON / 該站欄位名）洩漏到 Source 之外。
- ❌ 不要在 Source 裡做比對 / 存 DB / 發通知 —— 那是核心的事；Source 只負責「抓 + 標準化」。
- ❌ 不要用 `get_*_fetcher()` 這類**全域 singleton** 當 Source 的資源（會和排程器互相關閉
  瀏覽器）；每個 Source 實例建自己的 fetcher（見 591 的 `X591Source.start`）。

---

## 8. 多來源相關待辦（接第二個來源時要一起處理）

目前只有 591（純數字 source_id），以下在單一來源下不影響，**接第二個來源時要補**：

- `redis seen-set` / object key 加 `source` 前綴（目前 region-only，跨來源會撞 source_id）。
- `broadcaster` 去重 key 由 `(provider, provider_id, source_id)` 改為帶 `source`。
- `redis.get_seen_ids` 等對 id 的 `int()` cast 改吃字串（英數 source_id 會炸）。

詳見 `docs/specs/2026-06-09-objects-multisource-storage-design.md` 的 Phase 2 章節與
`docs/specs/2026-06-09-ddroom-source-design.md`。
