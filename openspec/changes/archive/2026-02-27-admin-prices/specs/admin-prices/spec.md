## ADDED Requirements

### Requirement: List prices for admin UI

The server MUST expose `GET /api/admin/prices` that returns the full set of rows from the `prices` table.

The response MUST include, for each row:
- `option`: a `ProductOption` identifier
- `price`: integer (RUB)
- `reports_amount`: integer

The endpoint MUST require admin authentication via `X-Telegram-Init-Data` (Telegram WebApp initData), consistent with other `/api/admin/*` endpoints.

#### Scenario: Admin loads prices table
- **WHEN** an admin calls `GET /api/admin/prices` with a valid `X-Telegram-Init-Data`
- **THEN** the server responds with HTTP 200 and a JSON body containing a list of all prices

#### Scenario: Non-admin request is rejected
- **WHEN** a non-admin (or unauthenticated) client calls `GET /api/admin/prices`
- **THEN** the server responds with HTTP 401 or 403

### Requirement: Update prices in bulk

The server MUST expose `POST /api/admin/prices` that accepts a JSON body containing a list of price rows to update, keyed by `option`.

For each submitted row, the server MUST update the corresponding row in the `prices` table (and MAY upsert if the row does not exist).

The endpoint MUST validate each submitted row:
- `option` MUST be a valid `ProductOption`
- `price` MUST be an integer and MUST be \(\ge 0\)
- `reports_amount` MUST be an integer and MUST be \(> 0\)

If validation fails for any row, the server MUST reject the request with HTTP 400 and MUST NOT apply partial updates.

The endpoint MUST require admin authentication via `X-Telegram-Init-Data`.

#### Scenario: Admin updates multiple price rows
- **WHEN** an admin calls `POST /api/admin/prices` with valid rows
- **THEN** the server persists the new values to the `prices` table
- **AND THEN** the server responds with a success response indicating the update completed

#### Scenario: Validation error rejects update
- **WHEN** an admin calls `POST /api/admin/prices` with `reports_amount=0` for any row
- **THEN** the server responds with HTTP 400
- **AND THEN** the server does not update any rows

