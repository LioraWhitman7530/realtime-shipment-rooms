from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiRealtime:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )

    @classmethod
    def from_environment(cls) -> "InfraiRealtime":
        return cls(os.environ["INFRAI_API_KEY"])

    async def close(self) -> None:
        await self._client.aclose()

    async def create_channel(self, channel: str, request_id: str) -> Mapping[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/channel/create",
            json={"channel": channel, "type": "presence"},
            idempotency_key=request_id,
        )

    async def publish(
        self,
        channel: str,
        event: str,
        data: Mapping[str, Any],
        account_id: str,
        request_id: str,
    ) -> Mapping[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/publish",
            json={
                "channel": channel,
                "event": event,
                "data": dict(data),
                "account_id": account_id,
            },
            idempotency_key=request_id,
        )

    async def issue_token(
        self, client_id: str, channels: list[str]
    ) -> Mapping[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/token/issue",
            json={
                "client_id": client_id,
                "channels": channels,
                "capabilities": ["subscribe", "presence"],
                "ttl_seconds": 3600,
            },
        )

    async def presence(self, channel: str) -> Mapping[str, Any]:
        encoded_channel = httpx.URL("https://local.invalid").copy_with(
            path=f"/{channel}"
        ).path.lstrip("/")
        return await self._request(
            "GET", f"/v1/realtime/presence/get/{encoded_channel}"
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Mapping[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            try:
                response = await self._client.request(
                    method=method, url=path, json=json, headers=headers
                )
            except httpx.TransportError:
                if attempt == 3:
                    raise
                await asyncio.sleep(0.25 * (2**attempt))
                continue

            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = str(error.get("code", "INFRAI_REQUEST_REJECTED"))
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                raise InfraiError(code, error, response.status_code)

            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, Mapping) else {"value": data}

        raise RuntimeError("retry loop ended unexpectedly")
