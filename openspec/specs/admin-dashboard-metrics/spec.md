# admin-dashboard-metrics Specification

## Purpose
Provide an Admin Dashboard inside the existing Admin Mini App to view business metrics (Overview) and compute group-to-group conversion percentages (Conversions), with manual refresh and range presets.

## Requirements

### Requirement: Dashboard range presets are applied consistently
All dashboard requests that are range-aware MUST support the following range presets:
- `1d`: last 24 hours
- `7d`: last 7 * 24 hours
- `1m`: last 30 * 24 hours
- `all`: no lower bound

For a given refresh, the server MUST define:
- `range_end`: server "now"
- `range_start`:
  - `range_end - duration` for `1d/7d/1m`
  - `null` for `all`

#### Scenario: Server computes a 7d range
- **WHEN** the admin requests any range-aware dashboard data with `range="7d"`
- **THEN** the server uses a `range_end` equal to server "now"
- **AND THEN** the server uses `range_start = range_end - 7 days`

### Requirement: Overview metrics endpoint returns required sections
The server MUST expose `POST /api/admin/overview` that returns dashboard metrics for the selected range.

The response MUST include:
- `range`: the requested preset (`1d|7d|1m|all`)
- `range_start` and `range_end` as ISO-8601 timestamps (or `range_start=null` for `all`)
- `core_kpis`
- `payments`
- `referrals`
- `repeat_reporters`
- `payer_segmentation`

#### Scenario: Admin requests Overview for 1d
- **WHEN** an admin calls `POST /api/admin/overview` with `{"range":"1d"}`
- **THEN** the server responds `200 OK` with JSON including `range="1d"`, `range_start`, and `range_end`
- **AND THEN** the JSON includes `core_kpis`, `payments`, `referrals`, `repeat_reporters`, and `payer_segmentation` objects

### Requirement: Overview core KPIs are computed from users and reports
For `POST /api/admin/overview`, `core_kpis` MUST include:
- `new_users`: count of `users` with `created_at ∈ [range_start, range_end]` (or `created_at <= range_end` for `all`)
- `active_users`: count of `users` with `last_active_at ∈ [range_start, range_end]` (range presets other than `all`)
- `reports_generated`: count of `reports` where `state="GENERATED"` and the completion timestamp is within range:
  - preferred: `reports.updated_at ∈ [range_start, range_end]`
  - fallback: `reports.created_at ∈ [range_start, range_end]` if `updated_at` is missing

#### Scenario: Overview response includes core KPIs
- **WHEN** an admin calls `POST /api/admin/overview` for any range preset
- **THEN** the server responds with `core_kpis.new_users`, `core_kpis.active_users`, and `core_kpis.reports_generated`

### Requirement: Overview payment metrics are computed from payments
For `POST /api/admin/overview`, `payments` MUST be computed from `payments` filtered by `payments.created_at ∈ range` and MUST include:
- `revenue`: sum of `payments.total_price` where `payments.status="SUCCESS"`
- `paying_users`: count of distinct `payments.user_id` where `payments.status="SUCCESS"`
- `by_status`: counts grouped by `payments.status`
- `revenue_by_option`: sum of `payments.total_price` grouped by `payments.option` for `payments.status="SUCCESS"`

#### Scenario: Overview response includes payment metrics
- **WHEN** an admin calls `POST /api/admin/overview` for any range preset
- **THEN** the server responds with `payments.revenue`, `payments.paying_users`, `payments.by_status`, and `payments.revenue_by_option`

### Requirement: Overview referral metrics are computed from invited_by, events, and payments
For `POST /api/admin/overview`, `referrals` MUST include at least the following fields, computed per the selected range where applicable:
- `active_referrers`: distinct `users.invited_by` among users created in range with `invited_by` not null
- `new_referred_users`: count of users created in range with `invited_by` not null
- `referrals_per_referrer_avg`: average referrals per active referrer (based on referred users created in range)
- `referrals_per_referrer_median`: median referrals per active referrer (based on referred users created in range)
- `top_referrers_by_referred_users`: top N inviters by referred users created in range
- `qualified_referrals_count`: referred users created in range who have ≥1 activation event in range
- `qualified_referrals_rate`: `qualified_referrals_count / new_referred_users` (or `null` if denominator is 0)
- `referred_revenue`: revenue from `SUCCESS` payments in range made by users with `users.invited_by` not null
- `top_referrers_by_referred_revenue`: top N inviters by referred revenue in range
- `referral_funnel`: aggregated counts for created → activated → paid for referred users in the selected range
- `estimated_bonus_earned`: recomputed bonus total for the range as `ceil(payment.total_price * 0.2)` for each `SUCCESS` payment in range made by a referred user, attributed to their inviter

Activation event for qualified referrals MUST be `EventType.CLICK_COMPARE`.

#### Scenario: Overview response includes referral section
- **WHEN** an admin calls `POST /api/admin/overview` for any range preset
- **THEN** the response includes a `referrals` object containing the referral fields described in this requirement

### Requirement: Repeat reporters are computed all-time
For `POST /api/admin/overview`, `repeat_reporters` MUST ignore the selected range and MUST be computed all-time from `reports` with `state="GENERATED"`:
- `repeat_reporters_count`: count of users with ≥2 generated reports
- `repeat_reporters_rate`: `repeat_reporters_count / total_reporters_count` where `total_reporters_count` is users with ≥1 generated report (or `null` if denominator is 0)

#### Scenario: Overview includes repeat reporters regardless of range
- **WHEN** an admin calls `POST /api/admin/overview` with any `range` preset
- **THEN** the response includes `repeat_reporters.repeat_reporters_count` and `repeat_reporters.repeat_reporters_rate`

### Requirement: Payer segmentation splits payers into lifecycle and frequency groups
For `POST /api/admin/overview`, `payer_segmentation` MUST define a "successful payer" as a user with ≥1 `payments` row where `payments.status="SUCCESS"`.

The response MUST include:

- Lifecycle / recency (range-aware unless stated otherwise):
  - `new_payer_count`: users whose first-ever `SUCCESS` payment happened in the selected range
  - `returning_payer_count`: users with a `SUCCESS` payment before `range_start` AND a `SUCCESS` payment in range
  - `churned_payer_count`: users with ≥1 `SUCCESS` payment historically but no `SUCCESS` payments in the last 60 days relative to `range_end`
- Frequency (all-time):
  - `one_time_payer_count`: exactly 1 `SUCCESS` payment all-time
  - `repeat_payer_count`: 2–3 `SUCCESS` payments all-time
  - `power_payer_count`: 4+ `SUCCESS` payments all-time

#### Scenario: Overview includes payer segmentation groups
- **WHEN** an admin calls `POST /api/admin/overview` for any range preset
- **THEN** the response includes `payer_segmentation` with lifecycle/recency and frequency group counts as defined in this requirement
