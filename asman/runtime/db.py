"""数据库后端抽象：SQLite / PostgreSQL 统一接口

平台化 P0：让引擎支持 PostgreSQL（多租户/并发需要），
同时保持 SQLite 作为默认（开发/单机）。
约定：占位符统一用 `?`，后端内部转换；upsert 的表以第一列为主键。
"""

import re
import sqlite3
import threading
from typing import Any, List, Optional, Tuple


class DBBackend:
    def execute(self, sql: str, params: tuple = ()) -> Any:
        raise NotImplementedError

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[tuple]:
        raise NotImplementedError

    def fetchall(self, sql: str, params: tuple = ()) -> List[tuple]:
        raise NotImplementedError

    def upsert(self, sql: str, params: tuple = ()) -> None:
        """INSERT OR REPLACE 的方言封装（第一列为主键）"""
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class SQLiteBackend(DBBackend):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = None

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._get_conn().execute(sql, params)
            self._get_conn().commit()
            return cur

    def fetchone(self, sql, params=()):
        with self._lock:
            return self._get_conn().execute(sql, params).fetchone()

    def fetchall(self, sql, params=()):
        with self._lock:
            return self._get_conn().execute(sql, params).fetchall()

    def upsert(self, sql, params=()):
        self.execute(sql, params)

    def close(self):
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


class PostgresBackend(DBBackend):
    def __init__(self, dsn: str):
        import psycopg2
        self.dsn = dsn
        self._lock = threading.Lock()
        self._conn = None

    def _get_conn(self):
        if self._conn is None:
            import psycopg2
            self._conn = psycopg2.connect(self.dsn)
            self._conn.autocommit = True
        return self._conn

    @staticmethod
    def _adapt(sql: str) -> str:
        return sql.replace("?", "%s")

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._get_conn().cursor()
            cur.execute(self._adapt(sql), params)
            return cur

    def fetchone(self, sql, params=()):
        with self._lock:
            cur = self._get_conn().cursor()
            cur.execute(self._adapt(sql), params)
            return cur.fetchone()

    def fetchall(self, sql, params=()):
        with self._lock:
            cur = self._get_conn().cursor()
            cur.execute(self._adapt(sql), params)
            return cur.fetchall()

    def upsert(self, sql, params=()):
        # INSERT OR REPLACE INTO t (c1,c2,...) → INSERT ... ON CONFLICT (c1) DO UPDATE
        m = re.match(r"INSERT OR REPLACE INTO\s+(\w+)\s*\(([^)]+)\)", sql, re.IGNORECASE)
        if m:
            cols = [c.strip() for c in m.group(2).split(",")]
            updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols[1:])
            base = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO", 1)
            sql = f"{base} ON CONFLICT ({cols[0]}) DO UPDATE SET {updates}"
        else:
            sql = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO")
        self.execute(sql, params)

    def close(self):
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


def make_backend(dsn: str = None, sqlite_path: str = None) -> DBBackend:
    """根据配置创建后端：dsn（postgres://...）优先，否则 SQLite"""
    if dsn:
        return PostgresBackend(dsn)
    return SQLiteBackend(sqlite_path or "asman_state.db")
