from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Subscription


@dataclass(frozen=True)
class FamilySchema:
    name: str
    primary_key: tuple[str, ...]
    state_type: str
    required_fields: tuple[str, ...]
    numeric_fields: tuple[str, ...]

    def validate(self, payload: dict[str, Any]) -> None:
        missing = [field for field in self.required_fields if field not in payload]
        if missing:
            raise ValueError(f"{self.name} missing required fields: {missing}")
        for field in self.numeric_fields:
            if not isinstance(payload[field], (int, float)):
                raise ValueError(f"{self.name}.{field} must be numeric")


@dataclass(frozen=True)
class Manifest:
    version: str
    api_key_env: str
    heartbeat_timeout_seconds: float
    max_reconnects: int
    subscriptions: tuple[Subscription, ...]


def load_schemas(path: str | Path) -> dict[str, FamilySchema]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        name: FamilySchema(
            name=name,
            primary_key=tuple(spec["primary_key"]),
            state_type=spec["state_type"],
            required_fields=tuple(spec["required_fields"]),
            numeric_fields=tuple(spec.get("numeric_fields", [])),
        )
        for name, spec in raw["families"].items()
    }


def load_manifest(path: str | Path) -> Manifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    subscriptions = tuple(
        Subscription(
            family=item["family"],
            symbols=tuple(item["symbols"]),
            fields=tuple(item["fields"]),
        )
        for item in raw["subscriptions"]
    )
    return Manifest(
        version=raw["manifest_version"],
        api_key_env=raw["api_key_env"],
        heartbeat_timeout_seconds=float(raw["heartbeat_timeout_seconds"]),
        max_reconnects=int(raw["max_reconnects"]),
        subscriptions=subscriptions,
    )

