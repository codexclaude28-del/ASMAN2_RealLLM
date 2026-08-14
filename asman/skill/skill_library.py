"""ASMAN Skill Library - 成功模式持久化与检索

使用持久连接 + WAL + 线程锁，避免每次操作 connect/close。
"""

import sqlite3
import json
import time
import hashlib
import threading
from typing import Dict, Any, List, Optional, Tuple


class SkillLibrary:
    def __init__(self, db_path: str = "asman_skills.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS skill_fts USING fts5(skill_id, capability, profile, description, prompt_template, tags)")
            cursor.execute("CREATE TABLE IF NOT EXISTS skills (skill_id TEXT PRIMARY KEY, capability TEXT, profile TEXT, description TEXT, prompt_template TEXT, success_rate REAL, usage_count INTEGER, avg_score REAL, created_at REAL, last_used REAL, version INTEGER, parent_skill_id TEXT, evolution_notes TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS skill_evolution (evolution_id TEXT PRIMARY KEY, skill_id TEXT, old_prompt TEXT, new_prompt TEXT, improvement_score REAL, trigger_task TEXT, timestamp REAL)")
            conn.commit()

    def store_skill(self, capability: str, profile: str, description: str,
                    prompt_template: str, tags: List[str],
                    success_rate: float = 0.0, avg_score: float = 0.0) -> str:
        skill_id = f"sk_{capability}_{profile}_{int(time.time())}"
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO skills (skill_id, capability, profile, description, prompt_template, success_rate, usage_count, avg_score, created_at, last_used, version, parent_skill_id, evolution_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (skill_id, capability, profile, description, prompt_template, success_rate, 0, avg_score, time.time(), time.time(), 1, "", ""))
            cursor.execute("INSERT INTO skill_fts (skill_id, capability, profile, description, prompt_template, tags) VALUES (?, ?, ?, ?, ?, ?)",
                         (skill_id, capability, profile, description, prompt_template, " ".join(tags)))
            conn.commit()
        return skill_id

    def find_best_skill(self, capability: str, profile: str,
                        context: Dict = None) -> Optional[Dict]:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT skill_id, prompt_template, success_rate, usage_count, avg_score FROM skills WHERE capability = ? AND profile = ? ORDER BY success_rate DESC, avg_score DESC LIMIT 1", (capability, profile))
            row = cursor.fetchone()
            if row:
                return {"skill_id": row[0], "prompt_template": row[1], "success_rate": row[2], "usage_count": row[3], "avg_score": row[4]}
            query = f"{capability} {profile}"
            cursor.execute("SELECT s.skill_id, s.prompt_template, s.success_rate, s.usage_count, s.avg_score FROM skill_fts fts JOIN skills s ON fts.skill_id = s.skill_id WHERE skill_fts MATCH ? ORDER BY rank LIMIT 1", (query,))
            row = cursor.fetchone()
        if row:
            return {"skill_id": row[0], "prompt_template": row[1], "success_rate": row[2], "usage_count": row[3], "avg_score": row[4]}
        return None

    def record_usage(self, skill_id: str, success: bool, score: float):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT usage_count, success_rate, avg_score FROM skills WHERE skill_id = ?", (skill_id,))
            row = cursor.fetchone()
            if row:
                old_count, old_rate, old_score = row
                new_count = old_count + 1
                new_rate = (old_rate * old_count + (1.0 if success else 0.0)) / new_count
                new_score = (old_score * old_count + score) / new_count
                cursor.execute("UPDATE skills SET usage_count = ?, success_rate = ?, avg_score = ?, last_used = ? WHERE skill_id = ?",
                             (new_count, new_rate, new_score, time.time(), skill_id))
            conn.commit()

    def extract_skill_from_success(self, capability: str, profile: str,
                                   prompt: str, output: Any, score: float) -> str:
        if score < 0.9:
            return ""
        description = f"Auto-extracted skill for {capability}/{profile} with score {score:.2f}"
        tags = [capability, profile, "auto-extracted", f"score_{int(score*10)}"]
        skill_id = self.store_skill(capability, profile, description, prompt, tags, success_rate=1.0, avg_score=score)
        return skill_id

    def get_skill_stats(self) -> Dict:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), AVG(success_rate), AVG(avg_score) FROM skills")
            row = cursor.fetchone()
        return {"total_skills": row[0], "avg_success_rate": row[1], "avg_score": row[2]}

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
