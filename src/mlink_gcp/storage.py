from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class HashChainedJsonlStore:
    """Append-only local evidence store; GCS Object Lock is the cloud equivalent."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.previous_hash = "0" * 64
        self.count = 0

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        envelope = {"previous_hash": self.previous_hash, "record": record}
        canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        record_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        persisted = {**envelope, "record_hash": record_hash}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(persisted, sort_keys=True) + "\n")
        self.previous_hash = record_hash
        self.count += 1
        return persisted

    @staticmethod
    def verify(path: str | Path) -> bool:
        previous = "0" * 64
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            persisted = json.loads(line)
            if persisted["previous_hash"] != previous:
                return False
            envelope = {"previous_hash": previous, "record": persisted["record"]}
            canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
            expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if expected != persisted["record_hash"]:
                return False
            previous = expected
        return True


class CurrentStateStore:
    def __init__(self) -> None:
        self.records: dict[tuple[str, ...], dict[str, Any]] = {}

    def upsert(self, primary_key: tuple[str, ...], record: dict[str, Any]) -> bool:
        key = tuple(str(record[field]) for field in primary_key)
        existing = self.records.get(key)
        if existing and existing["event_time"] > record["event_time"]:
            return False
        self.records[key] = record
        return True

