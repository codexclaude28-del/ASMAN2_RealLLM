"""运行时配置：引擎级配置 + YAML 加载"""

from typing import Any, Dict
import yaml
from pydantic import BaseModel, Field


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


class LLMConfig(BaseModel):
    provider: str = "mock"
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""


class JudgeConfig(BaseModel):
    enabled: bool = True
    provider: str = ""          # 空 → 复用主 LLM 配置
    api_key: str = ""
    base_url: str = ""
    model: str = ""             # 空 → 用 provider 默认
    temperature: float = 0.2    # judge 用低温，输出更稳定
    threshold: float = 0.85     # 质检通过阈值
    max_tokens: int = 500


class EngineConfig(BaseModel):
    network: Dict[str, Any] = Field(default_factory=dict)
    profiles: Dict[str, Any] = Field(default_factory=dict)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    state_db: str = "asman_state.db"
    skill_db: str = "asman_skills.db"
    dsn: str = ""                 # PostgreSQL DSN（postgres://...），空则用 SQLite
    worker_concurrency: int = 5   # 站点处理并发度
    worker_mode: str = "local"    # local | distributed（distributed 预留，未实现）
    artifact_dir: str = "artifacts"  # 产物落地目录（内容存储层）
    max_concurrent_tasks: int = 3  # 任务并发度（任务队列）
