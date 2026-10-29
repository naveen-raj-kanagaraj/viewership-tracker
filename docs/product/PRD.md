# PRD: letsgrowesports Live

Owner: Naveen Raj Kanagaraj (product, design direction, data definitions) · Status: live, in beta · Last updated 29 Oct 2026

## 1. Problem

Creator and live-streaming audiences are measured badly in fast-growing markets like India.

- **Numbers arrive late and are incomplete.** Published viewership for an event usually lands days later and often counts the official broadcast alone. During BMSD 2026 (a national esports final) this site measured 653,067 people watching at the peak, and **57% of them were watching creators' watch parties, not the official stream**. A report that counts only the official broadcast misses most of the audience.
- **No single place covers every platform.** YouTube, Twitch and Kick each show their own numbers in their own way; nobody adds them up per game, per country or per creator.
- **Channel analytics tools are built for the US.** Existing trackers show subscriber counts but say little about Indian creators, live audiences or how a channel's recent videos perform.

## 2. Users and jobs to be done

| User | Job to be done | What they need from the site |
|---|---|---|
| Creators and streamers | "Show me how I'm growing and where I rank, so I can prove it to sponsors." | Channel page, rank badges, share cards, compare |
| Brands and agencies | "Find creators with a real, current audience in my category and country." | Rankings by views gained, category, country; channel performance; compare |
| Tournament organizers and publishers | "Know the true audience of my event, including watch parties, while it is live." | Tournament tracker with official + watch-party split, every 2 seconds |
| Fans and media | "What is everyone watching right now, and who is biggest today?" | Live dashboard, top today, moments, world map |

## 3. Goals and non-goals

**Goals**
1. Show the live audience across YouTube, Twitch and Kick within seconds, worldwide and for India.
2. Give every tracked channel a useful page without anyone having to request it.
3. Make the numbers trustworthy: defined, reproducible, and protected against bad readings.
4. Make the numbers easy to share (cards, badges, links), because sharing is how the site grows.

**Non-goals (for now)**
- Accounts, logins or anything that needs a creator's private analytics (OAuth). Public data only.
- Paid plans or ads. The site is free while the data and audience grow.
- Uploading or changing anything on YouTube, Twitch or Kick.

## 4. Requirements

| # | Requirement | Priority | Status |
|---|---|---|---|
| R1 | Live dashboard: watching now, by platform, section and game, refreshed every 2 s | P0 | Shipped |
| R2 | Tournament tracker: official broadcast + permitted watch parties, peak, average, per-stream split | P0 | Shipped (BMSD 2026, BMIC 2026) |
| R3 | Channel page for any YouTube, Twitch or Kick channel: subscribers, lifetime views, views per day, recent video performance (views, likes, comments, engagement), live stats | P0 | Shipped |
| R4 | Rankings: channels by views gained (day, 7 d, 30 d), total views, subscribers; streamers by hours watched, peak, average; filters for category, game, country | P0 | Shipped |
| R5 | Search any channel on YouTube, Twitch and Kick; every channel found is followed daily from then on | P1 | Shipped |
| R6 | Moments: sudden audience jumps detected from chat and viewers, with a link to that second | P1 | Shipped |
| R7 | Compare up to 4 channels across platforms | P1 | Shipped |
| R8 | Share cards and creator badges | P1 | Shipped |
| R9 | India-first experience for Indian visitors | P2 | Shipped |
| R10 | Same creator across platforms (platform switcher) | P2 | Shipped |
| R11 | Comment insights (top comments, themes) | P3 | Backlog: needs an extra YouTube API method |
| R12 | Alerts ("tell me when X goes live / hits 1M") | P3 | Backlog |

## 5. Data and accuracy requirements

- Every metric has one written definition ([METRICS.md](METRICS.md)) used by every page and share card.
- Readings that cannot be true are rejected, not shown: lifetime views below the channel's own biggest video, totals that drop, day-over-day jumps over 25%.
- Platform totals that the site cannot fully cover are labelled (for example, YouTube totals are a floor because YouTube has no complete list of live streams). Twitch worldwide counts every live stream, not only the top ones.
- The YouTube Data API allowance is metered; optional jobs stop before the daily limit so the essential daily stats always run.

## 6. Success metrics

North star: **channel pages viewed per week** (the site's core value is answering "how is this channel doing?").

Supporting: weekly returning visitors, share cards and badges created, visitors from shared links, share of tracked channels with complete pages, data freshness (minutes since last reading), number of source failures per day. Definitions in [METRICS.md](METRICS.md).

## 7. Risks

| Risk | Mitigation |
|---|---|
| Platform API limits (YouTube quota) | Quota meter with priorities; cheaper calls (uploads playlist id derived, no extra lookups); quota extension request |
| Unofficial endpoints change (Kick follower counts, YouTube live pages) | Official APIs first; failures surfaced on the owner page; graceful fallbacks |
| Wrong numbers going viral | Sanity checks, labelled estimates, "not final yet" notice during beta |
| Policy compliance | Privacy policy, terms, YouTube API attribution on every page; public data only; no OAuth |

## 8. Release history

55 pull requests merged between 19 and 29 October 2026, each with tests. Highlights: tournament tracker for BMSD 2026 (7 days, 92 streams), worldwide live dashboard and world map, channel pages and rankings, moments, compare, creator badges, accuracy and quota work, privacy and terms for the YouTube API audit. Detail: [DECISIONS.md](DECISIONS.md) and [../HANDOFF.md](../HANDOFF.md).
