## ADDED Requirements

### Requirement: Serve Admin Mini App entrypoint
The embedded HTTP server MUST expose `GET /miniapp/admin` that returns an HTML page which can run inside Telegram Web App context.

The page MUST load Telegram Web App JS (`window.Telegram.WebApp`) and MUST be able to read `window.Telegram.WebApp.initData`.

#### Scenario: Admin opens Mini App URL in Telegram
- **WHEN** an admin taps the Web App button produced by `/admin`
- **THEN** Telegram opens `GET /miniapp/admin` inside the Web App container
- **AND THEN** the page initializes with access to `window.Telegram.WebApp.initData`

### Requirement: Mini App uses admin API endpoints with initData header
The Mini App client MUST send `X-Telegram-Init-Data` with every request to `/api/admin/*` using the current `window.Telegram.WebApp.initData` value.

#### Scenario: Conversions request carries initData
- **WHEN** the Mini App calls `POST /api/admin/conversions`
- **THEN** the request includes `X-Telegram-Init-Data` with the current `initData` string

### Requirement: Conversions endpoint returns counts and step conversions
`POST /api/admin/conversions` MUST accept a request that identifies a sequence of category numbers (integers) representing steps in a funnel.

The endpoint MUST return:
- count per step
- conversion percentage per step transition (step \(i-1\) → step \(i\))

#### Scenario: Compute conversions for a 3-step funnel
- **WHEN** an admin submits categories `[1, 2, 3]`
- **THEN** the server returns counts for steps 1, 2, 3
- **AND THEN** the server returns conversion percentages for `1→2` and `2→3`

### Requirement: Usernames endpoint returns usernames for a category
`POST /api/admin/usernames` MUST accept a request that identifies a single category number (integer).

The endpoint MUST return the list of usernames in that category.

#### Scenario: Export usernames for a category
- **WHEN** an admin submits category `5`
- **THEN** the server responds with a list of usernames for category `5`
