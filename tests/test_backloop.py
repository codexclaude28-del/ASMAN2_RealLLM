"""回环通道单元测试"""

import asyncio

from asman.core.backloop import BackloopChannel
from asman.core.models import TaskConfig, Ticket, Segment, Itinerary, Passenger


class _FakeNetwork:
    def __init__(self, occ):
        self.occ = occ

    def get_station(self, sid):
        return None


def _passenger():
    t = Ticket(origin="S1", destinations=["V"], transfer_hubs=[], config=TaskConfig())
    it = Itinerary(segments=[Segment("L1", "S1", ["S2", "H1"], "H1")])
    p = Passenger("P1", t, it)
    p.current_location = "S2"
    return p


def test_send_back_creates_fix_passenger():
    p = _passenger()
    occ = type("OCC", (), {"registry": {}})()
    bl = BackloopChannel(_FakeNetwork(occ))

    fix = asyncio.run(bl.send_back(p, "质量差", "S1", {"score": 0.5}))

    assert fix.is_fix is True
    assert fix.original_id == "P1"
    assert fix.target_station == "S1"
    assert fix.priority == p.priority + 1  # 修正任务优先级更高
    assert len(p.fix_history) == 1
    assert p.fix_history[0].reason == "质量差"
