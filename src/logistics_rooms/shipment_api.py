from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .infrai_realtime import InfraiError, InfraiRealtime
from .room_service import EventReceipt, ShipmentEventRequest, ShipmentRoomService


class RoomTokenRequest(BaseModel):
    client_id: str = Field(min_length=1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    realtime = InfraiRealtime.from_environment()
    app.state.realtime = realtime
    app.state.rooms = ShipmentRoomService(realtime)
    yield
    await realtime.close()


api = FastAPI(title="Shipment room service", lifespan=lifespan)


@api.exception_handler(InfraiError)
async def infrai_error_response(_: Request, exc: InfraiError) -> JSONResponse:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(
        status_code=status, content={"detail": {"code": exc.code, **exc.detail}}
    )


@api.post("/shipments/{shipment_id}/events", response_model=EventReceipt)
async def record_shipment_event(
    request: Request,
    shipment_id: str,
    event: ShipmentEventRequest,
    x_account_id: str = Header(min_length=1),
    idempotency_key: str = Header(min_length=8),
) -> EventReceipt:
    return await request.app.state.rooms.record_event(
        shipment_id, x_account_id, idempotency_key, event
    )


@api.post("/shipments/{shipment_id}/room-token")
async def issue_room_token(
    request: Request, shipment_id: str, token_request: RoomTokenRequest
) -> dict[str, Any]:
    channel = f"shipment:{shipment_id}"
    return dict(await request.app.state.realtime.issue_token(token_request.client_id, [channel]))


@api.get("/shipments/{shipment_id}/participants")
async def list_participants(request: Request, shipment_id: str) -> dict[str, Any]:
    channel = f"shipment:{shipment_id}"
    return dict(await request.app.state.realtime.presence(channel))


def run() -> None:
    uvicorn.run("logistics_rooms.shipment_api:api", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
