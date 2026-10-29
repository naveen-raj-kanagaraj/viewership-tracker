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

Hosting (since 26 Oct 2026): Oracle Cloud, us-chicago-1, VM.Standard.A1.Flex (2 OCPU / 12 GB, Always Free) on a Pay As You Go account, Ubuntu 24.04, `tracker` systemd service in `/home/ubuntu/viewership-tracker`. Deployed with `scripts/deploy_oracle.sh`; managed from the Mac with `scripts/oracle.sh` (server IP and key path are in the Mac's git-ignored `.server`). The Mac copy must stay stopped. YouTube scraping works from the server (checked at deploy). Nightly backups land on the server; `oracle.sh backup` copies the newest to the Mac.

Backups and moving: the database is copied every night to `backups/` (`tracker/backup.py`, newest 3, git-ignored);
`python track.py backup` makes one now. `docs/MOVING.md` is the step-by-step for a new machine, server or domain
(code from GitHub + `data/tracker.db` + `.env`). The site's own address comes from `EVENT_PUBLIC_URL`.

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

## Site layout (owner's brief, 26 Oct: "a user must understand it at a glance")

Every page: sticky top bar (brand, INDIA | GLOBAL, updated), section menu (Overview, Gaming, Esports, IRL, Just
Chatting, News, Music, Sports, Devotional, Podcasts & Talk, Other with live viewers), breadcrumb, one-line intro,
KPI row (Watching now with platform split, Live channels, Peak today, Hours watched today, Biggest stream now).
Overview adds section cards and games grid; then Top live streams | Top streamers today (LIVE + viewers, or
"Last live 2 h ago"), Live tournaments, chart, "How these numbers are counted". Section pages (`/s/<key>`) show their
games/categories; Esports ranks tournaments. Numbers move every 2s (`/api/scene/live`), rankings every 30s.

Phones are the main audience (owner, 26 Oct). Under 600px: section menu becomes icon pills (active one scrolled into
view), KPIs in a 3-column grid, sections as compact tiles (empty ones hidden), games and tournaments as swipeable rows,
list controls shortened. A BETA badge sits next to the brand while the site is being tested. Check every UI change at
390px wide (no horizontal overflow) as well as desktop.

## Updates without touching the Mac

`tracker/autoupdate.py`: the running tracker checks GitHub every `AUTO_UPDATE_MIN` (10) minutes, fast-forwards to
origin/main if the folder has no hand edits, checks everything compiles (else rolls back), and restarts itself in
place. Never during a live tournament broadcast. `AUTO_UPDATE=false` turns it off. So: merge to main = live on the
site within ~10 minutes. New Python packages in requirements.txt still need `pip install` by hand.

## Site routes

| Route | Page |
|---|---|
| `/` | Worldwide overview (default). `track.py home bmic` makes an event the front page for a tournament day; `track.py home hub` switches back |
| `/india`, `/india/s/<key>`, `/india/c/<slug>` | India overview, sections, games |
| `/s/<key>` | One section worldwide (gaming, esports, irl, just-chatting, news, music, sports, devotional, podcasts, other) |
| `/c/<slug>` | One game/category worldwide |
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

## India and Global (owner's choice, 26 Oct: the site opens on Global; India is the INDIA tab; track everything)

One scan finds both. Every channel is stored with `sc_channels.india` (1/0). Global pages (`/`, `/s/<key>`, `/c/<slug>`) show
everything; India pages (`/india`, `/india/s/<key>`, `/india/c/<slug>`) show india=1. Old `/global...` links redirect. Global sources: Twitch top
`SCENE_TWITCH_PAGES`x100 streams + official esports channels (`ESPORTS_TWITCH`), Kick top 100, YouTube's Live page
(US edition) and `GLOBAL_QUERIES` (US edition). Non-Indian streams under `SCENE_GLOBAL_MIN` (100) are left out.
Per-scan totals: India in `sc_cat`, Global in `sc_reg` (region 'global'), tournaments in `sc_reg` ('tour:in',
'tour:global'). Raw readings kept `SCENE_KEEP_DAYS` (3: the global scan writes ~1,000+ rows per scan).

**Live tournaments:** `tournament(title, game)` matches named tournaments (`TOURNAMENTS`: VCT, LCK, IEM, BLAST, PGL,
TI, EWC, PMGC, BGIS, BMIC, FFWS, MPL, RLCS ...; add new ones there) or a generic tournament word plus a match word
(Grand Final + vs/Day/Stage...), never scrims/ranked. Streams of the same tournament (official + co-streams) are
grouped; `TOUR_GAME` sets the game. Shown in the "Live tournaments" section with today's peak.

## How the India scan counts (`tracker/scene.py`)

Every `SCENE_SEC` (120s):
1. Kick and Twitch (needs the platform keys): every live stream in `SCENE_LANGS` (default `hi`), plus the top 100
   overall and in the main Indian categories (`SCENE_KICK_CATS`, `SCENE_TWITCH_CATS`) whose title is in an Indian
   script or names India/Hindi/Tamil/BGMI/Indian cities (`INDIA_MARK`). No platform exposes country.
   Plus channels added by hand (`track.py scene add kick <slug>`; Kick works without keys via its public pages).
2. YouTube (no key needed): YouTube's own Live page for India + ~38 India-localised live searches (games, languages,
   news, devotional, music, cricket, talk) every `SCENE_YT_SEC` (300s; 15 min while a tournament broadcast is live so
   the 2s tournament counter keeps priority). Every YouTube stream already found is re-counted each scan from the
   live counter. Hand-added `@handles` are checked every 10 min.
