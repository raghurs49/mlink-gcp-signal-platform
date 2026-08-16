from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone

from .models import Frame
from .transport import ConnectionClosed, MockWebSocketConnection


class SyntheticFeed:
    """Deterministic mock feed; it contains no SpiderRock data or proprietary schema."""

    def __init__(self, valid_api_key: str = "synthetic-demo-key", disconnect_once: bool = True):
        self.valid_api_key = valid_api_key
        self.disconnects_remaining = 1 if disconnect_once else 0
        self.connection_count = 0
        self._tasks: set[asyncio.Task[None]] = set()

    async def connect(self) -> MockWebSocketConnection:
        self.connection_count += 1
        connection = MockWebSocketConnection(self.connection_count)
        task = asyncio.create_task(self._serve(connection))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return connection

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        for task in list(self._tasks):
            with suppress(asyncio.CancelledError):
                await task

    async def _serve(self, connection: MockWebSocketConnection) -> None:
        sequence = 1
        try:
            auth = await connection.server_receive()
            accepted = auth.message_type == "LOGON" and auth.payload.get("api_key") == self.valid_api_key
            await connection.server_send(
                Frame("ADMIN", {"authenticated": accepted, "connection_id": connection.connection_id}, sequence)
            )
            sequence += 1
            if not accepted:
                await connection.close()
                return

            subscribe = await connection.server_receive()
            if subscribe.message_type != "SUBSCRIBE":
                await connection.server_send(Frame("SUBSCRIPTION_ACK", {"accepted": False}, sequence))
                await connection.close()
                return

            families = subscribe.payload.get("families", [])
            await connection.server_send(
                Frame("SUBSCRIPTION_ACK", {"accepted": True, "families": families}, sequence)
            )
            sequence += 1
            await connection.server_send(Frame("CHECKPOINT", {"state": "BEGIN"}, sequence))
            sequence += 1
            await connection.server_send(self._quote(sequence, 99.90, 100.10, cached=True))
            sequence += 1
            await connection.server_send(Frame("CHECKPOINT", {"state": "ACTIVE"}, sequence))
            sequence += 1
            await connection.server_send(Frame("CHECKPOINT", {"state": "COMPLETE"}, sequence))
            sequence += 1

            for offset in range(4):
                await asyncio.sleep(0.01)
                await connection.server_send(Frame("HEARTBEAT", {"status": "ok"}, sequence))
                sequence += 1
                await connection.server_send(
                    self._quote(sequence, 100.00 + offset * 0.05, 100.20 + offset * 0.05)
                )
                sequence += 1
                await connection.server_send(self._trade(sequence, offset, 100.10 + offset * 0.05))
                sequence += 1
                if self.disconnects_remaining and offset == 0:
                    self.disconnects_remaining -= 1
                    await connection.close()
                    return
            await connection.server_send(Frame("END_OF_DEMO", {}, sequence))
        except ConnectionClosed:
            return

    @staticmethod
    def _event_time() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _quote(self, sequence: int, bid: float, ask: float, cached: bool = False) -> Frame:
        return Frame(
            "DATA",
            {
                "family": "SyntheticQuote",
                "symbol": "DEMO",
                "bid": bid,
                "ask": ask,
                "event_time": self._event_time(),
                "cached": cached,
            },
            sequence,
        )

    def _trade(self, sequence: int, offset: int, price: float) -> Frame:
        return Frame(
            "DATA",
            {
                "family": "SyntheticTrade",
                "symbol": "DEMO",
                "trade_id": f"T{sequence}-{offset}",
                "price": price,
                "size": 10 + offset,
                "event_time": self._event_time(),
                "cached": False,
            },
            sequence,
        )

