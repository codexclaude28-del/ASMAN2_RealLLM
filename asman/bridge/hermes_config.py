"""Hermes Profile 定义与加载

Profile = 每个站点绑定的一段执行规格（system_prompt / model / temperature / ...）。
由配置文件（dict / YAML）加载，而非硬编码。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class HermesProfile:
    name: str
    system_prompt: str
    model: str = ""          # 空串 → 用 LLMClient 的 provider 默认模型
    temperature: float = 0.7
    max_tokens: int = 2000
    skills: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    role: str = ""           # CrewAI 式角色卡：role / goal / backstory
    goal: str = ""
    backstory: str = ""


def profile_from_dict(name: str, data: Dict[str, Any]) -> HermesProfile:
    return HermesProfile(
        name=data.get("name", name),
        system_prompt=data.get("system_prompt", ""),
        model=data.get("model", ""),
        temperature=data.get("temperature", 0.7),
        max_tokens=data.get("max_tokens", 2000),
        skills=data.get("skills", []),
        constraints=data.get("constraints", []),
        role=data.get("role", ""),
        goal=data.get("goal", ""),
        backstory=data.get("backstory", ""),
    )


def load_profiles(config: Dict[str, Any]) -> Dict[str, HermesProfile]:
    """从 dict 加载全部 Profile：{station_id: {name, system_prompt, ...}}"""
    profiles = {}
    for station_id, data in config.items():
        profiles[station_id] = profile_from_dict(station_id, data)
    return profiles