Between scans, every live Kick/Twitch channel is re-read every `SCENE_FAST_SEC` (2s, one batched request per
   platform, backs off to 30s on errors) and the page polls `/api/scene/live` every 2s; rankings and charts every 30s.
   The platforms refresh their own counts about every 30-60s, so the 2s readings often repeat. The biggest
   `SCENE_YT_FAST_N` (25) YouTube channels are re-counted every 2s from the live counter (`yt_fast_once`, every 10s
   while a tournament broadcast is live, backs off if YouTube refuses); the rest once per scan (2 min).
   Logos: YouTube channel page picture (`events.avatar`), Twitch users API, Kick users API (fallback: public page).
   Category art (`resolve_art`): exact names only. Twitch box art by the game's Twitch name (`TWITCH_NAMES`), else
   Kick's category image by exact name (`KICK_NAMES`), else initials; never a near match (BGMI, PUBG: Battlegrounds
   and PUBG Mobile are separate games and covers). `NO_ART` names that cover several games (Call of Duty, EA Sports
   FC, Cricket games) get no art. Files in `static/gameart/<slug>.png|webp|jpg` win over everything. Cached in kv
   `cat_art2:<game>` (delete the key to refetch). `scene probe` prints where each main game's cover comes from.
Who counts as Indian (`verdict()`): YouTube channels by their own country setting (YouTube Data API with
   `YOUTUBE_API_KEY`, else the channel's About page; cached in `sc_channels.country`): India = yes, another country =
   no. No country set, and all Kick/Twitch (no country exposed): Hindi language tag (Kick/Twitch), or an Indian script
   or Indian words in the title/name. Hand-added (`scene add`) and `scene allow` always count; `scene block` never.
   Rejected channels are kept in `sc_channels` with `india=0` and hidden. `scene clean` re-judges everything and
   deletes non-Indian readings. Twitch's Hindi tag is small and partly mis-tagged (Japanese/Korean channels), so
   Indian Twitch streamers mostly need adding by hand.
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
- Hosting: Oracle Cloud (us-chicago-1, A1.Flex, Ubuntu 24.04), systemd service `tracker`; the Mac copy stays
  stopped. Code reaches the server by itself: tracker/autoupdate.py pulls merged commits every 10 min.
- Site: worldwide dashboard at `/`, India at `/india`, sections `/s/<sec>`, games `/c/<slug>` (India: `/india/...`).
  Fonts: Barlow + Barlow Condensed (replaced Chakra Petch / Share Tech Mono on 26 Oct, owner wanted a less generic look).
- Overview event cards show only live/upcoming tournaments (BMSD 2026 finished, so it moved off the front page).
  Game pages list that game's tournaments (BGMI: BMIC countdown, BMSD finished) and the all-time peaks chart from
  `scene.GAME_HISTORY` (moved from the event page; tracked events add their recorded peak by their `hist` key).
- Peak today shows the channel that led at that moment (`peak_lead` in `scene._kpis`).
- Search (top-bar magnifier, or `/` key): `/api/search?q=&region=` over every channel ever seen live (sc_channels).
- `/map`: 3D globe (d3 orthographic on canvas, d3/topojson/world-atlas from jsdelivr), data `/api/geo`
  (`scene.geo`). Country = YouTube channel country, India-detected streams = India, Kick/Twitch by single-country
  language (`scene.LANG_COUNTRY`, marked estimated); the rest is counted as unknown and disclosed on the page.
- Front page (27 Oct, owner said it felt overwhelming): 4 KPIs + a spinning globe card (iframe `/map?embed=1`),
  empty sections hidden, tournaments card only when one is live, "Day by day" bar chart (`data()["daily"]`: peak and
  hours watched per IST day, 30 days) with the old line as a toggle.
- Tap any streamer row: analytics drops open under it (`/api/channel?sid=`, `scene.channel`): today / 7 / 30 days /
  all time peak, average, hours watched, hours streamed, days live, 30-day bars, last-3-days line, recent days.
  Total views are not shown: Kick/Twitch don't publish them for live streams.
- Game history chart on game pages is the event page's original line chart with event logos (`/elogo/`).
- Globe: spins 24 deg/s, labels countries (top 3 ranked gold/silver/bronze), faint names for big empty countries,
  per-country categories filter that country's stream list (India links to `/india/c/<slug>`).
  `LANG_COUNTRY` also places pt->BR, de->DE, fr->FR, ru->RU, nl->NL (estimated).
- All pages (event, predict, crowd too) use Barlow / Barlow Condensed.
- 27 Oct fix: YouTube counts shown rounded ("10.56K watching") were read by stripping non-digits (= 1,056). Now
  `platforms.parse_count` handles K/M/lakh/crore, and the live counter prefers YouTube's exact originalViewCount.
  Peaks recorded before this fix can be 10x too low for YouTube channels in the 1K-100K range.
- Rankings: `/rankings`, `/india/rankings` (rankpage.py, `/api/rank`, `scene.rankings`): day / week / month to any
  date, by hours watched / peak / average / hours live, filtered by category, streamer country, platform; podium, rank
  arrows vs the previous period, share-top-10 image. The dashboard's board shows the top 10 with arrows and links here.
- Streamer panel has SHARE: a 1080x1350 card with rank, peak, 7d average, 30d hours, all-time peak, 30-day bars.
- Worldwide scan also reads YouTube's Live page for 20 countries (`SCENE_YT_COUNTRIES`), so the globe fills in.
- Categories without cover art get an icon tile (cricket, football, news ...), never letters.
- Numbers count up and list rows glide to new ranks (FLIP); off with prefers-reduced-motion.
- Super Chats (tracker/ytextra.py): live chat of the top `SUPERCHAT_TOP`=50 YouTube streams is read every 5-15s
  (chat popout page -> youtubei live_chat/get_live_chat). Paid messages, stickers, memberships, gifts stored once each
  in `sc_superchat`, converted with open.er-api.com daily rates (built-in fallback). Shown in the streamer panel and
  as the "Super Chats" ranking. Check from the server: `track.py scene superchat <video id> 60`.
  Not verified against live YouTube from the build environment (no access): if the probe finds nothing on a stream
  with visible Super Chats, the chat page format changed.
- Channel stats: `sc_chstats` daily snapshot (subs, total views, videos) of YouTube channels seen live, most watched
  first, up to `CHANNEL_STATS_MAX`=3000/day; YouTube Data API if YOUTUBE_API_KEY, else About pages (~120 every
  15 min). "Views gained" ranking + panel. Check: `track.py scene stats @handle`. Only channels that have gone live
  are covered; channels that never stream are not discovered.
- Channel pages `/ch/<sid>` (`/india/ch/<sid>`, chpage.py): header + Watch button, the full analytics panel, and
  "Streams, last 30 days" from the platform (`/api/past`, `ytextra.past_streams`: YouTube channel Live tab HTML,
  Twitch helix/videos archives; Kick has no public list). Search matches channel names and stream titles and opens
  these pages. Third-party trackers (Playboard, Streams Charts) are not scraped: their terms forbid it.
- 28 Oct: search froze the site (per-row MAX(peak) over sc_daily with no sid index, under the DB lock). Indexes
  sc_daily(sid, day) and sc_samples(sid, ts) added. Search also asks YouTube's channel search (`/api/ytsearch`);
  opening any YouTube channel adds it (sc_channels.tracked=1) and snapshots its subscribers/total views daily, first.
  Channel page "Channel views on YouTube": daily views gained chart, 7/30-day and monthly totals.
- Coverage: Twitch top 2000 (SCENE_TWITCH_PAGES=20, stops under 100 viewers), Kick top 100 + top 100 in its 12
  biggest categories, YouTube Live page + 4 "more" pages per country edition.
- CEGC countdown: preset `cegc` (auto-created at startup), Kick `cegc` official, starts 2026-11-03 13:30 IST.
  Its game isn't set: add "game" to the preset when known.
- India esports page shows the BGMI tournament history chart.
- Moments (tracker/moments.py, momentpage.py, `/moments`, `/api/moments`): every 2s reading of the top Kick/Twitch
  and YouTube streams is watched for jumps (>= 25% and >= 1,500 over ~1 min, base >= 1,000, stream live 5+ min, one
  per channel per 15 min). YouTube links/embeds start 30s before (stream start from the watch page); Twitch gets a
  real clip when an account is connected (`track.py twitch-login`, device code, tokens in kv twitch_user, max 20
  clips/hour), else the replay at the time; Kick links the channel. `track.py moments` lists them.
- Per-scan totals (sc_cat, sc_reg) older than 35 days are compacted to the highest reading per 10 minutes, hourly,
  a few days at a time (kv scene_compacted).
- Moments v2 (28 Oct): chat speed (tracker/chat.py: Twitch anonymous IRC for the top 150, Kick Pusher websocket for
  the top 80 (needs chatroom ids from kick.com/api/v2, may be blocked), YouTube from the Super Chat reader) plus
  viewers, both judged against the stream's own normal (robust z-scores). Raids, first 10 minutes and recovery after a
  break excluded. `track.py scene chat 60` shows the chat readers working.
- Lookup for any channel: `/api/lookup` (YouTube channel search, Twitch helix/search/channels, Kick exact slug).
  Opening a channel follows it daily: YouTube subs/total views (sc_chstats), Twitch followers (needs the connected
  account from twitch-login), Kick followers (kick.com/api/v2, unofficial). Channel page shows views/followers gained
  and YouTube's latest uploads. `track.py scene lookup <name>` checks it.
- YouTube players on the site need a referrer: iframes set referrerpolicy=strict-origin-when-cross-origin (the
  site-wide header is no-referrer, which makes YouTube show "Video player configuration error").
- Channel videos (29 Oct): `yt_videos` table, `ytextra.channel_videos/videos_summary`, `/api/videos`. A year of
  uploads and past live streams per YouTube channel (refreshed every 6 h when the page is opened). With
  YOUTUBE_API_KEY: uploads playlist + videos.list (exact dates, views, likes, comments; ~1 quota unit per 50 videos).
  Without: the Videos/Live tabs with "load more" continuations (dates approximate, views only). Channel page: range
  1W/1M/3M/6M/YTD/1Y, all/uploads/live, chart by post date, engagement = (likes + comments) / views.
- About-page reader fix: total views are read only inside aboutChannelViewModel (it used to grab a video tile's
  views). Old About-based YouTube snapshots were deleted once (kv chstats_fix_about).
- Channel performance (29 Oct): video kind from YouTube's per-channel playlists UULV<id> (live streams) and
  UUSH<id> (Shorts); premieres are normal videos (the API gives them liveStreamingDetails too). yt_videos.short
  added; all rows re-read once (kv ytv_fix_premieres). Channel page: lifetime row, range/kind/metric pickers, line
  chart per post with median, best day/time (IST) and format insights, "vs median", 1080x1350 share card.
  Engagement = (likes + comments) / views over the posts in range.
- Speed (29 Oct): web._memo is stale-while-revalidate (expired copies served instantly, rebuilt in a background
  thread); web._warm_forever keeps the busiest pages/APIs built every 10 s; pages get Chrome speculation-rules
  prerender on hover and a prefetch-on-touch fallback (web.FASTNAV); the dashboard starts its data fetch in <head>.
- Channel videos for YouTube, Twitch (helix/videos type=all) and Kick (kick.com/api/v2/channels/<slug>/videos);
  first visit fetches the whole history (YouTube with key: up to 3,000), then served from the DB with background
  refresh (last 60 days every 6 h, everything weekly; kv vids:<sid>). "ALL TIME" range.
- Ranks (tracker/ranks.py): every 30 min, per platform: size (subs/followers), growth (YouTube views / followers
  gained, 30 d), live (hours watched, 30 d), worldwide / country / category (YouTube topic tags via the API) / game,
  among channels tracked. Channel page badges; Rankings page "Channels" mode (`/api/topch`).
- Discovery: ytextra.discover_once adds channels from YouTube channel search (games/topics x countries), 2 searches
  every 15 min; daily stats now up to 2,000 channels per run with the API key (CHANNEL_STATS_MAX 50,000/day).
- Kick seeds always include `skyesports` and `cegc` (`scene.ALWAYS`); "CEGC" is also a tournament name.
- v16 (29 Oct): Home = KPIs, then "Top today" cards of 5 (live now, streamers today, YouTube channels by views
  gained in the last day, trending videos of the last 3 days, top moments) with a category dropdown that filters all
  of them (`/api/home?region=&cat=`), then games live, tournaments, chart. On phones the globe moves below the cards.
  Nav: Overview, Rankings, Moments, World map, Compare, sections. Category pages add Biggest channels (main game =
  this one, uploaders and streamers), channels today, trending videos, moments. yt_videos.game is tagged by
  scene.classify; a channel's game = most common game of its last 40 posts.
- Same creator on several platforms: `ytextra.linked` (hand links in kv chan_links via `track.py scene link A B` /
  `unlink`, else exact normalized-name match of 5+ chars). Channel page shows platform pills and COMPARE.
- `/compare?c=sid,sid` (up to 4, any platform): lifetime, posts in range, live, ranks, avg views per post chart,
  per-day growth chart (`/api/compare`). Channel range default is 30D (7D/30D/90D/6M/YTD/1Y/ALL).
- Moments: sort by peak viewers by default (MOST WATCHED / BIGGEST JUMP / HYPE / NEWEST); a YouTube moment only
  embeds when its start offset is known and the stream has ended (else "replay when it ends"), never from 0:00.
- Daily channel views: no public source gives past days. Every tracked channel is snapshotted daily from now on;
  "views per day" fills in after two snapshots. Gains are divided by the day gap and >25%-of-total jumps ignored.
- Back button (29 Oct): web.FASTNAV adds a BACK arrow to the top bar of every page except / and /india (goes back
  in history when the visitor came from this site, else to the dashboard). Phones: channel page hides the top links,
  map hides GLOBAL/INDIA and the clock so nothing overflows.
- v18 (29 Oct): YouTube categories are YouTube's own 15 (ytextra.YT_CATS / CATEGORIES, alphabetical): a channel's
  category = the categoryId most of its last 40 videos carry (sc_channels.ytcat, needs the API key), else its topic
  tags mapped to the nearest one (topic_of). Home dropdown: "YouTube categories" + "Games & categories live now",
  both alphabetical; a YouTube category filters every card (`/api/home?topic=`). Home leads with "Top YouTube channels
  today" (views gained). Rankings opens on CHANNELS (YouTube: views today / 7d / 30d / total views / subscribers / live
  hours; Twitch, Kick: followers and follower gains), filters: YouTube category, game, country. ranks.METRICS adds
  views, vday, v7. Live streamers stay one tab away (`/rankings?mode=live`).
