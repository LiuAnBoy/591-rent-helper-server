# Changelog

本檔記錄專案所有重要變更。
格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
版本規範採用日期分組（YYYY-MM-DD）。

分類：`Added`（新增）、`Changed`（變更）、`Fixed`（修復）、
`Removed`（移除）、`Deprecated`（棄用）、`Security`（安全）。

## [Unreleased]

### Fixed

- **TG 選單按鈕回覆實際訊息**：按下暫停/恢復選單的按鈕後，改回覆一則**聊天訊息**確認結果
  （成功 ✅／被擋的提示），而非只有容易忽略的 callback toast。操作失敗回「請稍後再試一次」；
  同一使用者**連續 3 次失敗**改回「請聯絡開發者」（成功即重置計數）。

### Added

- **各別訂閱來源開關（per-subscription × per-source）**：每一筆訂閱可各別選擇要收哪些
  來源的通知。`subscriptions` 新增 `disabled_sources TEXT[]`（opt-out，不在清單 = 收，
  預設全收、新來源自動全收）。比對迴圈（`checker` / `instant_notify`）加上來源 guard；
  `matcher.py` 維持純條件比對。新 API：`PATCH /subscriptions/{id}/sources`（`{source, enabled}`，
  未知來源 400）、`GET /sources`（來源 key + 顯示名稱，給前端/TG 用）。來源開關**只改
  `disabled_sources`、不碰 `subscriptions.enabled`**（後者是使用者手動主開關，單一寫入者）；
  全來源關 = 靠 guard 自然不推播。
- **三層通知階梯 + 編輯 guard**：送達需三層皆開（使用者 `notify_enabled` → 訂閱 `enabled`
  → 來源不在 `disabled_sources`）。**編輯下層受上層約束**：使用者通知關 → 不能改訂閱／來源
  開關（API 403、TG「請先開啟使用者通知」）；訂閱關 → 不能改其來源開關（403、「請先啟用此訂閱」）。
  前端對應灰掉、TG 選單僅在使用者通知開啟時顯示訂閱按鈕。
- **TG 暫停／開始通知改為動態選單**：「暫停通知 / 開始通知」不再立即切換，改回覆「掃描現況 +
  動態按鈕」選單（使用者層、各訂閱、詳細設定 WebApp）。新增 inline **callback query 路由**
  （`notif:*`，含伺服器端擁有權驗證，不信任 callback_data、防畸形 data）。共用 mutation
  service（`src/modules/subscriptions/service.py`）給 REST toggle / TG callback 共用。

### Changed

- **source 宣告統一為單一 manifest**：`src/crawler/registry.py` 改為 `SOURCES: list[SourceDescriptor]`
  （`key` / `name` / `factory` / `fetch_all` 一處寫齊）。新增 `source_catalog()`、
  `source_default_fetch_all()`;`source_keys` / `get_source` / `all_sources` 向後相容改從
  `SOURCES` 衍生。`settings.sources` 退化為**覆蓋層**（預設空 `{}`），政策解析改為「manifest
  預設 + settings 覆蓋」（在 checker）。**加新來源只需編輯 manifest 一筆**，crawl / 政策 /
  API / TG label 全部自動沿用。
- **詳細頁抓取改為「全爬」（per-source 設定）**：新增**每來源**爬取設定 `settings.sources`
  （`config/settings.py`，以 `Source.key` 為鍵的 `SourceConfig`），591 設 `fetch_all=true`，
  日後新增來源就加一個區塊（如 `ddroom: SourceConfig(fetch_all=False)`）。`fetch_all=true`
  時每輪「全新物件」一律抓詳細頁、不再經 pre-filter → 物件全部以 `has_detail=True` 入庫
  （資料完整、日後新增的訂閱可比對只有詳細頁才有的欄位），且不會因 pre-filter 誤判而漏推播。
  pre-filter 邏輯（`src/matching/pre_filter.py`）完整保留(仍供 `instant_notify` 與未來來源使用)，
  某來源要改回粗篩設 `fetch_all=False` 即可。Checker 於爬取時依
  `settings.source_config(source.key)` 解析策略;`instant_notify` 不受影響。
- **架構 / 來源外掛化（Phase 2）**：把爬蟲重構成「來源（Source）外掛」架構。每個租屋網站
  是一個 `Source` 實作，收在 `src/crawler/sources/<name>/`，輸出標準化的 `DBReadyData`；
  核心（去重/比對/儲存/通知）與推播層完全來源無關。新增來源 = 新資料夾 + 實作 `Source` +
  registry 註冊一行，核心零改動。新增 `crawler/base.py`（Source 介面 + `ListBatch`/`DetailBatch`）、
  `crawler/contract.py`（`DBReadyData`）、`crawler/registry.py`、`crawler/workers.py`；
  591 全部管線移入 `crawler/sources/x591/`。`checker` / `instant_notify` 改透過 `Source` 介面
  驅動，不再 import 任何爬蟲內部模組。**新增說明書 `docs/ADDING_A_SOURCE.md`。**
