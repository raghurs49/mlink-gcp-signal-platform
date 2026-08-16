from __future__ import annotations

import math
import time
from collections import defaultdict


class Metrics:
    def __init__(self) -> None:
        self.counters: defaultdict[str, int] = defaultdict(int)
        self.latencies_ms: defaultdict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] += amount

    def observe(self, name: str, milliseconds: float) -> None:
        self.latencies_ms[name].append(milliseconds)

    def timer(self) -> float:
        return time.perf_counter()

    def p95(self, name: str) -> float:
        values = sorted(self.latencies_ms[name])
        if not values:
            return 0.0
        return values[max(0, math.ceil(0.95 * len(values)) - 1)]

    def report(self) -> dict[str, object]:
        return {
            "counters": dict(self.counters),
            "p95_ms": {name: round(self.p95(name), 3) for name in self.latencies_ms},
        }

