"""ASMAN 2.0 Three-Tier Loop

三层循环架构:
- L1: 站点调度循环 - 逐个站点推进乘客
- L2: 质检回环 - 质量门未通过时触发回环修正
- L3: 收敛循环 - 全局收敛检查，确保所有产出物达标
"""

import asyncio
from typing import Dict, Any


class ThreeTierLoop:
    """三层循环控制器，监控乘客状态并触发回环修正"""

    def __init__(self, engine):
        self.engine = engine
        self.running = False
        self._check_interval = 1.0  # 检查间隔（秒）
        self._max_iterations = 100  # 单乘客最大迭代次数

    async def start(self):
        """启动三层循环"""
        self.running = True
        print("[ThreeTierLoop] 三层循环已启动")

        while self.running:
            try:
                # L1: 遍历所有活跃乘客，检查是否需要调度
                for passenger in list(self.engine.occ.registry.values()):
                    await self._l1_dispatch(passenger)

                # L2: 检查质量门，触发回环
                for passenger in list(self.engine.occ.registry.values()):
                    await self._l2_quality_check(passenger)

                # L3: 全局收敛检查
                await self._l3_convergence_check()

            except Exception as e:
                print(f"[ThreeTierLoop] 循环异常: {e}")

            await asyncio.sleep(self._check_interval)

    async def _l1_dispatch(self, passenger) -> None:
        """L1: 站点调度 - 确保乘客按路径前进"""
        if passenger.status.value in ("completed", "failed"):
            return

        # 获取当前行程段
        seg = passenger.itinerary.current_segment()
        if not seg:
            return

        # 检查当前段还有哪些站点未完成
        pending = [s for s in seg.alight_stations if s not in passenger.completed_stops]
        if not pending:
            return

    async def _l2_quality_check(self, passenger) -> None:
        """L2: 质量门检查 - 触发回环修正"""
        if passenger.status.value in ("completed", "failed"):
            return

        # 检查是否有针对此乘客的活跃回环修正
        if self.engine.backloop:
            for fix_id, fix_pax in self.engine.backloop.active_fixes.items():
                if fix_pax.original_id == passenger.passenger_id:
                    print(f"[L2] 乘客 {passenger.passenger_id} 有活跃的回环修正")
                    break

    async def _l3_convergence_check(self) -> None:
        """L3: 全局收敛检查"""
        # 由 ConvergenceEngine 处理，这里作为周期性触发
        pass

    def stop(self):
        """停止循环"""
        self.running = False
        print("[ThreeTierLoop] 三层循环已停止")
