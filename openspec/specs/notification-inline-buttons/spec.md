## ADDED Requirements

### Requirement: Notification campaigns can include inline keyboards
The system SHALL support attaching an inline keyboard to a notification message based on the notification campaign id (`campaign_id`).

#### Scenario: Campaign has a configured keyboard
- **WHEN** a notification message is sent for a campaign id that is present in the campaign-to-keyboard mapping
- **THEN** the message SHALL be sent with the mapped inline keyboard as `reply_markup`

#### Scenario: Campaign has no configured keyboard
- **WHEN** a notification message is sent for a campaign id that is not present in the campaign-to-keyboard mapping
- **THEN** the message SHALL be sent without `reply_markup`

### Requirement: Notification inline keyboards reuse existing callback actions
Notification inline keyboards SHALL reuse existing bot callback actions via existing `callback_data` strings and SHALL NOT require new callback routing for this capability.

#### Scenario: Example report button
- **WHEN** a notification message includes a button with `callback_data="show_example_report"`
- **THEN** clicking the button SHALL trigger the existing example report flow handled by the bot

