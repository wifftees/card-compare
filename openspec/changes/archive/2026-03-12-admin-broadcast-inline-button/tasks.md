## 1. Backend broadcast support

- [x] 1.1 Add an optional validated `button_preset` field to the admin broadcast request model with support for `balance`, `buy_single`, `buy_packet`, `buy_packet_first`, and `buy_packet_second`.
- [x] 1.2 Update the broadcast send path to map each supported preset to a one-button inline keyboard, send no keyboard when the preset is absent, and keep existing sent/failed counting and rate limiting behavior.

## 2. Admin Mini App updates

- [x] 2.1 Extend the Broadcast tab UI with a Russian CTA selector that offers no button, the balance and purchase-options CTA, and direct-purchase CTAs for `SINGLE`, `PACKET`, `PACKET_FIRST`, and `PACKET_SECOND`.
- [x] 2.2 Update the Broadcast tab submit logic to send the selected `button_preset` to `POST /api/admin/broadcast` while preserving the existing category/message validation and result display.

## 3. Verification

- [x] 3.1 Verify the broadcast endpoint accepts requests with no button, `balance`, `buy_single`, `buy_packet`, `buy_packet_first`, and `buy_packet_second`, and rejects unsupported preset values with HTTP 400.
- [x] 3.2 Verify CTA-enabled broadcasts reuse existing callback behavior (`balance`, `buy:SINGLE`, `buy:PACKET`, `buy:PACKET_FIRST`, and `buy:PACKET_SECOND`) without requiring new callback handlers.
