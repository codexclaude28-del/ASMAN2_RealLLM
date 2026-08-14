"""注册表单元测试"""

from asman.registry import register_agent, create_agent, get_agent, register_profile, get_profile, clear_all
from asman.agents.base import Agent


def test_agent_registry():
    clear_all()
    factory = lambda: Agent("dummy", "dummy")
    register_agent("dummy", factory)
    assert get_agent("dummy") is factory
    inst = create_agent("dummy")
    assert isinstance(inst, Agent)
    assert create_agent("missing") is None


def test_profile_registry():
    clear_all()
    profile = {"name": "p1", "system_prompt": "hi"}
    register_profile("S1", profile)
    assert get_profile("S1") is profile
    assert get_profile("NOPE") is None
    clear_all()