- **物件 / 多來源儲存（Phase 1）**：`objects` 改用 DB 自動產生的 UUID 主鍵，原 `id` 轉為
  `source_id`，新增 `source`（現有資料填 `591`），以 `(source, source_id)` 辨識物件。
- **Migration / 合併單一檔**：將 12 支增量 migration（`002`~`20260211002`）合併回單一
  `migrations/init.sql`，內容對齊正式機現況（以 prod schema dump 逐欄/索引/view/seed 驗證等價）。
  正式機 `schema_migrations` 已記錄各檔名故不重跑；全新部署只套用 `init.sql`，
  順帶修掉先前 `init.sql` 因檔名排序落在 migration 之後、導致全新 DB 部署失敗的隱患。
  日後 schema 變更直接更新 `init.sql`（既有 DB 仍需手動 ALTER 或另開 migration）。

### Added

- **推播 / 性別**：Telegram 物件通知在最底下顯示「性別：限男／限女」，
  不限性別（`all`）則不顯示。
- **通知 / 失敗重試**：推播失敗時自動重試（最多 3 次、間隔 60 秒），3 次都失敗才計為
  失敗並沿用既有 admin 告警推播。重試期間釋放併發名額，不阻塞其他通知。

### Fixed（通知流程，續）

- **即時通知 / 共用 fetcher**：即時通知與排程爬蟲共用同一個 detail fetcher 單例，
  並發時一方結束會關掉另一方仍在用的瀏覽器。即時通知改用自己的 `DetailFetcher` 實例，
  與排程完全隔離（多筆即時通知之間也不再互相干擾）。
- **初始化 / 漏通知**：訂閱的 initialized 旗標只在「有物件匹配時」才標記、且 7 天 TTL
  不像 seen set 會刷新，導致 ① 無匹配的訂閱永遠不初始化、之後第一筆符合的新物件被吞掉、
  ② 活躍訂閱每約 7 天過期一次、週期性漏一筆通知。改為每輪對本區所有訂閱刷新 initialized
  旗標（保留 TTL，活躍不過期、已刪訂閱自動過期不累積），維持 seen set 空時的防洗版抑制。
- **即時通知 / backfill 原子性**：即時通知補 detail 時逐筆更新 PostgreSQL、最後才更新
  Redis，中途失敗會造成兩邊 `has_detail`/detail 不一致。改為用單一交易的
  `update_batch_with_detail`（全有或全無），成功後才刷新 Redis 快取。

### Fixed（多來源化，Phase 2）

- **通知 / 冷啟動洗版**：server 重啟（或 redis seen-set 被清/過期）時，seen-set 是空的、
  整頁都被當「新」，而訂閱旗標還在 `initialized` → 不抑制 → 整頁全推播。改為：某區若**沒有
  爬取歷史**（`has_seen_ids` 為 false），該輪當「靜默基準」——照常存物件、填 seen-set、標記
  訂閱 initialized，但**不發任何通知**；下一輪 seen-set 暖了才正常推真正的新刊登。一條規則
  涵蓋重啟 / redis flush / seen-set 過期 / 全新區域。順帶把原本沒接線的 `force_notify` 接上
  （手動測試時可繞過抑制）。
- **比對 / section 未知被誤篩**：pre-filter 改在標準化資料上跑後，list 頁未解析出的 `section`
  會變成 `0`，導致原本「區域未知先不過濾」的物件被提前淘汰、漏抓 detail。改為 `match_section_quick`
  把 `0`（標準化的未知哨兵）與 `None` 同樣視為「不過濾」。
- **即時通知 / 共用 singleton fetcher（重構回歸修正）**：`X591Source` 改建自己的全新 fetcher
  實例（而非 `get_*_fetcher()` 單例），`close()` 只關自己擁有的；即時通知每次建自己的 source、
  用完即關,不會關掉排程器正在用的瀏覽器。

### Fixed

- **比對 / 缺價格**：租屋物件一定有租金，`price=0` 代表解析失敗。先前 `0 or price_raw`
  的 falsy 陷阱使缺價物件被當「價格未知 → 視為符合」，無視訂閱價格條件推給所有人。
  改為：有設價格條件的訂閱不通過未知/0 價格（不誤推使用者）；爬到 `price=0` 仍存入。
- **資料 / kind 補齊**：list 頁本來就有房型名稱，但數字 `kind` 過去只在 detail 取得，
  list-only 物件 `kind=0`。改為缺數字碼時用 `kind_name` 換算（`雅房→4` 等），所有物件都有 kind。
- **觀測 / 欄位解析異常**：物件存檔後若 `price`/`section`/`kind` 為 0（理應永遠有），
  仍照存，並發 admin 異常推播（`FIELD_MISSING`）附上 IDs，方便察覺 591 改版。
