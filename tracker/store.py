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
import sys
import threading
import time
from datetime import datetime, timezone

DB_PATH = os.getenv("TRACKER_DB", os.path.join("data", "tracker.db"))

_tl = threading.local()


HOLDER = {}          # who holds the write lock right now (health page)


def write_slices(sql: str, rows, n: int = 1000):
    """executemany in slices, taking and releasing the write lock per slice, so a big write never stalls the scans
    (20 Nov: one 'INSERT OR REPLACE' of every channel's period metrics held the lock for 14 minutes)."""
    rows = list(rows)
    for i in range(0, len(rows), n):
        with _lock:
            c = main()
            c.executemany(sql, rows[i:i + n])
            c.commit()


def delete_slices(table: str, where: str, args=(), n: int = 2000):
    """DELETE ... WHERE in slices of n rows, releasing the write lock between them."""
    while True:
        with _lock:
            c = main()
            k = c.execute(f"DELETE FROM {table} WHERE rowid IN (SELECT rowid FROM {table} WHERE {where} LIMIT {n})", args).rowcount
            c.commit()
        if k < n:
            return


class _Lock:
    """The write lock (a re-entrant lock that remembers, per thread, that it is held): code that takes it inside a
    store.reading() block gets the read-write connection again, so nested writes keep working."""

    def __init__(self):
        self._l = threading.RLock()

    def acquire(self, *a, **k):
        ok = self._l.acquire(*a, **k)
        if ok:
            _tl.held = getattr(_tl, "held", 0) + 1
            if _tl.held == 1:
                f = sys._getframe(2) if hasattr(sys, "_getframe") else None
                _tl.since = (time.time(), f"{os.path.basename(f.f_code.co_filename)}:{f.f_lineno} {f.f_code.co_name}" if f else "?")
                HOLDER.update(at=_tl.since[0], where=_tl.since[1], thread=threading.current_thread().name)
        return ok

    def release(self):
        _tl.held -= 1
        if _tl.held == 0 and getattr(_tl, "since", None):
            dt = time.time() - _tl.since[0]
            HOLDER.clear()
            if dt > 2:                          # everyone else waited this long: name the culprit in the log
                print(f"Slow write lock: {dt:.1f}s held by {_tl.since[1]}")
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
        if _tl.depth == 1:                      # a fresh read connection now and then: a cursor left half-read in a
            c = getattr(_tl, "rc", None)        # long-lived thread keeps its snapshot open, and the database log can't
            if c is not None and time.time() - getattr(_tl, "rc_at", 0) > 60:   # reset past it (20 Nov: 19 GB log)
                try:
                    c.close()
                except Exception:
                    pass
                _READERS.discard(c)
                _tl.rc = None
        return self

    def __exit__(self, *exc):
        _tl.depth -= 1
        return False


def is_reading() -> bool:
    return getattr(_tl, "depth", 0) > 0


_READERS = set()     # every read-only connection, so the checkpointer can interrupt them
_RGEN = [0]          # bumped when the checkpointer interrupts the readers: each thread then opens a fresh one


def _reader() -> sqlite3.Connection:
    c = getattr(_tl, "rc", None)
    if c is not None and getattr(_tl, "rc_gen", 0) != _RGEN[0]:
        _READERS.discard(c)
        c = _tl.rc = None                       # dropped: its statements are finalized, its snapshot released
    if c is None or getattr(_tl, "rc_path", None) != DB_PATH:
        if _conn is None:                       # tables exist before anyone reads them; never wait on the write lock
            main()                              # otherwise (20 Nov: every new reader queued behind 36 s writes)
        c = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)   # autocommit: every read sees
        c.row_factory = sqlite3.Row                                                    # the latest data, never an old snapshot
        c.execute("PRAGMA busy_timeout=5000")
        c.execute("PRAGMA query_only=1")
        _tl.rc, _tl.rc_path, _tl.rc_at, _tl.rc_gen = c, DB_PATH, time.time(), _RGEN[0]
        _READERS.add(c)
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
            # Checkpoints run in their own thread (checkpointer), not inside commits made under the write lock: on
            # 19 Nov the WAL had grown to 5 GB (bigger than the 4 GB database) and commits stalled 40 s copying it.
            _conn.execute("PRAGMA wal_autocheckpoint=0")
            _conn.execute("PRAGMA journal_size_limit=268435456")
            _init(_conn)
        return _conn


