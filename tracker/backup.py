"""Copies of the database, so the history survives a broken disk or a move to another machine.

`python track.py backup` makes one now; the running tracker makes one every night (about 03:30 IST, when traffic is
lowest). Each is a complete, consistent SQLite file made with SQLite's own online backup (safe while the tracker is
writing), saved as backups/tracker-YYYY-MM-DD.db. The newest BACKUP_KEEP (default 3) are kept. backups/ is git-ignored
(the database holds Predict & Win player data): copy a backup to another disk or cloud folder yourself, or set
BACKUP_DIR to a folder that syncs (iCloud Drive, Google Drive, Dropbox).
"""
import glob
import os
import sqlite3
import threading
import time
from datetime import datetime

from tracker import store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def folder() -> str:
    d = os.path.expanduser(os.getenv("BACKUP_DIR", os.path.join(ROOT, "backups")))
    os.makedirs(d, exist_ok=True)
    return d


def make() -> str:
    """One backup now. Returns its path."""
    dest = os.path.join(folder(), f"tracker-{datetime.now().strftime('%Y-%m-%d')}.db")
    tmp = dest + ".part"
    src = sqlite3.connect(store.DB_PATH, timeout=30)
    out = sqlite3.connect(tmp)
    try:
        src.backup(out, pages=4096, sleep=0.05)     # in chunks, so the live tracker is never blocked for long
    finally:
        out.close()
        src.close()
    os.replace(tmp, dest)
    keep = max(1, int(os.getenv("BACKUP_KEEP", "3")))
    for old in sorted(glob.glob(os.path.join(folder(), "tracker-*.db")))[:-keep]:
        os.remove(old)
    return dest


def start():
    """Nightly backup thread for the running tracker."""
    if os.getenv("BACKUP_NIGHTLY", "true").lower() != "true":
        return

    def loop():
        while True:
            time.sleep(600)
            try:
                from tracker import events
                now = datetime.now(events.REPORT_TZ)
                done = store.kv_get("backup_last_day")
                if now.hour == 3 and now.strftime("%Y-%m-%d") != done:
                    path = make()
                    store.kv_set("backup_last_day", now.strftime("%Y-%m-%d"))
                    print(f"Backup saved: {path} ({os.path.getsize(path) / 1e6:.0f} MB)", flush=True)
            except Exception as e:
                print(f"Nightly backup failed: {str(e)[:160]}", flush=True)
    threading.Thread(target=loop, daemon=True).start()
