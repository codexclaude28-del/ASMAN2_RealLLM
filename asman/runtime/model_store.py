"""模型接入管理：用户自己配置 LLM 模型，API key 加密存储

平台化 P1：多租户场景下，用户自己接模型 key（Fernet 对称加密），
任务运行时用指定的模型配置。列表接口返回脱敏 key，绝不回传明文。
"""

import base64
import hashlib
import os
import time
from typing import Dict, List, Optional

from cryptography.fernet import Fernet

from .db import make_backend, DBBackend


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


class ModelStore:
    """模型配置存储：name / provider / api_key(加密) / base_url / model"""

    def __init__(self, db: DBBackend = None, db_path: str = "asman_models.db",
                 encryption_secret: str = None):
        self.db = db or make_backend(None, db_path)
        secret = encryption_secret or os.getenv("ENCRYPTION_SECRET", "asman-dev-secret")
        self._fernet = Fernet(_derive_fernet_key(secret))
        self._init_db()

    def _init_db(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS models ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, "
                        "provider TEXT, api_key_enc TEXT, base_url TEXT, "
                        "model TEXT, created_at REAL)")

    def create(self, name: str, provider: str, api_key: str,
               base_url: str = "", model: str = "") -> bool:
        enc = self._fernet.encrypt(api_key.encode()).decode()
        self.db.execute("INSERT INTO models (name, provider, api_key_enc, base_url, model, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                      (name, provider, enc, base_url, model, time.time()))
        return True

    @staticmethod
    def _mask(key: str) -> str:
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def list_models(self) -> List[Dict]:
        """列表（api_key 脱敏，绝不回传明文）"""
        rows = self.db.fetchall("SELECT id, name, provider, api_key_enc, base_url, model FROM models ORDER BY id")
        result = []
        for r in rows:
            try:
                key = self._fernet.decrypt(r[3].encode()).decode()
            except Exception:
                key = ""
            result.append({"id": r[0], "name": r[1], "provider": r[2],
                           "api_key_masked": self._mask(key),
                           "base_url": r[4], "model": r[5]})
        return result

    def get_model(self, model_id: int) -> Optional[Dict]:
        """取单个模型（含解密后的 api_key，仅内部使用）"""
        row = self.db.fetchone("SELECT id, name, provider, api_key_enc, base_url, model FROM models WHERE id = ?", (model_id,))
        if not row:
            return None
        api_key = self._fernet.decrypt(row[3].encode()).decode()
        return {"id": row[0], "name": row[1], "provider": row[2],
                "api_key": api_key, "base_url": row[4], "model": row[5]}

    def delete(self, model_id: int) -> bool:
        self.db.execute("DELETE FROM models WHERE id = ?", (model_id,))
        return True

    def close(self):
        self.db.close()
