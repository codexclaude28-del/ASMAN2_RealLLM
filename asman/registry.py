"""Agent / Profile 全局注册表

业务方通过 register_agent / register_profile 注入实现，
引擎通过名字查找，实现业务与引擎解耦。
"""

from typing import Dict, Callable, Optional, Any

_AGENTS: Dict[str, Callable] = {}
_PROFILES: Dict[str, Any] = {}


def register_agent(name: str, factory: Callable) -> None:
    """注册 Agent 工厂（零参 callable，返回 Agent 实例）"""
    _AGENTS[name] = factory


def get_agent(name: str) -> Optional[Callable]:
    return _AGENTS.get(name)


def create_agent(name: str):
    """创建 Agent 实例；未注册返回 None"""
    factory = _AGENTS.get(name)
    return factory() if factory else None


def register_profile(name: str, profile: Any) -> None:
    _PROFILES[name] = profile


def get_profile(name: str) -> Optional[Any]:
    return _PROFILES.get(name)


def clear_all() -> None:
    """清空注册表（测试用）"""
    _AGENTS.clear()
    _PROFILES.clear()
