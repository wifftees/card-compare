## 1. Data access (prices table)

- [x] 1.1 Add query to fetch all rows from `prices` (option, price, reports_amount)
- [x] 1.2 Add query to bulk update (or upsert) price rows keyed by `option`
- [x] 1.3 Ensure server-side validation is enforced before DB writes (price >= 0, reports_amount > 0)

## 2. Admin API models

- [x] 2.1 Add Pydantic response model for `GET /api/admin/prices`
- [x] 2.2 Add Pydantic request model for `POST /api/admin/prices` bulk update
- [x] 2.3 Add response model for update result (e.g. updated count / echoed rows)

## 3. Admin API handlers and routing

- [x] 3.1 Implement `GET /api/admin/prices` handler (admin initData auth + list prices)
- [x] 3.2 Implement `POST /api/admin/prices` handler (admin initData auth + validate + bulk update)
- [x] 3.3 Register new routes in the aiohttp server router
- [x] 3.4 Return clear HTTP 400 errors on validation failures with no partial updates

## 4. Admin Mini App UI: "Цены" tab

- [x] 4.1 Add a new tab labeled "Цены" in the Admin Mini App navigation
- [x] 4.2 Fetch and render prices as an editable table (one row per ProductOption)
- [x] 4.3 Add inline editing for `price` and `reports_amount` with basic client-side validation
- [x] 4.4 Add "Сохранить" action that submits bulk changes to `POST /api/admin/prices`
- [x] 4.5 Show Russian success/error message and refresh table after save

## 5. Tests

- [x] 5.1 Add tests for `GET /api/admin/prices` (auth required, returns rows)
- [x] 5.2 Add tests for `POST /api/admin/prices` (bulk update happy path)
- [x] 5.3 Add tests for `POST /api/admin/prices` validation failures (rejects and does not partially update)

