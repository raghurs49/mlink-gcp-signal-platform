from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .models import Frame


class ConnectionClosed(RuntimeError):
    pass


_CLOSED = object()


@dataclass
class MockWebSocketConnection:
    """In-process duplex transport with WebSocket-like send/receive semantics."""

    connection_id: int

    def __post_init__(self) -> None:
        self._client_to_server: asyncio.Queue[Frame | object] = asyncio.Queue()
        self._server_to_client: asyncio.Queue[Frame | object] = asyncio.Queue()
        self.closed = False

    async def client_send(self, frame: Frame) -> None:
        if self.closed:
            raise ConnectionClosed("connection is closed")
        await self._client_to_server.put(frame)

    async def client_receive(self) -> Frame:
        item = await self._server_to_client.get()
        if item is _CLOSED:
            raise ConnectionClosed("server closed connection")
        return item  # type: ignore[return-value]

    async def server_send(self, frame: Frame) -> None:
        if self.closed:
            raise ConnectionClosed("connection is closed")
        await self._server_to_client.put(frame)

    async def server_receive(self) -> Frame:
        item = await self._client_to_server.get()
        if item is _CLOSED:
            raise ConnectionClosed("client closed connection")
        return item  # type: ignore[return-value]

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self._server_to_client.put(_CLOSED)
        await self._client_to_server.put(_CLOSED)

