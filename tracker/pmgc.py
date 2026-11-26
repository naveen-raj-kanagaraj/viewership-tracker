"""Predict & Win: PMGC 2026 Gauntlet (26-27 Nov 2026, Istanbul; 16 teams, 12 matches, top 6 to the Grand Finals).

Players sign in with Google (tracker/auth.py) and add their Instagram ID; one entry per Google account and per
Instagram ID. Eight questions, all required; picks can be changed until the lock (default 26 Nov 5 PM IST, the
Gauntlet's start; the owner can move it at /admin/pmgc). After the lock the crowd split shows (once 20 people have
played); the owner enters the results at /admin/pmgc and turns the leaderboard on.

Scoring (like BMIC / BMSD): a right answer earns 100 + an underdog bonus of 100 x (1 - share of players who got it
right). The 6 finalists earn that per right team, split six ways; the top 3 per team in the right place, split three
ways. Ties: more right answers, then whoever submitted first.

Team logos: the original files from each team's Liquipedia page (dark-mode version when there is one), fetched once
by the server (logo_loop), kept in data/teamlogos/ and served from /pmgc/logo/<slug>. A logo that can't be found
shows the team's initials; the owner can paste an image link for any team at /admin/pmgc.
"""
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from tracker import store

GAME = "pmgc26g"
NAME = "PMGC 2026 Gauntlet"
IST = timezone(timedelta(hours=5, minutes=30))
SET_KEY = "pg_" + GAME
MIN_CROWD = 1           # the owner wants the split shown after the lock (percentages only, never how many played)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_DIR = os.path.join(ROOT, "data", "teamlogos")
STATIC_LOGOS = os.path.join(ROOT, "static", "pmgclogos")    # the owner's logos (26 Nov, from Liquipedia), 320 px webp

# name shown, slug, Liquipedia page names to try (owner's list from Liquipedia, 26 Nov)
TEAMS = [
    ("AK Gold Esports", "ak-gold", ["AK Gold Esports", "AK Gold"]),
    ("Sharper Esports", "sharper", ["Sharper Esports", "Sharper"]),
    ("4Thrives", "4thrives", ["4Thrives", "4Thrives Esports"]),
    ("The MongolZ", "the-mongolz", ["The MongolZ", "MongolZ"]),
    ("Aurora", "aurora", ["Aurora Gaming", "Aurora"]),
    ("4K Esports", "4k", ["4K Esports", "4K"]),
    ("iKURD ESPORTS", "ikurd", ["IKURD Esports", "IKURD ESPORTS", "IKURD"]),
    ("S2G Esports", "s2g", ["S2G Esports", "S2G"]),
    ("Gaming Stars", "gaming-stars", ["Gaming Stars"]),
    ("Hustler Crew", "hustler-crew", ["Hustler Crew"]),
    ("Wolves", "wolves", ["Wolves Esports", "Wolves"]),
    ("RoW Esports", "row", ["RoW Esports", "ROW Esports", "RoW"]),
    ("XForce Rejects", "xforce-rejects", ["XForce Rejects", "XForce"]),
    ("All Gamers", "all-gamers", ["All Gamers"]),
    ("Team SouL", "team-soul", ["Team SouL", "SouL"]),
    ("NS RedForce", "ns-redforce", ["NS RedForce", "Nongshim RedForce"]),
]
TEAM_NAMES = [t[0] for t in TEAMS]
SLUG = {t[0]: t[1] for t in TEAMS}

