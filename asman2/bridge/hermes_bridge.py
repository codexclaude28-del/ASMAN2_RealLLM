"""
ASMAN-Hermes Bridge
桥接层：ASMAN拓扑编排 ↔ Hermes单Agent执行（真实LLM）
"""

import asyncio
from typing import Dict, Any, Optional, List
from .hermes_worker import HermesWorker
from .hermes_config import get_profile
from ..llm.client import LLMClient


class HermesBridge:
    """
    Hermes桥接器 - 真实LLM版
    """

    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient(provider="mock")
        self.workers: Dict[str, HermesWorker] = {}
        self.worker_pool: Dict[str, list] = {}
        self.execution_log: list = []

    def get_worker(self, station_id: str) -> HermesWorker:
        """获取/创建站点对应的Hermes Worker"""
        if station_id not in self.workers:
            self.workers[station_id] = HermesWorker(station_id, self.llm_client)
        return self.workers[station_id]

    async def execute(self, station_id: str, input_data: Dict, passenger_id: str) -> Dict:
        """核心桥接方法"""
        worker = self.get_worker(station_id)
        result = await worker.execute(input_data, passenger_id)

        self.execution_log.append({
            "station_id": station_id,
            "passenger_id": passenger_id,
            "profile": result.get("profile"),
            "model": result.get("model"),
            "duration_ms": result.get("duration_ms"),
            "cost_usd": result.get("cost_usd", 0),
            "validation": result.get("validation"),
            "skill_applied": result.get("skill_applied")
        })

        return result

    async def batch_execute(self, station_id: str, tasks: list) -> list:
        """批量执行（切片后的子乘客并行）"""
        coros = []
        for task in tasks:
            coros.append(self.execute(station_id, task["input"], task["passenger_id"]))
        return await asyncio.gather(*coros, return_exceptions=True)

    def get_worker_stats(self) -> Dict[str, Dict]:
        """获取所有Worker统计"""
        return {
            station_id: worker.get_stats()
            for station_id, worker in self.workers.items()
        }

    def get_execution_summary(self) -> Dict:
        """执行摘要"""
        if not self.execution_log:
            return {}

        total = len(self.execution_log)
        passed = sum(1 for e in self.execution_log if e["validation"].get("passed", False))
        avg_duration = sum(e["duration_ms"] for e in self.execution_log) / total
        total_cost = sum(e.get("cost_usd", 0) for e in self.execution_log)

        station_stats = {}
        for e in self.execution_log:
            sid = e["station_id"]
            if sid not in station_stats:
                station_stats[sid] = {"total": 0, "passed": 0, "cost": 0}
            station_stats[sid]["total"] += 1
            if e["validation"].get("passed"):
                station_stats[sid]["passed"] += 1
            station_stats[sid]["cost"] += e.get("cost_usd", 0)

        return {
            "total_executions": total,
            "pass_rate": passed / total if total > 0 else 0,
            "avg_duration_ms": avg_duration,
            "total_cost_usd": round(total_cost, 4),
            "station_breakdown": station_stats,
            "top_skills": self._get_top_skills()
        }

    def _get_top_skills(self) -> list:
        """高频Skill"""
        skill_counts = {}
        for e in self.execution_log:
            skill = e.get("skill_applied")
            if skill:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
        return sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    async def evolve_skills(self):
        """触发Skill进化"""
        high_score_logs = [
            e for e in self.execution_log
            if e["validation"].get("score", 0) > 0.95
        ]
        return {"evolved_skills": len(high_score_logs) // 5}
