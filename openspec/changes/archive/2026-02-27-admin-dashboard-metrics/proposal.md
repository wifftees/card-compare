## Why

Admins currently lack a quick, auditable view of core business KPIs (users, reports, payments, referrals) and have to rely on ad-hoc checks. Adding a dashboard to the existing Admin Mini App enables faster decisions and easier monitoring without introducing new tooling/build steps.

## What Changes

- Add an **Admin Dashboard** UI to the existing **Admin Mini App** (`GET /miniapp/admin`) with two tabs:
  - **Overview**: KPIs for core usage, payments, referrals, repeat reporters, and payer segmentation.
  - **Conversions**: conversion percentages between selected “groups”, derived from existing conversion categories.
- Add **manual refresh** behavior per tab (no background polling).
- Add **range presets** (`1d`, `7d`, `1m`, `all-time`) that drive server-side filtering where applicable.
- Add **tooltip help** for every metric label (including conversion formulas with numerator/denominator for auditability).
- Add/extend **admin API endpoints** under `/api/admin/*` to serve dashboard metrics, authorized via existing Telegram WebApp `X-Telegram-Init-Data`.

## Capabilities

### New Capabilities
- `admin-dashboard-metrics`: Admin Mini App dashboard (Overview + Conversions UI) and backend metrics APIs, including range presets, manual refresh semantics, and tooltip/auditability requirements.

### Modified Capabilities
- `admin-miniapp`: Extend the Admin Mini App requirements to include the dashboard UI and update/extend the conversions contract to support range presets and group semantics used by the dashboard.

## Impact

- **UI**: `GET /miniapp/admin` inline HTML/JS will be expanded with Web Components-based UI (CDN-loaded), theming integration with Telegram CSS variables, and refresh/range controls.
- **API**: new/extended `POST /api/admin/*` endpoints for metrics and conversions; existing auth/authorization remains (`X-Telegram-Init-Data`, `settings.admin_id_list`).
- **Data access**: new Supabase queries against existing tables (`users`, `events`, `payments`, `reports`) to compute metrics and group membership sets.
- **Business logic reuse**: conversions “groups” are based on existing `CONVERSION_CATEGORIES` definitions in the bot admin handler.
