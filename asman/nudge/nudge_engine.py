"""Nudge Engine：后台复盘引擎（真实探测）

定时体检：瓶颈站点 / 弱 Skill / 回环模式，输出复盘报告。
"""

import asyncio
import time
from typing import Dict, Any, List, Optional


class NudgeEngine:
    def __init__(self, state_layer, skill_library,
                 self_healing=None, network=None):
        self.state_layer = state_layer
        self.skill_library = skill_library
        self.self_healing = self_healing
        self.network = network
        self.review_interval = 3600
        self.running = False

    async def start(self):
        self.running = True
        asyncio.create_task(self._review_loop())

    async def _review_loop(self):
        while self.running:
            await self._perform_review()
            await asyncio.sleep(self.review_interval)

    async def _perform_review(self):
        review = {"timestamp": time.time(), "findings": [], "recommendations": []}
        bottleneck = await self._find_bottleneck_stations()
        if bottleneck:
            review["findings"].append(f"瓶颈站点: {bottleneck}")
            review["recommendations"].append(f"建议扩容Agent池或提高列车频率: {bottleneck}")
        weak_skills = await self._find_weak_skills()
        if weak_skills:
            review["findings"].append(f"弱Skill: {weak_skills}")
            review["recommendations"].append("建议触发GEPA进化")
        backloop_patterns = await self._analyze_backloop_patterns()
        if backloop_patterns:
            review["findings"].append(f"回环模式: {backloop_patterns}")
            review["recommendations"].append("建议调整上游Agent prompt或质量阈值")
        await self._emit_review_report(review)

    async def _find_bottleneck_stations(self) -> List[str]:
        """从站台等待队列长度找瓶颈站点"""
        if not self.network:
            return []
        bottlenecks = []
        for station in self.network.stations.values():
            waiting = station.platform.get_waiting_count()
            if waiting > 10:
                bottlenecks.append(f"{station.station_id}(等待{waiting})")
        return bottlenecks[:5]

    async def _find_weak_skills(self) -> List[str]:
        stats = self.skill_library.get_skill_stats()
        if stats.get("avg_success_rate") and stats["avg_success_rate"] < 0.7:
            return ["low_success_rate_skills"]
        return []

    async def _analyze_backloop_patterns(self) -> Dict:
        """统计回环模式：哪些站间回环最频繁"""
        patterns = {}
        if self.network and getattr(self.network, "occ", None):
            for p in self.network.occ.registry.values():
                for fix in p.fix_history:
                    key = f"{fix.from_station}->{fix.to_station}"
                    patterns[key] = patterns.get(key, 0) + 1
        return patterns

    async def _emit_review_report(self, review: Dict):
        count = len(review["findings"])
        print(f"[NudgeEngine] 系统复盘报告: {count} 个发现")
        for f in review["findings"]:
            print(f"   - {f}")
