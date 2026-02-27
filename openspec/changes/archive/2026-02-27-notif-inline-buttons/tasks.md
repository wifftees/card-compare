## 1. Add per-campaign keyboard mapping

- [x] 1.1 Create `notifications/keyboards.py` with `campaign_id -> InlineKeyboardMarkup` mapping
- [x] 1.2 Add initial mapping for `click_start_no_report` to show `callback_data="show_example_report"`
- [x] 1.3 click_example_report -> `callback_data="buy:SINGLE"`
- [x] 1.4 generated_report -> `callback_data="buy:SINGLE"`

## 2. Wire keyboards into notification sending

- [x] 2.1 Update `NotificationService._try_send` to accept optional `reply_markup`
- [x] 2.2 Update `_send_and_advance` to look up keyboard by `campaign.id` and pass it into send

## 3. Quality checks

- [x] 3.1 Run Python formatting/lint/type checks for touched files
- [x] 3.2 Smoke test: trigger a notification cycle and verify the button appears and `show_example_report` works

