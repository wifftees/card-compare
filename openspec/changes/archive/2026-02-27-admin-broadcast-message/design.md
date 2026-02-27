# Admin Broadcast Message — Design

## Context

The Admin Mini App (`api/miniapp.py`) currently has two tabs: **Обзор** (Overview) and **Конверсии** (Conversions). Both use `GET /api/admin/categories` to load the conversion category list and `POST /api/admin/conversions` / `POST /api/admin/overview` for data. The legacy bot flow (`bot/handlers/admin.py`) has a separate broadcast feature using `GROUP_QUERY_MAP` (no_activity, used_trial, bought_single), which differs from `CONVERSION_CATEGORIES`. This design adds a Broadcast tab to the Mini App that reuses `CONVERSION_CATEGORIES` for consistency.

## Goals / Non-Goals

**Goals:**
- Add a Broadcast tab to the Admin Mini App with Russian UI text.
- Implement two-step flow: select category → type message → send.
- Reuse existing `CONVERSION_CATEGORIES` and `_resolve_user_ids` for target resolution.
- Add `POST /api/admin/broadcast` endpoint protected by admin auth.
- Send messages via Telegram Bot API with rate limiting (~30 msg/sec).

**Non-Goals:**
- Changing the legacy bot broadcast flow.
- HTML/rich formatting in broadcast messages (plain text only).
- Scheduling or delayed sends.
- Multi-category broadcast in a single request.

## Decisions

### 1. Single category per broadcast
**Decision:** One category per broadcast request. Admin selects one category, types message, sends.

**Rationale:** Matches the user's described flow and keeps the API simple. Multi-category can be added later if needed.

**Alternatives considered:** Allow multiple categories in one request — rejected for MVP simplicity.

### 2. Synchronous send in HTTP handler
**Decision:** The broadcast handler fetches user IDs, iterates, and sends messages within the request lifecycle. No background queue.

**Rationale:** Admin expects immediate feedback (sent/failed counts). For typical segment sizes (<10k users), in-request send is acceptable. Telegram rate limit (~30 msg/sec) is respected with `asyncio.sleep(0.05)` between sends.

**Alternatives considered:** Enqueue to a worker — adds complexity; defer to future if scale demands it.

### 3. Reuse `_resolve_user_ids` from admin_handlers
**Decision:** Use the same `_resolve_user_ids(source)` helper that `usernames_handler` uses. Categories are all-time (no range) for broadcast, matching usernames behavior.

**Rationale:** Avoids duplication and ensures broadcast targets match the same logic as conversions/usernames.

### 4. Bot instance for sending
**Decision:** The API layer needs access to the aiogram `Bot` instance to call `bot.send_message`. Inject via `request.app` or a shared app state (e.g. `request.app["bot"]`).

**Rationale:** The aiohttp app and aiogram bot run in the same process (`main.py`). The server setup already has access to the bot; we pass it into the app for admin routes.

**Alternatives considered:** Separate service — overkill for single-process setup.

### 5. Response format
**Decision:** Return `{ "sent": N, "failed": M }` after completion. Optionally include `total` for clarity.

**Rationale:** Simple, sufficient for UI feedback. No need to return failed user IDs in the response (logged server-side).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Long-running request for large segments | Add timeout; consider future async/queue for >5k users |
| User blocks bot → send fails | Catch exception, increment `failed`, continue; log failed IDs |
| Bot instance not available in request | Ensure `main.py` passes bot to aiohttp app state at startup |
| Duplicate broadcast (double-click) | Disable submit button after click; optional: idempotency key later |

## Migration Plan

1. Add `POST /api/admin/broadcast` route and handler.
2. Add Broadcast tab to `api/miniapp.py` HTML/JS.
3. Ensure bot is available in aiohttp app (verify `main.py` wiring).
4. Deploy; no DB migrations required.
5. **Rollback:** Revert miniapp HTML and remove broadcast route; no data to migrate.

## Open Questions

- Should we add a confirmation step (preview + "Send?") in the UI? **Assumption:** Yes, per user's flow — show preview before final send.
- Should the legacy bot broadcast be deprecated? **Assumption:** No change in this design; can be addressed separately.