- Creator badges (tracker/badge.py): `/badge/<sid>.svg?m=<metric>&s=<scope>`, a live image of one rank (only ranks
  among 10+ channels), cached 30 min. Channel page "Creator badge" card: pick a rank, copy HTML / Markdown / link,
  download PNG. `/api/badges?sid=`.
- Home event cards: upcoming tournaments sorted soonest first (BMIC 30 Oct, then CEGC 3 Nov).
- v19 (29 Oct): Visitors are now counted on every page (web.FASTNAV pings /hit every 30 s; event pages keep their
  own ping). Owner page `/admin/visitors?key=<ADMIN_KEY>`: 404 unless ADMIN_KEY (16+ chars) is set in .env.
  India visitors land on /india: WEB.REGIONJS runs in <head> of "/" and redirects when the device time zone is
  Asia/Kolkata, unless the visitor picked GLOBAL/INDIA before (localStorage lge_region). Done in the browser so the
  CDN can keep one cached copy of "/".
- Tournament cards (BMIC, CEGC) only on India pages. Home: 6 cards (adds "Most subscribers gained"), "See all"
  scrolls inside the card. Category dropdown always lists every game in scene.GAMES (BGMI, Free Fire ...) plus
  whatever is live, alphabetical. Channel lines show the YouTube category, not the live game.
