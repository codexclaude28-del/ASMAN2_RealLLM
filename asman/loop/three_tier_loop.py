"""Three-Tier Loop：三层控制循环（真实实现）

- L1 调度兜底：卡住的 WAITING 乘客重新调度到正确站台。
- L2 质检回环：failed_gates 累积且无活跃修正时告警兜底。
- L3 收敛交付：全局收敛检查，达标则交付。
"""

import asyncio
from typing import Any

from ..core.models import Passenger, PassengerStatus


class ThreeTierLoop:
    def __init__(self, engine: Any):
        self.engine = engine
        self.running = False
        self._check_interval = 1.0

    async def start(self):
        self.running = True
        while self.running:
            try:
                await self._l1_dispatch()
                await self._l2_quality_check()
                await self._l3_convergence_check()
            except Exception as e:
                print(f"[ThreeTierLoop] 循环异常: {e}")
            await asyncio.sleep(self._check_interval)

    async def _l1_dispatch(self):
        """L1：卡住的 WAITING 乘客重新入正确站台"""
        for passenger in list(self.engine.occ.registry.values()):
            if passenger.status != PassengerStatus.WAITING:
                continue
            station = self.engine.network.get_station(passenger.current_location)
            if station and passenger not in station.platform.waiting:
                await station.platform.wait(passenger)

    async def _l2_quality_check(self):
        """L2：failed_gates 累积但无活跃修正 → 告警兜底"""
        if not self.engine.backloop:
            return
        for passenger in list(self.engine.occ.registry.values()):
            if passenger.status.value in ("completed", "failed", "backlooping", "split_waiting"):
                continue
            # 已有活跃修正则跳过
            if any(f.original_id == passenger.passenger_id
                   for f in self.engine.backloop.active_fixes.values()):
                continue
            if passenger.failed_gates:
                print(f"[L2] 乘客 {passenger.passenger_id} 存在失败门: "
                      f"{passenger.failed_gates[-3:]}，等待站点重试/回环处理")

    async def _l3_convergence_check(self):
        """L3：全局收敛 → 交付"""
        for passenger in list(self.engine.occ.registry.values()):
            if passenger.status in (PassengerStatus.COMPLETED, PassengerStatus.FAILED):
                continue
            try:
                converged = await self.engine.convergence.converge(passenger)
                if converged and passenger.status != PassengerStatus.COMPLETED:
                    await self.engine.deliverer.deliver(passenger)
            except Exception:
                pass

    def stop(self):
        self.running = False
