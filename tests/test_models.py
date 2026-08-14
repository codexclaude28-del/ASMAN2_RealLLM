"""核心模型单元测试"""

from asman.core.models import (
    TaskConfig, Ticket, Segment, Itinerary, Passenger, QualityScores, Train, TrainStatus
)


def test_taskconfig_params():
    cfg = TaskConfig(title="t", params={"genre": "玄幻", "chapters": 5})
    assert cfg.title == "t"
    assert cfg.params["genre"] == "玄幻"
    assert cfg.quality_threshold == 0.85


def test_itinerary_progress():
    it = Itinerary(segments=[
        Segment("L1", "S1", ["S2", "H1"], "H1"),
        Segment("L2", "H1", ["R1", "H2"], "H2"),
    ])
    assert it.progress_percent() == 0.0
    it.current_segment_idx = 1
    assert it.progress_percent() == 50.0
    assert it.next_segment() is None
    assert it.current_segment().line_id == "L2"


def _make_passenger():
    ticket = Ticket(origin="S1", destinations=["V_END"], transfer_hubs=["H1"], config=TaskConfig())
    it = Itinerary(segments=[Segment("L1", "S1", ["S2", "H1"], "H1")])
    return Passenger("P1", ticket, it)


def test_passenger_alight_logic():
    p = _make_passenger()
    assert p.should_alight_at("S2") is True
    assert p.should_alight_at("S1") is False  # 不在 alight 列表
    p.completed_stops.append("S2")
    assert p.should_alight_at("S2") is False  # 已下过车


def test_passenger_has_more_stops():
    p = _make_passenger()
    assert p.has_more_stops_in_segment() is True
    p.completed_stops = ["S2", "H1"]
    assert p.has_more_stops_in_segment() is False


def test_quality_scores_average():
    s = QualityScores(0.8, 0.9, 0.7, 0.85, 0.95)
    assert abs(s.average() - 0.84) < 1e-9


def test_sub_passenger_slice_id():
    from asman.core.models import SubPassenger
    t = Ticket(origin="S1", destinations=[], transfer_hubs=[])
    it = Itinerary(segments=[])
    sub = SubPassenger("P1#ch2", "P1", ticket=t, itinerary=it)
    assert sub.is_sub is True
    assert sub.slice_id == "ch2"
