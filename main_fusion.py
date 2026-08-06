"""ASMAN 2.0 + 真实LLM 演示"""

import asyncio
import sys
import os

# Windows UTF-8 编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 加载 .env
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asman2.engine import AutonomousNovelEngine


async def main():
    # 读取LLM配置
    provider = os.getenv("LLM_PROVIDER", "mock")
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")

    print("=" * 70)
    print("🚇 ASMAN 2.0 + 🤖 真实LLM 融合架构")
    print("=" * 70)

    if provider == "mock":
        print("\n⚠️  当前使用 MOCK 模式（模拟执行）")
        print("   要启用真实LLM，请设置环境变量:")
        print("   export LLM_PROVIDER=openai")
        print("   export LLM_API_KEY=sk-your-key")
        print("   或使用: cp .env.example .env 并编辑\n")
    else:
        print(f"\n✅ LLM Provider: {provider}")
        if api_key:
            masked_key = api_key[:8] + "..." + api_key[-4:]
            print(f"   API Key: {masked_key}")
        else:
            print("   ⚠️  API Key 未设置，将使用mock模式")
            provider = "mock"

    # 创建引擎
    engine = AutonomousNovelEngine(
        llm_provider=provider,
        api_key=api_key,
        base_url=base_url
    )
    await engine.build_network()

    user_input = "帮我做一本能火的小说，要有视频"
    print(f"\n🎫 用户输入: \"{user_input}\"")
    print("   [ASMAN] 自治推断参数 → 规划6线行程 → 创建乘客")
    print("   [LLM]   每个站点 = Profile Worker → 真实API调用 → 验证")

    task_id = await engine.run(user_input)
    print(f"\n✅ 任务已创建: {task_id}")
    print("   地铁网络已启动...")

    prev_progress = -1
    stable_count = 0
    max_wait = 600
    waited = 0

    while waited < max_wait:
        progress = await engine.get_progress(task_id)

        if "error" in progress:
            print("错误:", progress["error"])
            break

        current = progress["progress_percent"]
        status = progress["status"]

        if current != prev_progress:
            bar = "█" * int(current / 5) + "░" * (20 - int(current / 5))
            skill_info = progress.get("skill_stats", {})
            hermes_info = progress.get("hermes_workers", {})
            total_hermes = sum(v.get("executions", 0) for v in hermes_info.values())
            total_cost = sum(v.get("cost", 0) for v in hermes_info.values())
            print(f"   [{bar}] {current:.1f}% | 站点: {progress['current_station']:<12} | 状态: {status}")
            print(f"         Skill库: {skill_info.get('total_skills', 0)}个 | Hermes调用: {total_hermes}次 | 成本: ${total_cost:.4f}")
            prev_progress = current

        if progress.get("is_converged") or status == "completed":
            stable_count += 1
            if stable_count >= 3:
                print(f"\n🎉 任务已收敛完成！")
                final = await engine.get_progress(task_id)
                print(f"   质量评分: {final.get('quality_scores', {})}")
                print(f"   修正次数: {final['fix_count']}")
                print(f"   Skill统计: {final.get('skill_stats', {})}")

                hermes_summary = engine.get_hermes_summary()
                if hermes_summary:
                    print(f"\n📊 LLM执行摘要:")
                    print(f"   总调用: {hermes_summary.get('total_executions', 0)}次")
                    print(f"   通过率: {hermes_summary.get('pass_rate', 0):.1%}")
                    print(f"   平均耗时: {hermes_summary.get('avg_duration_ms', 0):.0f}ms")
                    print(f"   总成本: ${hermes_summary.get('total_cost_usd', 0):.4f}")
                    print(f"   高频Skill: {hermes_summary.get('top_skills', [])[:3]}")
                break
        else:
            stable_count = 0

        await asyncio.sleep(1)
        waited += 1

    if waited >= max_wait:
        print("\n⏱️ 达到最大等待时间")

    await engine.shutdown()
    print("\n系统已关闭")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断")
        sys.exit(0)
