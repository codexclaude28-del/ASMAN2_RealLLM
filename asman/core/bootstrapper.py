"""Bootstrapper：自举协议（注入式）

业务方实现 bootstrap(user_input) -> TaskConfig，
把模糊的用户输入转化为完整的任务配置。
引擎在 run() 时调用注入的 bootstrapper。
"""

from typing import Protocol, runtime_checkable
from .models import TaskConfig


@runtime_checkable
class Bootstrapper(Protocol):
    async def bootstrap(self, user_input: str) -> TaskConfig: ...


class DefaultBootstrapper:
    """默认兜底：不推断业务参数，仅透传输入"""

    async def bootstrap(self, user_input: str) -> TaskConfig:
        return TaskConfig(user_input=user_input)
