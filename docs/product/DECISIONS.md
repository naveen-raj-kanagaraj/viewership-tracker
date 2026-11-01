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
| 13 | Show a time range only once the site has that much history | A "1 year" button showing 30 days of data reads as wrong | Fewer options at launch; a note says longer ranges are coming |
| 14 | Read every channel's latest posts from free feeds, not the API | Every channel page should have data before anyone opens it, without spending the YouTube API allowance | Feeds give the latest 15 posts with views and likes only; opening the page fills in the rest |
| 15 | Predict & Win locks at a fixed time (BMIC: Day 1, 2 PM IST), enforced on the server | Picks made after matches start aren't predictions; a rule in code can't be forgotten | Players who arrive later can only see the results |
| 16 | Keep IP addresses for Predict & Win players; visitors' only in memory for 2 days | Prizes attract duplicate accounts; visitor IPs are only needed to spot bots | More personal data held, so disclosed in the privacy policy and deletable on request |
| 17 | Moments measure a jump against the level a minute earlier and play a 60-second clip | Multi-minute "jumps" were slow climbs, not moments; a clip around the jump is what people want to see | Slow, steady rises no longer count as moments |
