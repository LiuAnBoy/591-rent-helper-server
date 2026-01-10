# API 文件

## 基礎資訊

- **Base URL**: `http://localhost:8000`
- **認證方式**: Bearer Token (JWT)
- **Content-Type**: `application/json`

## 統一回覆格式

| 操作類型 | 成功回覆 | 失敗回覆 |
| -------- | -------- | -------- |
| 註冊 | `{"success": true}` | `{"success": false, "message": "..."}` |
| 登入 | `{"token": "..."}` | `{"success": false, "message": "..."}` |
| 查詢資料 | 直接回傳資料 | `{"success": false, "message": "..."}` |
| 新增/修改/刪除 | `{"success": true}` | `{"success": false, "message": "..."}` |

---

## 認證 `/auth`

### POST `/auth/register` - 註冊帳號

**Request:**

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

**Response (201):**

```json
{ "success": true }
```

**Error (400):**

```json
{ "success": false, "message": "此 Email 已被註冊" }
```

---

### POST `/auth/login` - 登入

**Request:**

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

**Response (200):**

```json
{ "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." }
```

**Error (401):**

```json
{ "success": false, "message": "Email 或密碼錯誤" }
```

---

## 使用者 `/users`

### GET `/users/me` - 取得個人資料

**Request:**

```bash
curl -X GET http://localhost:8000/users/me \
  -H "Authorization: Bearer <token>"
```

**Response (200):**

```json
{
  "id": 1,
  "email": "user@example.com",
  "role": "user",
  "enabled": true,
  "created_at": "2025-01-10T12:00:00+08:00"
}
```

---

## 訂閱 `/subscriptions`

### POST `/subscriptions` - 新增訂閱

**Request:**

```bash
curl -X POST http://localhost:8000/subscriptions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "台北套房",
    "region": 1,
    "section": [5, 6, 7],
    "kind": [2, 3],
    "price_min": 8000,
    "price_max": 15000,
    "area_min": 5,
    "area_max": 15,
    "layout": [1],
    "exclude_rooftop": true,
    "pet_required": false
  }'
```

**Response (201):**

```json
{ "success": true }
```

---

### GET `/subscriptions` - 列出所有訂閱

**Request:**

```bash
curl -X GET http://localhost:8000/subscriptions \
  -H "Authorization: Bearer <token>"
```

**Query Parameters:**

| 參數          | 類型 | 說明               |
| ------------- | ---- | ------------------ |
| `enabled_only`| bool | 只顯示啟用的訂閱   |

**Response (200):**

```json
{
  "total": 2,
  "items": [
    {
      "id": 1,
      "name": "台北套房",
      "region": 1,
      "enabled": true,
      ...
    }
  ]
}
```

---

### GET `/subscriptions/{id}` - 取得單一訂閱

**Request:**

```bash
curl -X GET http://localhost:8000/subscriptions/1 \
  -H "Authorization: Bearer <token>"
```

**Response (200):**

```json
{
  "id": 1,
  "name": "台北套房",
  "region": 1,
  ...
}
```

**Error (404):**

```json
{ "success": false, "message": "訂閱不存在" }
```

---

### PUT `/subscriptions/{id}` - 更新訂閱

> **注意**: 無法透過此 API 更新 `enabled` 欄位，請使用 `PATCH /subscriptions/{id}/toggle`

**Request:**

```bash
curl -X PUT http://localhost:8000/subscriptions/1 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "台北套房-更新",
    "price_max": 20000
  }'
```

**Response (200):**

```json
{ "success": true }
```

---

### DELETE `/subscriptions/{id}` - 刪除訂閱

**Request:**

```bash
curl -X DELETE http://localhost:8000/subscriptions/1 \
  -H "Authorization: Bearer <token>"
```

**Response (200):**

```json
{ "success": true }
```

---

### PATCH `/subscriptions/{id}/toggle` - 啟用/停用訂閱

**Request:**

```bash
curl -X PATCH http://localhost:8000/subscriptions/1/toggle \
  -H "Authorization: Bearer <token>"
```

**Response (200):**

```json
{ "success": true }
```

---

## 綁定 `/bindings`

### GET `/bindings` - 列出所有綁定

**Request:**

```bash
curl -X GET http://localhost:8000/bindings \
  -H "Authorization: Bearer <token>"
```

**Response (200):**

