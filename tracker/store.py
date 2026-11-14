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

_tl = threading.local()


class _Lock:
    """The write lock (a re-entrant lock that remembers, per thread, that it is held): code that takes it inside a
    store.reading() block gets the read-write connection again, so nested writes keep working."""

    def __init__(self):
        self._l = threading.RLock()

    def acquire(self, *a, **k):
        ok = self._l.acquire(*a, **k)
        if ok:
            _tl.held = getattr(_tl, "held", 0) + 1
        return ok

    def release(self):
        _tl.held -= 1
        self._l.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
        return False


_lock = _Lock()
_conn = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class reading:
    """`with store.reading():` instead of `with store._lock:` for read-only work done while serving a page. Inside it,
    conn() hands this thread its own read-only connection, so pages read in parallel with each other and with the
    background writers (SQLite WAL) instead of queueing behind one lock. A write inside it raises at once."""

    def __enter__(self):
        _tl.depth = getattr(_tl, "depth", 0) + 1
        return self

    def __exit__(self, *exc):
        _tl.depth -= 1
        return False


def is_reading() -> bool:
    return getattr(_tl, "depth", 0) > 0


def _reader() -> sqlite3.Connection:
    c = getattr(_tl, "rc", None)
    if c is None or getattr(_tl, "rc_path", None) != DB_PATH:
        main()                                  # tables exist before anyone reads them
        c = sqlite3.connect(DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=5000")
        c.execute("PRAGMA query_only=1")
        _tl.rc, _tl.rc_path = c, DB_PATH
    return c


def conn() -> sqlite3.Connection:
    if is_reading() and not getattr(_tl, "held", 0):
        return _reader()
    return main()


def main() -> sqlite3.Connection:
    """The one shared read-write connection (use it under _lock)."""
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
        r = main().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        if not r:
            return default
        try:
            return json.loads(r["value"])
        except (ValueError, TypeError):
            return default


def kv_set(key: str, value):
    with _lock:
        c = main()
        c.execute(
            "INSERT INTO kv (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)))
        c.commit()
