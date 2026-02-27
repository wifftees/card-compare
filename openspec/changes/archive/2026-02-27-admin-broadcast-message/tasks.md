# Admin Broadcast Message — Tasks

## 1. API Layer

- [x] 1.1 Add Pydantic model `BroadcastRequest` with `category: int` and `message: str`; add `BroadcastResponse` with `sent`, `failed`, `total`
- [x] 1.2 Add `broadcast_handler` in `api/admin_handlers.py` that validates category, resolves user IDs via `_resolve_user_ids`, sends via bot, returns `BroadcastResponse`
- [x] 1.3 Ensure bot instance is available in aiohttp app (check `main.py` / `api/server.py` and pass `bot` into app state if needed)
- [x] 1.4 Register `POST /api/admin/broadcast` route in `api/server.py` with admin auth middleware

## 2. Mini App UI

- [x] 2.1 Add Broadcast tab (`<sl-tab slot="nav" panel="broadcast">Рассылка</sl-tab>`) and `<sl-tab-panel name="broadcast">` to `api/miniapp.py`
- [x] 2.2 Add Broadcast tab content: category select (reuse categories from `loadCategories`), textarea for message, "Отправить" button
- [x] 2.3 ~~Add confirmation step: show preview and "Подтвердить отправку" before calling API~~ (removed per user request - send immediately)
- [x] 2.4 Wire send button to `POST /api/admin/broadcast`; display result (Отправлено / Ошибок) in Russian
- [x] 2.5 Add tab switching logic for Broadcast panel in `sl-tab-show` handler and `.active` class toggling

## 3. Verification

- [ ] 3.1 Manually test: select category, type message, confirm, verify messages received by users in that category
- [x] 3.2 Verify invalid category and empty message return 400
- [x] 3.3 Verify unauthenticated request returns 401/403
