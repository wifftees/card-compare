## Why

Admins can currently send only plain-text broadcasts from the Admin Mini App, which limits how effectively they can direct users into existing purchase flows. Adding a small set of selectable call-to-action buttons lets admins turn broadcasts into actionable messages without introducing a fully custom button builder.

## What Changes

- Extend admin broadcast requests to optionally include a selected inline button preset.
- Support CTA presets for broadcasts that cover:
  - open the existing balance and purchase-options flow via `callback_data="balance"`
  - start the existing direct-purchase flows via `callback_data="buy:SINGLE"`, `callback_data="buy:PACKET"`, `callback_data="buy:PACKET_FIRST"`, and `callback_data="buy:PACKET_SECOND"`
- Update the Admin Mini App broadcast tab so the admin can choose which CTA button, if any, to attach before sending.
- Send broadcast messages with the selected inline keyboard when a CTA preset is provided, and without a keyboard otherwise.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `admin-broadcast`: extend broadcast payload and sending behavior to support an optional inline CTA button.
- `admin-miniapp`: extend the Broadcast tab UI so admins can choose one supported CTA preset for a message.

## Impact

- Affected code: `api/admin_handlers.py`, `api/admin_models.py`, `api/miniapp.py`, and shared broadcast-button helpers if introduced.
- Affected API: `POST /api/admin/broadcast` request body and broadcast send behavior.
- Affected bot behavior: broadcast messages may include inline keyboards that reuse existing callback actions instead of introducing new routing.
