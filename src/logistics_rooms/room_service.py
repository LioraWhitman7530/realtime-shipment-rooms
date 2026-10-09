from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ShipmentEventKind(StrEnum):
    PICKED_UP = "shipment.picked_up"
    IN_TRANSIT = "shipment.in_transit"
    DELIVERED = "shipment.delivered"
    EXCEPTION = "shipment.exception"


class ProofOfDelivery(BaseModel):
    object_key: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    content_type: str = Field(pattern=r"^(image/|application/pdf)")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ShipmentEventRequest(BaseModel):
    kind: ShipmentEventKind
    occurred_at: datetime
    location: str = Field(min_length=1)
    note: str | None = None
    proof: ProofOfDelivery | None = None

    @model_validator(mode="after")
    def validate_business_fields(self) -> "ShipmentEventRequest":
        if self.kind == ShipmentEventKind.DELIVERED and self.proof is None:
            raise ValueError("delivered events require proof")
        if self.kind == ShipmentEventKind.EXCEPTION and not self.note:
            raise ValueError("exception events require a note")
        if self.kind != ShipmentEventKind.DELIVERED and self.proof is not None:
            raise ValueError("proof is accepted only for delivered events")
        return self


class EventReceipt(BaseModel):
    shipment_id: str
    channel: str
    event: ShipmentEventKind
    accepted: bool


class ShipmentRoomService:
    def __init__(self, realtime: Any) -> None:
        self._realtime = realtime

    async def record_event(
        self,
        shipment_id: str,
        account_id: str,
        request_id: str,
        event: ShipmentEventRequest,
    ) -> EventReceipt:
        channel = f"shipment:{shipment_id}"
        await self._realtime.create_channel(channel, f"{request_id}:channel")
        payload = event.model_dump(mode="json", exclude_none=True)
        payload["shipment_id"] = shipment_id
        await self._realtime.publish(
            channel,
            event.kind.value,
            payload,
            account_id,
            f"{request_id}:event",
        )
        return EventReceipt(
            shipment_id=shipment_id,
            channel=channel,
            event=event.kind,
            accepted=True,
        )
