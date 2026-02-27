## ADDED Requirements

### Requirement: Prices tab in Admin Mini App

The Admin Mini App MUST include a tab labeled **Цены** displayed alongside existing tabs (e.g. Обзор, Конверсии, Рассылка). All user-facing text in this tab MUST be in Russian.

The Prices tab MUST:
1. Load the current `prices` table rows from `GET /api/admin/prices`.
2. Render a table with one row per `ProductOption`.
3. Allow editing `price` (RUB integer) and `reports_amount` (integer) values.
4. Provide an explicit save action that sends all edited rows to `POST /api/admin/prices`.
5. Display a Russian success/error message after attempting to save.

#### Scenario: Admin views current prices
- **WHEN** an admin opens the Prices tab
- **THEN** the client calls `GET /api/admin/prices`
- **AND THEN** the client displays a table of price rows

#### Scenario: Admin edits and saves prices
- **WHEN** an admin edits one or more table cells and clicks “Сохранить”
- **THEN** the client calls `POST /api/admin/prices` with the updated rows
- **AND THEN** the client displays the save result in Russian

