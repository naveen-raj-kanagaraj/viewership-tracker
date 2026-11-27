"""Weekly and monthly data zips for the owner's reports (owner, 27 Nov: "a zip of everything the site is tracking, as
CSV, all categories: every Sunday 12 am for the previous week, and at 12 am after the month ends for the whole month").

Sent to the owner's Telegram bot (TELEGRAM_BOT_TOKEN / OWNER_TELEGRAM_ID), times in IST:
  weekly   Sunday 00:00 IST   the 7 days before (Sunday 00:00 to Sunday 00:00)
  monthly  1st 00:00 IST      the previous calendar month
One CSV per table, rows inside the period (tables with no time column: their current state). Every row with a unix
time also gets time_ist. Kept out: accounts and emails (users), API keys, Predict & Win players and picks, the kv store
(private), and the 2-second event readings (ev_fine: ev_samples has every stream every ~30 s). The big live scan
(sc_samples, every stream every few minutes) comes as hourly peak / average per channel. Zips over 45 MB are split
(Telegram's limit for a bot is 50 MB). A copy stays in data/reports/."""
import csv
import io
import os
import sqlite3
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone

from tracker import store

IST = timezone(timedelta(hours=5, minutes=30))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports")
SKIP = {"users", "api_keys", "api_use", "kv", "pw_players", "pw_picks", "pg_entries", "ev_fine", "sqlite_sequence"}
PART = 45 * 1024 * 1024
_BUSY = [False]


def _ro():
    c = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True, timeout=30, check_same_thread=False)
    c.execute("PRAGMA busy_timeout=30000")
    return c


def _where(cols: list, t0: int, t1: int):
    """The period filter for a table, from its time columns; None: no time column (the current state)."""
    d0 = datetime.fromtimestamp(t0, IST).strftime("%Y-%m-%d")
    d1 = datetime.fromtimestamp(t1, IST).strftime("%Y-%m-%d")
    if "ts" in cols:
        return "ts >= ? AND ts < ?", (t0, t1)
    if "day" in cols:
        return "day >= ? AND day < ?", (d0, d1)
    for a, b in (("first_ts", "last_ts"), ("first_seen", "last_seen")):
        if a in cols and b in cols:
            return f"{a} < ? AND {b} >= ?", (t1, t0)
    for a in ("created", "updated", "checked"):
        if a in cols:
            return f"{a} >= ? AND {a} < ?", (t0, t1)
    return None


CHUNK = 1_000_000     # rows per CSV file (a big table becomes name_1.csv, name_2.csv ...)


