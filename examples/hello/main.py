"""最小示例入口：文本处理流水线（mock 模式跑通）"""

import asyncio
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from asman.engine import MetroEngine
from asman.runtime.config import EngineConfig, LLMConfig, JudgeConfig, load_yaml
from examples.hello.agents import register_all
from asman.core.bootstrapper import DefaultBootstrapper


async def main():
    here = Path(__file__).resolve().parent
    config = EngineConfig(
        network=load_yaml(str(here / "network.yaml")),
        profiles=load_yaml(str(here / "profiles.yaml")),
        llm=LLMConfig(provider=os.getenv("LLM_PROVIDER", "mock")),
        judge=JudgeConfig(enabled=True),
        state_db=str(here / "hello_state.db"),
        skill_db=str(here / "hello_skills.db"),
    )
    register_all()
    engine = MetroEngine(config=config, bootstrapper=DefaultBootstrapper())
    await engine.build_network()

    task_id = await engine.run("把复杂任务建模成地铁系统")
    print(f"任务 {task_id} 已创建，等待完成...")

    for _ in range(60):
        progress = await engine.get_progress(task_id)
        if progress["status"] == "completed":
            break
        await asyncio.sleep(0.5)

    passenger = engine.occ.get_passenger(task_id)
    print(f"状态: {passenger.status.value}")
    print(f"完成站点: {passenger.completed_stops}")
    print(f"产物: {list(passenger.baggage.keys())}")
    # 事件轨迹（事件溯源）
    events = engine.get_events(task_id)
    print(f"事件轨迹({len(events)}条): {[e['event_type'] for e in reversed(events)]}")
    await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
