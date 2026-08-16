from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Frame:
    """A deliberately generic frame inspired by streaming market-data protocols."""

    message_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    sequence: int = 0
    emitted_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Subscription:
    family: str
    symbols: tuple[str, ...]
    fields: tuple[str, ...]


@dataclass(frozen=True)
class Signal:
    signal_id: str
    symbol: str
    signal_type: str
    value: float
    explanation: str
    source_sequence: int
    event_time: str
    strategy_version: str = "synthetic-spread-v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

