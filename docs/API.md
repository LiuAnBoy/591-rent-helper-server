# API 文件

## 基礎資訊

- **Base URL**: `http://localhost:8000`
- **認證方式**: Bearer Token (JWT)
- **Content-Type**: `application/json`

---

## 認證說明

### Token 格式

登入成功後會取得 JWT Token，包含以下資訊：

| 欄位 | 說明 | 範例 |
|-----|------|------|
| `sub` | User ID | `"1"` |
| `email` | Email | `"user@example.com"` |
| `role` | 角色 | `"user"` / `"admin"` |
| `exp` | 過期時間 (Unix timestamp) | `1736582400` |
| `iat` | 簽發時間 (Unix timestamp) | `1736496000` |

### 使用方式

在 Header 加入：
```
Authorization: Bearer <token>
```

### 認證錯誤回覆

| HTTP Status | 情況 | 回覆 |
|-------------|------|------|
| 401 | 未提供 Token | `{"success": false, "message": "未提供認證資訊"}` |
| 401 | Token 格式錯誤 | `{"success": false, "message": "認證格式錯誤"}` |
| 401 | Token 過期/無效 | `{"success": false, "message": "認證已過期或無效"}` |
| 401 | 用戶不存在 | `{"success": false, "message": "用戶不存在"}` |
| 403 | 帳號被停用 | `{"success": false, "message": "帳號已被停用"}` |

---

## 統一回覆格式

| 操作類型 | 成功回覆 | 失敗回覆 |
| -------- | -------- | -------- |
| 登入 | `{"token": "...", "user": {...}}` | `{"detail": "..."}` |
| 查詢資料 | 直接回傳資料 | `{"success": false, "message": "..."}` |
| 新增/修改/刪除 | `{"success": true}` | `{"success": false, "message": "..."}` |

---

## API 總覽

| 模組 | 端點 | 方法 | 🔒 | 說明 |
|------|------|------|:--:|------|
| 認證 | `/auth/telegram` | POST | | Telegram Web App 登入 |
| 使用者 | `/users/me` | GET | ✓ | 取得個人資料 |
| 訂閱 | `/subscriptions` | GET | ✓ | 列出所有訂閱 |
|      | `/subscriptions` | POST | ✓ | 新增訂閱 |
|      | `/subscriptions/{id}` | GET | ✓ | 取得單一訂閱 |
|      | `/subscriptions/{id}` | PUT | ✓ | 更新訂閱 |
|      | `/subscriptions/{id}` | DELETE | ✓ | 刪除訂閱 |
|      | `/subscriptions/{id}/toggle` | PATCH | ✓ | 啟用/停用訂閱 |
| 綁定 | `/bindings/telegram/toggle` | PATCH | ✓ | 啟用/停用通知 |
| 爬蟲 | `/checker/run` | POST | | 手動觸發爬蟲 |
| 健康檢查 | `/health` | GET | | 健康檢查 |

---

## 認證 `/auth`

### POST `/auth/telegram` - Telegram Web App 登入

透過 Telegram Web App 的 initData 進行驗證登入，自動建立或取得用戶帳號。

**Body:**

| 欄位 | 類型 | 必填 | 說明 |
|------|------|:----:|------|
| `initData` | string | ✓ | Telegram Web App initData 字串 |

**Response:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "name": "John Doe",
    "role": "user",
    "max_subscriptions": 3,
    "providers": [
      {
        "provider": "telegram",
        "provider_id": "123456789",
        "notify_enabled": true
      }
    ]
  }
}
```

---

## 使用者 `/users`

### GET `/users/me` - 取得個人資料 🔒

**Response:**

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe",
  "role": "user",
  "enabled": true,
  "created_at": "2025-01-10T12:00:00+08:00",
  "updated_at": "2025-01-10T12:00:00+08:00",
  "bindings": [
    {
      "service": "telegram",      // 通訊頻道：Telegram
      "is_bound": true,           // 是否已綁定
      "service_id": "123456789",  // Telegram Chat ID
      "enabled": true,            // 是否啟用通知
      "created_at": "2025-01-10T12:00:00+08:00"
    }
    // 未來可擴充：LINE, Discord 等
  ],
  "subscription_count": 2,
  "max_subscriptions": 5
}
```

**Bindings 欄位說明:**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `service` | string | 通訊頻道 (`telegram`, 未來: `line`, `discord`) |
| `is_bound` | bool | 是否已完成綁定 |
| `service_id` | string | 該頻道的用戶 ID (如 Telegram Chat ID) |
| `enabled` | bool | 是否啟用該頻道的通知 |
| `created_at` | string | 綁定時間 |

