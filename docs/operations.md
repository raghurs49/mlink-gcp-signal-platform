# Operations and verification runbook

## Health signals

Monitor:

- last authenticated connection
- last successful subscription acknowledgement
- last heartbeat
- last data message by family
- reconnect count and time to recover
- input/output record counts
- schema-validation failures and dead-letter depth
- event-time lag and processing p95
- raw-to-normalized reconciliation

## Deliberate recovery test

1. Start the synthetic demo.
2. The feed closes the first connection after its first live quote and trade.
3. Confirm `disconnects=1` and `reconnects=1`.
4. Confirm two successful authentication and subscription cycles.
5. Confirm the second bootstrap reaches `COMPLETE`.
6. Verify the raw and signal hash chains.
7. Confirm four explainable signals and a non-zero processing p95.

## Incident response

If data freshness fails:

1. Pause downstream signal publication.
2. Inspect authentication and subscription acknowledgements.
3. Compare heartbeat freshness with data-family freshness.
4. Verify current manifest and schema versions.
5. Inspect the dead-letter topic and raw archive.
6. Reconnect and replay the manifest.
7. Reconcile raw-to-normalized counts before resuming signals.

## Limitations

This is an engineering demonstration, not a live trading system. The signal is intentionally simple and synthetic. It has not been evaluated for profitability and must not be used for financial decisions.