def _csv(tmp: str, base: str, cur, ts_col=None) -> tuple:
    """Streams the cursor to CSV files in tmp; returns ([file names], rows)."""
    header = [d[0] for d in cur.description]
    tsi = header.index(ts_col) if ts_col in header else -1
    names, n, f, w = [], 0, None, None
    for r in cur:
        if n % CHUNK == 0:
            if f:
                f.close()
            nm = f"{base}.csv" if n == 0 else f"{base}_{n // CHUNK + 1}.csv"
            names.append(nm)
            f = open(os.path.join(tmp, nm), "w", newline="", encoding="utf-8")
            w = csv.writer(f)
            w.writerow((["time_ist"] if tsi >= 0 else []) + header)
        if tsi >= 0:
            t = r[tsi]
            w.writerow([datetime.fromtimestamp(t, IST).strftime("%Y-%m-%d %H:%M:%S") if t else ""] + list(r))
        else:
            w.writerow(r)
        n += 1
    if f:
        f.close()
    if not names:                                        # empty: still a file with the header
        names.append(f"{base}.csv")
        with open(os.path.join(tmp, names[0]), "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow((["time_ist"] if tsi >= 0 else []) + header)
    if len(names) > 1:                                   # first chunk named like the rest
        os.replace(os.path.join(tmp, names[0]), os.path.join(tmp, f"{base}_1.csv"))
        names[0] = f"{base}_1.csv"
    return names, n


def build(t0: int, t1: int, label: str) -> list:
    """Writes the zip(s) for [t0, t1) into data/reports/ and returns their paths."""
    import shutil
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, label + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    c = _ro()
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    files, readme = [], [f"letsgrowesports data: {label}",
                         f"{datetime.fromtimestamp(t0, IST):%d %b %Y %H:%M} to {datetime.fromtimestamp(t1, IST):%d %b %Y %H:%M} IST",
                         "One CSV per table (big tables split every 1,000,000 rows). ts = unix time (seconds), time_ist "
                         "next to it; day = IST date.", ""]
    for t in tables:
        if t in SKIP or t.startswith("sqlite_"):
            continue
        try:
            cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
            if t == "sc_samples":     # every stream every few minutes: hourly peak and average per channel
                cur = c.execute("SELECT (ts/3600)*3600 AS hour, sid, game, MAX(viewers) AS peak, CAST(AVG(viewers) AS INTEGER) "
                                "AS avg, COUNT(*) AS readings FROM sc_samples WHERE ts >= ? AND ts < ? GROUP BY hour, sid, game "
                                "ORDER BY hour", (t0, t1))
                names, n = _csv(tmp, "sc_samples_hourly", cur, "hour")
                note = "live scan, per channel per hour: peak, average, readings"
            else:
                wh = _where(cols, t0, t1)
                cur = c.execute(f"SELECT * FROM {t}" + (f" WHERE {wh[0]}" if wh else ""), wh[1] if wh else ())
                names, n = _csv(tmp, t, cur, "ts" if "ts" in cols else None)
                note = "rows in the period" if wh else "current state (no time column)"
            files += names
            readme.append(f"{', '.join(names)}: {n:,} rows, {note}")
        except Exception as e:
            readme.append(f"{t}: not exported ({str(e)[:100]})")
    c.close()
    with open(os.path.join(tmp, "README.txt"), "w") as f:
        f.write("\n".join(readme) + "\n")
    files.insert(0, "README.txt")
    # pack, splitting into parts under Telegram's limit (CSV compresses about 6 to 1)
    groups, cur_g, size = [], [], 0
    for nm in files:
        est = os.path.getsize(os.path.join(tmp, nm)) // 6 + 1
        if cur_g and size + est > PART:
            groups.append(cur_g)
            cur_g, size = [], 0
        cur_g.append(nm)
        size += est
    if cur_g:
        groups.append(cur_g)
    paths = []
    for i, g in enumerate(groups, 1):
        p = os.path.join(OUT, f"{label}.zip" if len(groups) == 1 else f"{label}-part{i}.zip")
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for nm in g:
                z.write(os.path.join(tmp, nm), nm)
        paths.append(p)
    shutil.rmtree(tmp, ignore_errors=True)
    return paths


def send(paths: list, caption: str) -> str:
    from tracker import eventlog
    res = []
    for i, p in enumerate(paths, 1):
        with open(p, "rb") as f:
            r = eventlog._send(caption + (f" (part {i} of {len(paths)})" if len(paths) > 1 else ""), f.read(), os.path.basename(p))
        res.append(r)
    return "ok" if all(r == "ok" for r in res) else ", ".join(res)


def _run(kind: str, t0: int, t1: int, label: str, flag: str):
    try:
        t = time.time()
        paths = build(t0, t1, label)
        mb = sum(os.path.getsize(p) for p in paths) / 1e6
        cap = (f"letsgrowesports {kind} data: {datetime.fromtimestamp(t0, IST):%d %b} to "
               f"{datetime.fromtimestamp(t1 - 1, IST):%d %b %Y} (IST). All tracked tables as CSV, README inside.")
        res = send(paths, cap)
        store.kv_set("report_zip_last", {"kind": kind, "label": label, "mb": round(mb, 1), "parts": len(paths),
                                         "secs": round(time.time() - t), "result": res, "ts": int(time.time())})
        if res == "ok":
            store.kv_set(flag, True)
        print(f"Report zip {label}: {len(paths)} file(s), {mb:.1f} MB, {res}")
    except Exception as e:
        store.kv_set("report_zip_last", {"kind": kind, "label": label, "result": "failed: " + str(e)[:150], "ts": int(time.time())})
        print(f"Report zip {label} failed: {str(e)[:150]}")
    finally:
        _BUSY[0] = False


def due(now: float = None):
    """(kind, t0, t1, label, flag) for a zip that is due and not sent yet, else None."""
    n = datetime.fromtimestamp(now or time.time(), IST)
    mid = n.replace(hour=0, minute=0, second=0, microsecond=0)
    if n.day == 1:                                       # the month that just ended
        m1 = mid
        m0 = (m1 - timedelta(days=1)).replace(day=1)
        label = f"letsgrowesports-month-{m0:%Y-%m}"
        if not store.kv_get(f"report_zip:{label}"):
            return "monthly", int(m0.timestamp()), int(m1.timestamp()), label, f"report_zip:{label}"
    if n.weekday() == 6:                                 # Sunday: the 7 days before
        w1 = mid
        w0 = w1 - timedelta(days=7)
        label = f"letsgrowesports-week-{w0:%Y-%m-%d}-to-{(w1 - timedelta(days=1)):%Y-%m-%d}"
        if not store.kv_get(f"report_zip:{label}"):
            return "weekly", int(w0.timestamp()), int(w1.timestamp()), label, f"report_zip:{label}"
    return None


def tick():
    """Called every minute: starts a due zip on its own thread (never two at once)."""
    if _BUSY[0]:
        return
    d = due()
    if not d:
        return
    last = store.kv_get("report_zip_last") or {}
    if last.get("label") == d[3] and time.time() - (last.get("ts") or 0) < 1800:
        return                                           # failed a moment ago: try again in 30 minutes
    _BUSY[0] = True
    threading.Thread(target=_run, args=d, daemon=True).start()