---

## 訂閱 `/subscriptions`

### POST `/subscriptions` - 新增訂閱 🔒

建立訂閱後會觸發即時通知，檢查現有物件並推播符合條件的結果。

**Body:**

| 欄位 | 類型 | 必填 | 說明 |
|------|------|:----:|------|
| `name` | string | ✓ | 訂閱名稱 |
| `region` | int | ✓ | 縣市代碼 (1=台北市, 3=新北市) |
| `section` | int[] | | 區域代碼陣列 |
| `kind` | int[] | | 1=整層, 2=獨立套房, 3=分租套房, 4=雅房 |
| `price_min` | int | | 最低租金 |
| `price_max` | int | | 最高租金 |
| `area_min` | float | | 最小坪數 |
| `area_max` | float | | 最大坪數 |
| `layout` | int[] | | 1=1房, 2=2房, 3=3房, 4=4房以上 |
| `shape` | int[] | | 1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅 |
| `floor` | str[] | | "1", "2_6", "6_12", "13_" |
| `bathroom` | int[] | | 1=1衛, 2=2衛, 3=3衛, 4=4衛以上 |
| `fitment` | int[] | | 99=新裝潢, 3=中檔, 4=高檔 |
| `other` | str[] | | near_subway, pet, cook, lift 等 |
| `options` | str[] | | cold, washer, icebox 等 |
| `exclude_rooftop` | bool | | 排除頂樓加蓋 (預設 false) |
| `gender` | string | | boy=限男, girl=限女, null=不限 |
| `pet_required` | bool | | 需要可養寵物 (預設 false) |

**Response:** `{"success": true}`

---

### GET `/subscriptions` - 列出所有訂閱 🔒

**Query:**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `enabled_only` | bool | 只顯示啟用的訂閱 |

**Response:**

```json
{
  "total": 2,
  "items": [...]
}
```

---

### GET `/subscriptions/{id}` - 取得單一訂閱 🔒

**Path:**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `id` | int | 訂閱 ID |

**Response:**

```json
{
  "id": 1,
  "user_id": 1,
  "name": "台北套房",
  "region": 1,
  "section": [5, 6, 7],
  "kind": [2, 3],
  "price_min": 8000,
  "price_max": 15000,
  "area_min": 5.0,
  "area_max": 15.0,
  "layout": [1],
  "shape": [1, 2],
  "floor": ["2_6", "6_12"],
  "floor_min": 2,
  "floor_max": 12,
  "bathroom": [1, 2],
  "fitment": [99, 3],
  "other": ["near_subway"],
  "options": ["cold", "washer"],
  "exclude_rooftop": true,
  "gender": null,
  "pet_required": false,
  "enabled": true,
  "created_at": "2025-01-10T12:00:00+08:00",
  "updated_at": "2025-01-10T12:00:00+08:00"
}
```

---

### PUT `/subscriptions/{id}` - 更新訂閱 🔒

> **注意**: 無法更新 `enabled` 欄位，請使用 toggle API

**Path:**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `id` | int | 訂閱 ID |

**Body:** 同新增訂閱，所有欄位皆為選填

**Response:** `{"success": true}`

---

### DELETE `/subscriptions/{id}` - 刪除訂閱 🔒

**Path:**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `id` | int | 訂閱 ID |

**Response:** `{"success": true}`

---

### PATCH `/subscriptions/{id}/toggle` - 啟用/停用訂閱 🔒

**Path:**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `id` | int | 訂閱 ID |

**Response:** `{"success": true}`

---

## 綁定 `/bindings`

### PATCH `/bindings/telegram/toggle` - 啟用/停用通知 🔒

啟用時會觸發即時通知，檢查現有物件並推播符合條件的結果。

**Query:**

| 欄位 | 類型 | 必填 | 說明 |
|------|------|:----:|------|
| `enabled` | bool | ✓ | 是否啟用 |

**Response:** `{"success": true}`

---

## 爬蟲 `/checker`

### POST `/checker/run` - 手動觸發爬蟲

立即對所有有訂閱的活躍區域執行一次爬取流程（列表 → 過濾 → 詳情 → 儲存 → 推播）。

**Response:**

```json
{
  "status": true,
  "results": [
    {
      "region": 1,
      "fetched": 30,
      "new_count": 5,
      "matches": 2,
      "broadcast": { "total": 2, "success": 2, "failed": 0 }
    }
  ]
}
```

---

## 健康檢查

### GET `/health` - 健康檢查

**Response:** `{"status": "healthy"}`

---

## 附錄

詳細訂閱條件代碼請參考 [OPTIONS.md](OPTIONS.md)
