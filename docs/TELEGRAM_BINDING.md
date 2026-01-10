# Telegram 綁定流程說明

> 更新日期：2025-01-11

## 概述

簡化 Telegram 綁定流程，使用者不需要手動輸入綁定碼，點擊連結即可自動完成綁定。

---

## 綁定流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   前端網頁   │────▶│   後端 API   │────▶│  Telegram   │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                    │
      │  1. POST /bindigs/telegram             │
      │ ──────────────────▶│                    │
      │                    │                    │
      │  2. 回傳 bind_url  │                    │
      │ ◀──────────────────│                    │
      │                    │                    │
      │  3. 開啟 bind_url (Deep Link)          │
      │ ───────────────────────────────────────▶│
      │                    │                    │
      │                    │  4. Bot 自動綁定   │
      │                    │◀───────────────────│
      │                    │                    │
      │  5. 綁定完成，重新查詢狀態              │
      │ ──────────────────▶│                    │
```

### 步驟說明

1. **前端呼叫綁定 API**
   - `POST /bindings/telegram`
   - 需要 JWT Token 認證

2. **後端回傳綁定連結**
   - 回傳 `bind_url`（Telegram Deep Link）
   - 綁定碼有效期 10 分鐘

3. **前端開啟連結**
   - 使用 `window.open(bind_url)` 或 `<a href={bind_url}>`
   - 手機會自動開啟 Telegram App
   - 電腦會開啟 Telegram Web 或桌面版

4. **Bot 自動完成綁定**
   - 使用者進入 Bot 後會自動發送 `/start BIND_xxx`
   - Bot 驗證綁定碼並完成綁定
   - Bot 回覆「綁定成功」

5. **前端更新狀態**
   - 使用者返回網頁後，重新查詢綁定狀態
   - `GET /bindings/telegram`

---

## API 規格

### 開始綁定

```
POST /bindings/telegram
Authorization: Bearer <token>
```

#### Response

```json
{
  "code": "A1B2C3",
  "expires_in": 600,
  "bind_url": "https://t.me/YourBot?start=BIND_A1B2C3"
}
```

| 欄位 | 類型 | 說明 |
|------|------|------|
| `code` | string | 綁定碼（6 碼） |
| `expires_in` | number | 有效秒數（600 = 10 分鐘） |
| `bind_url` | string | Telegram 綁定連結 |

---

### 查詢綁定狀態

```
GET /bindings/telegram
Authorization: Bearer <token>
```

#### Response（未綁定）

```json
{
  "service": "telegram",
  "is_bound": false,
  "service_id": null,
  "enabled": false,
  "created_at": null
}
```

#### Response（已綁定）

```json
{
  "service": "telegram",
  "is_bound": true,
  "service_id": "123456789",
  "enabled": true,
  "created_at": "2025-01-11T12:00:00+08:00"
}
```

| 欄位 | 類型 | 說明 |
|------|------|------|
| `service` | string | 服務類型（固定 `telegram`） |
| `is_bound` | boolean | 是否已綁定 |
| `service_id` | string | Telegram Chat ID |
| `enabled` | boolean | 是否啟用通知 |
| `created_at` | string | 綁定時間 |

---

### 解除綁定

```
DELETE /bindings/telegram
Authorization: Bearer <token>
```

#### Response

```json
{
  "success": true
}
```

---

### 開關通知

```
PATCH /bindings/telegram/toggle?enabled=true
Authorization: Bearer <token>
```

#### Response

```json
{
  "success": true
}
```

---

## 前端實作建議

### 綁定按鈕

```tsx
const handleBind = async () => {
  try {
    const res = await fetch('/api/bindings/telegram', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();

    if (data.bind_url) {
      // 開啟 Telegram 綁定連結
      window.open(data.bind_url, '_blank');

      // 提示使用者完成後返回
      showToast('請在 Telegram 完成綁定後返回此頁面');

      // 可選：輪詢檢查綁定狀態
      startPollingBindStatus();
    }
  } catch (error) {
    showError('綁定失敗');
  }
};
```

### 輪詢綁定狀態（可選）

```tsx
const startPollingBindStatus = () => {
  const interval = setInterval(async () => {
    const status = await fetchBindingStatus();

    if (status.is_bound) {
      clearInterval(interval);
      showToast('綁定成功！');
      refreshUserData();
    }
  }, 3000); // 每 3 秒檢查一次

  // 5 分鐘後停止輪詢
  setTimeout(() => clearInterval(interval), 5 * 60 * 1000);
};
```

### UI 狀態

| 狀態 | 顯示 | 操作 |
|------|------|------|
| 未綁定 | 「綁定 Telegram」按鈕 | 呼叫 POST API |
| 已綁定 | 顯示 Chat ID + 開關 | 解綁 / 開關通知 |

---

## 注意事項

1. **Deep Link 行為**
   - 手機：自動開啟 Telegram App
   - 電腦：可能開啟新分頁或桌面版
   - 使用者需要手動返回網頁

2. **綁定碼有效期**
   - 10 分鐘內有效
   - 過期需重新產生

3. **重複綁定**
   - 同一 Telegram 帳號只能綁定一個網站帳號
   - 已綁定的使用者會收到錯誤訊息

4. **環境變數**
   - 後端需設定 `TELEGRAM_BOT_USERNAME`
   - 否則 `bind_url` 會是 `null`

---

## 測試檢查清單

- [ ] 點擊綁定按鈕能取得 `bind_url`
- [ ] `bind_url` 能正確開啟 Telegram
- [ ] 在 Telegram 中看到「綁定成功」訊息
- [ ] 返回網頁後狀態更新為已綁定
- [ ] 解除綁定功能正常
- [ ] 開關通知功能正常
