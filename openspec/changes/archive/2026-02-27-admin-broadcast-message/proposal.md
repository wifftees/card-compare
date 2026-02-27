# Admin Broadcast Message

## Why

Admins need to send broadcast messages to user segments directly from the Admin Mini App. Currently, broadcast exists only in the legacy bot callback flow (`bot/handlers/admin.py`) and uses a different set of groups (no_activity, used_trial, bought_single) than the conversion categories. Moving broadcast into the Mini App as a dedicated tab provides a unified admin experience and reuses the same conversion categories for consistency.

## What Changes

- Add a **Рассылка** (Broadcast) tab to the Admin Mini App, alongside Обзор and Конверсии.
- Implement a two-step broadcast flow:
  1. Admin selects a single conversion category (same categories as in Конверсии tab) and types the message.
  2. On confirmation, the message is sent to all users in that category.
- Add `POST /api/admin/broadcast` endpoint to trigger sending.
- All user-facing text in the Mini App MUST be in Russian; specs and internal code MUST be in English.

## Capabilities

### New Capabilities

- `admin-broadcast`: Broadcast message to a conversion category from the Admin Mini App. Covers the new tab UI, API endpoint, and sending logic.

### Modified Capabilities

- `admin-miniapp`: Add requirement for the Broadcast tab and its integration with the existing category list and auth flow.

## Impact

- `api/miniapp.py`: Add Broadcast tab markup, styles, and client-side logic.
- `api/admin_handlers.py`: Add `broadcast_handler` and route registration.
- `api/server.py`: Register `POST /api/admin/broadcast`.
- `bot/handlers/admin.py`: No changes required; legacy broadcast remains for backward compatibility (or can be deprecated later).
- Reuse `CONVERSION_CATEGORIES` and `_resolve_user_ids` from `api/admin_handlers.py` for resolving target users.
- Telegram Bot API: `bot.send_message` for each recipient (rate-limited).
