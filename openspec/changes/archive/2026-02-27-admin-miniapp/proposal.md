## Why

Admin operations (conversions analytics, username export) currently run as multi-step Telegram chat flows. This is slow and error-prone for admins and hard to evolve UX-wise. A Telegram Mini App provides a faster, more reliable admin surface while keeping all user-facing bot flows unchanged.

## What Changes

- Add an **Admin Mini App** served by the existing embedded `aiohttp` server at `GET /miniapp/admin`.
- Change admin entry point: `/admin` replies with **only** a Telegram Web App button (no other UI changes; all current `/start` buttons/flows remain as-is).
- Add admin HTTP API endpoints behind Telegram WebApp auth:
  - `POST /api/admin/conversions`
  - `POST /api/admin/usernames`
- Add stateless auth transport: Mini App sends Telegram `initData` on every request via `X-Telegram-Init-Data`.
- Add server-side verification for `initData` (HMAC SHA-256 using bot token), extract Telegram `user.id`, and allow only `settings.admin_id_list` (reject otherwise).
- Add `PUBLIC_BASE_URL` env var to build the Mini App URL for the `/admin` Web App button (`PUBLIC_BASE_URL + "/miniapp/admin"`).
- Deployment shape: HTTPS terminates at nginx on VPS; nginx proxies to the existing container on `:8080` (Mini App URL like `https://<domain>/miniapp/admin`).

## Capabilities

### New Capabilities
- `admin-miniapp`: Admin Mini App UI + server routes that reproduce `bot/handlers/admin.py` features (conversions, usernames).
- `telegram-webapp-auth`: Server-side validation of Telegram Mini App `initData` and admin authorization for all `/api/admin/*` endpoints.

### Modified Capabilities
<!-- none -->

## Impact

- **Bot**: `/admin` handler updated to return only a Web App button (WebAppInfo URL derived from `PUBLIC_BASE_URL`).
- **HTTP server**: `api/server.py` extended with Mini App static route and new admin API routes (existing `/api/payment/yookassa` + `/health` unchanged).
- **Security**: New `initData` verification utility; enforce admin ACL based on `settings.admin_id_list`.
- **Ops/Hosting**: nginx config for HTTPS termination and proxy to `http://127.0.0.1:8080`; Telegram BotFather Web App domain allowlist must include the public domain.
