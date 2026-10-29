# Product decisions

The calls that shaped the product, with the trade-off behind each.

| # | Decision | Why | Trade-off accepted |
|---|---|---|---|
| 1 | Count watch parties together with the official broadcast | At BMSD 2026, 57% of the peak audience watched creators' watch parties. Official-only numbers undercount the event. | Needs a permitted watch-party list per event, maintained with the organizer's list |
| 2 | Public data only, no logins | Zero friction for visitors; no private data to protect; simpler YouTube API compliance | No creator-private analytics (watch time, revenue) |
| 3 | Refresh live numbers every 2 seconds | Live audiences move by the minute; esports moments are seconds long | Higher load, solved with caching and stale-while-revalidate |
| 4 | Every channel gets a page by default, not only searched ones | The core job ("how is this channel doing?") must be answered on first visit | API quota: solved by metering, cheaper calls and a quota extension request |
| 5 | Show "views in the last hours" instead of waiting a day | New channels showed empty cards until tomorrow | Short windows are noisier; labelled clearly |
| 6 | Reject impossible readings instead of showing them | One wrong screenshot costs more trust than a missing number | A real but unusual change can be held back for a day |
| 7 | Twitch: count every live stream, not only the top 2,000 | The long tail is a large share of Twitch viewers; partial counts read as wrong next to other trackers | About 1,000 API calls every 5 minutes, inside Twitch's limits |
| 8 | Moments need at least 8% and 1,000 new viewers; skip news | Small or routine jumps (130K to 134K) are noise; news streams swing constantly | Fewer moments; the ones shown matter |
| 9 | India visitors land on the India view, decided in the browser | India is the core audience; deciding by IP on the server would make every page uncacheable | Based on the device time zone; a visitor's own choice always wins |
| 10 | YouTube's own 15 categories for channels | Matches what creators and brands already use; verifiable | Coarser than custom taxonomies (vlogging sits in People & Blogs) |
| 11 | Free, no ads during beta | Grow the audience and data first; keep YouTube API review simple | No revenue yet |
| 12 | "Not final yet" notice during beta | Data is still filling in; honest framing protects trust | Signals the product is early |
