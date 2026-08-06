# ASMAN 2.0 - 自治地铁多Agent网络（真实LLM版）

## 架构

```
┌─────────────────────────────────────────┐
│  ASMAN 2.0 拓扑编排层                    │
│  地铁网络 → 切片并行 → 回环修正 → 终态收敛 │
├─────────────────────────────────────────┤
│  bridge/hermes_bridge.py (桥接层)       │
│  每个站点任务 → 路由到 LLM Profile Worker │
├─────────────────────────────────────────┤
│  llm/client.py (真实LLM执行层)           │
│  OpenAI / Claude / Ollama / Mock        │
└─────────────────────────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置LLM

**方式A：环境变量**
```bash
export LLM_PROVIDER=openai
export LLM_API_KEY=sk-your-openai-api-key
```

**方式B：.env文件**
```bash
cp .env.example .env
# 编辑 .env 填入你的API Key
```

### 3. 运行

```bash
python main_fusion.py
```

## 支持的LLM Provider

| Provider | 模型示例 | 说明 |
|---------|---------|------|
| `openai` | gpt-4o, gpt-4o-mini | 推荐，效果最佳 |
| `claude` | claude-3-sonnet, claude-3-opus | Anthropic |
| `ollama` | qwen2.5:14b, llama3.1:8b | 本地模型，零成本 |
| `mock` | - | 模拟模式，用于测试 |

## 成本估算

一本20章小说（约6万字）的完整流程：

| 站点 | 调用次数 | 单次token | 预估成本 |
|-----|---------|----------|---------|
| S1-S2 (灵感) | 2 | 2K | $0.01 |
| R1-R3 (参考) | 3 | 4K | $0.03 |
| W1 (大纲) | 1 | 8K | $0.04 |
| W2_SLICE (切片) | 1 | 2K | $0.01 |
| W3 (写作×20章) | 20 | 4K×20 | $1.20 |
| W4 (润色×20章) | 20 | 4K×20 | $1.20 |
| P1-P3 (发布) | 3 | 2K | $0.02 |
| D1-D3 (剧本) | 3 | 4K | $0.04 |
| V1-V4 (视频) | 4 | 2K | $0.02 |
| **总计** | **57次** | **~120K tokens** | **~$2.57** |

使用 gpt-4o-mini 可降至 **~$0.30**

## 项目结构

```
asman2/
├── core/              # 核心模型、自举器、质检门、回环、自愈、收敛
├── agents/            # Agent基类 + 小说创作Agent
├── stations/           # 站点基类 + 切片站（集成Hermes Bridge）
├── lines/             # 线路动态路由
├── state/             # SQLite持久化 + Ralph日志
├── skill/             # Skill库 + GEPA进化
├── verifier/          # 独立Verifier + MoA聚合
├── loop/              # Loop契约 + 三层循环
├── profile/           # Profile隔离
├── nudge/             # 复盘引擎
├── bridge/            # Hermes桥接层
│   ├── hermes_config.py    # 18个Profile定义
│   ├── hermes_worker.py    # Profile Worker（真实LLM）
│   └── hermes_bridge.py    # 桥接器核心
├── llm/               # 真实LLM客户端
│   └── client.py      # OpenAI/Claude/Ollama统一接口
├── network.py         # 六线网络拓扑
└── engine.py          # 融合主引擎
```

## 关键设计

- **拓扑编排**：ASMAN地铁网络负责多Agent并行、切片、回环
- **真实执行**：llm/client.py统一调用OpenAI/Claude/Ollama API
- **成本追踪**：每次LLM调用记录token用量和美元成本
- **降级机制**：LLM调用失败自动降级到mock，不阻塞流程
- **状态持久**：SQLite保存所有乘客状态，支持崩溃恢复
