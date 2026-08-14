"""ASMAN State Layer - Loop Engineering 风格状态外部化

持久化层。通过 DBBackend 抽象支持 SQLite（默认）+ PostgreSQL（多租户/并发）。
"""

import json
import time
import hashlib
from typing import Dict, Any, Optional, List

from ..runtime.db import make_backend, DBBackend, SQLiteBackend


class StateLayer:
    def __init__(self, db_path: str = "asman_state.db", dsn: str = None, db: DBBackend = None):
        self.db = db or make_backend(dsn, db_path)
        self._init_db()

    def _init_db(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS passengers (passenger_id TEXT PRIMARY KEY, parent_id TEXT, status TEXT, current_location TEXT, line_id TEXT, segment_idx INTEGER, completed_stops TEXT, baggage TEXT, priority INTEGER, created_at REAL, updated_at REAL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS slice_tracking (parent_id TEXT PRIMARY KEY, station_id TEXT, total INTEGER, arrived INTEGER, results TEXT, start_time REAL, status TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS platform_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, station_id TEXT, passenger_id TEXT, priority INTEGER, enqueued_at REAL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS hub_transfer (hub_id TEXT, passenger_id TEXT, from_line TEXT, to_line TEXT, arrived_at REAL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS checkpoints (checkpoint_id TEXT PRIMARY KEY, passenger_id TEXT, state_snapshot TEXT, created_at REAL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS execution_log (id INTEGER PRIMARY KEY AUTOINCREMENT, passenger_id TEXT, station_id TEXT, action TEXT, input_hash TEXT, output_hash TEXT, duration_ms INTEGER, timestamp REAL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS passenger_events (id INTEGER PRIMARY KEY AUTOINCREMENT, passenger_id TEXT, event_type TEXT, payload TEXT, timestamp REAL)")
        # SQLite 专属索引（PostgreSQL 会因语法不同而忽略失败，容错）
        if isinstance(self.db, SQLiteBackend):
            try:
                self.db.execute("CREATE INDEX IF NOT EXISTS idx_events_pid ON passenger_events(passenger_id, id)")
            except Exception:
                pass

    def save_passenger(self, passenger) -> bool:
        line_id = ""
        if passenger.itinerary.current_segment():
            line_id = passenger.itinerary.current_segment().line_id
        self.db.upsert("INSERT OR REPLACE INTO passengers (passenger_id, parent_id, status, current_location, line_id, segment_idx, completed_stops, baggage, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (passenger.passenger_id, passenger.parent_id or "", passenger.status.value, passenger.current_location, line_id, passenger.itinerary.current_segment_idx, json.dumps(passenger.completed_stops), json.dumps(passenger.baggage, default=str), passenger.priority, passenger.created_at, time.time()))
        return True

    def load_passenger(self, passenger_id: str) -> Optional[Dict]:
        row = self.db.fetchone("SELECT * FROM passengers WHERE passenger_id = ?", (passenger_id,))
        if row:
            return {"passenger_id": row[0], "parent_id": row[1], "status": row[2], "current_location": row[3], "line_id": row[4], "segment_idx": row[5], "completed_stops": json.loads(row[6]), "baggage": json.loads(row[7]), "priority": row[8], "created_at": row[9]}
        return None

    def save_slice_tracking(self, parent_id: str, tracking: Dict):
        self.db.upsert("INSERT OR REPLACE INTO slice_tracking (parent_id, station_id, total, arrived, results, start_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (parent_id, tracking.get("station_id", ""), tracking.get("total", 0), tracking.get("arrived", 0), json.dumps(tracking.get("results", [])), tracking.get("start_time", time.time()), tracking.get("status", "active")))

    def enqueue_to_platform(self, station_id: str, passenger_id: str, priority: int):
        self.db.execute("INSERT INTO platform_queue (station_id, passenger_id, priority, enqueued_at) VALUES (?, ?, ?, ?)", (station_id, passenger_id, priority, time.time()))

    def dequeue_from_platform(self, station_id: str, max_count: int) -> List[str]:
        rows = self.db.fetchall("SELECT passenger_id FROM platform_queue WHERE station_id = ? ORDER BY priority DESC, enqueued_at ASC LIMIT ?", (station_id, max_count))
        passenger_ids = [r[0] for r in rows]
        if passenger_ids:
            placeholders = ",".join(["?"] * len(passenger_ids))
            self.db.execute(f"DELETE FROM platform_queue WHERE station_id = ? AND passenger_id IN ({placeholders})", [station_id] + passenger_ids)
        return passenger_ids

    def log_execution(self, passenger_id: str, station_id: str, action: str, input_data: Any, output_data: Any, duration_ms: int):
        input_hash = hashlib.md5(json.dumps(input_data, default=str).encode()).hexdigest()[:16]
        output_hash = hashlib.md5(json.dumps(output_data, default=str).encode()).hexdigest()[:16]
        self.db.execute("INSERT INTO execution_log (passenger_id, station_id, action, input_hash, output_hash, duration_ms, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (passenger_id, station_id, action, input_hash, output_hash, duration_ms, time.time()))

    def create_checkpoint(self, passenger_id: str, state_snapshot: Dict) -> str:
        checkpoint_id = f"cp_{passenger_id}_{int(time.time())}"
        self.db.execute("INSERT INTO checkpoints (checkpoint_id, passenger_id, state_snapshot, created_at) VALUES (?, ?, ?, ?)", (checkpoint_id, passenger_id, json.dumps(state_snapshot, default=str), time.time()))
        return checkpoint_id

    def restore_from_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        row = self.db.fetchone("SELECT state_snapshot FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,))
        if row:
            return json.loads(row[0])
        return None

    def get_all_active_passengers(self) -> List[str]:
        rows = self.db.fetchall("SELECT passenger_id FROM passengers WHERE status NOT IN (?, ?)", ("completed", "failed"))
        return [r[0] for r in rows]

    def load_active_passengers_full(self) -> List[Dict]:
        """加载所有未完成乘客的完整状态（用于崩溃恢复）"""
        rows = self.db.fetchall("SELECT * FROM passengers WHERE status NOT IN (?, ?)", ("completed", "failed"))
        result = []
        for row in rows:
            result.append({
                "passenger_id": row[0], "parent_id": row[1], "status": row[2],
                "current_location": row[3], "line_id": row[4], "segment_idx": row[5],
                "completed_stops": json.loads(row[6]), "baggage": json.loads(row[7]),
                "priority": row[8], "created_at": row[9],
            })
        return result

    def append_event(self, passenger_id: str, event_type: str, payload: Dict = None):
        self.db.execute("INSERT INTO passenger_events (passenger_id, event_type, payload, timestamp) VALUES (?, ?, ?, ?)",
                      (passenger_id, event_type, json.dumps(payload or {}, default=str), time.time()))

    def get_events(self, passenger_id: str, limit: int = 100) -> List[Dict]:
        rows = self.db.fetchall("SELECT event_type, payload, timestamp FROM passenger_events WHERE passenger_id = ? ORDER BY id DESC LIMIT ?", (passenger_id, limit))
        return [{"event_type": r[0], "payload": json.loads(r[1]), "timestamp": r[2]} for r in rows]

    def close(self):
        self.db.close()