PEAKS = ["250K-350K", "350K-450K", "450K-550K", "550K-650K", "650K-750K", "750K-850K", "850K-950K", "950K-1M", "1M+"]
YN = ["Yes", "No"]
QUESTIONS = [
    {"id": "q1", "kind": "multi", "pick": 6, "tag": "GRAND FINALS",
     "title": "Pick the 6 teams that qualify for the Grand Finals", "sub": "The top 6 of the Gauntlet go straight to the Grand Finals."},
    {"id": "q2", "kind": "team", "tag": "GAUNTLET #1", "title": "Who finishes #1 in the Gauntlet?"},
    {"id": "q3", "kind": "yesno", "tag": "TEAM SOUL", "title": "Will Team SouL make it to the Grand Finals from the Gauntlet?"},
    {"id": "q4", "kind": "team", "tag": "CHICKEN DINNERS", "title": "Which team gets the most chicken dinners?"},
    {"id": "q5", "kind": "yesno", "tag": "3+ DINNERS", "title": "Will any team win 3 or more chicken dinners?"},
    {"id": "q6", "kind": "choice", "tag": "PEAK VIEWERS", "options": PEAKS,
     "title": "What will the Gauntlet's peak live viewership be?",
     "sub": "Most people watching at once, all platforms together: official streams and watch parties."},
    {"id": "q7", "kind": "choice", "tag": "DIFFERENT WINNERS", "options": [str(i) for i in range(1, 13)],
     "title": "How many different teams will win a chicken dinner?", "sub": "12 matches across the two days."},
    {"id": "q8", "kind": "rank", "pick": 3, "tag": "TOP 3", "title": "Pick the top 3 of the Gauntlet, in order",
     "sub": "Tap teams in order: first tap is #1, then #2, then #3. Tap a team again to remove it."},
]
QMAP = {q["id"]: q for q in QUESTIONS}
for _q in QUESTIONS:
    if _q["kind"] in ("team", "multi", "rank"):
        _q["options"] = TEAM_NAMES
    elif _q["kind"] == "yesno":
        _q["options"] = YN

DEFAULTS = {"lock": datetime(2026, 11, 26, 17, 0, tzinfo=IST).timestamp(), "answers": {}, "show_lb": False,
            "prize": "Top predictors win free UC, cash prizes, gift cards and coupons. Winners are announced after the Gauntlet on 27 Nov.",
            "logo_urls": {}}
AUTO_FROM = datetime(2026, 11, 26, 12, 0, tzinfo=IST).timestamp()   # an official PMGC stream after this locks picks

_init = [False]
_cache = {}
_lk = threading.Lock()


class GameError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


def _db():
    if not _init[0]:
        try:                                      # made already: no need to wait for the write lock (a 25 s scan
            with store.reading():                  # write after a restart made the first page load take 14 s)
                if store.conn().execute("SELECT 1 FROM sqlite_master WHERE name='pg_entries'").fetchone():
                    _init[0] = True
                    return store.conn()
        except Exception:
            pass
        c = store.main()
        with store._lock:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS pg_entries (
                game TEXT NOT NULL, uid INTEGER NOT NULL, handle TEXT NOT NULL, name TEXT NOT NULL, email TEXT,
                picks TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, hidden INTEGER DEFAULT 0,
                PRIMARY KEY (game, uid));
            CREATE UNIQUE INDEX IF NOT EXISTS pg_entries_handle ON pg_entries(game, handle);
            """)
            c.commit()
        _init[0] = True
    return store.conn()


# ---------------- settings ----------------
def settings() -> dict:
    s = dict(DEFAULTS)
    s.update(store.kv_get(SET_KEY, {}) or {})
    return s


def save(**kw) -> dict:
    s = store.kv_get(SET_KEY, {}) or {}
    for k, v in kw.items():
        if k in DEFAULTS and v is not None:
            s[k] = v
    store.kv_set(SET_KEY, s)
    _cache.clear()
    return settings()


def official_start():
    """When the PMGC tracker first saw an official PUBG MOBILE stream of the event (title naming it) on Gauntlet day,
    or None. Read from the tracker's own records, so it holds across restarts (cached 15 s)."""
    hit = _cache.get("off")
    if hit and time.time() - hit[0] < 15:
        return hit[1]
    t = None
    try:
        from tracker import events
        with store.reading():
            r = events._db().execute("SELECT MIN(ts) FROM ev_ticks WHERE event='pmgc' AND official>0 AND ts>=?", (AUTO_FROM,)).fetchone()
        t = float(r[0]) if r and r[0] else None
    except Exception:
        t = None
    _cache["off"] = (time.time(), t)
    return t


def closed(now: float = None) -> bool:
    """Picks lock at the set time (26 Nov 5 PM IST; the owner can move it at /admin/pmgc). Not tied to the official
    stream (owner, 26 Nov: 'just lock it at 5 pm')."""
    return (now or time.time()) >= float(settings()["lock"])


def fmt_ist(ts: float) -> str:
    return datetime.fromtimestamp(ts, IST).strftime("%a %d %b, %I:%M %p IST").replace(" 0", " ")


