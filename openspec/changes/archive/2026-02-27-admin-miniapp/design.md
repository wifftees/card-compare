## Context

The bot is a single async Python process that runs aiogram polling and an embedded `aiohttp` server (webhooks + health). Admin functionality currently lives in Telegram chat flows (`bot/handlers/admin.py`) and includes:
- conversions analytics based on “category numbers”
- exporting usernames for a category

We want to keep the user-facing bot UI unchanged while moving admin operations into a Telegram Mini App (Web App). The Mini App must be securely gated to admins and hosted behind nginx HTTPS on a VPS, proxying to the existing container on `:8080`.

## Goals / Non-Goals

**Goals:**
- Provide an Admin Mini App at `GET /miniapp/admin` that reproduces the current admin features from `bot/handlers/admin.py`.
- Add admin API endpoints under `/api/admin/*` served by the embedded `aiohttp` app.
- Implement **server-side Telegram WebApp authentication**:
  - client sends `window.Telegram.WebApp.initData` in every request via `X-Telegram-Init-Data`
  - server verifies `initData` (HMAC-SHA256 using bot token), extracts Telegram `user.id`
  - server authorizes only admins (`settings.admin_id_list`)
- Preserve existing endpoints (`POST /api/payment/yookassa`, `GET /health`) and existing Telegram bot user flows.
- Make the `/admin` command reply with **only** a Web App button that opens the Admin Mini App URL derived from `PUBLIC_BASE_URL`.

**Non-Goals:**
- No changes to `/start` menu, user-facing callbacks, report flow, payments, or notifications engine behavior.
- No attempt to build a complex SPA; the Mini App UI is intentionally minimal (HTML + JS) to reduce dependencies and maintenance.

## Decisions

### Serve the Mini App from the existing `aiohttp` server
- **Decision**: Extend `api/server.py` to add `GET /miniapp/admin` returning an `index.html` (and optionally a small JS/CSS payload).
- **Rationale**: Keeps deployment as a single container/process, matches current architecture, and avoids introducing a separate web service.
- **Alternatives considered**:
  - Separate web service/container: adds operational complexity (extra deploy, networking, health, logs).
  - Hosting static files only in nginx: still needs API auth + API host; coupling is manageable but coordination is harder.

### Stateless auth via header on every request
- **Decision**: The Mini App sends `initData` with every API call using `X-Telegram-Init-Data`.
- **Rationale**: Simple, no server-side sessions, no cookies, no CSRF surface, works well behind reverse proxy.
- **Alternatives considered**:
  - Issue server session after first verification: fewer bytes per request, but more state and session invalidation concerns.

### Centralize auth verification + admin gate for `/api/admin/*`
- **Decision**: Implement a small auth helper that:
  - parses and validates Telegram `initData`
  - extracts `user.id`
  - checks membership in `settings.admin_id_list`
  - rejects with 401/403
- **Rationale**: Security-critical logic should be shared, tested, and consistently applied to all admin endpoints.
- **Alternatives considered**:
  - Duplicating checks inside handlers: error-prone and easy to miss on new endpoints.

## Risks / Trade-offs

- **[Security: initData verification is easy to get wrong] → Mitigation**: Implement verification strictly per Telegram algorithm; add unit tests with known-good vectors; enforce admin allowlist.
- **[Reverse proxy header handling / URL mismatches] → Mitigation**: Use `PUBLIC_BASE_URL` for Web App URL; keep `/miniapp/admin` path stable; document nginx config and BotFather allowlist requirements.

## Migration Plan

1. Add `PUBLIC_BASE_URL` to environment (e.g. `https://your-domain.com`).
2. Configure nginx to terminate HTTPS and proxy to `http://127.0.0.1:8080`.
3. Add the public domain to BotFather Mini App/Web App domain allowlist.
4. Deploy new container image and restart.
5. Validate:
   - `/admin` shows only the Web App button
   - Mini App loads at `https://<domain>/miniapp/admin`
   - Non-admins get 401/403 for `/api/admin/*`
   - Admin requests succeed for conversions/usernames

**Rollback**: Revert `/admin` handler to prior behavior and remove `/miniapp/admin` + `/api/admin/*` routes; keep nginx proxy unchanged (safe).

## Open Questions

- Do we need additional hardening (e.g., strict `Origin`/`Referer` checks) beyond `initData` validation?
