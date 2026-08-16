from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from .client import StreamingClient
from .config import load_manifest, load_schemas
from .feed import SyntheticFeed
from .metrics import Metrics
from .pipeline import StreamingPipeline
from .storage import HashChainedJsonlStore


async def run_demo(config_path: Path, output_dir: Path, target_signals: int) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(config_path)
    schema_path = config_path.with_name("schemas.json")
    schemas = load_schemas(schema_path)
    api_key = os.getenv(manifest.api_key_env, "synthetic-demo-key")
    feed = SyntheticFeed(valid_api_key="synthetic-demo-key", disconnect_once=True)
    raw_store = HashChainedJsonlStore(output_dir / "raw_events.jsonl")
    signal_store = HashChainedJsonlStore(output_dir / "signals.jsonl")
    pipeline = StreamingPipeline(schemas, raw_store, signal_store)
    metrics = Metrics()
    client = StreamingClient(feed, manifest, pipeline, api_key, metrics)
    try:
        report = await client.run(target_signals=target_signals)
    finally:
        await feed.shutdown()
    report["evidence"] = {
        "raw_chain_valid": HashChainedJsonlStore.verify(raw_store.path),
        "signal_chain_valid": HashChainedJsonlStore.verify(signal_store.path),
        "raw_records": raw_store.count,
        "signal_records": signal_store.count,
    }
    (output_dir / "recovery_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the synthetic MLink-style streaming demo")
    parser.add_argument("--config", type=Path, default=Path("configs/subscriptions.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    parser.add_argument("--signals", type=int, default=4)
    args = parser.parse_args()
    report = asyncio.run(run_demo(args.config, args.output, args.signals))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

