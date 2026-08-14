"""结构化日志 + 全链路 trace

通过 contextvars 传递 passenger_id / station_id，
日志自动附带当前乘客与站点，便于追踪单个乘客的完整旅程。
"""

import contextvars
import logging
import sys

passenger_id_var = contextvars.ContextVar("passenger_id", default=None)
station_id_var = contextvars.ContextVar("station_id", default=None)


class TraceFilter(logging.Filter):
    def filter(self, record):
        record.passenger_id = passenger_id_var.get() or "-"
        record.station_id = station_id_var.get() or "-"
        return True


_FORMAT = "%(asctime)s %(levelname)-7s [pid=%(passenger_id)s][st=%(station_id)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO):
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT))
        handler.addFilter(TraceFilter())
        root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