_CKPT = {"on": False}


def checkpointer(every: int = 30):
    """Copy the WAL into the database every `every` seconds on a separate connection, outside the write lock, and
    reset the WAL file whenever no page is mid-read (TRUNCATE, short wait), so it stays small and reads stay fast."""
    if _CKPT["on"] or not os.path.exists(DB_PATH):
        return
    _CKPT["on"] = True

    def loop():
        import time as _t
        c = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        c.execute("PRAGMA busy_timeout=200")
        n, fails = 0, 0
        while True:
            t0 = _t.time()
            try:
                busy, log, done = c.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
                n += 1
                tr = None
                big = log > 250000                # ~1 GB
                if fails >= 2 and n % 4 == 0:
                    # Two resets in a row found readers in the way (a page read running for minutes or a cursor left
                    # half-read keeps an old snapshot). Stop them: interrupt every read connection's running query
                    # (that page build fails once and is served from its last copy), make every thread open a fresh
                    # connection, then reset while the tracker's writes are held. (20 Nov: the log grew 70 MB a
                    # minute for hours because a reset never found a moment without old readers.)
                    with _lock:
                        _RGEN[0] += 1
                        for rc in list(_READERS):
                            try:
                                rc.interrupt()          # a query running now stops ...
                                rc.close()              # ... and a cursor left half-read is finalized with it
                            except Exception:
                                pass
                        _READERS.clear()
                        global _conn
                        if _conn is not None:             # the shared connection too: a cursor left half-read on it
                            try:                          # (code reading through it outside the lock) pins the log
                                if _conn.in_transaction:
                                    _conn.commit()
                                _conn.close()
                            except Exception:
                                pass
                            _conn = None
                        c.execute("PRAGMA busy_timeout=15000")
                        tr = c.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                        c.execute("PRAGMA busy_timeout=200")
                    print(f"WAL checkpoint: readers interrupted, reset {'done' if tr and not tr[0] else 'busy'}")
                elif (n % 4 == 0 and not big) or (big and n % 30 == 0):
                    # Reset the file with the tracker's writes held. Normally there is little to copy, so 2 s is plenty.
                    # When it has grown (a long read kept it from resetting), wait up to 20 s every 10 minutes for the
                    # old readers to finish instead of 5 s every 30 s (20 Nov: that held writes 5 s of every 35 s and
                    # still never reset; the log reached 19 GB and every restart spent 6 minutes recovering it).
                    with _lock:
                        if _conn is not None and _conn.in_transaction:   # a write left uncommitted keeps an old
                            print(f"WAL checkpoint: committed a write left open on the main connection")   # snapshot
                            _conn.commit()
                        # big: wait up to 90 s, once every 15 min. Only reads that began before the copy finished
                        # block the reset (20 Nov: page reads of 60-130 s outlasted a 20 s wait every time)
                        c.execute(f"PRAGMA busy_timeout={90000 if big else 2000}")
                        tr = c.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                        c.execute("PRAGMA busy_timeout=200")
                if tr is not None:
                    fails = 0 if not tr[0] else fails + 1
                took = _t.time() - t0
                if took > 5 or tr is not None or n % 10 == 1:
                    print(f"WAL checkpoint: {took:.0f}s, {log} pages in the WAL, {done} copied"
                          + (f", reset {'done' if tr and not tr[0] else 'busy'}" if tr is not None else ""))
            except Exception as e:
                print(f"WAL checkpoint: {str(e)[:100]}")
            _t.sleep(every)
    threading.Thread(target=loop, name="wal-checkpoint", daemon=True).start()


def _init(c):
    c.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)")
    c.commit()


def kv_get(key: str, default=None):
    """Read a setting. Never waits for the write lock: it uses this thread's read-only connection (which sees every
    committed write), unless this thread holds the lock already (then it must see its own uncommitted writes)."""
    if getattr(_tl, "held", 0):
        r = main().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    else:
        r = _reader().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
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
