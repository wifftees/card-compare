## MODIFIED Requirements

### Requirement: Broadcast endpoint accepts category and message

`POST /api/admin/broadcast` MUST accept a JSON body with:
- `category`: integer — a valid conversion category number (same as `CONVERSION_CATEGORIES`)
- `message`: string — the plain-text message to send (non-empty)
- `button_preset`: string|null — optional inline CTA preset

Supported `button_preset` values are:
- `balance` — send the message with one inline button that triggers the existing `callback_data="balance"` flow
- `buy_single` — send the message with one inline button that triggers the existing `callback_data="buy:SINGLE"` flow
- `buy_packet` — send the message with one inline button that triggers the existing `callback_data="buy:PACKET"` flow
- `buy_packet_first` — send the message with one inline button that triggers the existing `callback_data="buy:PACKET_FIRST"` flow
- `buy_packet_second` — send the message with one inline button that triggers the existing `callback_data="buy:PACKET_SECOND"` flow

If `button_preset` is omitted or `null`, the broadcast MUST be sent without `reply_markup`.

The endpoint MUST resolve the category to user IDs using the same logic as `POST /api/admin/usernames` (all-time, no range). The endpoint MUST send the message to each user via the Telegram Bot API. The endpoint MUST return a JSON body with:
- `sent`: integer — number of messages successfully sent
- `failed`: integer — number of sends that failed (e.g. user blocked bot)
- `total`: integer — total number of users in the category

#### Scenario: Successful broadcast to category without button

- **WHEN** an admin submits `POST /api/admin/broadcast` with `{ "category": 3, "message": "Hello" }`
- **THEN** the server resolves category 3 to user IDs
- **AND THEN** the server sends "Hello" to each user via `bot.send_message` without `reply_markup`
- **AND THEN** the response includes `sent`, `failed`, and `total` with `sent + failed == total`

#### Scenario: Successful broadcast to category with balance button

- **WHEN** an admin submits `POST /api/admin/broadcast` with `{ "category": 3, "message": "Hello", "button_preset": "balance" }`
- **THEN** the server resolves category 3 to user IDs
- **AND THEN** the server sends "Hello" to each user with an inline keyboard containing one button that uses `callback_data="balance"`
- **AND THEN** the response includes `sent`, `failed`, and `total` with `sent + failed == total`

#### Scenario: Successful broadcast to category with packet-first button

- **WHEN** an admin submits `POST /api/admin/broadcast` with `{ "category": 3, "message": "Hello", "button_preset": "buy_packet_first" }`
- **THEN** the server resolves category 3 to user IDs
- **AND THEN** the server sends "Hello" to each user with an inline keyboard containing one button that uses `callback_data="buy:PACKET_FIRST"`
- **AND THEN** the response includes `sent`, `failed`, and `total` with `sent + failed == total`

#### Scenario: Invalid category rejected

- **WHEN** an admin submits `POST /api/admin/broadcast` with `{ "category": 99, "message": "Hi" }`
- **THEN** the server responds with HTTP 400 and an error message indicating invalid category

#### Scenario: Empty message rejected

- **WHEN** an admin submits `POST /api/admin/broadcast` with `{ "category": 1, "message": "" }`
- **THEN** the server responds with HTTP 400 and an error message

#### Scenario: Unsupported button preset rejected

- **WHEN** an admin submits `POST /api/admin/broadcast` with `{ "category": 1, "message": "Hi", "button_preset": "custom" }`
- **THEN** the server responds with HTTP 400 and an error message indicating an unsupported button preset

#### Scenario: Broadcast respects rate limits

- **WHEN** the server sends messages to multiple users
- **THEN** the server MUST introduce a delay between sends (e.g. ~0.05s) to respect Telegram rate limits (~30 msg/sec)
