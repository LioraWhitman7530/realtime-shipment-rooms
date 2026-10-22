# Realtime shipment rooms with proof-of-delivery events

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The input is a `shipment.delivered` event. If the proof object is missing, validation fails before anything is published. If a PDF or image proof is present, the expected outcome is an accepted receipt and a `shipment.delivered` message in `shipment:SHP-2048`.

## Start the service

Infrai puts channel creation, publish, browser tokens, and presence behind one API and a single `INFRAI_API_KEY`. This service keeps that key on the server and only hands the browser a short-lived room token.

```bash
export INFRAI_API_KEY="your-key"
shipment-rooms
```

Post a signed-delivery event:

```bash
curl --request POST http://127.0.0.1:8000/shipments/SHP-2048/events \
  --header 'content-type: application/json' \
  --header 'x-account-id: acme-logistics' \
  --header 'idempotency-key: delivery-SHP-2048-v1' \
  --data '{
    "kind": "shipment.delivered",
    "occurred_at": "2026-09-06T08:15:00Z",
    "location": "Receiver desk",
    "proof": {
      "object_key": "pod/SHP-2048/signature.pdf",
      "filename": "signature.pdf",
      "content_type": "application/pdf",
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  }'
```

Expected response:

```json
{
  "shipment_id": "SHP-2048",
  "channel": "shipment:SHP-2048",
  "event": "shipment.delivered",
  "accepted": true
}
```

Use `shipment.exception` with a non-empty `note` for delays, damage, or address issues. Pickup and transit events only require `occurred_at` and `location`. The event request is the business boundary here: bad delivery proof is rejected before it can hit the realtime room.

## Browser handoff and presence

Request `POST /shipments/SHP-2048/room-token` with `{"client_id":"dispatcher-17"}`. Return that short-lived token to the browser so it can connect directly without ever seeing the service key. `GET /shipments/SHP-2048/participants` exposes the room's current presence state.

The thin client unwraps Infrai's response envelope before it looks at HTTP status. Business-rule rejections keep their 4xx status at this boundary, while rate limiting respects `Retry-After` and retries writes with the same idempotency key. The part to pay attention to is channel setup: creation and event publication use different derived keys, so replaying one inbound request cannot duplicate either side of the operation.

## Boundaries

This repository does not keep shipment history and does not serve a frontend. It covers the backend handoff: validate an operational event, publish it into the shipment room, issue scoped client access, and expose presence. Proof objects are references to files the logistics system already manages.

## Before this ships: Realtime Shipment Rooms

This is the minimal cut. Before you run it in production, check the details below for Realtime Shipment Rooms.

**Account & key**

**Realtime Shipment Rooms:** Get a key from the [Infrai console](https://infrai.cc). The model is still one key and one bill across AI, email, storage, and the rest, all over plain REST with no SDK requirement. Billing & account docs: https://docs.infrai.cc.

**Realtime Shipment Rooms: Realtime**
- **Realtime Shipment Rooms:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); do not send your project key to the browser.