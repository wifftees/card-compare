## Why

Notification campaigns are currently delivered as plain messages with no inline call-to-action, which reduces engagement and makes it harder to guide users to the next step (e.g. viewing an example report).

## What Changes

- Notification messages can optionally include an inline keyboard.
- Inline keyboards are selected per notification `campaign_id` via a simple in-code map.
- Existing `callback_data` values are reused (e.g. `show_example_report`) so no new callback routing is required.
- Initial mapping includes a campaign that targets users who never opened the example report, showing a single **Пример отчета** button.

## Capabilities

### New Capabilities

- `notification-inline-buttons`: Attach per-campaign inline keyboards to notification messages using an `id -> keyboard` mapping, reusing existing bot callback actions.

### Modified Capabilities

- (none)

## Impact

- `notifications/service.py`: extend send to pass optional `reply_markup`.
- `notifications/`: add a small campaign-to-keyboard mapping module.
- No DB schema changes and no changes to existing bot handlers are required (callbacks already exist).

