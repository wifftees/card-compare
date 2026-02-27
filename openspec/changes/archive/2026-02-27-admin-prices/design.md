## Context

The project already stores product pricing in the `prices` table (`option`, `price`, `reports_amount`) and uses it for purchases, but admins cannot adjust it via UI. The Admin Mini App currently exposes multiple tabs (e.g. Обзор / Конверсии / Рассылка) and communicates with `/api/admin/*` endpoints authorized via Telegram WebApp `initData` (`X-Telegram-Init-Data`).

This change adds a new admin-facing “Цены” section to view and update rows in `prices`.

## Goals / Non-Goals

**Goals:**
- Add a new Admin Mini App tab labeled **Цены** with a table UI to view/edit prices.
- Add admin API endpoints to list and update `prices` rows (admin-only, initData-protected).
- Provide basic validation so malformed/unsafe values cannot be persisted.
- Make the flow robust for partial failures and easy to test.

**Non-Goals:**
- No redesign of the existing payments flow, products catalog, or user purchase UX.
- No new pricing rules engine (discounts, promo codes, time-based pricing).
- No multi-currency support.
- No admin role model beyond the existing `settings.admin_id_list` allowlist.

## Decisions

### API shape: list + bulk update by `option`

- Add `GET /api/admin/prices` to fetch the full list of price rows.
- Add `POST /api/admin/prices` (bulk update) where the request contains a list of rows keyed by `option`.

Rationale:
- The UI needs to show the whole table and allow multiple edits before saving.
- Bulk update reduces round-trips and simplifies “Save” UX.
- `option` is a natural stable key because it is already the primary identifier in code (`ProductOption`).

### Update semantics: upsert / last-write-wins

The update endpoint should update existing rows (and MAY upsert missing ones) with last-write-wins semantics.

Rationale:
- The admin UI is a single screen with a final “Save”; concurrent edits are rare.
- Upsert keeps the system resilient if a new `ProductOption` is introduced and the table is missing a row.

### Validation rules (server-side)

- `option` MUST be a valid `ProductOption`.
- `price` MUST be an integer in RUB and MUST be \(\ge 0\).
- `reports_amount` MUST be an integer and MUST be \(> 0\).

Rationale:
- Prevent breaking purchases and balance crediting due to negative/zero quantities.
- Keep validation minimal and aligned with existing integer representation.

### UI: table with inline editing + explicit save

The “Цены” tab should:
- Load data on open (or on app init) and render as a table.
- Allow inline edits for `price` and `reports_amount`.
- Provide an explicit “Сохранить” action; optionally a confirm dialog.
- After save, show a Russian success/error message and refresh the table from the server.

Rationale:
- Minimizes accidental changes (explicit save).
- Refresh ensures the UI reflects server truth after updates.

## Risks / Trade-offs

- **Accidental wrong prices** → Mitigation: explicit save, optional confirmation, and post-save refresh.
- **Concurrent edits by multiple admins** → Mitigation: last-write-wins is acceptable; UI refresh after save reduces confusion.
- **Missing rows in `prices` table** → Mitigation: upsert behavior (or clear error message if upsert is not supported).
- **Breaking changes to purchases if invalid values slip in** → Mitigation: strict server-side validation; tests for edge cases.

## Migration Plan

- No DB schema migration required.
- Deploy server changes first (new endpoints) behind existing admin auth.
- Deploy UI changes next (new “Цены” tab).
- Rollback: UI can be reverted independently; endpoints are additive and can remain without affecting users.

## Open Questions

- Should we require a confirmation step for saving price changes (yes/no)?
- Should we include any “audit” trail (who changed what) in the future?

