"""
ASMAN Network
地铁网络拓扑构建器
"""

from typing import Dict, List, Optional
from .core.models import Segment, Itinerary, TaskConfig
from .stations.base import Station
from .stations.slice_station import SliceStation
from .lines.line import Line
from .agents.novel_agents import *


class HubManager:
    """Hub管理器"""

    def __init__(self):
        self.hubs: Dict[str, Station] = {}
        self.network = None  # 由 engine.build_network 注入

    def register_hub(self, station: Station):
        self.hubs[station.station_id] = station

    def get_hub(self, hub_id: str) -> Optional[Station]:
        return self.hubs.get(hub_id)

    async def handle_arrival(self, passenger, station: Station):
        """乘客到达Hub：判断是终点还是需要换乘到下一线路"""
        hub = self.get_hub(station.station_id)
        if not hub:
            return

        # 子乘客到达Hub：通知父切片站进行重组追踪
        if getattr(passenger, 'is_sub', False) and passenger.parent_id:
            parent_id = passenger.parent_id
            # 查找切片站
            if self.network:
                for s in self.network.stations.values():
                    if hasattr(s, 'parent_tracking') and parent_id in s.parent_tracking:
                        await s.on_sub_passenger_arrive(passenger)
                        return  # 子乘客不换乘，等重组

        # 检查是否有下一段行程，且下一段属于不同线路
        next_seg = passenger.itinerary.next_segment()
        current_seg = passenger.itinerary.current_segment()
        if next_seg and next_seg.line_id != current_seg.line_id:
            # 换乘：将乘客送到下一线路的第一个可下车站点
            next_line = self.network.get_line(next_seg.line_id) if self.network else None
            if next_line:
                first_station = next_line.stations[0]
                passenger.itinerary.current_segment_idx += 1
                passenger.current_location = first_station.station_id
                await first_station.platform.wait(passenger)
                print(f"  [Hub {station.station_id}] Transfer -> {first_station.station_id} (Line {next_seg.line_id})")
                return

        # 无换乘：在当前Hub等待
        await hub.platform.wait(passenger)


class TrainDispatcher:
    """列车调度器"""

    def __init__(self):
        self.urgent_queue: List[str] = []
        self.agent_switches: Dict[str, str] = {}

    def should_dispatch(self, line: Line) -> bool:
        return line.get_total_waiting() > 0

    def assign_train(self, line: Line) -> Optional:
        from .core.models import Train
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
    """控制中心"""

    def __init__(self):
        self.registry: Dict[str, object] = {}
        self.network = None

    def register_passenger(self, passenger):
        self.registry[passenger.passenger_id] = passenger

    def get_passenger(self, passenger_id: str):
        return self.registry.get(passenger_id)

    def remove_passenger(self, passenger_id: str):
        self.registry.pop(passenger_id, None)


class NovelSubwayNetwork:
    """小说创作地铁网络"""

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

    def build_default_network(self, backloop, hub_manager):
        """构建默认六线网络"""

        # ===== 1号线：灵感线 =====
        s1 = Station("S1", IntentParserAgent(), "L1")
        s2 = Station("S2", BrainstormAgent(), "L1")
        h1 = Station("H1", None, "L1", is_hub=True)

        line1 = Line("L1", "灵感线", [s1, s2, h1])
        self.lines["L1"] = line1
        for s in [s1, s2, h1]:
            self.stations[s.station_id] = s
        self.hubs["H1"] = h1
        hub_manager.register_hub(h1)

        # ===== 2号线：参考线 =====
        r1 = Station("R1", ResearchAgent("全网采集", "collect"), "L2")
        r2 = Station("R2", ResearchAgent("去重整理", "dedup"), "L2")
        r3 = Station("R3", ResearchAgent("标签分析", "analyze"), "L2")
        h2 = Station("H2", None, "L2", is_hub=True)

        line2 = Line("L2", "参考线", [r1, r2, r3, h2])
        self.lines["L2"] = line2
        for s in [r1, r2, r3, h2]:
            self.stations[s.station_id] = s
        self.hubs["H2"] = h2
        hub_manager.register_hub(h2)

        # ===== 3号线：创作线 =====
        w1 = Station("W1", OutlineAgent(), "L3")
        w2 = SliceStation("W2_SLICE", ChapterSliceAgent(), "L3", "H3")
        w3 = Station("W3", ChapterWriteAgent(), "L3")
        w4 = Station("W4", PolishAgent(), "L3")
        h3 = Station("H3", None, "L3", is_hub=True)

        line3 = Line("L3", "创作线", [w1, w2, w3, w4, h3])
        self.lines["L3"] = line3
        for s in [w1, w2, w3, w4, h3]:
            self.stations[s.station_id] = s
        self.hubs["H3"] = h3
        hub_manager.register_hub(h3)

        # ===== 4号线：发布线 =====
        p1 = Station("P1", PublishAgent("排版生成", "format"), "L4")
        p2 = Station("P2", PublishAgent("封面设计", "cover"), "L4")
        p3 = SliceStation("P3_SLICE", PlatformSliceAgent(), "L4", "H4")
        h4 = Station("H4", None, "L4", is_hub=True)

        line4 = Line("L4", "发布线", [p1, p2, p3, h4])
        self.lines["L4"] = line4
        for s in [p1, p2, p3, h4]:
            self.stations[s.station_id] = s
        self.hubs["H4"] = h4
        hub_manager.register_hub(h4)

        # ===== 5号线：剧本线 =====
        d1 = Station("D1", ScriptAgent("结构改编", "adapt"), "L5")
        d2 = Station("D2", ScriptAgent("对白生成", "dialogue"), "L5")
        d3 = SliceStation("D3_SLICE", SceneSliceAgent(), "L5", "H5")
        h5 = Station("H5", None, "L5", is_hub=True)

        line5 = Line("L5", "剧本线", [d1, d2, d3, h5])
        self.lines["L5"] = line5
        for s in [d1, d2, d3, h5]:
            self.stations[s.station_id] = s
        self.hubs["H5"] = h5
        hub_manager.register_hub(h5)

        # ===== 6号线：视频线 =====
        v1 = Station("V1", VideoAgent("分镜视频", "storyboard"), "L6")
        v2 = Station("V2", VideoAgent("AI配音", "voice"), "L6")
        v3 = Station("V3", VideoAgent("视频合成", "compose"), "L6")
        v4 = Station("V4", VideoAgent("多平台投放", "distribute"), "L6")
        v_end = Station("V_END", None, "L6")

        line6 = Line("L6", "视频线", [v1, v2, v3, v4, v_end])
        self.lines["L6"] = line6
        for s in [v1, v2, v3, v4, v_end]:
            self.stations[s.station_id] = s

        # 注入依赖
        for line in self.lines.values():
            for s in line.stations:
                s.occ = self.occ
                s.backloop = backloop
                s.hub_manager = hub_manager

        return self.lines

    def plan_itinerary(self, config: TaskConfig) -> Itinerary:
        """规划行程"""
        segments = [
            Segment("L1", "S1", ["S2", "H1"], "H1"),
            Segment("L2", "H1", ["R1", "R2", "R3", "H2"], "H2"),
            Segment("L3", "H2", ["W1", "W2_SLICE", "W3", "W4", "H3"], "H3"),
            Segment("L4", "H3", ["P1", "P2", "P3_SLICE", "H4"], "H4"),
            Segment("L5", "H4", ["D1", "D2", "D3_SLICE", "H5"], "H5"),
            Segment("L6", "H5", ["V1", "V2", "V3", "V4", "V_END"], None)
        ]
        return Itinerary(segments=segments)
