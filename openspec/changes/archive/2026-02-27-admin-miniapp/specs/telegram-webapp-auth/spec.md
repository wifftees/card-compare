## ADDED Requirements

### Requirement: Verify Telegram WebApp initData for admin API access
All `/api/admin/*` endpoints MUST require a valid Telegram Web App `initData` value provided by the client in the `X-Telegram-Init-Data` request header.

The server MUST validate `initData` server-side using the Telegram algorithm (HMAC-SHA256 with the bot token) and MUST reject requests with missing/invalid `initData`.

#### Scenario: Missing initData header
- **WHEN** a client calls any `/api/admin/*` endpoint without `X-Telegram-Init-Data`
- **THEN** the server responds with `401 Unauthorized`

#### Scenario: Invalid initData signature
- **WHEN** a client calls any `/api/admin/*` endpoint with a malformed or invalid `X-Telegram-Init-Data`
- **THEN** the server responds with `401 Unauthorized`

### Requirement: Authorize admin access by Telegram user id allowlist
After `initData` verification, the server MUST extract Telegram `user.id` from the verified data and MUST allow access only if `user.id` is present in `settings.admin_id_list`.

The server MUST reject verified-but-non-admin users.

#### Scenario: Verified user is not an admin
- **WHEN** a non-admin Telegram user opens the Mini App and calls `/api/admin/*` with valid `initData`
- **THEN** the server responds with `403 Forbidden`

#### Scenario: Verified user is an admin
- **WHEN** an admin Telegram user calls `/api/admin/*` with valid `initData`
- **THEN** the server processes the request and responds normally

### Requirement: Stateless auth transport for all admin endpoints
The client MUST send `X-Telegram-Init-Data` on every request to `/api/admin/*` (no server sessions required).

#### Scenario: Multiple independent API calls
- **WHEN** the Mini App performs multiple API calls in sequence (conversions, usernames)
- **THEN** each call is authorized solely by `X-Telegram-Init-Data` and does not depend on prior requests

