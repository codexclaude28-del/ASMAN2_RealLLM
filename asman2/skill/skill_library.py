"""ASMAN 2.0 Skill Library - Hermes风格Skill持久化与检索"""

import sqlite3
import json
import time
import hashlib
from typing import Dict, Any, List, Optional, Tuple


class SkillLibrary:
    """
    Skill库：存储可复用的成功模式
    每个Skill包含：capability(能力类型)、profile(风格画像)、
    prompt_template(优化后的prompt)、success_rate(成功率)、
    usage_count(使用次数)、evolution_history(进化历史)
    """

    def __init__(self, db_path: str = "asman_skills.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS skill_fts USING fts5(skill_id, capability, profile, description, prompt_template, tags)")
        cursor.execute("CREATE TABLE IF NOT EXISTS skills (skill_id TEXT PRIMARY KEY, capability TEXT, profile TEXT, description TEXT, prompt_template TEXT, success_rate REAL, usage_count INTEGER, avg_score REAL, created_at REAL, last_used REAL, version INTEGER, parent_skill_id TEXT, evolution_notes TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS skill_evolution (evolution_id TEXT PRIMARY KEY, skill_id TEXT, old_prompt TEXT, new_prompt TEXT, improvement_score REAL, trigger_task TEXT, timestamp REAL)")
        conn.commit()
        conn.close()

    def store_skill(self, capability: str, profile: str, description: str,
                    prompt_template: str, tags: List[str],
                    success_rate: float = 0.0, avg_score: float = 0.0) -> str:
        """存储新Skill"""
        skill_id = f"sk_{capability}_{profile}_{int(time.time())}"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO skills (skill_id, capability, profile, description, prompt_template, success_rate, usage_count, avg_score, created_at, last_used, version, parent_skill_id, evolution_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (skill_id, capability, profile, description, prompt_template, success_rate, 0, avg_score, time.time(), time.time(), 1, "", ""))
        cursor.execute("INSERT INTO skill_fts (skill_id, capability, profile, description, prompt_template, tags) VALUES (?, ?, ?, ?, ?, ?)",
                     (skill_id, capability, profile, description, prompt_template, " ".join(tags)))
        conn.commit()
        conn.close()
        return skill_id

    def find_best_skill(self, capability: str, profile: str,
                        context: Dict = None) -> Optional[Dict]:
        """
        查找最优Skill：先精确匹配capability+profile，
        再用FTS5全文检索近似匹配
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # 精确匹配
        cursor.execute("SELECT skill_id, prompt_template, success_rate, usage_count, avg_score FROM skills WHERE capability = ? AND profile = ? ORDER BY success_rate DESC, avg_score DESC LIMIT 1", (capability, profile))
        row = cursor.fetchone()
        if row:
            conn.close()
            return {"skill_id": row[0], "prompt_template": row[1], "success_rate": row[2], "usage_count": row[3], "avg_score": row[4]}
        # FTS5近似匹配
        query = f"{capability} {profile}"
        cursor.execute("SELECT s.skill_id, s.prompt_template, s.success_rate, s.usage_count, s.avg_score FROM skill_fts fts JOIN skills s ON fts.skill_id = s.skill_id WHERE skill_fts MATCH ? ORDER BY rank LIMIT 1", (query,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"skill_id": row[0], "prompt_template": row[1], "success_rate": row[2], "usage_count": row[3], "avg_score": row[4]}
        return None

    def record_usage(self, skill_id: str, success: bool, score: float):
        """记录Skill使用结果，更新成功率"""
        conn = sqlite3.connect(self.db_path)
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
        conn.close()

    def extract_skill_from_success(self, capability: str, profile: str,
                                   prompt: str, output: Any, score: float) -> str:
        """
        从成功执行中提取Skill：
        当QualityGate以高分通过时，自动将prompt+context存入Skill库
        """
        if score < 0.9:
            return ""
        description = f"Auto-extracted skill for {capability}/{profile} with score {score:.2f}"
        tags = [capability, profile, "auto-extracted", f"score_{int(score*10)}"]
        skill_id = self.store_skill(capability, profile, description, prompt, tags, success_rate=1.0, avg_score=score)
        return skill_id

    def get_skill_stats(self) -> Dict:
        """获取Skill库统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), AVG(success_rate), AVG(avg_score) FROM skills")
        row = cursor.fetchone()
        conn.close()
        return {"total_skills": row[0], "avg_success_rate": row[1], "avg_score": row[2]}