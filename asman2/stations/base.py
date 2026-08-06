"""ASMAN 2.0 Station Base - Hermes融合版
每个站点通过Hermes Bridge调用Hermes Profile Worker执行
"""

import asyncio
from typing import List, Optional
from ..core.models import Passenger, PassengerStatus, GateResult
from ..core.quality_gate import QualityGate
from ..agents.base import Agent


class Platform:
    """站台 = 等待队列"""

    def __init__(self):
        self.waiting: List[Passenger] = []
        self.lock = asyncio.Lock()

    async def wait(self, passenger: Passenger):
        async with self.lock:
            self.waiting.append(passenger)
            passenger.status = PassengerStatus.WAITING

    async def board_passengers(self, train, max_count: int) -> List[Passenger]:
        async with self.lock:
            self.waiting.sort(key=lambda p: -p.priority)
            boarding = []
            for p in self.waiting[:max_count]:
                if p.status == PassengerStatus.WAITING:
                    boarding.append(p)
                    p.status = PassengerStatus.ONBOARD
            self.waiting = [p for p in self.waiting if p not in boarding]
            return boarding

    def get_waiting_count(self) -> int:
        return len([p for p in self.waiting if p.status == PassengerStatus.WAITING])


class Station:
    """普通站点：通过Hermes Bridge调用Profile Worker执行"""

    def __init__(self, station_id: str, agent: Agent, line_id: str, is_hub: bool = False):
        self.station_id = station_id
        self.agent = agent
        self.line_id = line_id
        self.is_hub = is_hub
        self.platform = Platform()
        self.processing_capacity = 5
        self.current_load = 0
        self.semaphore = asyncio.Semaphore(self.processing_capacity)
        self.quality_gate = QualityGate(station_id)

        # 融合模块注入点
        self.occ = None
        self.dispatcher = None
        self.backloop = None
        self.hub_manager = None
        self.state_layer = None
        self.skill_library = None
        self.moa_verifier = None
        self.profile_manager = None
        self.hermes_bridge = None  # Hermes桥接器

    async def handle_boarding(self, train):
        available = train.capacity - len(train.passengers)
        if available <= 0:
            return
        boarding = await self.platform.board_passengers(train, available)
        for p in boarding:
            train.passengers.append(p)

    async def handle_alighting(self, train, hub_manager):
        alighting = [p for p in train.passengers if p.should_alight_at(self.station_id)]
        for p in alighting:
            train.passengers.remove(p)
            p.current_location = self.station_id
            p.completed_stops.append(self.station_id)

            if self.state_layer:
                self.state_layer.save_passenger(p)

            if self.is_hub:
                await hub_manager.handle_arrival(p, self)
            else:
                await self.process_passenger(p)

    async def process_passenger(self, passenger: Passenger):
        async with self.semaphore:
            self.current_load += 1
            passenger.status = PassengerStatus.PROCESSING

            if self.state_layer:
                self.state_layer.save_passenger(passenger)

            try:
                # ==== 核心：通过Hermes Bridge调用Profile Worker ====
                # 30s超时 + 自动降级到本地Agent，确保管道不阻塞
                if self.hermes_bridge:
                    try:
                        result = await asyncio.wait_for(
                            self._execute_via_hermes(passenger), timeout=120.0
                        )
                    except (asyncio.TimeoutError, Exception):
                        print(f"  [{self.station_id}] LLM超时/失败, 降级到本地Agent")
                        result = await self._execute_local(passenger)
                else:
                    result = await self._execute_local(passenger)

                passenger.baggage[f"output_{self.station_id}"] = result

                # MoA独立验证
                avg_score = await self._verify_with_moa(result, passenger)

                # Skill提取
                if self.skill_library and avg_score >= 0.9:
                    self._extract_skill(result, passenger)

                # 判断质检结果
                threshold = passenger.ticket.config.quality_threshold
                if avg_score >= threshold:
                    await self._continue_journey(passenger)
                else:
                    retry_count = passenger.get_retry_count(self.station_id)
                    if retry_count < passenger.ticket.config.max_retry:
                        passenger.increment_retry(self.station_id)
                        passenger.status = PassengerStatus.WAITING
                        await self.platform.wait(passenger)
                        if self.state_layer:
                            self.state_layer.save_passenger(passenger)
                    else:
                        await self._trigger_backloop(passenger, avg_score)

            except Exception as e:
                import traceback
                print(f"[Station {self.station_id}] ERROR: {e}")
                traceback.print_exc()
                passenger.baggage[f"error_{self.station_id}"] = str(e)
                passenger.status = PassengerStatus.FAILED
                if self.state_layer:
                    self.state_layer.save_passenger(passenger)
            finally:
                self.current_load -= 1

    async def _execute_via_hermes(self, passenger: Passenger) -> dict:
        """通过Hermes Bridge调用Profile Worker"""
        hermes_result = await self.hermes_bridge.execute(
            station_id=self.station_id,
            input_data=passenger.baggage,
            passenger_id=passenger.passenger_id
        )

        # 记录Hermes执行元数据
        passenger.baggage[f"_hermes_{self.station_id}"] = {
            "profile": hermes_result.get("profile"),
            "model": hermes_result.get("model"),
            "duration_ms": hermes_result.get("duration_ms"),
            "skill_applied": hermes_result.get("skill_applied"),
            "validation": hermes_result.get("validation")
        }

        return hermes_result.get("output", {})

    async def _execute_local(self, passenger: Passenger) -> dict:
        """本地Agent降级执行"""
        result = await self.agent.execute(
            input_data=passenger.baggage,
            passenger_id=passenger.passenger_id
        )
        return result

    async def _verify_with_moa(self, result: dict, passenger: Passenger) -> float:
        """MoA独立验证"""
        if self.moa_verifier:
            output = passenger.baggage.get(f"output_{self.station_id}")
            scores = await self.moa_verifier.aggregate_verify(
                output=output, context=passenger.baggage, station_id=self.station_id
            )
            passenger.quality_scores[self.station_id] = scores
            return scores.average()
        else:
            return 0.9  # 默认通过

    def _extract_skill(self, result: dict, passenger: Passenger):
        """提取Skill到Skill库"""
        if not self.skill_library:
            return
        capability = getattr(self.agent, 'capability', 'general') if self.agent else 'general'
        profile_key = passenger.ticket.config.genre if passenger.ticket.config else 'default'
        self.skill_library.extract_skill_from_success(
            capability=capability,
            profile=profile_key,
            prompt=str(self.station_id),
            output=result,
            score=passenger.quality_scores.get(self.station_id, type('obj', (object,), {'average': lambda: 0.9})()).average()
        )

    async def _continue_journey(self, passenger: Passenger):
        if passenger.has_more_stops_in_segment():
            passenger.status = PassengerStatus.WAITING
            await self.platform.wait(passenger)
        else:
            next_seg = passenger.itinerary.next_segment()
            if next_seg:
                passenger.itinerary.current_segment_idx += 1
                passenger.status = PassengerStatus.WAITING
                await self.platform.wait(passenger)
            else:
                passenger.status = PassengerStatus.COMPLETED
        if self.state_layer:
            self.state_layer.save_passenger(passenger)

    async def _trigger_backloop(self, passenger: Passenger, score: float):
        if not self.backloop:
            passenger.status = PassengerStatus.FAILED
            if self.state_layer:
                self.state_layer.save_passenger(passenger)
            return

        weakest = "consistency"
        target = self.quality_gate.get_upstream_fix(weakest, self.station_id)

        await self.backloop.send_back(
            passenger=passenger,
            reason=f"{self.station_id}质量不达标(score={score:.2f}), weakest={weakest}",
            target_station=target,
            error_context={
                "failed_station": self.station_id,
                "weakest_dimension": weakest,
                "score": score
            }
        )
