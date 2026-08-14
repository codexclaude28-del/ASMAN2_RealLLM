"""Station Worker 抽象 —— 分布式扩展点

当前用 LocalStationWorker（进程内 asyncio，由 Station.semaphore 控并发）。
未来若需跨进程/跨机扩展，实现 DistributedStationWorker（消息队列 + 独立 worker 进程），
Station 侧无需改动。

注意：真实分布式需要「状态可序列化 + 消息总线 + 进程间通信」，属架构级改动，
当前仅预留接口，不实现（单机 asyncio 足够时避免过度工程）。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class StationWorker(Protocol):
    async def process(self, station, passenger) -> None:
        """执行单个站点的乘客处理（产出 + 质检 + 放行/回环）"""
        ...


class LocalStationWorker:
    """进程内 worker：直接委托 station.process_passenger"""

    async def process(self, station, passenger) -> None:
        await station.process_passenger(passenger)
