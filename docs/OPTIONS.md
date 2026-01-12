# 591 租屋篩選條件參考

## 目錄

- [591 租屋篩選條件參考](#591-租屋篩選條件參考)
  - [目錄](#目錄)
  - [比對狀態總覽](#比對狀態總覽)
  - [位置](#位置)
    - [Region (縣市)](#region-縣市)
    - [Section (區域)](#section-區域)
      - [台北市 (region=1)](#台北市-region1)
      - [新北市 (region=3)](#新北市-region3)
  - [類型 Kind](#類型-kind)
  - [租金 Price](#租金-price)
  - [格局 Layout](#格局-layout)
  - [型態 Shape](#型態-shape)
  - [坪數 Area](#坪數-area)
  - [樓層 Floor](#樓層-floor)
    - [Floor Value Mapping](#floor-value-mapping)
    - [API 輸入格式（向後相容）](#api-輸入格式向後相容)
  - [衛浴 Bathroom](#衛浴-bathroom)
  - [特色 other](#特色-other)
  - [設備 Options](#設備-options)
  - [裝潢 Fitment](#裝潢-fitment)
  - [須知 Notice](#須知-notice)
    - [訂閱欄位](#訂閱欄位)
    - [物件欄位](#物件欄位)
    - [比對邏輯](#比對邏輯)
  - [比對邏輯總結](#比對邏輯總結)

---

## 比對狀態總覽

| 條件     | 訂閱欄位          | 物件欄位       | 比對方式 | 狀態                 |
| -------- | ----------------- | -------------- | -------- | -------------------- |
| 區域     | `region`          | `regionid`     | 精確比對 | ✅ 已實作            |
| 區段     | `section`         | `sectionid`    | 包含比對 | ✅ 已實作            |
| 類型     | `kind`            | `kind`         | 包含比對 | ✅ 已實作            |
| 租金     | `price_min/max`   | `price`        | 範圍比對 | ✅ 已實作            |
| 格局     | `layout`          | `layoutStr`    | 提取房數 | ✅ 已實作            |
| 型態     | `shape`           | ❌ 無          | -        | ❌ 需詳細頁          |
| 坪數     | `area_min/max`    | `area`         | 範圍比對 | ✅ 已實作            |
| 樓層     | `floor_min/max`   | `floor`        | 範圍比對 | ✅ 已實作            |
| 衛浴     | `bathroom`        | `layoutStr`    | 提取衛數 | ⚠️ 可實作            |
| 特色     | `features`        | `tags`         | 標籤比對 | ✅ 已實作            |
| 設備     | `options`         | `tags`         | 標籤比對 | ✅ 已實作            |
| 裝潢     | `fitment`         | `fitment_name` | -        | ⚠️ 列表頁不可靠      |
| 排除頂加 | `exclude_rooftop` | `is_rooftop`   | 布林比對 | ✅ 已實作            |
| 性別限制 | `gender`          | `gender`       | 包含比對 | ✅ 已實作 (需詳細頁) |
| 需養寵物 | `pet_required`    | `pet_allowed`  | 布林比對 | ✅ 已實作 (需詳細頁) |

> 詳細欄位分析請參考 `docs/FIELD_ANALYSIS.md`

---

## 位置

### Region (縣市)

| 代碼 | 名稱   |
| ---- | ------ |
| 1    | 台北市 |
| 3    | 新北市 |

### Section (區域)

#### 台北市 (region=1)

| 代碼 | 名稱   |     | 代碼 | 名稱   |
| ---- | ------ | --- | ---- | ------ |
| 1    | 中正區 |     | 7    | 信義區 |
| 2    | 大同區 |     | 8    | 士林區 |
| 3    | 中山區 |     | 9    | 北投區 |
| 4    | 松山區 |     | 10   | 內湖區 |
| 5    | 大安區 |     | 11   | 南港區 |
| 6    | 萬華區 |     | 12   | 文山區 |

#### 新北市 (region=3)

| 代碼 | 名稱   |     | 代碼 | 名稱   |
| ---- | ------ | --- | ---- | ------ |
| 20   | 萬里區 |     | 40   | 三峽區 |
| 21   | 金山區 |     | 41   | 樹林區 |
| 26   | 板橋區 |     | 42   | 鶯歌區 |
| 27   | 汐止區 |     | 43   | 三重區 |
| 28   | 深坑區 |     | 44   | 新莊區 |
| 29   | 石碇區 |     | 45   | 泰山區 |
| 30   | 瑞芳區 |     | 46   | 林口區 |
| 31   | 平溪區 |     | 47   | 蘆洲區 |
| 32   | 雙溪區 |     | 48   | 五股區 |
| 33   | 貢寮區 |     | 49   | 八里區 |
| 34   | 新店區 |     | 50   | 淡水區 |
| 35   | 坪林區 |     | 51   | 三芝區 |
| 36   | 烏來區 |     | 52   | 石門區 |
| 37   | 永和區 |     |      |        |
| 38   | 中和區 |     |      |        |
| 39   | 土城區 |     |      |        |

---

## 類型 Kind

| 代碼 | 名稱     | 說明         |
| ---- | -------- | ------------ |
| 1    | 整層住家 | 整層出租     |
| 2    | 獨立套房 | 有獨立衛浴   |
| 3    | 分租套房 | 共用部分空間 |
| 4    | 雅房     | 共用衛浴     |
| 8    | 車位     | 停車位       |
| 24   | 其他     | 其他類型     |

**比對方式:** `obj.kind IN sub.kind[]`

---

## 租金 Price

| 範圍        | API 格式      |
| ----------- | ------------- |
| 5000 以下   | `0*5000`      |
| 5000-10000  | `5000_10000`  |
| 10000-20000 | `10000_20000` |
| 20000-30000 | `20000_30000` |
| 30000-40000 | `30000_40000` |
| 40000 以上  | `40000*`      |

**訂閱欄位:** `price_min`, `price_max` (整數)

**比對方式:** `price_min <= obj.price <= price_max`

---

## 格局 Layout

| 代碼 | 名稱     |
| ---- | -------- |
| 1    | 1 房     |
| 2    | 2 房     |
| 3    | 3 房     |
| 4    | 4 房以上 |

**物件欄位:** `layout_str` (例: "2 房 1 廳 1 衛")

**比對方式:** 從 `layout_str` 提取房數，比對是否在 `sub.layout[]` 中

---

## 型態 Shape

| 代碼 | 名稱     |
| ---- | -------- |
| 1    | 公寓     |
| 2    | 電梯大樓 |
| 3    | 透天厝   |
| 4    | 別墅     |

> ⚠️ **未實作:** 物件資料中無對應欄位

---

## 坪數 Area

| 範圍      | API 格式 |
| --------- | -------- |
| 10 坪以下 | `0_10`   |
| 10-20 坪  | `10_20`  |
| 20-30 坪  | `20_30`  |
| 30-40 坪  | `30_40`  |
| 40-50 坪  | `40_50`  |
| 50 坪以上 | `_50`    |

**訂閱欄位:** `area_min`, `area_max` (Decimal)

**比對方式:** `area_min <= obj.area <= area_max`

---

## 樓層 Floor

### Floor Value Mapping

| 情況      | floor      | is_rooftop | 說明               |
| --------- | ---------- | ---------- | ------------------ |
| 一般樓層  | 1, 2, 3... | false      | 正整數             |
| 頂加      | 0          | true       | 用 is_rooftop 區分 |
| B1 地下室 | -1         | false      | 負數表示地下       |
| B2 地下室 | -2         | false      | 負數表示地下       |

### API 輸入格式（向後相容）

| 代碼   | 名稱      | floor_min | floor_max |
| ------ | --------- | --------- | --------- |
| `1_1`  | 1 樓      | 1         | 1         |
| `2_6`  | 2-6 層    | 2         | 6         |
| `6_12` | 6-12 層   | 6         | 12        |
| `12_`  | 12 樓以上 | 12        | NULL      |

**訂閱欄位:** `floor_min`, `floor_max` (INTEGER)

**物件欄位:** `floor` (INTEGER), `total_floor` (INTEGER), `floor_name` (原始字串如 "3F/10F")

**比對方式:** `floor_min <= obj.floor <= floor_max`（NULL 表示無限制）

---

## 衛浴 Bathroom

| 代碼 | 名稱     |
| ---- | -------- |
| 1    | 1 衛     |
| 2    | 2 衛     |
| 3    | 3 衛     |
| `4_` | 4 衛以上 |

> ⚠️ **未實作:** 物件資料中無對應欄位

---

## 特色 other

| 代碼               | 名稱       | 標籤對應           |
| ------------------ | ---------- | ------------------ |
| `newPost`          | 新上架     | 新上架             |
| `near_subway`      | 近捷運     | 近捷運, 捷運, mrt  |
| `pet`              | 可養寵物   | 可養寵, 寵物, pet  |
| `cook`             | 可開伙     | 可開伙, 開伙, 廚房 |
| `cartplace`        | 有車位     | 車位, 停車         |
| `lift`             | 有電梯     | 有電梯, 電梯       |
| `balcony_1`        | 有陽台     | 有陽台, 陽台       |
| `lease`            | 可短期租賃 | 短租               |
| `social-housing`   | 社會住宅   | -                  |
| `rental-subsidy`   | 租金補貼   | -                  |
| `elderly-friendly` | 高齡友善   | -                  |
| `tax-deductible`   | 可報稅     | -                  |
| `naturalization`   | 可入籍     | -                  |

**比對方式:** `obj.tags` 或 `obj.surrounding.subway` 包含任一特色 (OR)

---

## 設備 Options

| 代碼         | 名稱       | 標籤對應         |
| ------------ | ---------- | ---------------- |
| `cold`       | 有冷氣     | 冷氣, 空調       |
| `washer`     | 有洗衣機   | 洗衣機, 洗衣     |
| `icebox`     | 有冰箱     | 冰箱             |
| `hotwater`   | 有熱水器   | 熱水器, 熱水     |
| `naturalgas` | 有天然瓦斯 | 天然氣, 瓦斯     |
| `broadband`  | 有網路     | 網路, 寬頻, wifi |
| `bed`        | 有床       | 床, 床鋪         |

**比對方式:** `obj.tags` 包含任一設備 (OR)

---

## 裝潢 Fitment

| 代碼 | 名稱     |
| ---- | -------- |
| 99   | 新裝潢   |
| 3    | 中檔裝潢 |
| 4    | 高檔裝潢 |

**物件欄位:** `fitment_name` (例: "有裝潢", "精緻裝潢")

> ⚠️ **未實作:** 需建立 fitment_name 對應關係

---

## 須知 Notice

原本的 `notice: list[str]` 欄位已拆分為 3 個獨立欄位：

### 訂閱欄位

| 欄位              | 類型          | 說明                                            |
| ----------------- | ------------- | ----------------------------------------------- |
| `exclude_rooftop` | `bool`        | 排除頂樓加蓋 (預設 false)                       |
| `gender`          | `str \| null` | 性別限制 (`boy`=限男, `girl`=限女, `null`=不限) |
| `pet_required`    | `bool`        | 需要可養寵物 (預設 false)                       |

### 物件欄位

| 欄位          | 類型           | 來源                  | 說明                          |
| ------------- | -------------- | --------------------- | ----------------------------- |
| `is_rooftop`  | `bool`         | 列表頁 `floor_name`   | 是否頂樓加蓋                  |
| `gender`      | `str`          | 詳細頁 `service.rule` | 性別限制 (`boy`/`girl`/`all`) |
| `pet_allowed` | `bool \| null` | 詳細頁 `service.rule` | 可否養寵物                    |

### 比對邏輯

```python
# 排除頂樓加蓋
if sub.exclude_rooftop and obj.is_rooftop:
    return False

# 性別限制 (boy=需要限男或不限, girl=需要限女或不限)
if sub.gender == "boy" and obj.gender not in ["boy", "all"]:
    return False
if sub.gender == "girl" and obj.gender not in ["girl", "all"]:
    return False

# 需要可養寵物
if sub.pet_required and obj.pet_allowed == False:
    return False
```

---

## 比對邏輯總結

```
物件符合訂閱 =
    region 相同
    AND (section 為空 OR obj.section_id IN sub.section)
    AND (kind 為空 OR obj.kind IN sub.kind)
    AND (price_min 為空 OR obj.price >= price_min)
    AND (price_max 為空 OR obj.price <= price_max)
    AND (area_min 為空 OR obj.area >= area_min)
    AND (area_max 為空 OR obj.area <= area_max)
    AND (layout 為空 OR 房數符合)
    AND (floor 為空 OR 樓層符合)
    AND (features 為空 OR 任一特色符合)
    AND (options 為空 OR 任一設備符合)
    AND (exclude_rooftop 為 false OR obj 非頂樓加蓋)
    AND (gender 為空 OR 性別符合)
    AND (pet_required 為 false OR obj 可養寵物)
```

**原則:** 空條件 = 不篩選，條件間為 AND，同條件內多值為 OR
