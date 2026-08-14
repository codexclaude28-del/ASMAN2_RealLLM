"""ASMAN Skill Library - 成功模式持久化与检索

通过 DBBackend 支持 SQLite（默认，FTS5 全文检索）+ PostgreSQL（LIKE 降级）。
"""

import time
from typing import Dict, Any, List, Optional

from ..runtime.db import make_backend, DBBackend, SQLiteBackend


class SkillLibrary:
    def __init__(self, db_path: str = "asman_skills.db", dsn: str = None, db: DBBackend = None):
        self.db = db or make_backend(dsn, db_path)
        self._is_sqlite = isinstance(self.db, SQLiteBackend)
        self._init_db()

    def _init_db(self):
        if self._is_sqlite:
            self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS skill_fts USING fts5(skill_id, capability, profile, description, prompt_template, tags)")
        self.db.execute("CREATE TABLE IF NOT EXISTS skills (skill_id TEXT PRIMARY KEY, capability TEXT, profile TEXT, description TEXT, prompt_template TEXT, success_rate REAL, usage_count INTEGER, avg_score REAL, created_at REAL, last_used REAL, version INTEGER, parent_skill_id TEXT, evolution_notes TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS skill_evolution (evolution_id TEXT PRIMARY KEY, skill_id TEXT, old_prompt TEXT, new_prompt TEXT, improvement_score REAL, trigger_task TEXT, timestamp REAL)")

    def store_skill(self, capability: str, profile: str, description: str,
                    prompt_template: str, tags: List[str],
                    success_rate: float = 0.0, avg_score: float = 0.0) -> str:
        skill_id = f"sk_{capability}_{profile}_{int(time.time())}"
        self.db.execute("INSERT INTO skills (skill_id, capability, profile, description, prompt_template, success_rate, usage_count, avg_score, created_at, last_used, version, parent_skill_id, evolution_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (skill_id, capability, profile, description, prompt_template, success_rate, 0, avg_score, time.time(), time.time(), 1, "", ""))
        if self._is_sqlite:
            self.db.execute("INSERT INTO skill_fts (skill_id, capability, profile, description, prompt_template, tags) VALUES (?, ?, ?, ?, ?, ?)",
                          (skill_id, capability, profile, description, prompt_template, " ".join(tags)))
        return skill_id

    def find_best_skill(self, capability: str, profile: str, context: Dict = None) -> Optional[Dict]:
        # 精确匹配 capability + profile
        row = self.db.fetchone("SELECT skill_id, prompt_template, success_rate, usage_count, avg_score FROM skills WHERE capability = ? AND profile = ? ORDER BY success_rate DESC, avg_score DESC LIMIT 1", (capability, profile))
        if row:
            return {"skill_id": row[0], "prompt_template": row[1], "success_rate": row[2], "usage_count": row[3], "avg_score": row[4]}

        # 近似匹配：SQLite 用 FTS5，PostgreSQL 用 LIKE
        if self._is_sqlite:
            row = self.db.fetchone("SELECT s.skill_id, s.prompt_template, s.success_rate, s.usage_count, s.avg_score FROM skill_fts fts JOIN skills s ON fts.skill_id = s.skill_id WHERE skill_fts MATCH ? ORDER BY rank LIMIT 1", (f"{capability} {profile}",))
        else:
            row = self.db.fetchone("SELECT skill_id, prompt_template, success_rate, usage_count, avg_score FROM skills WHERE capability LIKE ? OR profile LIKE ? ORDER BY success_rate DESC LIMIT 1", (f"%{capability}%", f"%{profile}%"))
        if row:
            return {"skill_id": row[0], "prompt_template": row[1], "success_rate": row[2], "usage_count": row[3], "avg_score": row[4]}
        return None

    def record_usage(self, skill_id: str, success: bool, score: float):
        row = self.db.fetchone("SELECT usage_count, success_rate, avg_score FROM skills WHERE skill_id = ?", (skill_id,))
        if row:
            old_count, old_rate, old_score = row
            new_count = old_count + 1
            new_rate = (old_rate * old_count + (1.0 if success else 0.0)) / new_count
            new_score = (old_score * old_count + score) / new_count
            self.db.execute("UPDATE skills SET usage_count = ?, success_rate = ?, avg_score = ?, last_used = ? WHERE skill_id = ?",
                          (new_count, new_rate, new_score, time.time(), skill_id))

    def extract_skill_from_success(self, capability: str, profile: str,
                                   prompt: str, output: Any, score: float) -> str:
        if score < 0.9:
            return ""
        description = f"Auto-extracted skill for {capability}/{profile} with score {score:.2f}"
        tags = [capability, profile, "auto-extracted", f"score_{int(score*10)}"]
        return self.store_skill(capability, profile, description, prompt, tags, success_rate=1.0, avg_score=score)

    def get_skill_stats(self) -> Dict:
        row = self.db.fetchone("SELECT COUNT(*), AVG(success_rate), AVG(avg_score) FROM skills")
        return {"total_skills": row[0], "avg_success_rate": row[1], "avg_score": row[2]}

    def close(self):
        self.db.close()
