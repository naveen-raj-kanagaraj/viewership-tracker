#!/usr/bin/env python3
"""Live viewership tracker.

    python track.py                      run the tracker and the dashboard
    python track.py events               list events and their state
    python track.py create bmsd          create or re-activate an event
    python track.py pause bmsd           stop recording, keep serving history
    python track.py resume bmsd
    python track.py stats [bmsd]         peak, average, hours watched, per channel
    python track.py export [bmsd]        write the CSV and xlsx exports
    python track.py visitors             dashboard traffic

Running with no arguments starts three things: the live counter (every
EVENT_FAST_SEC), stream discovery (every EVENT_POLL_SEC) and the web dashboard.
"""
import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from tracker import events, store  # noqa: E402


def _discovery_loop():
    """Search YouTube for new streams carrying each active event.

    A slow poll skips the next one rather than piling up: discovery is a search,
    and two of them running at once just rate-limits the tracker.
    """
    lock = threading.Lock()
    pool = ThreadPoolExecutor(max_workers=1)

    def once():
        if not lock.acquire(blocking=False):
            return

        def body():
            try:
                events.run_all()
            except Exception as e:
                print(f"Discovery failed: {str(e)[:200]}", flush=True)
            finally:
                lock.release()
        pool.submit(body)

    while True:
        once()
        time.sleep(events.POLL_SEC)


def cmd_run(args) -> int:
    active = [e for e in events.events().values() if e.get("active")]
    if not active:
        print("No active event. Create one first:  python track.py create bmsd")
        print("Serving the dashboard anyway, which will show stored history.\n")

    print(f"Database:      {store.DB_PATH}")
    print(f"Live counter:  every {events.FAST_SEC}s")
    print(f"Discovery:     every {events.POLL_SEC}s")
    print(f"Counting from: {'YouTube Data API' if os.getenv('YOUTUBE_API_KEY') else 'public pages via yt-dlp (no API key)'}")
    if active:
        print(f"Tracking:      {', '.join(e['name'] for e in active)}")
    print()

    # Live counters, the per-minute export thread and the one-time repair all start here.
    threading.Thread(target=events.run_fast_forever, daemon=True).start()
    threading.Thread(target=_discovery_loop, daemon=True).start()

    from tracker import web
    if os.getenv("EVENT_PUBLIC_LINK", "true").lower() == "true":
        from tracker import tunnel
        tunnel.start(web.PORT)
    web.run()
    return 0


def cmd_events(args) -> int:
    evs = events.events()
    if not evs:
        print("No events yet. Known presets: " + ", ".join(events.PRESETS))
        return 0
    for k, ev in evs.items():
        if events.PRESETS.get(k, {}).get("ended"):
            state = "ended"
        elif not ev.get("active"):
            state = "inactive"
        else:
            state = "paused" if events.paused(k) else "recording"
        streams = len(ev.get("channels", []))
        print(f"{k:<10} {ev.get('name', ''):<24} {state:<10} {streams} channels seen")
    return 0


def cmd_create(args) -> int:
    ev = events.create(args.key)
    print(f"{ev['key']}: {ev['name']} is active.")
    print(f"Matching: {', '.join(ev['match'][:6])}")
    if events.PRESETS.get(ev["key"], {}).get("ended"):
        print("This preset is marked ended, so nothing new is recorded and the dashboard serves history.")
    return 0


def cmd_pause(args) -> int:
    store.kv_set(f"event_stop:{args.key}", time.time() + 10 * 365 * 86400)
    print(f"{args.key} paused. History is still served. Resume with:  python track.py resume {args.key}")
    return 0


def cmd_resume(args) -> int:
    store.kv_set(f"event_stop:{args.key}", 0)
    events.update(args.key, active=True)
    print(f"{args.key} is recording again.")
    return 0


def cmd_stats(args) -> int:
    print(events.summary(args.key))
    return 0


def cmd_export(args) -> int:
    from tracker import dataexport
    key = args.key or (events.get() or {}).get("key")
    if not key:
        print("No event to export.", file=sys.stderr)
        return 1
    ev = events.get(key)
    if not ev:
        print(f"No event called {key}.", file=sys.stderr)
        return 1
    result = dataexport.tick(ev, force=True)
    print(result if result else f"Exports written to exports/{key}/")
    return 0


def cmd_visitors(args) -> int:
    from tracker import visitors
    print(visitors.summary())
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Track concurrent viewers across every YouTube stream carrying an esports event.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("run", help="run the tracker and the dashboard (default)")
    sub.add_parser("events", help="list events and their state")
    sub.add_parser("visitors", help="dashboard traffic")
    for name, help_text in (("create", "create or re-activate an event"),
                            ("pause", "stop recording, keep serving history"),
                            ("resume", "start recording again")):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("key", help="event key, e.g. bmsd")
    for name, help_text in (("stats", "peak, average, hours watched"),
                            ("export", "write the CSV and xlsx exports")):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("key", nargs="?", help="event key (default: the active one)")

    args = p.parse_args()
    handlers = {None: cmd_run, "run": cmd_run, "events": cmd_events, "create": cmd_create,
                "pause": cmd_pause, "resume": cmd_resume, "stats": cmd_stats,
                "export": cmd_export, "visitors": cmd_visitors}
    try:
        return handlers[args.cmd](args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
