"""ASMAN Worker 入口 —— 水平扩展的独立进程

水平扩展模型：多个 worker 副本（web + 引擎一体）通过共享 PostgreSQL（DSN）
实现状态共享，由负载均衡器（K8s Service / Nginx）分发请求。

每个副本：
- 独立跑完整引擎（MetroEngine + 后台任务循环）
- 通过 DSN 共享 passenger/event/state 数据
- 无本地状态依赖（除 artifacts 目录，多副本建议换对象存储）

未来若需「真正的任务队列分布式」，在已预留的 TaskQueue / StationWorker
抽象上接 Redis/Celery 即可，引擎侧无需改动。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    import uvicorn
    from web_server import app  # web + 引擎一体

    port = int(os.getenv("PORT", "8000"))
    dsn = os.getenv("DSN", "")
    print("=" * 60)
    print("🚇 ASMAN Worker 启动")
    print(f"   端口: {port}")
    print(f"   数据库: {'PostgreSQL ' + dsn.split('@')[0] if dsn else 'SQLite（单机）'}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
