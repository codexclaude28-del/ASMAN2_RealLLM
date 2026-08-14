"""pytest fixtures：mock 引擎 + novel 示例配置"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from asman.runtime.config import EngineConfig, LLMConfig, JudgeConfig, load_yaml
from asman.engine import MetroEngine
from examples.novel.agents import register_all
from examples.novel.bootstrapper import NovelBootstrapper

NOVEL_DIR = ROOT / "examples" / "novel"


@pytest.fixture
def novel_config(tmp_path):
    return EngineConfig(
        network=load_yaml(str(NOVEL_DIR / "network.yaml")),
        profiles=load_yaml(str(NOVEL_DIR / "profiles.yaml")),
        llm=LLMConfig(provider="mock"),
        judge=JudgeConfig(enabled=True),
        state_db=str(tmp_path / "state.db"),
        skill_db=str(tmp_path / "skills.db"),
    )


@pytest.fixture
def engine(novel_config):
    register_all()
    return MetroEngine(config=novel_config, bootstrapper=NovelBootstrapper())