```json
[
  {
    "id": 1,
    "service": "telegram",
    "service_id": "123456789",
    "enabled": true,
    "created_at": "2025-01-10T12:00:00+08:00"
  }
]
```

---

### GET `/bindings/telegram` - 取得 Telegram 綁定

**Request:**

```bash
curl -X GET http://localhost:8000/bindings/telegram \
  -H "Authorization: Bearer <token>"
```

**Response (200):**

```json
{
  "id": 1,
  "service": "telegram",
  "service_id": "123456789",
  "enabled": true
}
```

**Error (404):**

```json
{ "success": false, "message": "綁定不存在" }
```

---

### POST `/bindings/telegram/code` - 產生綁定碼

**Request:**

```bash
curl -X POST http://localhost:8000/bindings/telegram/code \
  -H "Authorization: Bearer <token>"
```

**Response (200):**

```json
{
  "code": "ABC123",
  "expires_in": 600
}
```

---

### DELETE `/bindings/telegram` - 解除 Telegram 綁定

**Request:**

```bash
curl -X DELETE http://localhost:8000/bindings/telegram \
  -H "Authorization: Bearer <token>"
```

**Response (200):**

```json
{ "success": true }
```

---

### PATCH `/bindings/telegram/toggle` - 啟用/停用綁定

**Request:**

```bash
curl -X PATCH http://localhost:8000/bindings/telegram/toggle?enabled=false \
  -H "Authorization: Bearer <token>"
```

**Response (200):**

```json
{ "success": true }
```

---

## Telegram Webhook `/webhook/telegram`

### POST `/webhook/telegram` - 接收 Telegram 更新

> Telegram 自動呼叫，不需手動觸發

---

### POST `/webhook/telegram/setup` - 設定 Webhook

**Request:**

```bash
curl -X POST http://localhost:8000/webhook/telegram/setup
```

**Response (200):**

```json
{
  "success": true,
  "webhook_url": "https://example.com/webhook/telegram"
}
```

---

### GET `/webhook/telegram/info` - 查詢 Webhook 狀態

**Request:**

```bash
curl -X GET http://localhost:8000/webhook/telegram/info
```

**Response (200):**

```json
{
  "url": "https://example.com/webhook/telegram",
  "has_custom_certificate": false,
  "pending_update_count": 0
}
```

---

## 爬蟲 `/checker`

### POST `/checker/run` - 手動觸發爬蟲

**Request:**

```bash
curl -X POST http://localhost:8000/checker/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "region": 1,
    "max_items": 10
  }'
```

**Response (200):**

```json
{
  "region": 1,
  "fetched": 10,
  "new_count": 3,
  "matches": 2,
  "broadcast": {
    "total": 2,
    "success": 2,
    "failed": 0
  }
}
```

---

## 健康檢查

### GET `/health` - 健康檢查

**Request:**

```bash
curl -X GET http://localhost:8000/health
```

**Response (200):**

```json
{ "status": "healthy" }
```

---

## 訂閱條件欄位說明

| 欄位              | 類型    | 必填 | 說明                                   |
| ----------------- | ------- | ---- | -------------------------------------- |
| `name`            | string  | ✅   | 訂閱名稱                               |
| `region`          | int     | ✅   | 縣市代碼 (1=台北市, 3=新北市)          |
| `section`         | int[]   | -    | 區域代碼陣列                           |
| `kind`            | int[]   | -    | 1=整層, 2=獨立套房, 3=分租套房, 4=雅房 |
| `price_min`       | int     | -    | 最低租金                               |
| `price_max`       | int     | -    | 最高租金                               |
| `area_min`        | float   | -    | 最小坪數                               |
| `area_max`        | float   | -    | 最大坪數                               |
| `layout`          | int[]   | -    | 1=1房, 2=2房, 3=3房, 4=4房以上         |
| `floor`           | str[]   | -    | "1_1", "2_6", "6_12", "13_"            |
| `features`        | str[]   | -    | near_subway, pet, cook, lift 等        |
| `options`         | str[]   | -    | cold, washer, icebox 等                |
| `exclude_rooftop` | bool    | -    | 排除頂樓加蓋 (預設 false)              |
| `gender`          | string  | -    | boy=限男, girl=限女, null=不限         |
| `pet_required`    | bool    | -    | 需要可養寵物 (預設 false)              |

詳見 [OPTIONS.md](OPTIONS.md)
