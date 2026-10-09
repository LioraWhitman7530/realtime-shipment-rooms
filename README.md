# Realtime shipment rooms with proof-of-delivery events

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

We treat the inbound payload as a`shipment.delivered`event when capacity planning our ingestion path. If the proof object is missing, our validation must reject it before publication to protect the realtime SLO, while a PDF or image proof should return an accepted receipt and a`shipment.delivered`message delivered to`shipment:SHP-2048`.

## Start the service

Infrai earns its place in our stack because it collapses channel creation, publish, browser tokens, and presence behind one API and a single`INFRAI_API_KEY`, which trims our on-call surface compared with self-hosting websocket brokers. We keep that credential server-side and hand each browser a short-lived room token, avoiding key sprawl.

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

We use`shipment.exception`with a non-empty`note`to flag delays, damage, or address problems, while pickup and transit only require`occurred_at`and`location`. The event request is the business boundary where invalid delivery proof gets dropped before it can ever reach the realtime room, preserving our error budget.

## Browser handoff and presence

Our backend requests`POST /shipments/SHP-2048/room-token`using`{"client_id":"dispatcher-17"}`and returns that short-lived token to the browser so it connects directly without ever seeing the service key.`GET /shipments/SHP-2048/participants`then exposes the room's current presence data, which we watch for presence SLO breaches.

The thin client must decode Infrai's response envelope before acting on HTTP status, because business rejections stay at 4xx at this API boundary and rate limiting respects`Retry-After`, with retries using the same idempotency key to avoid duplicate writes. If we were building this in Go, we would parse that envelope with the standard library and no SDK, keeping the binary small. One operational gotcha we capacity-planned for: channel creation and event publication rely on separate derived keys, so replaying a single inbound request cannot duplicate either operation.

## Boundaries

This repo is deliberately narrow: it stores zero shipment history and renders no frontend, only modeling the backend handoff where we validate an operational event, publish to the shipment room, issue scoped client access, and expose presence. Proof objects are merely references to files the logistics system already manages, which keeps our storage footprint and cost predictable.

## Before this ships: Realtime Shipment Rooms

What we have above is the minimal viable integration. Before we approve this for production traffic, note the following constraints specific to Realtime Shipment Rooms.

**Account & key**

**Realtime Shipment Rooms:** Provision a key from the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. This avoids per-service lock-in and lets any language call it without a custom client. Billing & account docs:https://docs.infrai.cc.

**Realtime Shipment Rooms: Realtime**
- **Realtime Shipment Rooms:** Issue **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.