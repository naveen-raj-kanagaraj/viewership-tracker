# Handoff: how this project works and where it stands

Read this first if you are picking the project up in a new chat or as a new person. It is the single place that
explains what exists, where it runs, how to operate it and what is unfinished. Keep it current: update the
"Current state" section whenever something changes.

## What it is

`live.letsgrowesports.com`, run by letsgrowesports (Indian gaming media brand). Two products on one site, one
Python process, one SQLite file:

1. **India live streaming rankings** (the front page `/`): every Indian live stream we can find on YouTube, Kick and
   Twitch, sorted into games and categories (BGMI, Free Fire, GTA V, Valorant, News, Devotional, Music, Cricket ...),
   with live-now, viewers over time, and top streamers today / 7 days / 30 days. One page per category at
   `/c/<slug>` (`/c/bgmi`, `/c/free-fire`, `/c/news`). Shareable image cards on every section.
2. **Tournament trackers** (`/e/<key>/`): Esports-Charts-style live dashboards for one event (BGMI tournaments so
   far: BMSD 2026 finished at 653K peak, BMIC 2026 upcoming). Counts the official broadcast plus permitted watch
   parties every 2 seconds, history chart, by-day breakdown, share cards, Predict & Win game.

## Where it runs

| Thing | Where |
|---|---|
| Code | GitHub `naveen-raj-kanagaraj/viewership-tracker` (public repo; never commit secrets or player data) |
| Running copy | Owner's Mac: `~/Downloads/Projects/viewership-tracker` |
| Python | `~/my-agent/venv/bin/python` (shared venv with the owner's separate agent repo) |
| Database | `data/tracker.db` in the running copy (git-ignored). Back it up before risky changes. |
| Public link | Cloudflare tunnel (`tracker/tunnel.py`, env `EVENT_TUNNEL_NAME` / `EVENT_PUBLIC_URL`) to port 8092 |
| Secrets | `.env` in the running copy (git-ignored). Names are in `.env.example`; values never go in chat or git |

Start / update on the Mac:

```bash
cd ~/Downloads/Projects/viewership-tracker && git pull
~/my-agent/venv/bin/python track.py            # Ctrl+C to stop; runs counter + discovery + India scan + web
```

The owner's other repo, `naveen-raj-kanagaraj/strategic-agent` (cloned at `~/my-agent` on the Mac), is a separate
Telegram/news agent. It used to contain this tracker; the tracker was split out and the agent's copy disabled
(`EVENT_WEB_ENABLED=false` there). Do not run git commands for one repo inside the other's folder (that wiped the
tracker folder once; it was re-cloned).

## Rules (owner's standing instructions)

- Never print `.env` values, never ask the owner to paste keys into chat, never commit secrets. Repo stays public.
- Predict & Win player data (Instagram handles, picks) never goes to GitHub: `exports/private/` is git-ignored.
- Never write the live SQLite database from another machine or over a shared/mounted folder (it corrupted the `kv`
  index once; fixed with `REINDEX kv`). Give the owner `sqlite3` or `track.py` commands to run on the Mac instead.
- Test before shipping: `python tests/test_plat.py` and `python tests/test_scene.py` (mocked platforms, temp database), then render pages in headless Chromium (desktop and
  390px phone), check for page errors, then PR and merge. Owner wants it accurate, efficient, no filler.
- Style of the site: dark (`#0b0b12`), lime `#b6f23a`, red labels `// LIKE THIS`, fonts Chakra Petch + Share Tech
  Mono, Indian number format (`1,82,200`). No emojis or em dashes in copy.

## Code map

| File | What it does |
|---|---|
| `track.py` | CLI and entry point. `python track.py` runs everything; see its docstring for all commands |
| `tracker/events.py` | Tournament tracking: `PRESETS` (per-event config), YouTube discovery (`poll`, every 60s), live counter (`fast_tick`, every 2s), `stats()` |
| `tracker/platforms.py` | Kick and Twitch connectors (ids `kick:<slug>`, `twitch:<login>`), batched counts, keys from `.env` |
| `tracker/eventpage.py` | Tournament dashboard HTML/JS (one big template), share cards, history chart (`HIST`) |
| `tracker/scene.py` | India scan: one `cycle()` every 2 min, game/category classifier (`GAMES`), YouTube searches (`QUERIES`), storage, `data()` for the pages |
| `tracker/scenepage.py` | Front page and category pages (same template; `CAT` empty on the hub), share cards |
| `tracker/web.py` | Flask routes, response cache (`_memo`), CDN cache headers |
| `tracker/eventlog.py` | Telegram alerts (NOT LIVE roster alert), xlsx log |
| `tracker/dataexport.py` | CSV/xlsx exports every 10 minutes to `exports/<event>/` |
| `tracker/predict.py`, `predictpage.py`, `crowd.py`, `crowdpage.py` | Predict & Win game and its results page |
| `tracker/store.py` | SQLite connection (WAL) and the `kv` table |
| `tracker/tunnel.py` | Cloudflare tunnel |

## Site routes

