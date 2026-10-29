"""Creator badges: a small live image a creator can put on their website or link page, showing one of their ranks
("#3 BGMI YouTube channel, by subscribers"). /badge/<sid>.svg?m=<metric>&s=<scope> (default: their best rank).
The image is rebuilt from the latest ranks (every 30 minutes), so the badge stays current wherever it's embedded."""
import html

from tracker import eventpage, ranks

NAMES = {"youtube": "YouTube", "twitch": "Twitch", "kick": "Kick"}
MIN_OF = 10            # don't badge a rank among fewer than this many channels ("#1 of 3" means nothing)


def _by(metric: str, platform: str) -> str:
    yt = platform == "youtube"
    return {"size": "by subscribers" if yt else "by followers", "views": "by total views",
            "vday": "by views gained today" if yt else "by followers gained today",
            "v7": "by views this week" if yt else "by followers gained this week",
            "growth": "by views, last 30 days" if yt else "by followers gained, 30 days",
            "live": "by hours watched live, 30 days"}.get(metric, "")


def options(sid: str) -> list:
    """Every rank this channel can show on a badge, best first: [{m, s, rank, of, title, by}]."""
    with ranks._lock:
        row = ranks._R["rows"].get(sid)
    if not row:
        return []
    p = NAMES.get(row["platform"], "")
    out = []
    for r in ranks.for_channel(sid):
        if r["of"] < MIN_OF:
            continue
        w = r["where"]
        title = {"world": f"{p} channel worldwide", "country": f"{p} channel in {w}",
                 "category": f"{p} channel in {w}", "game": f"{w} {p} channel"}[r["scope"]]
        out.append({"m": r["metric"], "s": r["scope"], "rank": r["rank"], "of": r["of"], "title": title,
                    "by": _by(r["metric"], row["platform"])})
    spec = {"game": 0, "category": 1, "country": 2, "world": 3}
    pref = {"size": 0, "views": 1, "growth": 2, "v7": 3, "vday": 4, "live": 5}
    out.sort(key=lambda o: (o["rank"], spec[o["s"]], pref.get(o["m"], 9)))
    best, seen = [], set()
    for o in out:                        # the best rank per place, then the best per measure: a short list to pick from
        if o["s"] not in seen:
            seen.add(o["s"])
            best.append(o)
    for o in out:
        if len(best) >= 8:
            break
        if o not in best and o["m"] not in {b["m"] for b in best}:
            best.append(o)
    return best


def svg(sid: str, m: str = "", s: str = "") -> str:
    opts = options(sid)
    pick = next((o for o in opts if o["m"] == m and o["s"] == s), None) or (opts[0] if opts else None)
    e = html.escape
    brand = e(eventpage.BRAND.upper())
    font = "'Barlow Condensed','Roboto Condensed','Arial Narrow',Arial,sans-serif"
    if not pick:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="56" viewBox="0 0 300 56" role="img" aria-label="Stats on {brand}">'
                f'<rect width="300" height="56" rx="8" fill="#0b0b12" stroke="#2c2c3e"/><rect x="0" y="0" width="6" height="56" rx="3" fill="#b6f23a"/>'
                f'<text x="20" y="25" font-family="{font}" font-size="12" font-weight="700" fill="#b6f23a" letter-spacing="1.2">LIVE STATS</text>'
                f'<text x="20" y="43" font-family="{font}" font-size="16" font-weight="700" fill="#eeeef5">on {e(eventpage.BRAND)}</text></svg>')
    rk = f"#{pick['rank']:,}"
    rw = 70 + 14 * max(0, len(rk) - 3)                       # rank panel widens for long numbers
    rs = 34 if len(rk) <= 3 else 30 if len(rk) <= 5 else 24
    title = pick["title"] if len(pick["title"]) <= 40 else pick["title"][:39] + "."
    sub = f'{pick["by"]} · of {pick["of"]:,} tracked'
    # the image is drawn with the viewer's fonts (Arial at worst): size the box for the widest of them
    w = int(rw + 34 + max(10.8 * len(title), 7.4 * len(sub), 8.6 * len("RANKED BY " + brand), 200))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="80" viewBox="0 0 {w} 80" role="img" '
            f'aria-label="Ranked {e(rk)} {e(pick["title"])} {e(pick["by"])}, by {brand}">'
            f'<rect x=".5" y=".5" width="{w - 1}" height="79" rx="10" fill="#0b0b12" stroke="#2c2c3e"/>'
            f'<path d="M10 .5h{rw - 10}v79H10a9.5 9.5 0 0 1-9.5-9.5V10A9.5 9.5 0 0 1 10 .5z" fill="#b6f23a"/>'
            f'<text x="{rw / 2}" y="{42 + rs / 3}" text-anchor="middle" font-family="{font}" font-size="{rs}" font-weight="700" fill="#0b0b12">{e(rk)}</text>'
            f'<text x="{rw + 16}" y="24" font-family="{font}" font-size="11" font-weight="700" fill="#a58bff" letter-spacing="1.4">RANKED BY {brand}</text>'
            f'<text x="{rw + 16}" y="47" font-family="{font}" font-size="19" font-weight="700" fill="#eeeef5">{e(title)}</text>'
            f'<text x="{rw + 16}" y="66" font-family="{font}" font-size="13" fill="#8d8ca3">{e(sub)}</text></svg>')
