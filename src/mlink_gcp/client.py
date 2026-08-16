from __future__ import annotations

import asyncio

from .config import Manifest
from .feed import SyntheticFeed
from .metrics import Metrics
from .models import Frame
from .pipeline import StreamingPipeline
from .transport import ConnectionClosed


class StreamingClient:
    def __init__(
        self,
        feed: SyntheticFeed,
        manifest: Manifest,
        pipeline: StreamingPipeline,
        api_key: str,
        metrics: Metrics | None = None,
    ) -> None:
        self.feed = feed
        self.manifest = manifest
        self.pipeline = pipeline
        self.api_key = api_key
        self.metrics = metrics or Metrics()
        self.checkpoint_state = "DISCONNECTED"
        self.recovery_log: list[dict[str, object]] = []

    async def run(self, target_signals: int = 4) -> dict[str, object]:
        attempts = 0
        while len(self.pipeline.signals) < target_signals:
            try:
                await self._run_connection(target_signals)
            except ConnectionClosed:
                self.metrics.increment("disconnects")
                if attempts >= self.manifest.max_reconnects:
                    raise
                attempts += 1
                self.metrics.increment("reconnects")
                self.recovery_log.append(
                    {"attempt": attempts, "action": "reconnect_and_resubscribe", "status": "started"}
                )
                await asyncio.sleep(min(0.01 * (2 ** (attempts - 1)), 0.1))
        return {
            "manifest_version": self.manifest.version,
            "signals": [signal.to_dict() for signal in self.pipeline.signals],
            "checkpoint_state": self.checkpoint_state,
            "recovery": self.recovery_log,
            "metrics": self.metrics.report(),
        }

    async def _run_connection(self, target_signals: int) -> None:
        connection = await self.feed.connect()
        started = self.metrics.timer()
        await connection.client_send(Frame("LOGON", {"api_key": self.api_key}))
        admin = await asyncio.wait_for(
            connection.client_receive(), timeout=self.manifest.heartbeat_timeout_seconds
        )
        if admin.message_type != "ADMIN" or not admin.payload.get("authenticated"):
            raise PermissionError("feed authentication failed")
        self.metrics.observe("authentication", (self.metrics.timer() - started) * 1000)
        self.metrics.increment("authenticated_connections")

        await connection.client_send(
            Frame(
                "SUBSCRIBE",
                {
                    "manifest_version": self.manifest.version,
                    "families": [subscription.family for subscription in self.manifest.subscriptions],
                },
            )
        )
        ack = await connection.client_receive()
        if ack.message_type != "SUBSCRIPTION_ACK" or not ack.payload.get("accepted"):
            raise RuntimeError("subscription rejected")
        self.metrics.increment("successful_subscriptions")
        if self.recovery_log:
            self.recovery_log[-1]["status"] = "resubscribed"

        while len(self.pipeline.signals) < target_signals:
            frame = await asyncio.wait_for(
                connection.client_receive(), timeout=self.manifest.heartbeat_timeout_seconds
            )
            if frame.message_type == "CHECKPOINT":
                self.checkpoint_state = str(frame.payload["state"])
                self.metrics.increment(f"checkpoint_{self.checkpoint_state.lower()}")
            elif frame.message_type == "HEARTBEAT":
                self.metrics.increment("heartbeats")
            elif frame.message_type == "DATA":
                started = self.metrics.timer()
                self.pipeline.process(frame, connection.connection_id, self.checkpoint_state)
                self.metrics.observe("processing", (self.metrics.timer() - started) * 1000)
                self.metrics.increment("data_frames")
            elif frame.message_type == "END_OF_DEMO":
                return

