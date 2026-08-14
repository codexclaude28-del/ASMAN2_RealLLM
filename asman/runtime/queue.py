"""任务队列：控制并发任务数 + 预留分布式队列接口

平台化 P0：当前用进程内 LocalTaskQueue（asyncio.Queue + 信号量控并发）。
未来若需跨进程/跨机任务调度，实现 Redis/Celery 版 TaskQueue，引擎侧无需改动。
"""

import asyncio
from typing import Awaitable, Callable


class TaskQueue:
    """任务队列抽象接口"""

    async def submit(self, coro_factory: Callable[[], Awaitable]):
        raise NotImplementedError

    async def start(self):
        raise NotImplementedError

    async def stop(self):
        raise NotImplementedError


class LocalTaskQueue(TaskQueue):
    """进程内任务队列：asyncio.Queue + 信号量控制并发度"""

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._queue = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._worker = None

    async def submit(self, coro_factory):
        await self._queue.put(coro_factory)

    async def start(self):
        self._running = True
        self._worker = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            try:
                coro_factory = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            asyncio.create_task(self._run(coro_factory))

    async def _run(self, coro_factory):
        async with self._semaphore:
            try:
                await coro_factory()
            except Exception:
                pass

    async def stop(self):
        self._running = False
        if self._worker:
            self._worker.cancel()
