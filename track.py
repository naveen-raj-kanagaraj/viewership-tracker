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

  More games and platforms (YouTube is always on; Kick and Twitch per event):
    python track.py new valo "VCT Pacific" --game Valorant --match "vct,pacific" --queries "VCT Pacific"
    python track.py kick valo official valorant        count kick.com/valorant as the official broadcast
    python track.py kick valo add tarik                count a Kick channel while its title matches
    python track.py twitch valo official valorant
    python track.py twitch valo category VALORANT      top live streams in a Twitch category (title must match)
    python track.py kick valo remove tarik
    python track.py home hub                           the front page: India hub (default) or an event (home bmic)
    python track.py platforms                          which connectors have keys
    python track.py backup                             copy the database to backups/ (also automatic every night)

  India rankings (every streamer, every game; page at /india):
    python track.py scene top [today|7d|30d]           who is live now and who leads
    python track.py scene add kick skyesports          add a channel (youtube @handle, kick slug, twitch login)
    python track.py scene remove kick skyesports
    python track.py scene block <name or url>          hide a channel from the rankings (unblock to undo)
    python track.py scene allow <name>                 count a channel as Indian whatever the checks say
    python track.py scene clean                        re-judge every channel seen, delete non-Indian data
    python track.py scene probe                        check each source once

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
    for k, pr in events.PRESETS.items():       # presets marked auto exist without anyone running `track.py create`
        if pr.get("auto") and k not in events.events():
            events.create(k)
    active = [e for e in events.events().values() if e.get("active")]
    if not active:
        print("No active event. Create one first:  python track.py create bmsd")
        print("Serving the dashboard anyway, which will show stored history.\n")

    print(f"Database:      {store.DB_PATH}")
    print(f"Live counter:  every {events.FAST_SEC}s")
    print(f"Discovery:     every {events.POLL_SEC}s")
    print(f"Counting from: {'YouTube Data API' if os.getenv('YOUTUBE_API_KEY') else 'public pages via yt-dlp (no API key)'}")
    if os.getenv("SCENE_ENABLED", "true").lower() == "true":
        print("Rankings:      worldwide + India live streams (YouTube, Kick, Twitch), new streams every 2 min, counts every 2s")
    if active:
        ended = [e['name'] for e in active if events.PRESETS.get(e['key'], {}).get('ended')]
        live = [e['name'] for e in active if e['name'] not in ended]
        print(f"Tournaments:   {', '.join(live) or '-'}" + (f"  (finished, history only: {', '.join(ended)})" if ended else ""))
    print()

    # Live counters, the per-minute export thread and the one-time repair all start here.
    threading.Thread(target=events.run_fast_forever, daemon=True).start()
    threading.Thread(target=_discovery_loop, daemon=True).start()
    if os.getenv("SCENE_ENABLED", "true").lower() == "true":     # India rankings at /india
        from tracker import scene
        threading.Thread(target=scene.run_forever, daemon=True).start()
        from tracker import ytextra
        ytextra.start()                    # Super Chats on the biggest YouTube streams + daily channel stats

    from tracker import autoupdate, backup
    autoupdate.start()
    backup.start()                         # a copy of the database every night (backups/, newest 3 kept)                     # pulls new code from GitHub and restarts itself (AUTO_UPDATE=false to stop)

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


def cmd_new(args) -> int:
    split = lambda x: [v.strip() for v in (x or "").split(",") if v.strip()]
    ev = events.create(args.key, name=args.name, match=split(args.match) or None, queries=split(args.queries) or None,
                       official=split(args.official) or None)
    fields = {}
    if args.game:
        fields["game"] = args.game
    if args.any_title:
        fields["any_title"] = True
    if args.no_official:
        fields["need_official"] = False
    if fields:
        events.update(ev["key"], **fields)
    print(f"{ev['key']}: {ev['name']} is active. Matching: {', '.join(ev['match'][:6])}")
    print(f"Page: /e/{ev['key']}/   Add channels:  python track.py kick {ev['key']} official <slug>")
    return 0


