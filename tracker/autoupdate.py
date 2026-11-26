"""Keep the running tracker on the latest code from GitHub, so nobody has to `git pull` and restart by hand.

Every AUTO_UPDATE_MIN minutes (default 10): fetch origin/main; if it has new commits that fast-forward cleanly and the
local tracked files are unedited, pull them, check every Python file still compiles (else roll back), then restart
this process in place (same terminal, same arguments). Never while a tournament's official broadcast is live.
Turn off with AUTO_UPDATE=false in .env.
"""
import glob
import os
import py_compile
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args, timeout=60) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=True).stdout.strip()


def _on_air() -> bool:
    try:
        from tracker import events
        return any(s.get("kind") == "official" for d in events._LIVE.values() for s in d.values())
    except Exception:
        return False


def _compiles() -> bool:
    for f in glob.glob(os.path.join(ROOT, "tracker", "*.py")) + [os.path.join(ROOT, "track.py")]:
        try:
            py_compile.compile(f, doraise=True)
        except py_compile.PyCompileError as e:
            print(f"Auto-update: {os.path.basename(f)} does not compile: {str(e)[:200]}")
            return False
    return True


def check_once() -> str:
    """One check. Returns what happened (for the log); restarts the process when it updated."""
    _git("fetch", "-q", "origin", "main")
    head, remote = _git("rev-parse", "HEAD"), _git("rev-parse", "origin/main")
    if head == remote:
        return "up to date"
    changed = [f for f in _git("diff", "--name-only", head, remote).split("\n") if f]
    # Files the tracker itself rewrites (exports/, logos ...) used to stop every update (26 Nov, PMGC Day 1). Only a
    # local edit to a file the update changes is in the way: git can fast-forward past anything else.
    dirty = {f for f in (_git("diff", "--name-only") + "\n" + _git("diff", "--name-only", "--cached")).split("\n") if f}
    clash = sorted(dirty & set(changed))
    if changed and all(f.startswith("tracker/live/") for f in changed):
        # only the live lists (watch parties added / removed): no restart, the tracker reads them again by itself
        if clash:
            return "skipped: edited by hand on this machine: " + ", ".join(clash[:5])
        _git("merge", "--ff-only", "-q", "origin/main")
        return "live lists updated (no restart): " + ", ".join(changed)
    if _on_air() and "[live]" not in _git("log", "--format=%s", f"{head}..{remote}"):
        return "skipped: a tournament broadcast is live"     # code waits for the broadcast to end (owner: no restarts
                                                             # while people are on the site); [live] only with his OK
    if clash:
        return "skipped: edited by hand on this machine: " + ", ".join(clash[:5])
    try:
        _git("merge-base", "--is-ancestor", "HEAD", "origin/main")
    except subprocess.CalledProcessError:
        return "skipped: this copy has its own commits; update by hand"
    _git("merge", "--ff-only", "-q", "origin/main")
    if not _compiles():
        _git("reset", "--hard", "-q", head)
        return "rolled back: the new code did not compile"
    msg = _git("log", "--oneline", "-1")
    print(f"Auto-update: now on {msg}. Restarting in place.", flush=True)
    try:
        from tracker import tunnel
        tunnel.stop()
    except Exception:
        pass
    os.execv(sys.executable, [sys.executable] + sys.argv)
    return "restarted"


def start():
    if os.getenv("AUTO_UPDATE", "true").lower() != "true":
        return
    every = max(1, int(os.getenv("AUTO_UPDATE_MIN", "1"))) * 60

    def loop():
        while True:
            time.sleep(every)
            try:
                r = check_once()
                if r != "up to date":
                    print(f"Auto-update: {r}", flush=True)
            except Exception as e:
                print(f"Auto-update check failed: {str(e)[:160]}", flush=True)
    threading.Thread(target=loop, daemon=True).start()
