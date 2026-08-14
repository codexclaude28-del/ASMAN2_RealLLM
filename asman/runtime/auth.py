"""用户认证 + JWT 令牌

平台化 P0：多用户平台的第一块——用户注册/登录 + JWT 鉴权。
密码用 PBKDF2 哈希（标准库，无额外依赖），令牌用 PyJWT。
"""

import hashlib
import os
import secrets
import sqlite3
import threading
import time
from typing import Optional

import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "asman-dev-secret-change-me-please-32bytes-min")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 60 * 60 * 24 * 7  # 7 天


def hash_password(password: str, salt: str = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
        return hash_password(password, salt) == stored
    except (ValueError, AttributeError):
        return False


def create_token(username: str) -> str:
    payload = {"sub": username, "exp": time.time() + TOKEN_EXPIRE_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


class UserStore:
    """用户存储（SQLite，未来随数据库抽象层换 PostgreSQL）"""

    def __init__(self, db_path: str = "asman_users.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            conn.execute("CREATE TABLE IF NOT EXISTS users ("
                         "username TEXT PRIMARY KEY, password_hash TEXT, created_at REAL)")
            conn.commit()

    def register(self, username: str, password: str) -> bool:
        """注册新用户，返回是否成功（用户名已存在则 False）"""
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                             (username, hash_password(password), time.time()))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def authenticate(self, username: str, password: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT password_hash FROM users WHERE username = ?",
                               (username,)).fetchone()
        return bool(row) and verify_password(password, row[0])
