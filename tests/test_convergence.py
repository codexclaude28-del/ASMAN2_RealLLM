"""收敛引擎单元测试"""

import asyncio

from asman.core.convergence import ConvergenceEngine
from asman.core.models import TaskConfig, Ticket, Segment, Itinerary, Passenger


def _passenger(completed=None):
    t = Ticket(origin="S1", destinations=["V"], transfer_hubs=[], config=TaskConfig())
    it = Itinerary(segments=[Segment("L1", "S1", ["S2", "H1"], "H1")])
    p = Passenger("P1", t, it)
    p.completed_stops = completed or []
    return p


def test_itinerary_complete():
    eng = ConvergenceEngine(None, None)
    assert asyncio.run(eng._check_itinerary_complete(_passenger(["S2", "H1"]))) is True
    assert asyncio.run(eng._check_itinerary_complete(_passenger(["S2"]))) is False


def test_outputs_accessible():
    eng = ConvergenceEngine(None, None, required_outputs=["merged_A"])
    p = _passenger()
    assert asyncio.run(eng._check_all_outputs_accessible(p)) is False
    p.baggage["merged_A"] = {}
    assert asyncio.run(eng._check_all_outputs_accessible(p)) is True


def test_outputs_accessible_no_required():
    eng = ConvergenceEngine(None, None)  # 未配置 required_outputs → 跳过
    assert asyncio.run(eng._check_all_outputs_accessible(_passenger())) is True
