"""运行时指标收集（线程安全）

三类指标：
- counters：累计计数（任务完成、LLM 调用、修正次数等）
- timings：耗时（站点处理、LLM 延迟）
- costs：成本（LLM 美元）
- gauges：瞬时值（活跃任务数）
"""

import threading
from collections import defaultdict
from typing import Dict, Any


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.timings = defaultdict(list)
        self.costs = defaultdict(float)

    def incr(self, key: str, n: int = 1):
        with self._lock:
            self.counters[key] += n

    def set_gauge(self, key: str, value: float):
        with self._lock:
            self.gauges[key] = value

    def record_timing(self, key: str, ms: float):
        with self._lock:
            self.timings[key].append(ms)

    def add_cost(self, key: str, usd: float):
        with self._lock:
            self.costs[key] += usd

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            timings = {}
            for k, v in self.timings.items():
                if v:
                    timings[k] = {"count": len(v), "avg_ms": round(sum(v) / len(v), 2),
                                  "max_ms": round(max(v), 2)}
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "timings": timings,
                "costs": {k: round(v, 6) for k, v in self.costs.items()},
            }
