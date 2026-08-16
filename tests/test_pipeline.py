from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from mlink_gcp.cli import run_demo
from mlink_gcp.config import FamilySchema
from mlink_gcp.storage import HashChainedJsonlStore


ROOT = Path(__file__).resolve().parents[1]


class PipelineTest(unittest.TestCase):
    def test_reconnect_resubscribe_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = asyncio.run(
                run_demo(ROOT / "configs" / "subscriptions.json", Path(directory), target_signals=4)
            )
            counters = report["metrics"]["counters"]
            self.assertEqual(counters["disconnects"], 1)
            self.assertEqual(counters["reconnects"], 1)
            self.assertEqual(counters["successful_subscriptions"], 2)
            self.assertEqual(len(report["signals"]), 4)
            self.assertTrue(report["evidence"]["raw_chain_valid"])
            self.assertTrue(report["evidence"]["signal_chain_valid"])
            self.assertGreater(report["metrics"]["p95_ms"]["processing"], 0)

    def test_hash_chain_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = HashChainedJsonlStore(path)
            store.append({"value": 1})
            self.assertTrue(store.verify(path))
            persisted = json.loads(path.read_text(encoding="utf-8"))
            persisted["record"]["value"] = 2
            path.write_text(json.dumps(persisted) + "\n", encoding="utf-8")
            self.assertFalse(store.verify(path))

    def test_schema_validation_blocks_incomplete_records(self) -> None:
        schema = FamilySchema("Quote", ("symbol",), "current_state", ("symbol", "bid"), ("bid",))
        with self.assertRaises(ValueError):
            schema.validate({"symbol": "DEMO"})


if __name__ == "__main__":
    unittest.main()

