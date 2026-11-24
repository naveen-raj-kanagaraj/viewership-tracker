# Daily review of the India rankings (11:37 PM IST, before the 12:05 AM rankings run)

Goal: the India rankings on Twitch, Kick and YouTube contain only real, Indian streamers, each in the right
category. Decisions go into `overrides.json` (repo root). The server re-reads it from GitHub every 10 minutes,
so a merged change is live for the 12:05 AM run without a deploy.

Budget: this runs every day, so keep it small. Only check channels not reviewed in the last 14 days. Use the
site's own data first; open a platform page only when the data can't decide, and at most 15 pages per run. No
screenshots unless a page can't be read as text. Don't change any code: only `overrides.json`.

## Rules (owner's, 22-24 Nov)

- Indian = based in India, or speaking Indian languages, or Indian abroad ("British Indian"). Not Indian:
  Pakistan, Bangladesh, Nepal, other countries. Twitch's "Hindi" language setting alone is not proof (Pakistani
  streamers pick it: Twitch has no Urdu).
- Rankings are of real streamers. Block: viewbotted channels (live viewers their followers can't explain: peak
  above followers, or average above a quarter of followers; real channels average 1-5% of followers), banned or
  deleted channels, 24/7 restreams of TV shows or matches (Bigg Boss, cricket) with few followers, fakes and
  scams, upload-only channels (no live streams).
- Category = what the channel actually streams (its games / content over 30 days), not the platform's label.
  YouTube categories: Gaming, Sports, News & Politics, Music, Entertainment, People & Blogs. Kick / Twitch:
  Gaming, Esports, Just Chatting, IRL, Music, Sports, News, Devotional, Podcasts & Talk, Other.
  Chess, GTA RP, BGMI, Free Fire are Gaming. Tournament broadcasts (CEGC, BMSD ...) are Esports on Kick / Twitch.

## Steps

1. Repo: `/home/claude/viewership-tracker` (clone `naveen-raj-kanagaraj/viewership-tracker` if missing), `git pull`.
   Read `overrides.json`: `reviewed` holds the date each channel was last checked.
2. Site data, in the built-in browser on `https://live.letsgrowesports.com` (one `javascript_exec` per platform):
   `/api/topch?platform=twitch&metric=peak_7d&country=IN&limit=100`, the same for `kick`, and for `youtube` both
   `metric=peak_7d` and `metric=views_7d&category=Gaming`. For each row not reviewed in 14 days, fetch
   `/api/channel?sid=<sid>` and keep only: name, title, `india_why`, `profile` (followers, bio, links, gone),
   `periods['30d']` (peak, avg, hours, games), and the row's category / game. Return compact JSON.
3. Decide from that data:
   - followers known and the bot test fails, or `profile.gone` -> block.
   - `india_why` rests on weak evidence (a title word, a tag, the name) and the bio / title / games say another
     country -> not_india. Clear Indian evidence (Hindi / Indian-language chat share, Indian bio, Indian events)
     -> nothing to do.
   - category doesn't match the 30-day games / content -> set `category[sid]`.
   - Only if still unsure: open the channel page as text (`twitch.tv/<login>/about`, `kick.com/<slug>/about`,
     `youtube.com/channel/<id>/about`) and read followers, bio, country, recent streams. 15 pages at most.
4. Edit `overrides.json`: add to `india` / `not_india` / `block` / `category`, set `reviewed[sid]` to today's
   date for every channel checked (also the ones that were fine), and a short reason in `notes[sid]`
   ("634 followers, peak 17,184: viewbots"). Keep sids lowercase for Kick / Twitch, exact for YouTube (`yt:UC...`).
5. `python3 tests/test_overrides.py` must pass. Commit on a branch, open a PR, squash-merge (the session's
   attribution lines). No deploy is needed.
6. Tell the owner in a few lines: how many channels checked, what was blocked / moved / re-categorised and why,
   and anything only they can decide. If nothing changed, say so in one line.

Never write the live database, never print secrets, never log in to accounts, don't scrape TwitchTracker.
