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

## 水平扩展架构（多副本 + 共享数据库）

把「状态」从进程内 SQLite 抽到共享 PostgreSQL，多个无状态副本通过负载均衡分发请求：

```
                    ┌──────────────┐
  请求 ──▶ 负载均衡 ──▶ web 副本 1  │──┐
          (K8s Svc)  ├─▶ web 副本 2  │──┼─▶ PostgreSQL（共享状态）
                     └─▶ web 副本 3  │──┘   （passenger/event/state）
                              │
                     artifacts → 对象存储（S3/OSS）
```

**关键点**：

1. **状态共享**：`EngineConfig.dsn` 设为 `postgres://...`，所有副本读写同一个 PostgreSQL。`StateLayer`/`SkillLibrary` 已通过 `DBBackend` 抽象支持 PostgreSQL（占位符/upsert 自动转换）。
2. **副本无状态**：每个副本独立跑完整引擎（自己的 MetroEngine + 后台循环），靠共享 DB 协调，不依赖本地内存。
3. **负载均衡**：K8s Service / Nginx 把请求分发到副本，副本间互不感知。
4. **产物存储**：`artifacts/` 目录是本地文件，多副本下应换成对象存储（实现 `ArtifactStore` 接口的 S3 版即可）。

## 部署方式

### 方式一：K8s（推荐，生产）

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/web.yaml      # 3 副本 + HPA 自动扩缩容
```

- `web.yaml` 的 Deployment `replicas: 3`，HPA 按 CPU 自动 2~10 副本
- PostgreSQL StatefulSet 持久化 + PVC
- Secret 存 JWT_SECRET / API key（生产务必替换）

### 方式二：Docker Compose（单机多副本）

```bash
docker compose up --scale web=3
```

（`docker-compose.yml` 已含 web + PostgreSQL 16）

### 方式三：裸机多进程

```bash
# 每个进程设相同 DSN，即共享状态
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

1. **SQLite → PostgreSQL**：多副本必须设 `DSN`，否则各副本各写各的本地 SQLite，状态不共享。
2. **产物一致性**：多副本写本地 `artifacts/` 会不一致，应上对象存储。
3. **JWT_SECRET 一致**：所有副本的 `JWT_SECRET` 必须相同（否则 token 跨副本失效）。
4. **并发写冲突**：PostgreSQL 的 upsert（`ON CONFLICT`）已处理并发写，无需额外加锁。
