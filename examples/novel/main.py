"""小说创作示例入口 —— 用 MetroEngine 跑通六线地铁网络

用法：
  LLM_PROVIDER=mock python examples/novel/main.py        # 零成本验证
  LLM_PROVIDER=deepseek python examples/novel/main.py    # 真实 LLM
"""

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
from examples.novel.agents import register_all
from examples.novel.bootstrapper import NovelBootstrapper


async def main():
    here = Path(__file__).resolve().parent
    provider = os.getenv("LLM_PROVIDER", "mock")

    config = EngineConfig(
        network=load_yaml(str(here / "network.yaml")),
        profiles=load_yaml(str(here / "profiles.yaml")),
        llm=LLMConfig(
            provider=provider,
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", ""),
        ),
        judge=JudgeConfig(enabled=True),  # judge 复用主 provider；mock 下走启发式
        state_db=str(here / "novel_state.db"),
        skill_db=str(here / "novel_skills.db"),
    )

    register_all()
    engine = MetroEngine(config=config, bootstrapper=NovelBootstrapper())
    await engine.build_network()

    # 崩溃恢复：恢复上次未完成的乘客
    recovered = await engine.recover()

    print("=" * 70)
    print("🚇 ASMAN 通用地铁多Agent引擎 · 小说创作示例")
    print(f"   Provider: {provider}")
    if recovered:
        print(f"   🔄 已恢复 {recovered} 个未完成乘客")
    print("=" * 70)

    user_input = "帮我做一本能火的小说，要有视频"
    task_id = await engine.run(user_input)
    print(f"✅ 任务已创建: {task_id}")

    prev_progress = -1
    stable_count = 0
    max_wait = 120
    waited = 0

    while waited < max_wait:
        progress = await engine.get_progress(task_id)
        if "error" in progress:
            print("错误:", progress["error"])
            break

        current = progress["progress_percent"]
        if current != prev_progress:
            bar = "█" * int(current / 5) + "░" * (20 - int(current / 5))
            print(f"   [{bar}] {current:.1f}% | 站点: {progress['current_station']:<12} | "
                  f"状态: {progress['status']}")
            prev_progress = current

        if progress.get("is_converged") or progress["status"] == "completed":
            stable_count += 1
            if stable_count >= 3:
                print("\n🎉 任务收敛完成")
                print(f"   完成站点: {progress['completed_stops']}")
                print(f"   修正次数: {progress['fix_count']}")
                print(f"   质量评分: {progress['quality_scores']}")
                summary = engine.get_hermes_summary()
                if summary:
                    print(f"   LLM调用: {summary.get('total_executions', 0)}次 | "
                          f"成本: ${summary.get('total_cost_usd', 0):.4f}")
                metrics = engine.get_metrics()
                print(f"   指标: {metrics.get('counters', {})}")
                break
        else:
            stable_count = 0

        await asyncio.sleep(1)
        waited += 1

    if waited >= max_wait:
        print("\n⏱️ 达到最大等待时间")

    await engine.shutdown()
    print("系统已关闭")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断")
        sys.exit(0)
