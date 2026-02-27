# admin-miniapp Specification

## Purpose
TBD - created by archiving change admin-miniapp. Update Purpose after archive.
## Requirements
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
`POST /api/admin/conversions` MUST accept a request that identifies:
- a range preset (`1d|7d|1m|all`)
- an ordered sequence of category numbers (integers) representing conversion groups

For the selected range, each category MUST resolve to a set of user IDs \(U(G)\):
- Event-based category: distinct `events.user_id` where `event_type` matches the category's event(s) and `events.timestamp ∈ range`.
- Callable/segment category: category maps to a server-side function returning user IDs; it MAY ignore range.

The endpoint MUST return:
- `groups`: one entry per requested category with:
  - `category`: the category number
  - `size`: \(|U(G)|\)
  - `range_applied`: boolean indicating whether the selected range was applied when computing \(U(G)\)
- `conversions`: one entry per adjacent transition \(G_i → G_{i+1}\) with:
  - `from_category`, `to_category`
  - `numerator`: \(|U(G_{i+1}) ∩ U(G_i)|\)
  - `denominator`: \(|U(G_i)|\)
  - `percent`: `numerator / denominator * 100` when `denominator > 0`, otherwise `null`

#### Scenario: Compute conversions for a 3-step funnel
- **WHEN** an admin submits categories `[1, 3, 10]` with `range="7d"`
- **THEN** the server returns `groups` for categories `1`, `3`, and `10` including `size` for each
- **AND THEN** the server returns conversion entries for `1→3` and `3→10`

### Requirement: Usernames endpoint returns usernames for a category
`POST /api/admin/usernames` MUST accept a request that identifies a single category number (integer).

The endpoint MUST return the list of usernames in that category.

#### Scenario: Export usernames for a category
- **WHEN** an admin submits category `5`
- **THEN** the server responds with a list of usernames for category `5`

