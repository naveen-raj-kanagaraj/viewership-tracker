# Moving the tracker (new computer, a server, or a new domain)

Everything that runs the site is in three places. Move all three and it carries on exactly where it stopped.

| What | Where | In git? |
|---|---|---|
| Code | GitHub `naveen-raj-kanagaraj/viewership-tracker` | yes |
| Data: every reading, streamer, tournament, leaderboard, Predict & Win players | `data/tracker.db` (one SQLite file) | **no** (private data) |
| Keys and settings | `.env` | **no** (secrets) |

Optional, also not in git: `cookies.txt` (YouTube cookies, if you made one), `static/gameart/` files you added
(those are in git only if you committed them), `exports/private/` (Predict & Win player exports).

## Keep a copy (do this regardless of moving)

The tracker saves a copy of the database every night to `backups/` (newest 3). Make one any time with:

```bash
python track.py backup
```

Those copies sit on the same disk. To keep one off the Mac, set `BACKUP_DIR` in `.env` to a synced folder, e.g.
iCloud Drive: `BACKUP_DIR=~/Library/Mobile Documents/com~apple~CloudDocs/tracker-backups`. Never put a backup or
`.env` on GitHub: the repo is public.

## Move to another computer or server

1. On the old machine: stop the tracker (Ctrl+C), then `python track.py backup` (or just copy `data/tracker.db`
   while it is stopped).
2. On the new machine:
   ```bash
   git clone https://github.com/naveen-raj-kanagaraj/viewership-tracker.git
   cd viewership-tracker
   python3 -m venv venv && venv/bin/pip install -r requirements.txt
   mkdir -p data
   ```
3. Copy across (AirDrop, USB, scp, a synced folder): the backup as `data/tracker.db`, and `.env` (plus `cookies.txt`
   if you have one). Never send `.env` through chat or email.
4. Start it: `venv/bin/python track.py`. Check: `venv/bin/python track.py scene top` shows your history.
5. The public link: the Cloudflare tunnel (`EVENT_TUNNEL_NAME` in `.env`) needs its credentials on the new machine:
   copy `~/.cloudflared/` from the old one, or run `cloudflared tunnel login` and `cloudflared tunnel route dns
   <tunnel name> live.letsgrowesports.com` there. Only one machine should run the tracker at a time.
6. Keep it running: on a Linux server use systemd (or `tmux`), on a Mac keep the Terminal window open (or a
   launchd agent). The tracker updates itself from GitHub (`AUTO_UPDATE`) and backs itself up every night.

## Move to a new domain

Set `EVENT_PUBLIC_URL=https://your-new-domain` in `.env` (share links and cards use it), point the tunnel at the
new hostname (`cloudflared tunnel route dns <tunnel name> your-new-domain`), restart. Nothing else is tied to the old
domain except the brand text (`EVENT_BRAND`, `EVENT_BRAND_URL`).

## Starting over in a new chat

Read `docs/HANDOFF.md` first: what runs where, the owner's rules, the code map and the current state.
