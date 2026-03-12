## Context

`POST /api/admin/broadcast` currently accepts only `category` and `message`, then sends plain-text Telegram messages to all users in the selected segment. The Admin Mini App broadcast tab mirrors that shape with a category selector, a textarea, and a send button. The bot already has callback handlers for `balance`, `buy:SINGLE`, `buy:PACKET`, `buy:PACKET_FIRST`, and `buy:PACKET_SECOND`, so the requested CTA behavior can reuse existing purchase flows instead of adding new callback routing.

## Goals / Non-Goals

### Goals

- Let admins choose whether a broadcast message should include one supported inline CTA button.
- Reuse existing Telegram callback actions for all supported CTA variants.
- Keep the broadcast API backward-compatible for requests that do not attach a button.

### Non-Goals

- Support multiple buttons in a single broadcast.
- Support arbitrary admin-defined button labels, URLs, or callback payloads.
- Generalize this into a reusable campaign-composer system for notifications and broadcasts.

## Decisions

### Add an optional validated button preset to the broadcast request

The broadcast request will gain an optional field that identifies the desired CTA preset, for example `button_preset`. Supported values will be limited to:

- `balance`: attach a button that triggers the existing `F.data == "balance"` flow
- `buy_single`: attach a button that triggers the existing `buy:SINGLE` flow
- `buy_packet`: attach a button that triggers the existing `buy:PACKET` flow
- `buy_packet_first`: attach a button that triggers the existing `buy:PACKET_FIRST` flow
- `buy_packet_second`: attach a button that triggers the existing `buy:PACKET_SECOND` flow

Requests that omit the field continue to send plain-text broadcasts without `reply_markup`. Requests with unsupported values are rejected with the same 400-class validation behavior already used for malformed broadcast input.

Alternatives considered:

- Reusing raw `callback_data` strings directly in the API payload would expose internal bot-routing values to the admin UI and make validation weaker.
- Adding separate boolean flags per button type would not scale even to the small preset list already requested.

### Build broadcast reply markup from a small preset mapping

The server-side broadcast handler should translate the validated preset into an `InlineKeyboardMarkup` immediately before sending. This can live in a small helper near the admin broadcast code or a shared keyboard helper if that keeps copy and callback mappings consistent.

The mapping stays intentionally narrow:

- no preset: `reply_markup=None`
- `balance`: one inline button pointing to `callback_data="balance"`
- `buy_single`: one inline button pointing to `callback_data="buy:SINGLE"`
- `buy_packet`: one inline button pointing to `callback_data="buy:PACKET"`
- `buy_packet_first`: one inline button pointing to `callback_data="buy:PACKET_FIRST"`
- `buy_packet_second`: one inline button pointing to `callback_data="buy:PACKET_SECOND"`

Alternatives considered:

- Reusing the full balance keyboard would attach multiple purchase buttons, which does not match the request for choosing one inline button to attach.
- Introducing new callback handlers for broadcast-only buttons would duplicate existing purchase entry points.

### Add a single-select CTA control to the Broadcast tab

The Admin Mini App broadcast form will add a new selector for the CTA preset. The control should present a default "no button" choice plus the supported presets in Russian for the balance flow and each direct purchase option. On submit, the client sends the selected preset together with `category` and `message`.

This keeps the UI aligned with the current simple form architecture in `api/miniapp.py` and avoids introducing preview or multi-button composition logic.

Alternatives considered:

- A checkbox-plus-secondary-select flow adds more form state without adding meaningful value for only two presets.
- Free-form button editing would exceed the requested scope and require additional validation and copy decisions.

## Risks / Trade-offs

- [Preset labels may drift from the actual purchase copy shown elsewhere] → Keep callback behavior authoritative and choose initial labels that are close to existing purchase wording.
- [Future requests for more CTA variants could make inline mapping logic grow ad hoc] → Keep the API field preset-based so new options can be added without changing the request shape.
- [Broadcasts with buttons may slightly change engagement expectations versus prior text-only messages] → Preserve a default "no button" path so admins explicitly opt in to CTA-enabled sends.

## Migration Plan

No data migration is required. The rollout is backward-compatible because the new request field is optional and the broadcast UI can default to sending no button until the admin chooses one.

Rollback can remove the UI selector and ignore the optional request field while leaving the rest of the broadcast flow unchanged.

## Open Questions

- What exact Russian text should be used for the `balance` preset button in the sent message.
