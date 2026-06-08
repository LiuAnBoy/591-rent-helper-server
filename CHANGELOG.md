# Changelog

本檔記錄專案所有重要變更。
格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
版本規範採用日期分組（YYYY-MM-DD）。

分類：`Added`（新增）、`Changed`（變更）、`Fixed`（修復）、
`Removed`（移除）、`Deprecated`（棄用）、`Security`（安全）。

## [Unreleased]

### Fixed

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
