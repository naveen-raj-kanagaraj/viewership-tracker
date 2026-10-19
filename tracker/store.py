"""SQLite storage.

One connection shared across threads, guarded by a lock, with WAL enabled so the
live counter can write while the dashboard reads.

This module owns only the `kv` table, which holds JSON blobs: the event
definitions, tunnel state, visitor counters, export bookkeeping. Every other
table is created by the module that uses it:

  events.py    ev_streams, ev_samples, ev_fine, ev_ticks, ev_anomalies
  predict.py   pw_players, pw_questions, pw_picks
"""
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

DB_PATH = os.getenv("TRACKER_DB", os.path.join("data", "tracker.db"))

_lock = threading.RLock()
_conn = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            # The live counter writes every couple of seconds while the dashboard reads.
            # Wait rather than raising "database is locked".
            _conn.execute("PRAGMA busy_timeout=5000")
            _conn.execute("PRAGMA synchronous=NORMAL")
            _init(_conn)
        return _conn


def _init(c):
    c.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)")
    c.commit()


def kv_get(key: str, default=None):
    with _lock:
        r = conn().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        if not r:
            return default
        try:
            return json.loads(r["value"])
        except (ValueError, TypeError):
            return default


def kv_set(key: str, value):
    with _lock:
        c = conn()
        c.execute(
            "INSERT INTO kv (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)))
        c.commit()
