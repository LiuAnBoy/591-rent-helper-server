# Changelog

本檔記錄專案所有重要變更。
格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
版本規範採用日期分組（YYYY-MM-DD）。

分類：`Added`（新增）、`Changed`（變更）、`Fixed`（修復）、
`Removed`（移除）、`Deprecated`（棄用）、`Security`（安全）。

## [Unreleased]

### Added

- **推播 / 性別**：Telegram 物件通知在最底下顯示「性別：限男／限女」，
  不限性別（`all`）則不顯示。

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
