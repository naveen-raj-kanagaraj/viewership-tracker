#!/bin/bash
# One-time: fold the oversized WAL (5 GB on 19 Nov) into the database with the tracker stopped, so nothing competes
# for the disk, then start it again. Safe: SQLite's own checkpoint. The tracker is started again even if it fails.
# Run detached so a dropped ssh session can't leave the site down:
#   nohup bash scripts/wal_reset.sh > ~/wal_reset.log 2>&1 &
cd "$(dirname "$0")/.." || exit 1
echo "start $(date)"; ls -l data/tracker.db data/tracker.db-wal
sudo systemctl stop tracker
OWNER=$(stat -c %U data/tracker.db)
sudo -u "$OWNER" venv/bin/python - <<'PY'
import sqlite3, time
t = time.time()
c = sqlite3.connect("data/tracker.db", timeout=120)
print("checkpoint (busy, log pages, copied):", c.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone(), f"{time.time() - t:.0f}s")
c.close()
PY
ls -l data/tracker.db data/tracker.db-wal
sudo systemctl start tracker
sleep 20
echo "tracker $(systemctl is-active tracker) $(git log --oneline -1)"
echo "DONE $(date)"
