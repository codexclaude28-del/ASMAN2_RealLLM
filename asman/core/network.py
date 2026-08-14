"""ASMAN 通用地铁网络 —— 从配置构建（非硬编码）

网络拓扑完全由 NetworkConfig（YAML 加载）驱动：
线路 / 站点 / Agent / 切片站 / 换乘枢纽 / 行程 全部声明式定义。
"""

from typing import Dict, List, Optional
from pydantic import BaseModel

from .models import Segment, Itinerary, Train
from ..stations.base import Station
from ..stations.slice_station import SliceStation
from ..lines.line import Line
from ..registry import create_agent


# ================= 配置 schema =================

class StationConfig(BaseModel):
    id: str
    agent: Optional[str] = None       # Agent 注册名
    profile: Optional[str] = None     # Profile 名（默认 = station_id）
    is_hub: bool = False
    slice: bool = False               # 是否切片站（agent 需实现 slice/merge）
    reassemble_hub: Optional[str] = None  # 切片站的重组 Hub
    backloop_target: Optional[str] = None  # 质检失败回环的上游站（默认同线前一个站）


class LineConfig(BaseModel):
    id: str
    name: str = ""
    stations: List[StationConfig]


class SegmentConfig(BaseModel):
    line: str
    board: str
    alight: List[str]
    transfer: Optional[str] = None


class NetworkConfig(BaseModel):
    name: str = "metro"
    lines: List[LineConfig]
    itinerary: List[SegmentConfig]


# ================= 运行时组件 =================

class HubManager:
    """Hub 管理器：处理换乘与子乘客重组"""

    def __init__(self):
        self.hubs: Dict[str, Station] = {}
        self.network = None  # 由 engine.build_network 注入

    def register_hub(self, station: Station):
        self.hubs[station.station_id] = station

    def get_hub(self, hub_id: str) -> Optional[Station]:
        return self.hubs.get(hub_id)

    async def handle_arrival(self, passenger, station: Station):
        """乘客到达 Hub：判断是终点还是换乘到下一线路"""
        hub = self.get_hub(station.station_id)
        if not hub:
            return

        # 子乘客到达 Hub：通知父切片站进行重组追踪
        if getattr(passenger, 'is_sub', False) and passenger.parent_id:
            parent_id = passenger.parent_id
            if self.network:
                for s in self.network.stations.values():
                    if hasattr(s, 'parent_tracking') and parent_id in s.parent_tracking:
                        await s.on_sub_passenger_arrive(passenger)
                        return  # 子乘客不换乘，等重组

        # 检查是否有下一段行程，且下一段属于不同线路
        next_seg = passenger.itinerary.next_segment()
        current_seg = passenger.itinerary.current_segment()
        if next_seg and next_seg.line_id != current_seg.line_id:
            next_line = self.network.get_line(next_seg.line_id) if self.network else None
            if next_line:
                first_station = next_line.stations[0]
                passenger.itinerary.current_segment_idx += 1
                passenger.current_location = first_station.station_id
                await first_station.platform.wait(passenger)
                return

        # 无换乘：在当前 Hub 等待
        await hub.platform.wait(passenger)


class TrainDispatcher:
    """列车调度器"""

    def __init__(self):
        self.urgent_queue: List[str] = []
        self.agent_switches: Dict[str, str] = {}

    def should_dispatch(self, line: Line) -> bool:
        return line.get_total_waiting() > 0

    def assign_train(self, line: Line) -> Optional[Train]:
        line.train_counter += 1
        return Train(
            train_id=f"{line.line_id}_T{line.train_counter}",
            line_id=line.line_id,
            capacity=20
        )

    async def urgent_dispatch(self, line_id: str):
        self.urgent_queue.append(line_id)

    async def switch_agent(self, old_agent_id: str, new_agent_id: str):
        self.agent_switches[old_agent_id] = new_agent_id

    async def degrade_agent(self, agent_id: str):
        pass


class OCC:
    """控制中心：乘客注册表"""

    def __init__(self):
        self.registry: Dict[str, object] = {}
        self.network = None

    def register_passenger(self, passenger):
        self.registry[passenger.passenger_id] = passenger

    def get_passenger(self, passenger_id: str):
        return self.registry.get(passenger_id)

    def remove_passenger(self, passenger_id: str):
        self.registry.pop(passenger_id, None)


class MetroNetwork:
    """通用地铁网络（配置驱动）"""

    def __init__(self, occ: OCC):
        self.lines: Dict[str, Line] = {}
        self.stations: Dict[str, Station] = {}
        self.hubs: Dict[str, Station] = {}
        self.occ = occ
        occ.network = self

    def get_station(self, station_id: str) -> Optional[Station]:
        return self.stations.get(station_id)

    def get_line(self, line_id: str) -> Optional[Line]:
        return self.lines.get(line_id)

    def build_from_config(self, config: NetworkConfig, backloop, hub_manager, dispatcher):
        """从 NetworkConfig 构建线路与站点"""
        for lc in config.lines:
            stations = []
            prev_id = None
            for sc in lc.stations:
                agent = create_agent(sc.agent) if sc.agent else None
                # 回环目标：显式配置 > 同线前一个站点
                backloop_target = sc.backloop_target or prev_id

                if sc.is_hub:
                    st = Station(sc.id, None, lc.id, is_hub=True, backloop_target=backloop_target)
                elif sc.slice:
                    st = SliceStation(sc.id, agent, lc.id, sc.reassemble_hub,
                                      backloop_target=backloop_target)
                else:
                    st = Station(sc.id, agent, lc.id, backloop_target=backloop_target)

                stations.append(st)
                self.stations[st.station_id] = st
                if st.is_hub:
                    self.hubs[st.station_id] = st
                    hub_manager.register_hub(st)
                prev_id = sc.id

            self.lines[lc.id] = Line(lc.id, lc.name, stations)

        # 注入依赖
        for line in self.lines.values():
            for s in line.stations:
                s.occ = self.occ
                s.backloop = backloop
                s.hub_manager = hub_manager
                s.dispatcher = dispatcher

        return self.lines

    def plan_itinerary(self, config: NetworkConfig) -> Itinerary:
        """从配置规划行程"""
        segments = [Segment(s.line, s.board, s.alight, s.transfer) for s in config.itinerary]
        return Itinerary(segments=segments)
