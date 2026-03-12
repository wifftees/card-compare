## MODIFIED Requirements

### Requirement: Broadcast tab in Admin Mini App

The Admin Mini App MUST include a third tab labeled **Рассылка** (Broadcast), displayed alongside Обзор and Конверсии. All user-facing text in this tab MUST be in Russian.

The Broadcast tab MUST provide:
1. A category selector (single-select) populated with the same categories as the Конверсии tab (from `GET /api/admin/categories`).
2. A text input (or textarea) for the message to send.
3. A CTA selector that allows the admin to choose whether to attach no button, the balance and purchase-options button, or one of the direct-purchase buttons for `SINGLE`, `PACKET`, `PACKET_FIRST`, or `PACKET_SECOND`.
4. A send button that triggers `POST /api/admin/broadcast` with the selected category, message, and CTA preset choice.

Before sending, the UI MAY show a confirmation step (e.g. preview + "Подтвердить отправку"). After sending, the UI MUST display the result (sent count, failed count) in Russian.

#### Scenario: Admin selects category and sends broadcast without button

- **WHEN** an admin opens the Broadcast tab
- **THEN** the admin sees a category dropdown, a message input, and a CTA selector with a no-button option
- **AND WHEN** the admin selects a category, types a message, keeps the no-button option, and clicks send (and confirms if applicable)
- **THEN** the client calls `POST /api/admin/broadcast` with `{ "category": N, "message": "..." }`
- **AND THEN** the client displays the result (e.g. "Отправлено: X, Ошибок: Y")

#### Scenario: Admin selects balance CTA for broadcast

- **WHEN** an admin opens the Broadcast tab
- **THEN** the admin can choose the balance CTA option in the CTA selector
- **AND WHEN** the admin selects a category, types a message, chooses the balance CTA option, and clicks send
- **THEN** the client calls `POST /api/admin/broadcast` with `{ "category": N, "message": "...", "button_preset": "balance" }`

#### Scenario: Admin selects single-purchase CTA for broadcast

- **WHEN** an admin opens the Broadcast tab
- **THEN** the admin can choose the single-purchase CTA option in the CTA selector
- **AND WHEN** the admin selects a category, types a message, chooses the single-purchase CTA option, and clicks send
- **THEN** the client calls `POST /api/admin/broadcast` with `{ "category": N, "message": "...", "button_preset": "buy_single" }`

#### Scenario: Admin selects packet CTA for broadcast

- **WHEN** an admin opens the Broadcast tab
- **THEN** the admin can choose the packet CTA option in the CTA selector
- **AND WHEN** the admin selects a category, types a message, chooses the packet CTA option, and clicks send
- **THEN** the client calls `POST /api/admin/broadcast` with `{ "category": N, "message": "...", "button_preset": "buy_packet" }`

#### Scenario: Admin selects packet-first CTA for broadcast

- **WHEN** an admin opens the Broadcast tab
- **THEN** the admin can choose the packet-first CTA option in the CTA selector
- **AND WHEN** the admin selects a category, types a message, chooses the packet-first CTA option, and clicks send
- **THEN** the client calls `POST /api/admin/broadcast` with `{ "category": N, "message": "...", "button_preset": "buy_packet_first" }`

#### Scenario: Admin selects packet-second CTA for broadcast

- **WHEN** an admin opens the Broadcast tab
- **THEN** the admin can choose the packet-second CTA option in the CTA selector
- **AND WHEN** the admin selects a category, types a message, chooses the packet-second CTA option, and clicks send
- **THEN** the client calls `POST /api/admin/broadcast` with `{ "category": N, "message": "...", "button_preset": "buy_packet_second" }`

#### Scenario: Broadcast tab uses same categories as Conversions

- **WHEN** the Admin Mini App loads
- **THEN** the Broadcast tab category selector is populated from the same `GET /api/admin/categories` response used by the Конверсии tab
- **AND THEN** category labels are displayed in Russian (as returned by the API)
