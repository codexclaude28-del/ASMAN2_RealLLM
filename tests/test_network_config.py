"""拓扑配置解析与网络构建单元测试"""

from asman.core.network import NetworkConfig, MetroNetwork, OCC, HubManager, TrainDispatcher


SAMPLE = {
    "name": "test",
    "lines": [
        {"id": "L1", "name": "线1", "stations": [
            {"id": "S1", "agent": "intent_parser"},
            {"id": "H1", "is_hub": True},
        ]},
        {"id": "L2", "name": "线2", "stations": [
            {"id": "R1", "agent": "research_collect", "slice": True, "reassemble_hub": "H1"},
        ]},
    ],
    "itinerary": [
        {"line": "L1", "board": "S1", "alight": ["S1", "H1"], "transfer": "H1"},
    ],
}


def test_network_config_parse():
    cfg = NetworkConfig(**SAMPLE)
    assert cfg.name == "test"
    assert len(cfg.lines) == 2
    assert cfg.lines[1].stations[0].slice is True


def test_build_network():
    from asman.registry import clear_all, register_agent
    from asman.agents.base import Agent
    clear_all()
    register_agent("intent_parser", lambda: Agent("需求解析", "intent"))
    register_agent("research_collect", lambda: Agent("研究", "research"))

    cfg = NetworkConfig(**SAMPLE)
    occ = OCC()
    net = MetroNetwork(occ)
    net.build_from_config(cfg, backloop=None, hub_manager=HubManager(), dispatcher=TrainDispatcher())

    assert set(net.lines.keys()) == {"L1", "L2"}
    assert net.get_station("H1").is_hub is True
    # 回环目标：同线前一个站
    assert net.get_station("H1").backloop_target == "S1"
    # 切片站的重组 Hub
    assert net.get_station("R1").reassemble_hub == "H1"


def test_plan_itinerary():
    cfg = NetworkConfig(**SAMPLE)
    occ = OCC()
    net = MetroNetwork(occ)
    it = net.plan_itinerary(cfg)
    assert len(it.segments) == 1
    assert it.segments[0].board_station == "S1"
