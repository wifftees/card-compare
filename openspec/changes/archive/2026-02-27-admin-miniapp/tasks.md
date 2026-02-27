## 1. Config & wiring

- [x] 1.1 Add `PUBLIC_BASE_URL` setting/env loading and validation
- [x] 1.2 Update `/admin` handler to reply with only a Web App button to `PUBLIC_BASE_URL + "/miniapp/admin"`
- [x] 1.3 Ensure `settings.admin_id_list` is configured and used consistently for admin gating

## 2. Telegram WebApp auth (server-side)

- [x] 2.1 Implement Telegram `initData` parsing + HMAC-SHA256 verification utility (bot token)
- [x] 2.2 Add reusable `aiohttp` guard for `/api/admin/*` that reads `X-Telegram-Init-Data`, verifies it, extracts `user.id`, and enforces `admin_id_list`
- [x] 2.3 Add minimal unit tests for initData verification and admin allowlist behavior

## 3. Admin Mini App HTTP surface

- [x] 3.1 Add `GET /miniapp/admin` route that returns `index.html` (Telegram WebApp JS + minimal UI)
- [x] 3.2 Implement Mini App frontend JS to call admin APIs with `X-Telegram-Init-Data` on every request
- [x] 3.3 Add basic error rendering for 401/403 and API failures

## 4. Admin APIs: conversions and usernames

- [x] 4.1 Implement `POST /api/admin/conversions` handler (input categories → counts + step conversion %)
- [x] 4.2 Implement `POST /api/admin/usernames` handler (input category → list usernames)
- [x] 4.3 Reuse/port logic from `bot/handlers/admin.py` to ensure results match existing admin functionality

