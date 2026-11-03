"""并发模型测试：到站处理异步化

验证：
1. handle_alighting 摘下乘客后立即返回，列车不被处理（LLM 调用）阻塞；
2. 同站多个乘客的处理真正并发（站点 Semaphore 生效），总耗时 << 串行耗时。
"""

import asyncio
import time

from asman.agents.base import Agent
from asman.core.models import (
    TaskConfig, Ticket, Segment, Itinerary, Passenger, PassengerStatus, Train,
)
from asman.lines.line import Line
from asman.stations.base import Station


class SlowAgent(Agent):
    """带固定延时的 mock Agent，记录最大并发数"""

    def __init__(self, delay: float = 0.2):
        super().__init__("慢Agent", "slow")
        self.delay = delay
        self.max_concurrent = 0
        self._in_flight = 0

    async def execute(self, input_data, passenger_id):
        self._in_flight += 1
        self.max_concurrent = max(self.max_concurrent, self._in_flight)
        await asyncio.sleep(self.delay)
        self._in_flight -= 1
        return {"result": passenger_id}


def _passenger(pid: str, stations) -> Passenger:
    ticket = Ticket(origin=stations[0], destinations=[stations[-1]],
                    transfer_hubs=[], config=TaskConfig())
    itinerary = Itinerary(segments=[Segment("L1", stations[0], list(stations))])
    return Passenger(pid, ticket, itinerary)


async def _wait_platform_count(station, count: int, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while len(station.platform.waiting) < count:
        assert time.monotonic() < deadline, "乘客未在预期时间内完成处理"
        await asyncio.sleep(0.02)


async def test_alighting_dispatches_without_blocking_train():
    """handle_alighting 应立即返回（不等待处理完成）"""
    agent = SlowAgent(delay=0.2)
    station = Station("S1", agent, "L1")
    train = Train(train_id="T1", line_id="L1")
    passengers = [_passenger(f"P{i}", ["S1", "S2"]) for i in range(4)]
    train.passengers.extend(passengers)

    start = time.monotonic()
    await station.handle_alighting(train, hub_manager=None)
    elapsed = time.monotonic() - start

    # 串行处理需要 4 * 0.2s = 0.8s；异步派发应在毫秒内返回
    assert elapsed < 0.15, f"下车仍阻塞列车: {elapsed:.3f}s"
    assert len(train.passengers) == 0  # 乘客已下车

    # 等处理完成：乘客自行回到站台队列（继续行程）
    await _wait_platform_count(station, 4)
    total = time.monotonic() - start
    # 并发处理总耗时 ~0.2s，远小于串行 0.8s
    assert total < 0.6, f"同站多乘客处理未并发: {total:.3f}s"
    assert agent.max_concurrent > 1, "处理未真正并行"
    assert all(p.status == PassengerStatus.WAITING for p in passengers)


async def test_train_moves_on_while_processing():
    """run_train 不停站等待：列车走完全程时乘客可能仍在处理"""
    agent = SlowAgent(delay=0.3)
    s1 = Station("S1", agent, "L1")
    s2 = Station("S2", None, "L1")  # 终点站（无 Agent）
    line = Line("L1", "测试线", [s1, s2])

    train = Train(train_id="T1", line_id="L1")
    passengers = [_passenger(f"P{i}", ["S1", "S2"]) for i in range(3)]
    for p in passengers:
        p.status = PassengerStatus.ONBOARD
    train.passengers.extend(passengers)

    start = time.monotonic()
    await line.run_train(train, hub_manager=None)
    train_elapsed = time.monotonic() - start

    # 列车全程耗时与乘客处理耗时（0.3s/个）解耦
    assert train_elapsed < 0.3, f"列车仍被站点处理阻塞: {train_elapsed:.3f}s"
    assert train.status.value == "idle"

    # 处理完成后乘客回到 S1 站台等待下一班车
    await _wait_platform_count(s1, 3)
    assert agent.max_concurrent > 1
