# admin-miniapp Specification (delta)

## MODIFIED Requirements

### Requirement: Conversions endpoint returns counts and step conversions
`POST /api/admin/conversions` MUST accept a request that identifies:
- a range preset (`1d|7d|1m|all`)
- an ordered sequence of category numbers (integers) representing conversion groups

For the selected range, each category MUST resolve to a set of user IDs \(U(G)\):
- Event-based category: distinct `events.user_id` where `event_type` matches the category’s event(s) and `events.timestamp ∈ range`.
- Callable/segment category: category maps to a server-side function returning user IDs; it MAY ignore range.

The endpoint MUST return:
- `groups`: one entry per requested category with:
  - `category`: the category number
  - `size`: \(|U(G)|\)
  - `range_applied`: boolean indicating whether the selected range was applied when computing \(U(G)\)
- `conversions`: one entry per adjacent transition \(G_i → G_{i+1}\) with:
  - `from_category`, `to_category`
  - `numerator`: \(|U(G_{i+1}) ∩ U(G_i)|\)
  - `denominator`: \(|U(G_i)|\)
  - `percent`: `numerator / denominator * 100` when `denominator > 0`, otherwise `null`

#### Scenario: Compute conversions for a 3-step funnel
- **WHEN** an admin submits categories `[1, 3, 10]` with `range="7d"`
- **THEN** the server returns `groups` for categories `1`, `3`, and `10` including `size` for each
- **AND THEN** the server returns conversion entries for `1→3` and `3→10`
