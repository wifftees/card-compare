# admin-broadcast Specification

## Purpose

Define the broadcast message capability: admins send a plain-text message to all users in a selected conversion category via the Admin Mini App.

## ADDED Requirements

### Requirement: Broadcast endpoint accepts category and message

`POST /api/admin/broadcast` MUST accept a JSON body with:
- `category`: integer — a valid conversion category number (same as `CONVERSION_CATEGORIES`)
- `message`: string — the plain-text message to send (non-empty)

The endpoint MUST resolve the category to user IDs using the same logic as `POST /api/admin/usernames` (all-time, no range). The endpoint MUST send the message to each user via the Telegram Bot API. The endpoint MUST return a JSON body with:
- `sent`: integer — number of messages successfully sent
- `failed`: integer — number of sends that failed (e.g. user blocked bot)
- `total`: integer — total number of users in the category

#### Scenario: Successful broadcast to category

- **WHEN** an admin submits `POST /api/admin/broadcast` with `{ "category": 3, "message": "Hello" }`
- **THEN** the server resolves category 3 to user IDs
- **AND THEN** the server sends "Hello" to each user via `bot.send_message`
- **AND THEN** the response includes `sent`, `failed`, and `total` with `sent + failed == total`

#### Scenario: Invalid category rejected

- **WHEN** an admin submits `POST /api/admin/broadcast` with `{ "category": 99, "message": "Hi" }`
- **THEN** the server responds with HTTP 400 and an error message indicating invalid category

#### Scenario: Empty message rejected

- **WHEN** an admin submits `POST /api/admin/broadcast` with `{ "category": 1, "message": "" }`
- **THEN** the server responds with HTTP 400 and an error message

#### Scenario: Broadcast respects rate limits

- **WHEN** the server sends messages to multiple users
- **THEN** the server MUST introduce a delay between sends (e.g. ~0.05s) to respect Telegram rate limits (~30 msg/sec)

### Requirement: Broadcast uses admin authentication

`POST /api/admin/broadcast` MUST require the same authentication as other `/api/admin/*` endpoints: `X-Telegram-Init-Data` header validated against admin list. Unauthorized requests MUST receive HTTP 401 or 403.

#### Scenario: Unauthenticated request rejected

- **WHEN** a request to `POST /api/admin/broadcast` lacks valid `X-Telegram-Init-Data` or the user is not an admin
- **THEN** the server responds with HTTP 401 or 403
