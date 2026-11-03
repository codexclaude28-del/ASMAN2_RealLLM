
"""ASMAN 2.0 Slice Station - 融合版
注入: state_layer持久化 + Skill提取
"""

import asyncio
import time
from typing import Dict, List, Optional
from .base import Station
from ..core.models import Passenger, SubPassenger, PassengerStatus


class SliceStation(Station):
    """
    切片站：任务分裂与重组 (ASMAN 2.0 融合版)
    1. 主乘客到达 → Agent切片 → 生成N个子乘客
    2. 子乘客独立运行 → 到达重组Hub
    3. 所有子乘客到达 → 触发重组 → 恢复主乘客
    """

    def __init__(self, station_id: str, agent, line_id: str,
                 reassemble_hub: str, backloop_target: Optional[str] = None, gate: str = "auto",
                 output_schema: Optional[Dict] = None, processing_capacity: int = 5):
        super().__init__(station_id, agent, line_id, backloop_target=backloop_target,
                         gate=gate, output_schema=output_schema,
                         processing_capacity=processing_capacity)
        self.reassemble_hub = reassemble_hub
        self.parent_tracking: Dict[str, Dict] = {}

    async def process_passenger(self, passenger: Passenger):
        """切片处理"""
        if getattr(passenger, 'is_fix', False):
            await super().process_passenger(passenger)
            return

        if passenger.is_sub:
            await self.on_sub_passenger_arrive(passenger)
            return

        # 1. Agent执行切片
        passenger.status = PassengerStatus.PROCESSING
        slices = await self.agent.slice(passenger.baggage)

        # 2. 主乘客进入等待状态
        passenger.status = PassengerStatus.SPLIT_WAITING
        passenger.slice_station = self.station_id

        # 3. 创建追踪 (内存 + 持久化)
        tracking = {
            "total": len(slices),
            "arrived": 0,
            "results": [],
            "parent_passenger": passenger,
            "start_time": time.time(),
            "station_id": self.station_id
        }
        self.parent_tracking[passenger.passenger_id] = tracking
        # 注册到 HubManager 的父乘客索引（子乘客到站 O(1) 匹配）
        if self.hub_manager is not None:
            self.hub_manager.parent_index[passenger.passenger_id] = self

        # 持久化切片追踪 (Loop Eng. State外部化)
        if self.state_layer:
            await self._db(self.state_layer.save_slice_tracking, passenger.passenger_id, tracking)
            await self._db(self.state_layer.save_passenger, passenger)

        # 4. 创建子乘客
        for slice_data in slices:
            sub_id = f"{passenger.passenger_id}#{slice_data.get('id', '0')}"
            sub = SubPassenger(
                passenger_id=sub_id,
                parent_id=passenger.passenger_id,
                ticket=passenger.ticket.derive_for_slice(slice_data),
                itinerary=passenger.itinerary,
                baggage={
                    "slice_task": slice_data,
                    "parent_baggage": passenger.baggage,
                    "config": passenger.ticket.config
                },
                priority=passenger.priority
            )
            sub.current_location = self.station_id
            sub.status = PassengerStatus.WAITING
            await self.platform.wait(sub)

            # 持久化子乘客
            if self.state_layer:
                await self._db(self.state_layer.save_passenger, sub)
                await self._db(self.state_layer.enqueue_to_platform,
                               self.station_id, sub_id, sub.priority)

        # 5. 触发紧急调度
        if self.dispatcher:
            await self.dispatcher.urgent_dispatch(self.line_id)

    async def on_sub_passenger_arrive(self, sub_passenger: SubPassenger):
        """子乘客到达重组Hub后回调"""
        parent_id = sub_passenger.parent_id
        if parent_id not in self.parent_tracking:
            return

        tracking = self.parent_tracking[parent_id]
        tracking["arrived"] += 1
        tracking["results"].append({
            "sub_id": sub_passenger.passenger_id,
            "slice_id": sub_passenger.slice_id,
            "output": self._latest_sub_output(sub_passenger)
        })

        # 持久化更新
        if self.state_layer:
            await self._db(self.state_layer.save_slice_tracking, parent_id, tracking)

        if tracking["arrived"] >= tracking["total"]:
            await self.reassemble(parent_id)

    def _latest_sub_output(self, sub_passenger: SubPassenger) -> Dict:
        """取子乘客的上游最近产物（通用逻辑，不写死业务站点键）

        优先重组 Hub 的产出；否则按已完成站点倒序找最近的 output_* 产物。
        """
        hub_key = f"output_{self.reassemble_hub}"
        if hub_key in sub_passenger.baggage:
            return sub_passenger.baggage[hub_key]
        for stop in reversed(sub_passenger.completed_stops):
            key = f"output_{stop}"
            if key in sub_passenger.baggage:
                return sub_passenger.baggage[key]
        for key in reversed(list(sub_passenger.baggage.keys())):
            if key.startswith("output_"):
                return sub_passenger.baggage[key]
        return {}

    async def reassemble(self, parent_id: str):
        """重组所有子乘客"""
        if parent_id not in self.parent_tracking:
            return

        tracking = self.parent_tracking.pop(parent_id)
        parent = tracking["parent_passenger"]
        if self.hub_manager is not None:
            self.hub_manager.parent_index.pop(parent_id, None)

        # 1. Agent合并
        merged = await self.agent.merge(tracking["results"])
        parent.baggage[f"merged_{self.station_id}"] = merged

        if self.state_layer:
            await self._db(self.state_layer.append_event, parent.passenger_id,
                           "slice_reassembled",
                           {"station": self.station_id, "subs": tracking["total"]})

        # 2. 恢复主乘客（completed_stops 已在 handle_alighting 记录过，此处不重复）
        parent.status = PassengerStatus.WAITING
        parent.slice_station = None

        # 3. 找到重组Hub（用于触发换乘）
        hub_station = None
        if self.occ and self.occ.network:
            for line in self.occ.network.lines.values():
                for s in line.stations:
                    if s.station_id == self.reassemble_hub:
                        hub_station = s
                        break
                if hub_station:
                    break

        # 4. 不在此递进segment，由HubManager.handle_arrival统一处理换乘
        if hub_station and self.hub_manager:
            await self.hub_manager.handle_arrival(parent, hub_station)
        elif hub_station:
            await hub_station.platform.wait(parent)
        else:
            parent.status = PassengerStatus.COMPLETED

        # 5. 持久化
        if self.state_layer:
            await self._db(self.state_layer.save_passenger, parent)

        # 6. Skill提取: 重组成功模式存入Skill库（非关键路径，失败只记录）
        if self.skill_library and merged:
            try:
                params = getattr(parent.ticket.config, "params", {}) or {}
                profile_key = params.get("genre", "default") if isinstance(params, dict) else "default"
                await asyncio.to_thread(
                    self.skill_library.extract_skill_from_success,
                    capability="slice_merge",
                    profile=profile_key,
                    prompt=str(self.station_id),
                    output=merged,
                    score=0.95
                )
            except Exception as e:
                import logging
                logging.getLogger("asman.station").warning("重组Skill提取失败: %s", e)
