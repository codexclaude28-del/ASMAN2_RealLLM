"""兼容入口：委托给 examples/novel/main.py

保留此文件是为了向后兼容旧的 `python main_fusion.py` 启动方式。
推荐直接使用：`python examples/novel/main.py`
"""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from examples.novel.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断")
        sys.exit(0)