# ---------------- validation ----------------
def norm_handle(raw: str) -> str:
    h = (raw or "").strip()
    m = re.search(r"instagram\.com/([^/?#\s]+)", h, re.I)
    if m:
        h = m.group(1)
    h = h.strip().lstrip("@").lower()
    if not re.fullmatch(r"[a-z0-9._]{1,30}", h) or not h.strip("._"):
        return ""
    return h


def clean_picks(picks: dict) -> dict:
    """Every question answered and valid, or GameError naming the first problem."""
    if not isinstance(picks, dict):
        raise GameError("Answer every question.")
    out = {}
    for q in QUESTIONS:
        v = picks.get(q["id"])
        if q["kind"] in ("multi", "rank"):
            vals = [str(x) for x in v] if isinstance(v, list) else []
            if len(vals) != q["pick"] or len(set(vals)) != q["pick"] or any(x not in TEAM_NAMES for x in vals):
                raise GameError(f"{q['title']}: pick exactly {q['pick']} different teams.")
            out[q["id"]] = vals
        else:
            if not isinstance(v, str) or v not in q["options"]:
                raise GameError(f"{q['title']}: choose an answer.")
            out[q["id"]] = v
    return out


# ---------------- entries ----------------
def entry(uid: int):
    with store.reading():
        r = _db().execute("SELECT * FROM pg_entries WHERE game=? AND uid=?", (GAME, int(uid))).fetchone()
    if not r:
        return None
    d = dict(r)
    d["picks"] = json.loads(d["picks"])
    return d


def submit(user: dict, handle: str, name: str, picks: dict, now: float = None) -> dict:
    now = now or time.time()
    if closed(now):
        raise GameError("Picks are locked. The Gauntlet has started.", 409)
    if not user:
        raise GameError("Sign in with Google to play.", 401)
    h = norm_handle(handle)
    if not h:
        raise GameError("Enter your Instagram ID (letters, numbers, . and _ only).")
    name = re.sub(r"\s+", " ", name or "").strip()[:32] or (user.get("name") or h)[:32]
    p = clean_picks(picks)
    c = _db()
    with store._lock:
        other = c.execute("SELECT uid FROM pg_entries WHERE game=? AND handle=? AND uid<>?", (GAME, h, user["id"])).fetchone()
        if other:
            raise GameError("That Instagram ID is already playing from another account. If it's yours, DM "
                            "@letsgrowesports.igc on Instagram.", 409)
        had = c.execute("SELECT created, hidden FROM pg_entries WHERE game=? AND uid=?", (GAME, user["id"])).fetchone()
        if had and had["hidden"]:
            raise GameError("This entry was removed from the game.", 403)
        if had:
            c.execute("UPDATE pg_entries SET handle=?, name=?, email=?, picks=?, updated=? WHERE game=? AND uid=?",
                      (h, name, user.get("email"), json.dumps(p), now, GAME, user["id"]))
        else:
            c.execute("INSERT INTO pg_entries (game, uid, handle, name, email, picks, created, updated) VALUES (?,?,?,?,?,?,?,?)",
                      (GAME, user["id"], h, name, user.get("email"), json.dumps(p), now, now))
        c.commit()
    _cache.clear()
    return {"ok": True, "edited": bool(had)}


