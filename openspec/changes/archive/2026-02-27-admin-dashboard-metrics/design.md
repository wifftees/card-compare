## Context

The repository already contains an Admin Mini App served as inline HTML at `GET /miniapp/admin` and a small set of admin-only API endpoints under `/api/admin/*`. Admin API access is stateless and authorized by Telegram WebApp `initData` passed via the `X-Telegram-Init-Data` header and checked against an admin allowlist.

Business data required for the dashboard already exists in Supabase (Postgres) tables (`users`, `events`, `payments`, `reports`) and conversion group definitions already exist in bot code (`CONVERSION_CATEGORIES`).

Constraints:
- Keep the Admin Mini App as a single inline HTML page with no build step.
- Support Telegram theming and WebApp container behavior.
- Prefer server-side aggregation over client-side computation.

## Goals / Non-Goals

**Goals:**
- Provide an Admin Dashboard with **Overview** and **Conversions** tabs inside the existing Admin Mini App.
- Support a single range preset selection (`1d`, `7d`, `1m`, `all-time`) and **manual refresh** per tab.
- Ensure **auditability**: conversion percentages are accompanied by numerator/denominator data (for tooltips).
- Compute metrics from existing Supabase tables with clearly defined time filtering rules.

**Non-Goals:**
- No background polling, real-time streaming, or scheduled refresh.
- No new frontend build tooling (React/Vite/etc.).
- No new DB tables or schema migrations for this change.
- No “reports requested” and no report-generation latency metrics.

## Decisions

- **UI architecture (inline + Web Components)**: keep `GET /miniapp/admin` as a single inline page and use a Web Components UI kit (Shoelace) loaded via CDN. This fits the no-build constraint while enabling tabs, tables, buttons, and tooltips.
- **Single range model**: the client selects exactly one preset; the server derives `range_end = now()` (server time) and `range_start` per preset (or `null` for all-time). Server time is authoritative to avoid client clock skew.
- **API shape**:
  - Add a dedicated dashboard metrics endpoint (Overview) returning a structured response with all required sections (KPIs, payments, referrals, repeat reporters, payer segmentation) and explicit range metadata.
  - Extend/align the conversions endpoint to accept the selected range and an ordered list of group/category identifiers and to return:
    - group sizes
    - adjacent conversions with numerator/denominator and computed percentage
    - per-group metadata indicating whether range was applied (for “all-time” badge behavior).
- **Computation strategy**: use Supabase/Postgres aggregations (counts, distinct counts, group-bys, sums) and only transfer aggregated results to the client. Leaderboards are computed server-side and capped to top N.
- **Tooltips**:
  - UI uses a tooltip component with viewport-aware positioning.
  - Conversion tooltips are driven by the server-provided numerator/denominator to display exact \(a/b\) used.

Alternatives considered:
- **React/Vue + build step**: rejected due to operational overhead and mismatch with “single inline page” constraint.
- **Client-side aggregation**: rejected due to performance, security (data exposure), and auditability concerns.

## Risks / Trade-offs

- **[Risk] Slow or expensive DB queries over large tables** → **Mitigation**: server-side aggregation only, top-N limits, avoid returning raw event/payment rows, and prefer indexed timestamp filters (`created_at`, `timestamp`, `updated_at`) where possible.
- **[Risk] Timestamp inconsistencies (`updated_at` missing/null)** → **Mitigation**: explicitly define fallback logic (e.g., reports use `updated_at` preferred else `created_at`) and keep it consistent between spec and implementation.
- **[Risk] “Range-unaware” conversion groups are ambiguous** → **Mitigation**: make it explicit in the conversions API response per group (`range_applied: true/false`) so UI can badge and tooltip correctly.
- **[Risk] UI complexity without a framework** → **Mitigation**: constrain UI to a small set of Web Components and a simple refresh/render flow per tab; keep state minimal (range + selected groups).

## Migration Plan

- Deploy code changes that:
  - extend `GET /miniapp/admin` UI with new tabs/controls
  - add/extend `/api/admin/*` endpoints for dashboard metrics and conversions
- No DB migrations required.
- Rollback strategy: revert to previous mini app HTML and keep new endpoints unused; existing admin endpoints and auth remain unchanged.

## Open Questions

- Exact endpoint naming for Overview metrics (single `POST /api/admin/overview` vs more granular endpoints).
- Exact response schema versioning (whether to include a `schema_version` field for forward compatibility).
- Whether leaderboards should always be top-10 or configurable in the request.