- **爬蟲 / detail 成功標準不一致**：BS4 要 `tags` 非空才算成功，Playwright 找到結構就算，
  導致沒 tags 的有效物件被 BS4 誤判失敗、白白 fallback，且兩路徑接受品質不一。
  統一成 `_is_valid_detail`（`title` + `price_raw`），兩條路徑共用同門檻。
- **爬蟲 / 頂加物件遺失**：591 detail 把頂樓加蓋表示成一般樓層（如 `5F/5F`），覆蓋掉
  list 的 `頂樓加蓋/4F`，使 `is_rooftop` 翻成 False、「排除頂加」訂閱失效。combiner 改為
  當 list 標頂加而 detail 沒標時保留 list 的 floor，維持 `is_rooftop=True` 與總樓層。
- **爬蟲 / 漏抓觀測**：list 單筆解析失敗或缺 id 時只默默 `continue`，難察覺漏抓。
  兩條 list fetcher 改為統計被丟棄數量，有丟才記一筆 summary warning（`Dropped X/Y`）。
- **爬蟲 / detail 全頁比對誤抓**：BS4 詳情頁的格局/坪數/樓層/型態原本用全頁 regex，
  易抓到推薦物件或描述文字；裝潢程度更會把描述中的「新裝潢」誤判成分級。改為鎖定
  主物件 `.pattern` 區塊（依樣式分類 span）、裝潢程度讀結構化「裝潢程度」鍵值；
  找不到時 fallback 回原本全頁邏輯（不破壞）。Playwright 路徑不受影響。
- **即時通知 / API 不符**：`InstantNotifier` 以 `service`/`service_id` 呼叫
  broadcaster，但實際參數為 `provider`/`provider_id`，導致每次即時通知都 `TypeError`
  被吞掉、完全沒送出。已修正參數名，並改為檢查回傳 `success` 才計入已通知數。
- **即時通知 / 比對不一致**：即時通知自帶的簡化比對忽略 `gender`、`shape`、
  `bathroom`、`fitment`、`pet_required`、`other`、`options`，與正式 matcher 結果不同。
  改為統一呼叫 `match_object_to_subscription`，移除分歧的重複實作。
- **排程 / 重複推播**：daytime/night/startup 三個 job 共用 checker 但無鎖，重疊執行
  會把同一批新物件各自推播。加入 `job_defaults`（max_instances=1، coalesce）與全域鎖序列化。
- **Redis / 訂閱同步**：全量同步未清除「已無啟用訂閱」的 region key，導致
  `get_active_regions()` 仍把空區域當活躍。同步時一併刪除殘留的 region key。
- **推播 / 重複訊息**：同一使用者多個重疊訂閱綁同一聊天室時，同一物件會重複發送。
  廣播改以 `(provider, provider_id, object_id)` 去重。
- **資料庫 / 執行紀錄**：`crawler_runs` 例外路徑固定寫入 `total_fetched=0`、
  `new_objects=0`，掩蓋實際進度。改為保留例外發生前的實際計數。
- **Redis / 原子性**：`add_seen_ids` 與 `mark_subscription_initialized` 的寫入與
  TTL 設定改為單一操作（pipeline / `SET ex=`），避免中途失敗造成 key 永久無 TTL。
- **爬蟲 / 價格**：591 在列表頁價格區塊新增 `.extra-text`（額外費用）導致
  `price_unit` 寫入超過 `varchar(20)` 而整批爬取失敗。BS4 列表解析改為先移除
  `.extra-text`，`transform_price` 單位改為只比對 `元/[月週日天年期]` 樣式並預設
  `元/月`，避免任何尾綴文字溢位。
- **爬蟲 / 性別**：591 改版後性別欄位移到 `service.descData`（`{label, value}`），
  舊的 `service.rule` 已不存在，導致 Playwright 路徑性別全部變成 `all`。
  Playwright 改讀 `descData` 的 `性別` 項目，BS4 改用精準句型 `限[男女]生租住`。
- **爬蟲 / 列表 fallback**：BS4 列表抓取的 HTTP 例外未被攔截，導致 Playwright
  fallback 形同虛設、整輪檢查中止。例外現視同抓取失敗，正常進入重試與 fallback。
- **爬蟲 / 監控**：第一頁抓不到資料時 `crawler_runs` 仍記為 `success`，掩蓋故障。
  改記為 `failed` 並附 `error_message`。
- **資料庫 / 寫入一致性**：`ObjectRepository.save_batch` 逐筆寫入但無交易，
  單筆失敗會造成 DB 半寫入且與 Redis seen set 不同步。整批改包進單一 transaction。
- **爬蟲 / NUXT 解析韌性**：Playwright `_find_detail_data` 僅搜尋 NUXT 第一層，
  591 結構多包一層即全失效。改為遞迴搜尋（定位同時含 `service` 與 `info` 的節點）。
