## Context

The notification worker (`notifications/service.py`) sends campaign messages using `Bot.send_message(...)` without `reply_markup`, so campaigns cannot include inline call-to-action buttons today. The bot already supports several callback actions (e.g. `show_example_report`, `compare_cards`, `balance`) via existing aiogram callback handlers.

This change adds optional per-campaign inline keyboards to outgoing notification messages while reusing existing `callback_data` strings to avoid changes in callback routing.

## Goals / Non-Goals

**Goals:**
- Add a simple, explicit mapping from `campaign_id` → `InlineKeyboardMarkup` (or no keyboard).
- Send notifications with `reply_markup` when a campaign has a configured keyboard.
- Reuse existing `callback_data` values (no new callback handlers required).
- Keep behavior backward-compatible: campaigns without mapping remain unchanged.

**Non-Goals:**
- No new database tables/columns for keyboard configuration.
- No changes to campaign selection/resolvers logic.
- No per-user dynamic keyboard generation (beyond choosing by `campaign_id`).
- No changes to existing bot callback payload formats or analytics attribution.

## Decisions

1) Keep configuration in code (map), not DB

- **Decision**: Create an in-code `dict[str, InlineKeyboardMarkup]` mapping for keyboards.
- **Rationale**: Small scope and low change rate; avoids schema/migration work; easy to review in PRs.
- **Alternatives considered**:
  - Store keyboard JSON in `notification_campaigns`: adds parsing/validation and DB complexity.
  - Build keyboards inside resolvers: mixes audience selection with UI concerns.

2) Reuse existing callback routes

- **Decision**: Use existing `callback_data` strings (e.g. `show_example_report`) in notification keyboards.
- **Rationale**: Zero new routing; uses already-tested handlers and existing event tracking.
- **Alternatives considered**:
  - New callback namespace including campaign attribution: better analytics, but requires handler changes and payload parsing.

3) Pass `reply_markup` through notification sender

- **Decision**: Extend the internal send helper to accept optional `reply_markup` and pass it to `Bot.send_message`.
- **Rationale**: Minimal localized change; keeps send/advance logic intact.
- **Alternatives considered**:
  - Inline `send_message` in `_send_and_advance`: reduces indirection but duplicates error handling.

## Risks / Trade-offs

- **[Misconfigured keyboard / invalid callback_data]** → Use only known callback strings already present in the bot; keep mapping small and explicit.
- **[Telegram BadRequest due to markup issues]** → Keep keyboard structure simple (1 row / 1 button initially) and preserve existing error handling behavior.
- **[Future need for per-campaign analytics attribution]** → Consider a follow-up change to embed campaign_id in callback_data with backward-compatible parsing.