def cmd_platform(args) -> int:
    ev = events.get(args.key)
    if not ev:
        print(f"No event called {args.key}. Create it first:  python track.py new {args.key} \"Name\"", file=sys.stderr)
        return 1
    c = dict(ev.get(args.cmd) or events.preset(ev["key"]).get(args.cmd) or {})
    c.setdefault("official", []), c.setdefault("channels", [])
    v = args.value.strip()
    if args.action == "category":
        c["category"] = "" if v.lower() in ("none", "off", "-") else v
    else:
        x = v.lower().lstrip("@").rstrip("/").rsplit("/", 1)[-1]   # accepts a slug or a full channel URL
        c["official"] = [y for y in c["official"] if y != x]
        c["channels"] = [y for y in c["channels"] if y != x]
        if args.action in ("official", "add"):
            c["official" if args.action == "official" else "channels"].append(x)
    events.update(ev["key"], **{args.cmd: c})
    print(f"{ev['key']} {args.cmd}: official {c['official'] or '-'}, channels {c['channels'] or '-'}, "
          f"category {c.get('category') or '-'}  (picked up within a minute, no restart needed)")
    return 0


def cmd_home(args) -> int:
    if args.key == "hub":
        store.kv_set("site_home", "hub")
        print("/ now shows the India hub (every channel, every category). Events stay at /e/<key>/")
        return 0
    if not events.get(args.key):
        print(f"No event called {args.key}. Use an event key or 'hub'.", file=sys.stderr)
        return 1
    store.kv_set("site_home", args.key)
    store.kv_set("event_home", args.key)
    print(f"/ now shows {args.key}. The India hub stays at /india; switch back with: python track.py home hub")
    return 0


def cmd_platforms(args) -> int:
    from tracker import platforms
    print("youtube    always on (yt-dlp; YOUTUBE_API_KEY optional)")
    for p, st in platforms.status().items():
        print(f"{p:<10} {st}")
    return 0


def cmd_scene(args) -> int:
    from tracker import scene
    a = args.args
    if not a or a[0] == "top":
        print(scene.top(a[1] if len(a) > 1 else "today"))
        return 0
    if a[0] == "probe":
        print(scene.probe())
        return 0
    if a[0] == "clean":
        print(scene.clean())
        return 0
    if a[0] == "superchat" and len(a) >= 2:          # read one live stream's chat for a minute: track.py scene superchat <video>
        from tracker import ytextra
        print(ytextra.probe_chat(a[1], int(a[2]) if len(a) > 2 else 60))
        return 0
    if a[0] == "stats" and len(a) >= 2:              # one channel's subscribers / views / videos: track.py scene stats @handle
        from tracker import ytextra
        print(ytextra.probe_stats(a[1]))
        return 0
    if a[0] in ("allow", "disallow") and len(a) >= 2:
        want = " ".join(a[1:]).strip().lower().rstrip("/")
        with store._lock:
            rows = scene._db().execute("SELECT sid, name, url FROM sc_channels").fetchall()
        hit = [r["sid"] for r in rows if want in (r["sid"].lower(), (r["name"] or "").lower(), (r["url"] or "").lower())]
        if not hit:
            print(f"No channel called {want} has been seen yet.", file=sys.stderr)
            return 1
        al = set(store.kv_get("scene_allowed") or [])
        al = (al | set(hit)) if a[0] == "allow" else (al - set(hit))
        store.kv_set("scene_allowed", sorted(al))
        print(f"{a[0]}ed as Indian: {', '.join(hit)}")
        return 0
    if a[0] in ("add", "remove") and len(a) == 3 and a[1] in ("youtube", "kick", "twitch"):
        sd = scene.seeds()
        x = a[2].strip().rstrip("/").rsplit("/", 1)[-1]
        x = ("@" + x.lstrip("@")) if a[1] == "youtube" and not x.startswith("UC") else x.lower().lstrip("@")
        sd[a[1]] = [y for y in sd[a[1]] if y.lower() != x.lower()] + ([x] if a[0] == "add" else [])
        store.kv_set("scene_seeds", sd)
        print(f"{a[1]}: {', '.join(sd[a[1]]) or '-'}  (picked up in the next scan)")
        return 0
    if a[0] in ("block", "unblock") and len(a) >= 2:
        want = " ".join(a[1:]).strip().lower().rstrip("/")
        with store._lock:
            rows = scene._db().execute("SELECT sid, name, url FROM sc_channels").fetchall()
        hit = [r["sid"] for r in rows if want in (r["sid"].lower(), (r["name"] or "").lower(), (r["url"] or "").lower())
               or (want.startswith("http") and want.rsplit("/", 1)[-1] == r["sid"].split(":", 1)[-1].lower())]
        if not hit:
            print(f"No channel called {want} has been seen yet.", file=sys.stderr)
            return 1
        b = scene.blocked()
        b = (b | set(hit)) if a[0] == "block" else (b - set(hit))
        store.kv_set("scene_blocked", sorted(b))
        print(f"{a[0]}ed: {', '.join(hit)}")
        return 0
    print("Usage: track.py scene [top [today|7d|30d] | probe | superchat <video> [seconds] | stats <@handle> | add|remove <youtube|kick|twitch> <channel> | block|unblock <name>]",
          file=sys.stderr)
    return 1


