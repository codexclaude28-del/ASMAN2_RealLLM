"""
ASMAN Backloop Channel
回环修正通道：下游发现问题 → 坐回环线 → 上游修正
"""

import asyncio
from typing import Dict, Any, Optional
from .models import Passenger, FixPassenger, PassengerStatus, FixHistory


class BackloopChannel:
    """
    回环通道：地铁网络中的"环线"
    允许乘客从下游坐回上游修正问题
    """

    def __init__(self, network):
        self.network = network
        self.fix_queue: asyncio.Queue = asyncio.Queue()
        self.active_fixes: Dict[str, FixPassenger] = {}
        self.running = False

    async def send_back(
        self,
        passenger: Passenger,
        reason: str,
        target_station: str,
        error_context: Dict[str, Any]
    ) -> FixPassenger:
        """
        将乘客送回上游修正
        """
        fix_id = f"FIX_{passenger.passenger_id}_{int(asyncio.get_event_loop().time())}"

        # 创建修正乘客
        fix_passenger = FixPassenger(
            passenger_id=fix_id,
            original_id=passenger.passenger_id,
            target_station=target_station,
            error_context=error_context,
            ticket=passenger.ticket,
            itinerary=passenger.itinerary,
            baggage=passenger.baggage.copy(),
            priority=passenger.priority + 1  # 修正任务优先级更高
        )

        fix_passenger.status = PassengerStatus.BACKLOOPING
        fix_passenger.current_location = passenger.current_location

        # 记录修正历史
        passenger.fix_history.append(FixHistory(
            from_station=passenger.current_location,
            to_station=target_station,
            reason=reason
        ))

        # 放入回环队列
        self.active_fixes[fix_id] = fix_passenger
        await self.fix_queue.put(fix_passenger)

        # 原乘客进入等待修正状态
        passenger.status = PassengerStatus.SPLIT_WAITING
        passenger.slice_station = target_station

        return fix_passenger

    async def process_fix(self, fix_passenger: FixPassenger) -> bool:
        """
        处理修正乘客：送到目标站修正
        """
        target_station_id = fix_passenger.target_station
        station = self.network.get_station(target_station_id)

        if not station:
            return False

        # 将修正乘客放入目标站站台
        fix_passenger.status = PassengerStatus.WAITING
        fix_passenger.current_location = ""
        await station.platform.wait(fix_passenger)

        return True

    async def on_fix_complete(self, fix_passenger: FixPassenger):
        """
        修正完成：合并结果回原乘客，恢复行程
        """
        original_id = fix_passenger.original_id
        original = self.network.occ.get_passenger(original_id)

        if not original:
            # 原乘客已不存在，丢弃修正结果
            self.active_fixes.pop(fix_passenger.passenger_id, None)
            return

        # 合并修正结果
        for key, value in fix_passenger.baggage.items():
            if key.startswith("output_") or key.startswith("fixed_"):
                original.baggage[key] = value

        # 记录修正完成
        original.baggage[f"fix_applied_{fix_passenger.target_station}"] = {
            "fix_id": fix_passenger.passenger_id,
            "timestamp": asyncio.get_event_loop().time()
        }

        # 清除失败记录，允许重新质检
        original.failed_gates = [g for g in original.failed_gates 
                                  if not g.startswith(fix_passenger.target_station)]

        # 恢复状态
        original.status = PassengerStatus.WAITING
        original.slice_station = None

        # 将原乘客放回当前位置站台
        current_station = self.network.get_station(original.current_location)
        if current_station:
            await current_station.platform.wait(original)

        # 清理
        self.active_fixes.pop(fix_passenger.passenger_id, None)

    async def run(self):
        """回环通道主循环"""
        self.running = True
        while self.running:
            try:
                fix_passenger = await asyncio.wait_for(self.fix_queue.get(), timeout=1.0)
                await self.process_fix(fix_passenger)
            except asyncio.TimeoutError:
                await asyncio.sleep(0.1)
