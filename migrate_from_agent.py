#!/usr/bin/env python3
"""Copy the tracker's data out of the strategic-agent database into this repo.

    python migrate_from_agent.py ~/Downloads/projects/my-agent/data/agent.db --dry-run
    python migrate_from_agent.py ~/Downloads/projects/my-agent/data/agent.db

What moves:
    ev_streams      every stream found carrying an event, with its peak
    ev_samples      viewer counts, one row per stream per sample
    ev_fine         the high-resolution readings behind the live graph
    ev_ticks        combined totals per moment, split official / watch party / community
    ev_anomalies    flagged jumps and drops
    pw_players      Predict & Win players
    pw_questions    its questions and answers
    pw_picks        its picks
    kv rows         event definitions, tunnel URL, visitor counts, avatars, cached cards

What does not move: users, conversations, notes, reminders, spend, creators, deals and
every other agent table. Those belong to the agent and are left alone.

The agent database is opened read-only. Nothing in it is changed or deleted, so the
agent keeps working exactly as before until you remove the tracker code from it.

Re-running is safe. Rows for the events being migrated are replaced, not duplicated.
"""
import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tracker import store  # noqa: E402

# Tables keyed by event, cleared for those events before the copy so a second run
# does not double the sample count.
EVENT_TABLES = ("ev_streams", "ev_samples", "ev_fine", "ev_ticks", "ev_anomalies")
# Predict & Win. Copied whole, keeping ids, because picks reference player ids.
GAME_TABLES = ("pw_players", "pw_questions", "pw_picks")
# kv keys belonging to the tracker. "\" escapes the underscore so it is a literal.
KV_PATTERNS = ("events", "event\\_%", "ev\\_%", "pw\\_%", "visitors\\_%")


def _exists(c, name: str) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                     (name,)).fetchone() is not None


def _columns(c, table: str) -> list:
    return [r[1] for r in c.execute(f"PRAGMA table_info({table})")]


def _copy(src, dst, table: str, where: str = "", args: tuple = ()) -> int:
    """Copy a table by column name, so a schema that has drifted still lines up."""
    if not _exists(src, table):
        return 0
    s_cols, d_cols = _columns(src, table), _columns(dst, table)
    cols = [c for c in s_cols if c in d_cols]
    if not cols:
        return 0
    rows = src.execute(f"SELECT {', '.join(cols)} FROM {table} {where}", args).fetchall()
    if not rows:
        return 0
    dst.executemany(
        f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [tuple(r) for r in rows])
    return len(rows)


def migrate(src_path: str, dry_run: bool = False) -> int:
    src_path = os.path.expanduser(src_path)
    if not os.path.exists(src_path):
        print(f"No database at {src_path}", file=sys.stderr)
        print("Find it with:  find ~ -name agent.db -not -path '*/venv/*'", file=sys.stderr)
        return 1
    if os.path.abspath(src_path) == os.path.abspath(store.DB_PATH):
        print("Source and destination are the same file.", file=sys.stderr)
        return 1

    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    if not _exists(src, "ev_samples") and not _exists(src, "ev_ticks"):
        print(f"{src_path} has no event tables, so there is no tracker data in it.", file=sys.stderr)
        print("Tables found: " + ", ".join(
            r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")),
            file=sys.stderr)
        return 1

    counts = {t: src.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in EVENT_TABLES + GAME_TABLES if _exists(src, t)}
    kv_n = 0
    if _exists(src, "kv"):
        clause = " OR ".join("key LIKE ? ESCAPE '\\'" for _ in KV_PATTERNS)
        kv_n = src.execute(f"SELECT COUNT(*) FROM kv WHERE {clause}", KV_PATTERNS).fetchone()[0]

    keys = []
    if _exists(src, "ev_ticks"):
        keys = [r[0] for r in src.execute("SELECT DISTINCT event FROM ev_ticks ORDER BY event")]

    print(f"Reading {src_path}\n")
    print(f"  Events: {', '.join(keys) if keys else 'none'}")
    for t in EVENT_TABLES + GAME_TABLES:
        if t in counts:
            print(f"  {t:<14} {counts[t]:>9,} rows")
    print(f"  {'kv rows':<14} {kv_n:>9,}")

    if keys and _exists(src, "ev_ticks"):
        print("\n  Per event:")
        for k in keys:
            peak = src.execute("SELECT MAX(total) FROM ev_ticks WHERE event=?", (k,)).fetchone()[0] or 0
            span = src.execute("SELECT MIN(ts), MAX(ts) FROM ev_ticks WHERE event=?", (k,)).fetchone()
            import datetime as _dt
            fmt = (lambda t: _dt.datetime.fromtimestamp(t).strftime("%d %b %Y")) if span[0] else (lambda t: "?")
            days = ((span[1] - span[0]) / 86400) if span[0] and span[1] else 0
            print(f"    {k:<10} peak {peak:>9,} concurrent   "
                  f"{fmt(span[0])} to {fmt(span[1])}  ({days:.1f} days)")

    if dry_run:
        print("\nDry run. Nothing written.")
        src.close()
        return 0

    if not counts and not kv_n:
        print("\nNothing to migrate.")
        src.close()
        return 0

    dst = store.conn()
    # Create the tracker's own tables before copying into them.
    from tracker import events as _events, predict as _predict
    _events._db()
    _predict._db()

    print(f"\nWriting to {store.DB_PATH}")
    moved = {}
    with store._lock:
        for t in EVENT_TABLES:
            if not _exists(src, t) or not keys:
                continue
            marks = ", ".join("?" * len(keys))
            dst.execute(f"DELETE FROM {t} WHERE event IN ({marks})", keys)
            moved[t] = _copy(src, dst, t)
        for t in GAME_TABLES:
            moved[t] = _copy(src, dst, t)
        if _exists(src, "kv"):
            clause = " OR ".join("key LIKE ? ESCAPE '\\'" for _ in KV_PATTERNS)
            rows = src.execute(f"SELECT key, value FROM kv WHERE {clause}", KV_PATTERNS).fetchall()
            dst.executemany("INSERT OR REPLACE INTO kv (key, value) VALUES (?,?)",
                            [(r["key"], r["value"]) for r in rows])
            moved["kv"] = len(rows)
        dst.commit()
    src.close()

    for t, n in moved.items():
        if n:
            print(f"  {t:<14} {n:>9,} rows")

    print("\nDone. Check it with:")
    print("  python track.py events")
    print(f"  python track.py stats{' ' + keys[0] if keys else ''}")
    print("  python track.py run          then open the dashboard")
    print("\nThe agent database was not modified.")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Copy tracker data out of the strategic-agent database.")
    p.add_argument("agent_db", help="path to the agent's data/agent.db")
    p.add_argument("--dry-run", action="store_true", help="show what would move, write nothing")
    a = p.parse_args()
    sys.exit(migrate(a.agent_db, a.dry_run))
