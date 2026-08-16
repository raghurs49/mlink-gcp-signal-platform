from __future__ import annotations

import hashlib
from typing import Any

from .config import FamilySchema
from .models import Frame, Signal
from .storage import CurrentStateStore, HashChainedJsonlStore


class StreamingPipeline:
    def __init__(
        self,
        schemas: dict[str, FamilySchema],
        raw_store: HashChainedJsonlStore,
        signal_store: HashChainedJsonlStore,
    ) -> None:
        self.schemas = schemas
        self.raw_store = raw_store
        self.signal_store = signal_store
        self.current_state = CurrentStateStore()
        self.signals: list[Signal] = []

    def process(self, frame: Frame, connection_id: int, checkpoint_state: str) -> Signal | None:
        family = str(frame.payload["family"])
        schema = self.schemas[family]
        schema.validate(frame.payload)
        raw_envelope = {
            "connection_id": connection_id,
            "checkpoint_state": checkpoint_state,
            "frame": frame.to_dict(),
            "schema": family,
        }
        persisted = self.raw_store.append(raw_envelope)
        normalized = self._normalize(frame.payload, persisted["record_hash"])

        if schema.state_type == "current_state":
            self.current_state.upsert(schema.primary_key, normalized)
        if family != "SyntheticQuote" or frame.payload.get("cached"):
            return None

        midpoint = (normalized["bid"] + normalized["ask"]) / 2
        spread_bps = ((normalized["ask"] - normalized["bid"]) / midpoint) * 10_000
        digest = hashlib.sha256(
            f"{normalized['symbol']}:{frame.sequence}:{normalized['event_time']}".encode()
        ).hexdigest()[:16]
        signal = Signal(
            signal_id=digest,
            symbol=normalized["symbol"],
            signal_type="spread_quality",
            value=round(spread_bps, 4),
            explanation=(
                f"Synthetic quote spread is {spread_bps:.2f} bps; "
                "lower values indicate a tighter synthetic market. This is not trading advice."
            ),
            source_sequence=frame.sequence,
            event_time=normalized["event_time"],
        )
        self.signal_store.append({**signal.to_dict(), "source_record_hash": persisted["record_hash"]})
        self.signals.append(signal)
        return signal

    @staticmethod
    def _normalize(payload: dict[str, Any], raw_hash: str) -> dict[str, Any]:
        return {**payload, "raw_record_hash": raw_hash}