| Route | Page |
|---|---|
| `/` | India hub (default). `track.py home bmic` makes an event the front page for a tournament day; `track.py home hub` switches back |
| `/india` | India hub, always |
| `/c/<slug>` | One game/category |
| `/api/scene?period=today\|7d\|30d&cat=<slug>` | JSON behind the hub and category pages (cached 20s) |
| `/e/<key>/` (+ `data`, `series`, `daystreams/<date>`) | One tournament dashboard |
| `/events` | List of tournaments |
| `/predict` | Predict & Win (results page when `PREDICT_OPEN=0`) |
| `/data`, `/series`, `/daystreams/<date>` | Data for the home event (old links) |

## Data (SQLite, `data/tracker.db`)

| Table | Holds | Kept |
|---|---|---|
| `kv` | JSON settings: `events`, `scene_seeds`, `scene_blocked`, `site_home`, `event_home`, `event_next:<key>`, `event_stop:<key>` ... | always |
| `ev_streams`, `ev_samples`, `ev_fine`, `ev_ticks`, `ev_anomalies` | Tournament streams, 30s per-stream readings, 2s readings, 2s totals, flagged jumps | always |
| `sc_channels` | Every channel the India scan has seen (`yt:<channel id>`, `kick:<slug>`, `twitch:<login>`) | always |
| `sc_samples` | Each live channel's viewers per scan | `SCENE_KEEP_DAYS` (14) |
| `sc_daily` | Per IST day, channel and category: peak, minutes live, hours watched | always (leaderboards) |
| `sc_cat` | Per scan: total viewers and streams per category and India (`__all__`) | always (charts, peaks) |
| `pw_*` | Predict & Win players and picks (private) | always |

## How the India scan counts (`tracker/scene.py`)

Every `SCENE_SEC` (120s):
1. Kick and Twitch: every live stream in `SCENE_LANGS` (default `hi`), top 100 per language, needs the platform keys.
   Plus channels added by hand (`track.py scene add kick <slug>`; Kick works without keys via its public pages).
2. YouTube (no key needed): YouTube's own Live page for India + ~38 India-localised live searches (games, languages,
   news, devotional, music, cricket, talk) every `SCENE_YT_SEC` (300s; 15 min while a tournament broadcast is live so
   the 2s tournament counter keeps priority). Every YouTube stream already found is re-counted each scan from the
   live counter. Hand-added `@handles` are checked every 10 min.
3. Streams under `SCENE_MIN_VIEWERS` (20) are dropped. A channel is one streamer; two streams at once are summed.
4. Category = platform category (Kick/Twitch) or title keywords (YouTube), first match in `GAMES`; else `Other`.

It is not a census. YouTube has no "all live streams in India" list; anything not on the Live page, in the searches
or added by hand is missed. The page says totals are a floor. To widen it: add to `QUERIES`, add channels by hand,
add Kick/Twitch keys and languages.

Commands: `track.py scene top [today|7d|30d]`, `scene probe`, `scene add|remove <youtube|kick|twitch> <channel>`,
`scene block|unblock <name>`.

## How tournaments work (`tracker/events.py`)

A tournament is a preset in `PRESETS` (name, match words, YouTube searches, official channel ids, permitted
watch-party allow-list, `always_check` handles, `next_start` countdown in IST, `hist` place in the BGMI history
chart, `roster`, `ended`). Lifecycle:

1. Add the preset, `track.py create <key>`. The dashboard shows a countdown until the official stream is live.
2. While live it records only when the official broadcast is live (`need_official`). Between days, on the Mac:
   - next countdown: `sqlite3 data/tracker.db "INSERT INTO kv(key,value) VALUES('event_next:bmic','\"2026-10-31 13:00\"') ON CONFLICT(key) DO UPDATE SET value=excluded.value;"`
   - stop recording after the show until an epoch time: same with `'event_stop:bmic','<epoch>'`, or `track.py pause bmic` / `resume bmic`.
3. After the last day set `"ended": True`; it stops searching and the page shows history + by-day breakdown.

Other games and platforms: `track.py new <key> "<Name>" --game ...`, then `track.py kick|twitch <key> official|add|category ...`.

## Current state (update this)

As of 26 Oct 2026:
- BMSD 2026: finished, peak 653K. Results and Predict & Win winners published.
- BMIC 2026: preset ready, countdown to 30 Oct 2026 13:00 IST, official KRAFTON INDIA ESPORTS channel only.
  Its watch-party list is empty (`allowed: []`, `official_only: True`, `ROSTERS["bmic"] = []`) until the owner
  sends it; when it arrives fill `allowed`, `always_check`, `ROSTERS["bmic"]` and remove `official_only`.
- India hub and category pages: built and tested against mocked YouTube/Kick/Twitch responses. Not yet verified
  against the real platforms (the build environment could not reach them): run `track.py scene probe` on the Mac.
- Kick/Twitch keys: not added yet (owner creates developer apps and puts them in `.env`).
- Owner wants to move hosting from the Mac to Oracle Cloud (Always Free A1.Flex Ubuntu); not done yet.

## Ideas not built yet

- YouTube Data API key path for channel country (to confirm a channel is Indian) and exact counts.
- More Indian platforms (Loco, Rooter) if they expose live counts.
- Per-streamer pages (`/s/<sid>`) with their history.
- Weekly auto-posted share cards.
