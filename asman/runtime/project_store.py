"""项目/组织管理：多租户的数据隔离基础

平台化 P1：项目作为租户边界，任务/拓扑/模型按项目隔离。
"""

import time
from typing import Dict, List

from .db import make_backend, DBBackend


class ProjectStore:
    """项目 CRUD（owner = 归属用户）"""

    def __init__(self, db: DBBackend = None, db_path: str = "asman_projects.db"):
        self.db = db or make_backend(None, db_path)
        self._init_db()

    def _init_db(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS projects ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "name TEXT, owner TEXT, created_at REAL)")

    def create(self, name: str, owner: str) -> bool:
        self.db.execute("INSERT INTO projects (name, owner, created_at) VALUES (?, ?, ?)",
                      (name, owner, time.time()))
        return True

    def list_projects(self, owner: str = None) -> List[Dict]:
        if owner:
            rows = self.db.fetchall("SELECT id, name, owner, created_at FROM projects WHERE owner = ? ORDER BY id", (owner,))
        else:
            rows = self.db.fetchall("SELECT id, name, owner, created_at FROM projects ORDER BY id")
        return [{"id": r[0], "name": r[1], "owner": r[2], "created_at": r[3]} for r in rows]

    def delete(self, project_id: int):
        self.db.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def close(self):
        self.db.close()
