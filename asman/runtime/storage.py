"""内容存储层：把产物从 SQLite baggage 落地到文件系统 / 对象存储

解决「内容只存 SQLite」的隐患：
- 大内容不再塞进数据库，落地成文件
- 支持导出、查看、跨任务复用
- 未来可扩展 S3/OSS 等对象存储（实现 ArtifactStore 接口即可）
"""

import json
from pathlib import Path
from typing import Any, Dict, List


class ArtifactStore:
    """产物存储抽象接口（本地文件 / 对象存储 都实现它）"""

    def save(self, task_id: str, key: str, content: Any) -> Dict:
        """保存产物，返回 {name, path, size} 元信息"""
        raise NotImplementedError

    def list_artifacts(self, task_id: str) -> List[Dict]:
        """列出某任务的所有产物"""
        raise NotImplementedError

    def load(self, ref: str) -> Any:
        raise NotImplementedError


class LocalFileStore(ArtifactStore):
    """本地文件存储：artifacts/{task_id}/{key}.{ext}

    字符串内容 → .md；结构化内容 → .json（保真）。
    """

    def __init__(self, base_dir: str = "artifacts"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_key(key: str) -> str:
        return key.replace("/", "_").replace("\\", "_").replace(":", "_")

    def save(self, task_id: str, key: str, content: Any) -> Dict:
        task_dir = self.base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        safe_key = self._safe_key(key)

        if isinstance(content, str):
            path = task_dir / f"{safe_key}.md"
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            path = task_dir / f"{safe_key}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2, default=str)

        return {"name": path.name, "path": str(path), "size": path.stat().st_size}

    def list_artifacts(self, task_id: str) -> List[Dict]:
        task_dir = self.base_dir / task_id
        if not task_dir.exists():
            return []
        result = []
        for p in sorted(task_dir.iterdir()):
            if p.is_file():
                result.append({"name": p.name, "path": str(p), "size": p.stat().st_size})
        return result

    def load(self, ref: str) -> Any:
        p = Path(ref)
        if p.suffix == ".json":
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
