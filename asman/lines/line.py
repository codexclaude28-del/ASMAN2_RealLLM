"""
ASMAN Line
线路 = Agent工作流管道
"""

import asyncio
from typing import List, Dict
from ..core.models import Train, TrainStatus, Passenger, PassengerStatus


class Line:
    """线路"""

    def __init__(self, line_id: str, line_name: str, stations: List):
        self.line_id = line_id
        self.line_name = line_name
        self.stations = stations
        self.station_map = {s.station_id: s for s in stations}
        self.trains: List[Train] = []
        self.running = False
        self.train_counter = 0

    def get_station(self, station_id: str):
        return self.station_map.get(station_id)

    def get_total_waiting(self) -> int:
        return sum(s.platform.get_waiting_count() for s in self.stations)

    async def run(self, dispatcher, hub_manager, occ):
        self.running = True
        for station in self.stations:
            station.occ = occ
            station.dispatcher = dispatcher
            if hasattr(station, 'occ'):
                station.occ = occ
        while self.running:
            waiting = self.get_total_waiting()
            if waiting > 0:
                train = dispatcher.assign_train(self)
                if train:
                    asyncio.create_task(self._run_train_safe(train, hub_manager))
            await asyncio.sleep(0.1)  # 小 tick 轮询站台（乘客处理已异步化，无需长间隔）

    async def _run_train_safe(self, train, hub_manager):
        try:
            await self.run_train(train, hub_manager)
        except Exception as e:
            print(f"[Line {self.line_id}] Train error: {e}")
            import traceback
            traceback.print_exc()

    async def run_train(self, train: Train, hub_manager):
        train.status = TrainStatus.BOARDING

        # 在始发站上车
        origin = self.stations[0]
        await origin.handle_boarding(train)

        # 计算路线
        train.route_stops = self._compute_route(train)

        # 每站都停：下车是异步派发的，处理完的乘客会在列车过后才回到站台，
        # 后续列车必须能在任意站停靠接人（不能只停车上乘客的目的站）
        for station in self.stations:
            train.current_station = station.station_id
            train.status = TrainStatus.ARRIVED

            # 下车（异步派发处理，列车不停站等待）
            await station.handle_alighting(train, hub_manager)

            # 上车
            await station.handle_boarding(train)

            # 重新计算
            train.route_stops = self._compute_route(train)

            train.status = TrainStatus.RUNNING

        train.status = TrainStatus.IDLE

    def _compute_route(self, train: Train) -> List[str]:
        stops = set()
        for p in train.passengers:
            seg = p.itinerary.current_segment()
            if seg and seg.line_id == self.line_id:
                for s in seg.alight_stations:
                    if s in self.station_map:
                        stops.add(s)
        return [s.station_id for s in self.stations if s.station_id in stops]
