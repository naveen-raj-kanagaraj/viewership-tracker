# Live Viewership Tracker

Measures how many people are actually watching an esports tournament on YouTube, counting every stream carrying it at once: the official broadcast, permitted watch parties and community restreams. Produces peak concurrent viewers, average concurrent, hours watched and airtime, split by day and by channel.

Built because published tournament viewership arrives days late, covers the official broadcast only, and misses the watch parties. In Indian esports the watch parties are often a third of the total audience, so a number that ignores them understates the event.

No API key is required. Viewer counts are read from public YouTube pages through yt-dlp. A YouTube Data API key can be supplied for more exact counts.

<!-- Replace with a screenshot of the running dashboard -->
![Dashboard](docs/dashboard.png)

---

## What it does

**Finds the streams.** Every 60 seconds it searches YouTube for live streams matching the event's phrases, and checks a list of known channels directly. A stream that drops out of search ranking is re-checked for 15 minutes before being treated as ended, so a ranking change is not recorded as the audience leaving.

**Counts them.** Every 2 seconds each live stream is re-counted. Streams under 50 viewers are re-counted less often, so the budget goes where the audience is.

**Classifies them.** Each stream is labelled official, watch party or community. An allow-list decides which watch-party channels count, which keeps unrelated streams that happen to mention the tournament out of the totals.

**Catches bad readings.** When a stream ends, YouTube's watch page can report total views where a live viewer count used to be. Left alone that lands as a sudden spike. A jump or drop above a size and percentage threshold inside ~15 seconds is held as unconfirmed until the next reading agrees with it, and is recorded as an anomaly either way.

**Serves it.** A dashboard shows the live total, the per-stream breakdown, per-day peaks and the event's place in BGMI viewership history. It is served locally and can be exposed through a cloudflared tunnel without a server.

## Metrics

| Metric | How it is derived |
|---|---|
| **Peak concurrent** | Highest combined total across all live streams at one moment, not the sum of each stream's individual peak |
| **Average concurrent** | Mean of the combined totals, measured only while the official broadcast was live |
| **Hours watched** | Concurrent viewers integrated over time |
| **Airtime** | How long each stream was live |
| **Official / watch party / community split** | The same totals attributed by stream type |
| **Anomalies** | Jumps and drops that failed confirmation, kept for audit rather than discarded silently |

Peak concurrent is the combined figure at a single moment, which is the comparable number and is always lower than adding up per-stream peaks, since streams peak at different times.

## Install

```bash
git clone https://github.com/naveen-raj-kanagaraj/viewership-tracker
cd viewership-tracker
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Use

```bash
python track.py create bmsd      # start tracking an event
python track.py                  # run the tracker and the dashboard
python track.py events           # events and their state
python track.py stats bmsd       # peak, average, per day, per channel
python track.py export bmsd      # CSV and xlsx exports
python track.py pause bmsd       # stop recording, keep serving history
```

The dashboard runs at `http://localhost:8092`.

An event is defined by the phrases that identify it, the channels allowed to restream it and the official broadcaster. `bmsd` ships as a worked example in `tracker/events.py`. Adding another event means adding one entry to `PRESETS`.

## Data

Everything is stored in one SQLite file, `data/tracker.db`, written ahead of time with WAL so the live counter can write while the dashboard reads.

| Table | Holds |
|---|---|
| `ev_streams` | One row per stream found, with its peak and airtime |
| `ev_samples` | Viewer counts per stream, one row per sample |
| `ev_fine` | High-resolution readings behind the live graph |
| `ev_ticks` | Combined totals per moment, with the official / watch party / community split |
| `ev_anomalies` | Flagged jumps and drops, with the reading before and after |

`python track.py export` writes analysis-ready files to `exports/<event>/`: viewership at 2-minute resolution, every stream in long format, and daily peaks, as CSV and xlsx.

## Predict & Win

A prediction game runs on the same dashboard, at `/predict`: viewers pick outcomes, scores resolve when the answers are set, and a leaderboard ranks them. It exists to give the dashboard a reason to be revisited between matches rather than only during them.

Player handles are treated as private. They are written to `exports/private/`, which is gitignored and never pushed. The public export carries questions, answers and the crowd split with no player data.

Set `PREDICT_OPEN=1` to accept entries. With it off, the page shows what the crowd predicted and how it turned out.

## Migrating from the agent

This tracker previously ran inside a larger personal agent. To bring that data across:

```bash
python migrate_from_agent.py ~/path/to/my-agent/data/agent.db --dry-run
python migrate_from_agent.py ~/path/to/my-agent/data/agent.db
```

It copies the event tables, the prediction game and the related key-value rows, and leaves everything else in the agent alone. The source database is opened read-only. Running it twice does not duplicate rows.

## Limits

**YouTube only.** Events also stream on Loco, Rooter and JioCinema in India, and those are not counted. The totals are YouTube totals and are labelled as such.

**Concurrent viewers are YouTube's number.** What is recorded is what YouTube reports, including however it counts a viewer. The tracker's contribution is combining streams, attributing them and catching bad readings, not auditing YouTube.

**The allow-list is a judgement.** Which watch parties count is a decision, and a different allow-list gives a different total. It is kept explicit in `PRESETS` rather than hidden in a heuristic.

**Discovery depends on search.** A stream that never surfaces in search and is not on a known channel is missed. The known-channel list exists to narrow that gap, not to close it.

**Sampling is every 2 seconds.** A spike shorter than that is not seen.

## Configuration

Copy `.env.example` to `.env`. Every setting is optional.

| Variable | Default | Purpose |
|---|---|---|
| `YOUTUBE_API_KEY` | none | Exact counts from the official API instead of public pages |
| `EVENT_FAST_SEC` | `2` | How often live streams are re-counted |
| `EVENT_POLL_SEC` | `60` | How often YouTube is searched for new streams |
| `EVENT_TZ` | `Asia/Kolkata` | Timezone for day boundaries |
| `EVENT_WEB_PORT` | `8092` | Dashboard port |
| `EVENT_PUBLIC_LINK` | `true` | Public link through cloudflared |
| `PREDICT_OPEN` | `0` | Whether the prediction game accepts entries |
| `TRACKER_DB` | `data/tracker.db` | Database location |

## Layout

```
track.py                 CLI: run, stats, export, event management
tracker/events.py        discovery, counting, classification, anomalies, statistics
tracker/eventpage.py     the dashboard
tracker/web.py           Flask server
tracker/store.py         SQLite
tracker/tunnel.py        public link via cloudflared
tracker/eventlog.py      spreadsheet exports and alerts
tracker/dataexport.py    analysis-ready CSV and xlsx
tracker/visitors.py      dashboard traffic
tracker/predict.py       prediction game
tracker/crowd.py         crowd results once the game closes
migrate_from_agent.py    one-off import from the agent database
```
