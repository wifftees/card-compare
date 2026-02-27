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

### Requirement: Broadcast tab in Admin Mini App

The Admin Mini App MUST include a third tab labeled **Рассылка** (Broadcast), displayed alongside Обзор and Конверсии. All user-facing text in this tab MUST be in Russian.

The Broadcast tab MUST provide:
1. A category selector (single-select) populated with the same categories as the Конверсии tab (from `GET /api/admin/categories`).
2. A text input (or textarea) for the message to send.
3. A send button that triggers `POST /api/admin/broadcast` with the selected category and message.

Before sending, the UI MAY show a confirmation step (e.g. preview + "Подтвердить отправку"). After sending, the UI MUST display the result (sent count, failed count) in Russian.

#### Scenario: Admin selects category and sends broadcast

- **WHEN** an admin opens the Broadcast tab
- **THEN** the admin sees a category dropdown and a message input
- **AND WHEN** the admin selects a category, types a message, and clicks send (and confirms if applicable)
- **THEN** the client calls `POST /api/admin/broadcast` with `{ "category": N, "message": "..." }`
- **AND THEN** the client displays the result (e.g. "Отправлено: X, Ошибок: Y")

#### Scenario: Broadcast tab uses same categories as Conversions

- **WHEN** the Admin Mini App loads
- **THEN** the Broadcast tab category selector is populated from the same `GET /api/admin/categories` response used by the Конверсии tab
- **AND THEN** category labels are displayed in Russian (as returned by the API)

### Requirement: Prices tab in Admin Mini App

The Admin Mini App MUST include a tab labeled **Цены** displayed alongside existing tabs (e.g. Обзор, Конверсии, Рассылка). All user-facing text in this tab MUST be in Russian.

The Prices tab MUST:
1. Load the current `prices` table rows from `GET /api/admin/prices`.
2. Render a table with one row per `ProductOption`.
3. Allow editing `price` (RUB integer) and `reports_amount` (integer) values.
4. Provide an explicit save action that sends all edited rows to `POST /api/admin/prices`.
5. Display a Russian success/error message after attempting to save.

#### Scenario: Admin views current prices
- **WHEN** an admin opens the Prices tab
- **THEN** the client calls `GET /api/admin/prices`
- **AND THEN** the client displays a table of price rows

#### Scenario: Admin edits and saves prices
- **WHEN** an admin edits one or more table cells and clicks “Сохранить”
- **THEN** the client calls `POST /api/admin/prices` with the updated rows
- **AND THEN** the client displays the save result in Russian