def cmd_backup(args) -> int:
    from tracker import backup
    path = backup.make()
    print(f"Backup saved: {path} ({os.path.getsize(path) / 1e6:.1f} MB). Copy it somewhere safe; it holds private "
          "Predict & Win data, so never put it on GitHub.")
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
    s = sub.add_parser("new", help="create a custom event (any game)")
    s.add_argument("key")
    s.add_argument("name")
    s.add_argument("--game", help="e.g. Valorant, BGMI, Free Fire")
    s.add_argument("--match", help="comma-separated words a stream title must contain (default: the key)")
    s.add_argument("--queries", help="comma-separated YouTube searches")
    s.add_argument("--official", help="comma-separated official YouTube channel names")
    s.add_argument("--any-title", action="store_true", help="count listed Kick/Twitch channels whatever their title")
    s.add_argument("--no-official", action="store_true", help="record whenever anything is live, not only during the official broadcast")
    for plat in ("kick", "twitch"):
        s = sub.add_parser(plat, help=f"{plat.title()} channels for an event")
        s.add_argument("key")
        s.add_argument("action", choices=["official", "add", "remove", "category"])
        s.add_argument("value", help="channel slug/login or URL; for category, the game name (or 'none')")
    s = sub.add_parser("home", help="the event shown at /")
    s.add_argument("key")
    sub.add_parser("platforms", help="which connectors have keys")
    sub.add_parser("backup", help="save a copy of the database to backups/")
    s = sub.add_parser("scene", help="India rankings: top, probe, add/remove a channel, block")
    s.add_argument("args", nargs="*")
    for name, help_text in (("stats", "peak, average, hours watched"),
                            ("export", "write the CSV and xlsx exports")):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("key", nargs="?", help="event key (default: the active one)")

    args = p.parse_args()
    handlers = {None: cmd_run, "run": cmd_run, "events": cmd_events, "create": cmd_create,
                "pause": cmd_pause, "resume": cmd_resume, "stats": cmd_stats,
                "export": cmd_export, "visitors": cmd_visitors, "new": cmd_new, "kick": cmd_platform,
                "twitch": cmd_platform, "home": cmd_home, "platforms": cmd_platforms,
                "scene": cmd_scene, "backup": cmd_backup}
    try:
        return handlers[args.cmd](args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