- Same-day views: sc_intra keeps readings for 3 days (daily stats + a fresh reading when a channel page is opened,
  at most hourly, 1 API unit). views_series()["recent"] = views/subs gained between the first and latest reading.
- Search results (`/api/lookup`) are followed at once (ytextra.track_found, tracked=1): daily stats start without
  anyone opening them. /api/videos while still loading is cached 3 s, not 5 min (X-Short-Cache), and the channel
  page polls until the videos arrive. Day-over-day gains ignore jumps over 25% (views and subscribers).
- v20 (29 Oct): Accuracy. ytextra._sane drops impossible YouTube readings (lifetime views below the channel's own
  biggest video, or a total down >2%); stored ones were deleted once (kv chstats_fix_below_video). intra_once takes
  hourly readings of up to 1,250 channels per 15-minute run (25 API units), so channels show "views, last N hours"
  the same day. Twitch full count (scene.twitch_full_once, every 5 min, all live streams) replaces the tracked Twitch
  number on the worldwide overview (_with_full); peak today takes the full total into account (kv allpeak).

## Ideas not built yet

- YouTube Data API key path for channel country (to confirm a channel is Indian) and exact counts.
- More Indian platforms (Loco, Rooter) if they expose live counts.
- Per-streamer pages (`/s/<sid>`) with their history.
- Weekly auto-posted share cards.