def _entries(include_hidden=False) -> list:
    with store.reading():
        rows = _db().execute("SELECT * FROM pg_entries WHERE game=?" + ("" if include_hidden else " AND hidden=0") +
                             " ORDER BY created", (GAME,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["picks"] = json.loads(d["picks"])
        out.append(d)
    return out


# ---------------- crowd and scoring ----------------
def _crowd(es: list) -> dict:
    """Per question, how many players picked each option (multi / rank: included anywhere; rank also by slot)."""
    out = {q["id"]: {} for q in QUESTIONS}
    slots = [{}, {}, {}]
    for e in es:
        for q in QUESTIONS:
            v = e["picks"].get(q["id"])
            for x in (v if isinstance(v, list) else [v]):
                out[q["id"]][x] = out[q["id"]].get(x, 0) + 1
        for i, t in enumerate(e["picks"].get("q8") or []):
            slots[i][t] = slots[i].get(t, 0) + 1
    out["q8_slots"] = slots
    return out


def _ans(qid: str, s: dict = None):
    a = (s or settings())["answers"].get(qid)
    return a if a not in (None, "", []) else None


def points(e: dict, cr: dict, n: int, s: dict = None) -> tuple:
    """(points, right answers) for one entry."""
    s = s or settings()
    n = max(1, n)
    pts, right = 0, 0
    for q in QUESTIONS:
        a, v = _ans(q["id"], s), e["picks"].get(q["id"])
        if a is None or v is None:
            continue
        if q["kind"] == "multi":
            hit = [t for t in v if t in a]
            if hit:
                right += 1
            pts += sum((100 + 100 * (1 - cr[q["id"]].get(t, 1) / n)) / q["pick"] for t in hit)
        elif q["kind"] == "rank":
            got = 0
            for i, t in enumerate(v[:3]):
                if i < len(a) and a[i] == t:
                    got += 1
                    pts += (100 + 100 * (1 - cr["q8_slots"][i].get(t, 1) / n)) / 3
            right += 1 if got else 0
        else:
            ok = a if isinstance(a, list) else [a]                # ties (most chicken dinners): any of them
            if v in ok:
                right += 1
                share = sum(cr[q["id"]].get(x, 0) for x in ok) or 1
                pts += 100 + 100 * (1 - share / n)
    return round(pts), right


def board(now: float = None) -> dict:
    """Public numbers (cached 5 s): crowd split after the lock, results, leaderboard when shown."""
    return _board(now)[0]


def _board(now: float = None) -> tuple:
    now = now or time.time()
    hit = _cache.get("board")
    if hit and now - hit[0] < 5:
        return hit[1], hit[2], hit[3]
    shut = closed(now)                       # first: it can move the lock to the broadcast's start
    s = settings()
    es = _entries()
    n = len(es)
    cr = _crowd(es)
    pct = {}
    if shut and n >= MIN_CROWD:
        for q in QUESTIONS:
            pct[q["id"]] = {k: round(100 * v / n) for k, v in sorted(cr[q["id"]].items(), key=lambda kv: -kv[1])}
        pct["q8_first"] = {k: round(100 * v / n) for k, v in sorted(cr["q8_slots"][0].items(), key=lambda kv: -kv[1])}
        pct["q8_top3"] = pct.pop("q8")
    lb = []
    if s["show_lb"]:
        rows = []
        for e in es:
            p, r = points(e, cr, n, s)
            rows.append({"handle": e["handle"], "name": e["name"], "pts": p, "right": r, "t": e["updated"]})
        rows.sort(key=lambda r: (-r["pts"], -r["right"], r["t"]))
        lb = [{"rank": i + 1, "handle": r["handle"], "name": r["name"], "pts": r["pts"], "right": r["right"]}
              for i, r in enumerate(rows[:10]) if r["pts"] > 0]
    out = {"lock": float(s["lock"]), "closed": shut, "prize": s["prize"], "answers": {k: v for k, v in s["answers"].items() if v not in (None, "", [])},
           "crowd": pct, "leaderboard": lb, "show_lb": bool(s["show_lb"])}
    _cache["board"] = (now, out, cr, n)
    return out, cr, n


def state(user, now: float = None) -> dict:
    """Everything the page needs for this person."""
    now = now or time.time()
    b, cr, n = _board(now)
    me = None
    if user:
        e = entry(user["id"])
        me = {"name": user.get("name") or "", "picture": user.get("picture") or ""}
        if e:
            me.update(handle=e["handle"], display=e["name"], picks=e["picks"], submitted=e["created"], updated=e["updated"],
                      hidden=bool(e["hidden"]))
            if b["answers"]:
                me["pts"], me["right"] = points(e, cr, n)
    return {**b, "now": now, "me": me, "teams": teams(), "questions": QUESTIONS, "lock_text": fmt_ist(b["lock"])}


# ---------------- owner ----------------
def admin_entries(q: str = "") -> list:
    es = _entries(include_hidden=True)
    b, cr, n = _board()
    out = []
    for e in es:
        if q and q.lower() not in (e["handle"] + " " + (e["name"] or "") + " " + (e["email"] or "")).lower():
            continue
        p, r = points(e, cr, n)
        out.append({**e, "pts": p, "right": r})
    out.sort(key=lambda e: (-e["pts"], -e["right"], e["updated"])) if b["answers"] else out.sort(key=lambda e: -e["created"])
    return out


def set_answers(form) -> dict:
    """From the admin form: q1 (6 teams), q2, q3, q4 (one or more for a tie), q5, q6, q7, q8 (3 in order)."""
    a = {}
    for q in QUESTIONS:
        if q["kind"] == "multi":
            v = [t for t in form.getlist(q["id"]) if t in TEAM_NAMES]
            if v and len(v) != q["pick"]:
                raise GameError(f"{q['title']}: tick exactly {q['pick']} teams (or none).")
            a[q["id"]] = v
        elif q["kind"] == "rank":
            v = [form.get(f"{q['id']}_{i}", "") for i in range(3)]
            v = [t for t in v if t in TEAM_NAMES]
            if v and (len(v) != 3 or len(set(v)) != 3):
                raise GameError("Top 3: choose three different teams (or none).")
            a[q["id"]] = v
        elif q["id"] == "q4":
            a[q["id"]] = [t for t in form.getlist(q["id"]) if t in TEAM_NAMES]
        else:
            v = form.get(q["id"], "")
            a[q["id"]] = v if v in q["options"] else ""
    save(answers=a)
    return a


def entry_action(uid: int, action: str):
    with store._lock:
        c = _db()
        if action == "hide":
            c.execute("UPDATE pg_entries SET hidden=1 WHERE game=? AND uid=?", (GAME, int(uid)))
        elif action == "unhide":
            c.execute("UPDATE pg_entries SET hidden=0 WHERE game=? AND uid=?", (GAME, int(uid)))
        elif action == "delete":
            c.execute("DELETE FROM pg_entries WHERE game=? AND uid=?", (GAME, int(uid)))
        else:
            raise GameError("Unknown action.")
        c.commit()
    _cache.clear()


def csv_text() -> str:
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["rank_or_order", "instagram", "name", "email", "points", "right", "hidden", "submitted_ist", "updated_ist"] +
               [q["tag"] for q in QUESTIONS])
    t = lambda ts: datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d %H:%M:%S")
    for i, e in enumerate(admin_entries(), 1):
        w.writerow([i, e["handle"], e["name"], e["email"] or "", e["pts"], e["right"], "yes" if e["hidden"] else "",
                    t(e["created"]), t(e["updated"])] +
                   [" > ".join(v) if isinstance(v, list) else v for v in (e["picks"].get(q["id"], "") for q in QUESTIONS)])
    return out.getvalue()


def tracker_peak():
    """The PMGC tracker's peak over the Gauntlet days (26-27 Nov IST), or None."""
    a = datetime(2026, 11, 26, tzinfo=IST).timestamp()
    b = datetime(2026, 11, 28, tzinfo=IST).timestamp()
    try:
        from tracker import events
        with store.reading():
            r = events._db().execute("SELECT MAX(total) FROM ev_ticks WHERE event='pmgc' AND ts>=? AND ts<?", (a, b)).fetchone()
        return int(r[0]) if r and r[0] else None
    except Exception:
        return None


def peak_bucket(v: int) -> str:
    edges = [350, 450, 550, 650, 750, 850, 950, 1000]
    for i, e in enumerate(edges):
        if v < e * 1000:
            return PEAKS[i]
    return PEAKS[-1]


# ---------------- team logos ----------------
_EXT = (".png", ".webp", ".svg", ".jpg", ".jpeg")


def logo_file(slug: str):
    p = os.path.join(STATIC_LOGOS, slug + ".webp")
    if os.path.isfile(p):
        return p
    for ext in _EXT:
        p = os.path.join(LOGO_DIR, slug + ext)
        if os.path.isfile(p):
            return p
    return None


def teams() -> list:
    out = []
    for name, slug, _ in TEAMS:
        f = logo_file(slug)
        v = int(os.path.getmtime(f)) if f else 0
        out.append({"n": name, "s": slug, "logo": f"/pmgc/logo/{slug}?v={v}" if f else ""})
    return out


def _file_url(filename: str) -> str:
    """Liquipedia's own address for an uploaded file (MediaWiki's hashed path), no API call needed."""
    fn = filename.strip().replace(" ", "_")
    fn = fn[:1].upper() + fn[1:]
    h = hashlib.md5(fn.encode()).hexdigest()
    return f"https://liquipedia.net/commons/images/{h[0]}/{h[:2]}/{quote(fn)}"


def _save_logo(slug: str, data: bytes, ext: str):
    os.makedirs(LOGO_DIR, exist_ok=True)
    for e in _EXT:
        p = os.path.join(LOGO_DIR, slug + e)
        if os.path.isfile(p):
            os.remove(p)
    with open(os.path.join(LOGO_DIR, slug + ext), "wb") as f:
        f.write(data)


def _download(url: str):
    from tracker import events, liquipedia
    r = events._http.get(url, headers={"User-Agent": liquipedia.UA}, timeout=20)
    ct = (r.headers.get("Content-Type") or "").lower()
    if r.status_code != 200 or not ct.startswith("image/") or len(r.content) < 200 or len(r.content) > 5_000_000:
        return None, None
    ext = ".svg" if "svg" in ct else ".webp" if "webp" in ct else ".jpg" if "jpeg" in ct else ".png"
    return r.content, ext


def fetch_logo(name: str, slug: str, pages: list) -> str:
    """One team's logo from its Liquipedia page (dark-mode version first). Returns what happened."""
    from tracker import events, liquipedia
    for page in pages:
        title = page
        for _ in range(2):                                   # follow one redirect
            try:
                r = events._http.get(f"https://liquipedia.net/pubgmobile/{quote(title.replace(' ', '_'))}",
                                     params={"action": "raw"}, headers={"User-Agent": liquipedia.UA, "Accept-Encoding": "gzip"},
                                     timeout=20)
            except Exception as e:
                return f"failed: {str(e)[:60]}"
            time.sleep(liquipedia.GAP)
            if r.status_code != 200:
                break
            m = re.match(r"\s*#REDIRECT\s*\[\[([^\]|#]+)", r.text, re.I)
            if not m:
                break
            title = m.group(1).strip()
        else:
            continue
        if r.status_code != 200:
            continue
        files = []
        for key in ("imagedark", "image"):
            m = re.search(rf"^\s*\|\s*{key}\s*=\s*([^\n|}}]+)", r.text, re.M | re.I)
            if m and m.group(1).strip():
                files.append(m.group(1).strip().removeprefix("File:"))
        for fn in files:
            try:
                data, ext = _download(_file_url(fn))
            except Exception:
                data = None
            time.sleep(1)
            if data:
                _save_logo(slug, data, ext)
                return f"ok: {title} / {fn}"
    return "not found"


def logo_status() -> dict:
    return store.kv_get("pg_logo_status") or {}


def fetch_logos(force: bool = False) -> dict:
    """Every team without a logo (or all, with force): the owner's pasted link first, else Liquipedia."""
    st = logo_status()
    urls = settings().get("logo_urls") or {}
    for name, slug, pages in TEAMS:
        if logo_file(slug) and not force and slug not in urls:
            continue
        res = None
        if urls.get(slug):
            try:
                data, ext = _download(urls[slug])
                if data:
                    _save_logo(slug, data, ext)
                    res = "ok: owner's link"
                    u = dict(urls)
                    u.pop(slug, None)
                    save(logo_urls=u)
                else:
                    res = "owner's link is not an image"
            except Exception as e:
                res = f"owner's link failed: {str(e)[:60]}"
        if not (res and res.startswith("ok")):
            if logo_file(slug) and not force:
                st[slug] = {"result": res or "kept", "ts": time.time()}
                store.kv_set("pg_logo_status", st)
                continue
            lp = fetch_logo(name, slug, pages)
            res = f"{res}; Liquipedia: {lp}" if res else lp
        st[slug] = {"result": res, "ts": time.time()}
        store.kv_set("pg_logo_status", st)
    return st


def logo_loop():
    """At startup and every 6 hours: fetch any logo still missing (a few Liquipedia requests, 4 s apart)."""
    def run():
        time.sleep(20)
        while True:
            try:
                if any(not logo_file(s) for _, s, _ in TEAMS) or (settings().get("logo_urls") or {}):
                    fetch_logos()
            except Exception as e:
                print(f"PMGC logos: {str(e)[:120]}")
            time.sleep(6 * 3600)
    threading.Thread(target=run, daemon=True, name="pmgc-logos").start()
