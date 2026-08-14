# ASMAN —— 通用地铁多Agent引擎

把复杂的多Agent编排任务建模成一套**地铁系统**：

| 地铁概念 | 引擎抽象 |
|---------|---------|
| 乘客 | 任务（Passenger），携带行李（baggage，中间产物） |
| 线路 | 工作流管道（Line） |
| 站点 | 处理单元（Station），绑定一个 Agent + 一个 Profile |
| 列车 | 调度单元（Train） |
| 换乘枢纽 | 线路间衔接（Hub） |
| 安检门 | 质量门控（QualityGate + LLM-as-Judge） |
| 环线 | 回环修正（Backloop，下游不达标坐回上游重做） |
| 切片站 | Map-Reduce 并行（1 主乘客 → N 子乘客 → 重组） |

引擎**与业务无关**：网络拓扑、Agent、Profile 全部通过配置与注册表注入。`examples/novel/` 是一份完整的参考实现（小说 → 剧本 → 视频 → 多平台发布）。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 零成本跑通示例（mock 模式，不调用真实 LLM）
LLM_PROVIDER=mock python examples/novel/main.py

# 3. 用真实 LLM（配置 .env）
cp .env.example .env   # 填 LLM_PROVIDER / LLM_API_KEY
python examples/novel/main.py

# 4. 启动 Web 界面（FastAPI + WebSocket + 静态前端）
python web_server.py   # http://localhost:8000
```

Web API：`/api/tasks`（创建/查询任务）、`/api/tasks/{id}/output`（产物）、`/api/metrics`（运行时指标）、`/api/health`、`/docs`（Swagger）。

---

## 如何定义一条新流水线

只需 3 个文件 + 1 个入口，**不动引擎代码**：

### 1. 写 Agent（`my_agents.py`）

```python
from asman.agents.base import Agent
from asman.registry import register_agent

class SummarizeAgent(Agent):
    def __init__(self):
        super().__init__("摘要", "summarize")

    async def execute(self, input_data, passenger_id):
        text = input_data.get("text", "")
        return {"summary": text[:100]}

def register_all():
    register_agent("summarize", SummarizeAgent)
```

### 2. 写拓扑（`network.yaml`）

```yaml
name: my_pipeline
lines:
  - id: L1
    name: 处理线
    stations:
      - {id: S1, agent: summarize}
      - {id: S1_SLICE, agent: my_slicer, slice: true, reassemble_hub: H1}
      - {id: H1, is_hub: true}
itinerary:
  - {line: L1, board: S1, alight: [S1, S1_SLICE, H1], transfer: H1}
```

关键字段：`agent`（注册名）、`slice: true`（切片站，Agent 需实现 `slice`/`merge`）、`reassemble_hub`（切片重组 Hub）、`is_hub`（换乘枢纽）、`backloop_target`（质检失败回环的上游站，默认同线前一个站）。

### 3. 写 Profile（`profiles.yaml`）

```yaml
S1:
  name: summarize_profile
  system_prompt: "把输入压缩成 100 字摘要，只输出摘要。"
  model: ""              # 空串 = 用 provider 默认模型
  temperature: 0.3
  max_tokens: 500
```

### 4. 启动

```python
from asman.engine import MetroEngine
from asman.runtime.config import EngineConfig, LLMConfig, JudgeConfig, load_yaml
from my_agents import register_all
from asman.core.bootstrapper import DefaultBootstrapper

config = EngineConfig(
    network=load_yaml("network.yaml"),
    profiles=load_yaml("profiles.yaml"),
    llm=LLMConfig(provider="mock"),
    judge=JudgeConfig(enabled=True),
)
register_all()
engine = MetroEngine(config=config, bootstrapper=DefaultBootstrapper())
await engine.build_network()
task_id = await engine.run("你的输入")
```

**自举器（可选）**：实现 `Bootstrapper` 协议，把模糊输入转成 `TaskConfig`（业务参数放 `config.params`），引擎在 `run()` 时调用它——不追问用户、自治推断。

---

## 配置参考

### `EngineConfig`（引擎级）

| 字段 | 说明 |
|------|------|
| `network` | 拓扑配置 dict（来自 network.yaml） |
| `profiles` | Profile 配置 dict（来自 profiles.yaml） |
| `llm` | 主 LLM（provider/api_key/base_url/default_model） |
| `judge` | 评判 LLM（enabled/provider/model/temperature/threshold） |
| `state_db` / `skill_db` | SQLite 路径 |

### `JudgeConfig`（LLM-as-Judge）

独立于生成模型的质检。`enabled=true` 时用独立 `LLMClient`（`provider` 留空则复用主 LLM）对每个站点产出做五维评分（coherence/creativity/consistency/grammar/engagement），`threshold` 为通过线。mock/调用失败时降级启发式评分，保证流程不阻塞。

---

## 架构

```
asman/
├── core/        models / network(配置驱动) / backloop / convergence
│                self_healing / bootstrapper(注入式) / quality_gate
├── judge/       LLM-as-Judge（独立模型结构化评分）
├── bridge/      Hermes 桥接（站点 → Profile Worker）
├── llm/         LLMClient（openai/deepseek/claude/ollama/mock + 重试退避 + 熔断）
├── loop/        ThreeTierLoop（L1调度/L2质检回环/L3收敛交付）
├── nudge/       后台复盘（瓶颈/弱Skill/回环模式）
├── state/       SQLite 持久化（WAL + 持久连接 + 崩溃恢复）
├── skill/       Skill 库（FTS5）+ GEPA 提示词进化
├── verifier/    MoA 多评判聚合（去最高最低取中位数）
├── runtime/     config / logging(trace) / metrics
├── registry.py  Agent / Profile 注册表
└── engine.py    MetroEngine（主引擎）
```

**核心机制**：站点出站 = LLM 生成 → LLM-as-Judge 评分 → 达标放行 / 未达标重试(≤max_retry) / 重试耗尽坐回环线到 `backloop_target`。收敛需满足六条件：子乘客重组完、质检全过、回环收敛、产物齐全、无挂起重试、**行程走完**。

---

## 测试

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

覆盖：核心模型、拓扑配置解析、注册表、Judge 评分、收敛、回环、mock 全流程集成。

---

## 目录结构

```
asman/           通用引擎包（零业务代码）
examples/novel/  小说创作参考实现（agents/profiles.yaml/network.yaml/bootstrapper/main）
tests/           pytest
web_server.py    FastAPI 入口（挂载 novel 示例）
main_fusion.py   兼容入口（委托 examples/novel/main.py）
```
