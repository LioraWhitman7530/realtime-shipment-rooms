from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from logistics_rooms.room_service import (
    ProofOfDelivery,
    ShipmentEventKind,
    ShipmentEventRequest,
    ShipmentRoomService,
)


class RecordingRealtime:
    def __init__(self) -> None:
        self.created: list[tuple[str, str]] = []
        self.published: list[dict[str, Any]] = []

    async def create_channel(self, channel: str, request_id: str) -> dict[str, Any]:
        self.created.append((channel, request_id))
        return {"channel": channel}

    async def publish(
        self,
        channel: str,
        event: str,
        data: dict[str, Any],
        account_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        self.published.append(
            {
                "channel": channel,
                "event": event,
                "data": data,
                "account_id": account_id,
                "request_id": request_id,
            }
        )
        return {"published": True}


def test_delivery_requires_proof() -> None:
    with pytest.raises(ValidationError, match="delivered events require proof"):
        ShipmentEventRequest(
            kind=ShipmentEventKind.DELIVERED,
            occurred_at=datetime(2026, 9, 6, tzinfo=timezone.utc),
            location="Dock 4",
        )


def test_delivery_is_published_to_its_shipment_room() -> None:
    realtime = RecordingRealtime()
    service = ShipmentRoomService(realtime)
    event = ShipmentEventRequest(
        kind=ShipmentEventKind.DELIVERED,
        occurred_at=datetime(2026, 9, 6, 8, 15, tzinfo=timezone.utc),
        location="Receiver desk",
        proof=ProofOfDelivery(
            object_key="pod/SHP-2048/signature.pdf",
            filename="signature.pdf",
            content_type="application/pdf",
            sha256="a" * 64,
        ),
    )

    receipt = asyncio.run(
        service.record_event("SHP-2048", "acme-logistics", "req-2048", event)
    )

    assert receipt.accepted is True
    assert realtime.created == [("shipment:SHP-2048", "req-2048:channel")]
    assert realtime.published[0]["event"] == "shipment.delivered"
    assert realtime.published[0]["data"]["proof"]["object_key"] == "pod/SHP-2048/signature.pdf"
    assert realtime.published[0]["request_id"] == "req-2048:event"
