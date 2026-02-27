## Why

Admins need a safe, fast way to adjust product pricing without code changes and redeploys. Prices already live in the `prices` table, but the admin mini app has no section to view/edit them.

## What Changes

- Add a new Admin Mini App section/tab labeled **Цены** (separate from **Рассылка** and other tabs).
- Show current rows from the `prices` table as a table (one row per `ProductOption`).
- Allow editing `price` (RUB) and `reports_amount` and saving changes back to the database.
- Add admin API endpoints to read and update prices, protected by the existing Telegram WebApp `initData` auth.

## Capabilities

### New Capabilities
- `admin-prices`: Admin API + data model for listing and updating entries in the `prices` table (`option`, `price`, `reports_amount`).

### Modified Capabilities
- `admin-miniapp`: Extend the Admin Mini App UI to include a **Цены** tab and integrate it with the new admin prices endpoints.

## Impact

- Admin Mini App UI (`api/miniapp.py`): new tab, table UI, load/save flows.
- Admin API (`api/admin_handlers.py`, `api/admin_models.py`): new request/response models and handlers under `/api/admin/*`.
- DB access (`database/queries.py`): queries to select/update `prices`.
- Tests (`tests/test_admin_handlers.py`): coverage for new endpoints and auth/validation behavior.

