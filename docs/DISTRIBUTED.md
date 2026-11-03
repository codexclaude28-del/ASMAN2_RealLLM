# ASMAN 分布式 / 水平扩展架构

## 当前架构（单机）

```
┌─────────────────────────────────────────┐
│  web_server（FastAPI + WebSocket）        │
│    └─ MetroEngine（asyncio 后台循环）     │
│         ├─ 线路列车调度（line.run）        │
│         ├─ 三层循环 / 自愈 / 复盘          │
│         └─ 状态 → SQLite（默认）           │
└─────────────────────────────────────────┘
```

单进程 asyncio：所有乘客在同一个事件循环里被调度。适合单机、低并发。

## ⚠️ 当前限制（如实说明）

**当前版本只保证单副本安全。** 虽然 `StateLayer`/`SkillLibrary` 已通过 `DBBackend`
抽象支持 PostgreSQL（`EngineConfig.dsn`），但以下关键调度状态仍在**进程内存**中：

- `OCC.registry`（乘客注册表）、站台等待队列（`Platform.waiting`）
- 列车调度循环（`Line.run`）与三层控制循环（`ThreeTierLoop`）
- 切片追踪（`SliceStation.parent_tracking`）、回环队列（`BackloopChannel.fix_queue`）

因此**多副本直接水平扩展会重复调度**：每个副本各自跑完整引擎循环，共享 DB 里的
乘客会被多个副本同时拾取处理。共享 PostgreSQL 目前只解决「状态持久化/崩溃恢复」，
不构成多副本协调。

**多副本安全运行需要**（属 Roadmap，未实现）：

1. 外部锁或领导者选举（同一时刻只有一个副本跑调度循环），或
2. 把任务分发外置到消息队列（`StationWorker`/`TaskQueue` 抽象已预留扩展点），
   副本只作无状态 worker。

`k8s/web.yaml` 中的多副本/HPA 配置是目标形态，在上述协调机制落地前，
请将副本数固定为 1。

## 水平扩展架构（目标形态：多副本 + 共享数据库 + 外部协调）

把「状态」从进程内 SQLite 抽到共享 PostgreSQL，并引入外部协调（锁/队列）后，
多个无状态副本通过负载均衡分发请求：

```
                    ┌──────────────┐
  请求 ──▶ 负载均衡 ──▶ web 副本 1  │──┐
          (K8s Svc)  ├─▶ web 副本 2  │──┼─▶ PostgreSQL（共享状态）
                     └─▶ web 副本 3  │──┘   （passenger/event/state）
                              │
                     artifacts → 对象存储（S3/OSS）
```

**关键点**（目标形态全部落地后成立，当前仅第 1 条的 DB 抽象可用）：

1. **状态共享**：`EngineConfig.dsn` 设为 `postgres://...`，所有副本读写同一个 PostgreSQL。`StateLayer`/`SkillLibrary` 已通过 `DBBackend` 抽象支持 PostgreSQL（占位符/upsert/建表方言自动转换）。
2. **副本无状态**：每个副本独立跑完整引擎（自己的 MetroEngine + 后台循环），靠共享 DB 协调，不依赖本地内存。
3. **负载均衡**：K8s Service / Nginx 把请求分发到副本，副本间互不感知。
4. **产物存储**：`artifacts/` 目录是本地文件，多副本下应换成对象存储（实现 `ArtifactStore` 接口的 S3 版即可）。

## 部署方式

### 方式一：K8s（推荐，生产）

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/web.yaml      # 目标形态：多副本 + HPA（当前请先把 replicas 改为 1）
```

- `web.yaml` 的 Deployment `replicas: 3` + HPA 是目标形态；多副本协调机制落地前请先固定为 1 副本
- PostgreSQL StatefulSet 持久化 + PVC
- Secret 存 JWT_SECRET / API key（生产务必替换）

### 方式二：Docker Compose（单机）

```bash
docker compose up   # 单副本；--scale web=3 需等多副本协调落地
```

（`docker-compose.yml` 已含 web + PostgreSQL 16）

### 方式三：裸机多进程

```bash
# 每个进程设相同 DSN，即共享持久化状态（注意：调度循环仍会各自运行，见上方限制）
DSN=postgres://user:pass@host:5432/asman PORT=8001 python worker.py &
DSN=postgres://user:pass@host:5432/asman PORT=8002 python worker.py &
# Nginx 反向代理到 8001/8002
```

## 真正的「任务队列分布式」（远期）

上面的水平扩展是「**请求级分布式**」（负载均衡分发请求，各副本独立处理）。

若要「**任务级分布式**」（单个任务拆到多台机器并行，如切片站的子乘客分散到不同 worker），需要消息队列，已在引擎预留扩展点：

| 抽象 | 位置 | 现状 | 扩展方式 |
|---|---|---|---|
| `StationWorker` | `core/worker.py` | `LocalStationWorker`（进程内） | 实现 `QueueStationWorker`（发任务到队列，远程 worker 执行） |
| `TaskQueue` | `runtime/queue.py` | `LocalTaskQueue`（asyncio.Queue） | 实现 `RedisTaskQueue` / `CeleryTaskQueue` |

**任务级分布式要额外解决**：Agent/LLM 客户端可序列化（当前是内存对象）、结果回收、失败重试跨机器。属架构级重构，等有真实规模需求再做。

## 注意事项

1. **多副本重复调度**：见上方「当前限制」——多副本前必须有外部锁/队列，否则副本数保持 1。
2. **SQLite → PostgreSQL**：共享持久化必须设 `DSN`（并安装 `psycopg2-binary`），否则各副本各写各的本地 SQLite。
3. **产物一致性**：多副本写本地 `artifacts/` 会不一致，应上对象存储。
4. **JWT_SECRET 一致**：所有副本的 `JWT_SECRET` 必须相同（否则 token 跨副本失效）。
5. **并发写冲突**：PostgreSQL 的 upsert（`ON CONFLICT`）已处理并发写，无需额外加锁。
