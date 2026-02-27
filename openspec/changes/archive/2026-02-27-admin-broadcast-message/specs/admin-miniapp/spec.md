# admin-miniapp Specification (delta)

## ADDED Requirements

### Requirement: Broadcast tab in Admin Mini App

The Admin Mini App MUST include a third tab labeled **Рассылка** (Broadcast), displayed alongside Обзор and Конверсии. All user-facing text in this tab MUST be in Russian.

The Broadcast tab MUST provide:
1. A category selector (single-select) populated with the same categories as the Конверсии tab (from `GET /api/admin/categories`).
2. A text input (or textarea) for the message to send.
3. A send button that triggers `POST /api/admin/broadcast` with the selected category and message.

Before sending, the UI MAY show a confirmation step (e.g. preview + "Подтвердить отправку"). After sending, the UI MUST display the result (sent count, failed count) in Russian.

#### Scenario: Admin selects category and sends broadcast

- **WHEN** an admin opens the Broadcast tab
- **THEN** the admin sees a category dropdown and a message input
- **AND WHEN** the admin selects a category, types a message, and clicks send (and confirms if applicable)
- **THEN** the client calls `POST /api/admin/broadcast` with `{ "category": N, "message": "..." }`
- **AND THEN** the client displays the result (e.g. "Отправлено: X, Ошибок: Y")

#### Scenario: Broadcast tab uses same categories as Conversions

- **WHEN** the Admin Mini App loads
- **THEN** the Broadcast tab category selector is populated from the same `GET /api/admin/categories` response used by the Конверсии tab
- **AND THEN** category labels are displayed in Russian (as returned by the API)
