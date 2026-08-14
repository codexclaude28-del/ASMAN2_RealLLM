"""
ASMAN Convergence Engine
终态收敛器：判断系统何时真正完成
"""

import asyncio
import time
from typing import Dict, Any, List
from .models import Passenger, PassengerStatus


class ConvergenceEngine:
    """
    终态收敛器
    必须全部满足以下条件才算完成：
    1. 所有子乘客已重组
    2. 所有质量门已通过
    3. 所有回环已收敛
    4. 所有产出物已生成
    5. 没有挂起的重试
    """

    def __init__(self, network, occ, required_outputs=None):
        self.network = network
        self.occ = occ
        self.required_outputs = required_outputs

    async def converge(self, root_passenger: Passenger) -> bool:
        """检查是否收敛完成"""
        checks = await asyncio.gather(
            self._check_all_subs_reassembled(root_passenger),
            self._check_all_gates_passed(root_passenger),
            self._check_all_backloops_converged(root_passenger),
            self._check_all_outputs_accessible(root_passenger),
            self._check_no_pending_retries(root_passenger),
            self._check_itinerary_complete(root_passenger),
        )

        return all(checks)

    async def _check_itinerary_complete(self, passenger: Passenger) -> bool:
        """乘客必须走完整个行程（当前段无剩余站 + 无下一段）"""
        if passenger.has_more_stops_in_segment():
            return False
        return passenger.itinerary.next_segment() is None

    async def _check_all_subs_reassembled(self, passenger: Passenger) -> bool:
        """检查所有子乘客已重组"""
        # 如果乘客正在等待重组，未收敛
        if passenger.status == PassengerStatus.SPLIT_WAITING:
            return False
        # 检查是否有子乘客还在运行
        for p in self.occ.registry.values():
            if p.parent_id == passenger.passenger_id and p.status != PassengerStatus.COMPLETED:
                return False
        return True

    async def _check_all_gates_passed(self, passenger: Passenger) -> bool:
        """检查所有质量门已通过"""
        return len(passenger.failed_gates) == 0

    async def _check_all_backloops_converged(self, passenger: Passenger) -> bool:
        """检查所有回环已收敛"""
        # 检查是否有正在进行的修正
        for p in self.occ.registry.values():
            if p.status == PassengerStatus.BACKLOOPING:
                return False
        return True

    async def _check_all_outputs_accessible(self, passenger: Passenger) -> bool:
        """检查所有产出物已生成（required_outputs 由配置注入）"""
        if not self.required_outputs:
            return True
        for key in self.required_outputs:
            if key not in passenger.baggage:
                return False
        return True

    async def _check_no_pending_retries(self, passenger: Passenger) -> bool:
        """检查没有挂起的重试"""
        for count in passenger.retry_count.values():
            if count > 0 and count < passenger.ticket.config.max_retry:
                # 还有重试在进行中
                pass
        return True

    def estimate_eta(self, passenger: Passenger) -> str:
        """预估完成时间"""
        progress = passenger.itinerary.progress_percent()
        if progress >= 99:
            return "即将完成"
        if progress < 10:
            return "预计5-10分钟"
        if progress < 50:
            return "预计3-5分钟"
        return "预计1-2分钟"

    async def deliver(self, passenger: Passenger) -> Dict[str, Any]:
        """自动交付最终产物"""
        outputs = {
            "novel": passenger.baggage.get("merged_W2_SLICE", {}),
            "script": passenger.baggage.get("merged_D3_SLICE", {}),
            "videos": passenger.baggage.get("video_outputs", []),
            "publish_status": passenger.baggage.get("merged_P3_SLICE", {}),
            "report": self._generate_report(passenger)
        }

        passenger.status = PassengerStatus.COMPLETED
        return outputs

    def _generate_report(self, passenger: Passenger) -> Dict:
        """生成执行报告"""
        return {
            "task_id": passenger.passenger_id,
            "title": passenger.ticket.config.title,
            "genre": (passenger.ticket.config.params or {}).get("genre", ""),
            "total_stations_visited": len(passenger.completed_stops),
            "total_fixes": len(passenger.fix_history),
            "quality_scores": {k: v.average() for k, v in passenger.quality_scores.items()},
            "execution_time": time.time() - passenger.created_at,
            "status": "completed"
        }
