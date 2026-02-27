## 1. API contracts and shared helpers

- [x] 1.1 Define request/response models for `POST /api/admin/overview` (range preset, response sections)
- [x] 1.2 Define request/response models for `POST /api/admin/conversions` (range + ordered categories, groups + conversions output)
- [x] 1.3 Implement a shared helper to compute `(range_start, range_end)` from the range preset using server time

## 2. Supabase query layer for dashboard metrics

- [x] 2.1 Add query helpers to compute `core_kpis` (new users, active users, reports generated with updated_at fallback)
- [x] 2.2 Add query helpers to compute `payments` section (revenue, paying users, by status, revenue by option)
- [x] 2.3 Add query helpers to compute `referrals` section (active referrers, new referred users, avg/median referrals per referrer, top-N leaderboards, qualified referrals, referred revenue, funnel, estimated bonus)
- [x] 2.4 Add query helpers to compute `repeat_reporters` all-time metrics
- [x] 2.5 Add query helpers to compute `payer_segmentation` groups (new/returning/churned; one-time/repeat/power)

## 3. Implement Overview endpoint

- [x] 3.1 Add `POST /api/admin/overview` aiohttp handler wired into `api/server.py`
- [x] 3.2 Ensure handler uses existing Telegram WebApp auth (`X-Telegram-Init-Data`) and admin allowlist behavior
- [x] 3.3 Implement the handler response assembly to match `admin-dashboard-metrics` spec fields and range metadata

## 4. Extend Conversions endpoint

- [x] 4.1 Update `POST /api/admin/conversions` to accept range preset + ordered category list
- [x] 4.2 Implement per-category group resolution to `U(G)` (event-based by timestamp; callable/segment groups) and return `range_applied` per group
- [x] 4.3 Implement adjacent conversion computation returning numerator/denominator and `percent` (null when denominator is 0)
- [x] 4.4 Keep `/api/admin/usernames` behavior compatible with the updated conversion group semantics (or update it if needed)

## 5. Update Admin Mini App UI (inline HTML)

- [x] 5.1 Add Shoelace (or chosen Web Components kit) via CDN and apply Telegram theme variables for consistent styling
- [x] 5.2 Implement tabs: Overview and Conversions
- [x] 5.3 Implement range preset selector and per-tab Refresh button with loading/spinner state
- [x] 5.4 Implement Overview rendering (cards/tables) with an info icon + tooltip for every metric label
- [x] 5.5 Implement Conversions UI: ordered multi-select groups list sourced from `CONVERSION_CATEGORIES`
- [x] 5.6 Display group sizes table and adjacent conversions as percentages only, with tooltip showing formula and numerator/denominator
- [x] 5.7 Implement “all-time” badge + tooltip for range-unaware groups (based on server `range_applied=false`)
- [x] 5.8 Auto-refresh when range preset changes: when clicking between period ranges, trigger refresh for the active tab (Overview or Conversions) automatically

## 6. Tests and verification

- [x] 6.1 Add tests for range preset helper (1d/7d/1m/all) and boundary handling
- [x] 6.2 Add tests for `POST /api/admin/overview` auth behavior (missing/invalid initData → 401; non-admin → 403)
- [x] 6.3 Add tests for `POST /api/admin/overview` response shape and key computed fields (using controlled fixtures/mocks)
- [x] 6.4 Add tests for `POST /api/admin/conversions` group sizing and adjacent conversion math (including denominator=0)
- [x] 6.5 Manual test in Telegram: open Admin Mini App, switch tabs/ranges, refresh, verify tooltips and badges

## 7. Align Get Usernames UX with conversion groups select

- [x] 7.1 Replace the usernames category `sl-input` (type=number) with `sl-select` for choosing by text label
- [x] 7.2 Populate the usernames select from the same `/api/admin/categories` data, using label format `"N. Label"` (consistent with conversion groups)
- [x] 7.3 Update the usernames button click handler to read the selected category value from the select instead of a number input
