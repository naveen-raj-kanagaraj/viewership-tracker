"""Who counts as Indian on Kick / Twitch: real titles from 23 Nov. Run: python3 tests/test_india_verdict.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene
scene._db()
NOT = [("twitch", "olivescrossing", "IT'S MY BIRTHDAY (੭ˊᵕˋ)੭🎂 !rewards !incentives 🎈 ELGATO MIC !GIVEAWAY", ""),
       ("twitch", "guddu_kim", "aaj sabko giveaway😇", ""),
       ("kick", "kuttush17", "FFWS Global Finals 2026 | নকআউট ফেজ ২ | ডে 4 ll  WATCH PARTY WITH BLADE  & KUTTUSH", ""),
       ("kick", "raadvai_yt", "FFWS Global Finals 2026 | নকআউট ফেজ ২ | ডে ৪ | টিম বাংলাদেশ  কি পারবে ফাইনালে যেতে? 🇧🇩🔥", ""),
       ("twitch", "lakohh", "‼️ NEW HAIRCUT RATE 1-SEXY🫦 10 BITS = INDIAN TTS‼️ NEW SOUND ALERTS‼️ !socials", ""),
       ("twitch", "princesita1331", "he volvido𐙚 ♡︎₊˚ 🧸🎄⋆ ˚｡⋆❄️˚୨୧⋆｡˚ ⋆・₊✧  !redes !tts ENG/ESP", ""),
       ("twitch", "derdummbabbler", "Wisst ihr was? ಠ_ಠ | Specialist Gloves Mogul !Giveaway | !skinbaron", ""),
       ("twitch", "mochi_miu", "⋆˙⟡♡₊˚⊹Sick Bunny ASMR ♫୨୧♡₍ ⑅ᐢ..ᐢ₎ [18+]", ""),
       ("twitch", "belleoce", "happy fridaaaay. yapping. natural waves. meow  . ♡ ⋅˚₊‧ ୨୧ ‧₊˚ ⋅", ""),
       ("kick", "apollogamingbd", "GTA 5 Rolepaly Bangla | Kala Jahangir in the City", ""),
       ("kick", "aponunaq", "৻ꪆ Nefes al nefes verr ৻ꪆ | !donate !youtube !dc", ""),
       ("kick", "rodiksama", "FINAL ORACULO, MI PC ME ODIA y ME DUERMO 💤 | EXTENSIBLE 5: Edicion Esclavitud", ""),
       ("kick", "x", "Pakistani bhai aaj khelenge", "")]
YES = [("kick", "someone", "aaj sabko giveaway", ""),
       ("twitch", "someoneuk", "Playing GTA 6!!!! | 🇬🇧🇮🇳 British Indian Gamergirl", ""),   # Indians abroad count (owner)           # Hindi: Indian unless the owner says otherwise
       ("kick", "tg_delete25", "baat krte h aur tournament khelenge", ""),
       ("kick", "a", "BGMI live | rush gameplay", ""),
       ("kick", "b", "आज का स्ट्रीम GTA 6", ""),
       ("twitch", "c", "Tamil GTA RP night", ""),
       ("kick", "d", "Hindi stream GTA 6 launch", ""),
       ("kick", "e", "SoulCity RP | day 4", ""),
       ("kick", "f", "bhai log aaj GTA 6 khelenge", ""),
       ("kick", "focusedindian", "chill stream", "focusedindian"),
       ("kick", "g", "আমার বাংলা স্ট্রিম 🇮🇳", ""),          # Bengali with India's flag: West Bengal
       ("kick", "h", "GTA 6 from Mumbai, aaj full night", "")]
for p, sl, t, n in NOT:
    assert not scene.verdict({"sid": f"{p}:{sl}", "platform": p, "title": t, "name": n or sl}), (sl, t)
for p, sl, t, n in YES:
    assert scene.verdict({"sid": f"{p}:{sl}", "platform": p, "title": t, "name": n or sl}), (sl, t)
assert scene.verdict({"sid": "twitch:z", "platform": "twitch", "title": "ranked", "name": "z", "language": "hi"})
# an old BGMI stream (known list) doesn't keep a clearly foreign channel Indian; a plain English title stays Indian
assert not scene.verdict({"sid": "kick:k1", "platform": "kick", "title": "FFWS watch party 🇧🇩", "name": "k1"}, None, {"kick:k1"})
assert scene.verdict({"sid": "kick:k2", "platform": "kick", "title": "Just chatting", "name": "k2"}, None, {"kick:k2"})
assert not scene.verdict({"sid": "kick:cristravels", "platform": "kick", "game": "IRL",
                          "title": "Kochi, India 🇮🇳 (Last day in India) (Day 379 No Drinking) @isaavibe", "name": "cristravels"})
for t in ("Minecraft Anfängerin!✧˚.💚⋆|| NERDCRAFT mit @Hermi693 || ദ്ദി ˉ͈̀꒳ˉ͈́ )✧", "I'm back with some games  ദ്ദി(˵ •̀ ᴗ - ˵ ) ✧"):
    assert not scene.verdict({"sid": "twitch:q", "platform": "twitch", "title": t, "name": "q"}), t
for sl, t in (("mortal", "JASON AND LUCIA - GTA 6 India | Day 2  (PS5)"), ("hydrobgmi04", "PLAYING GTA 6 | FUN STREAM"),
              ("rachitroo_1", "GTA 6🔴BIGBOSS🔴30 DAYS RACHITROO IRL LIVE"), ("nonstopgaming", "INDIA 🇮🇳 vs BRU || FFWS WATCH PARTY")):
    assert scene.verdict({"sid": "kick:" + sl, "platform": "kick", "title": t, "name": sl}), sl
for nm in ("indialovewestbrooks", "IndiaGutierDj", "INDIANTVCZ", "IndianDiorrr", "BigBossRobinson", "Lzindiario",
           "iiindiao", "BigBossIncarnate", "BIGBOSS33", "Indianchewbacca70"):
    assert not scene.verdict({"sid": "twitch:" + nm.lower(), "platform": "twitch", "title": "stream", "name": nm}), nm
for nm in ("focusedindian", "India_Noob_", "hydrobgmi04", "s8ul_sid"):
    assert scene.verdict({"sid": "kick:" + nm.lower(), "platform": "kick", "title": "stream", "name": nm}), nm
print("INDIA VERDICT OK", len(NOT), len(YES))
# the hourly re-check corrects saved flags: foreign ones unmarked, Indian ones kept
from tracker import store
c = store.main()
c.executemany("INSERT INTO sc_channels (sid, platform, name, title, game, india) VALUES (?,?,?,?,?,?)",
              [("twitch:mochi_miu", "twitch", "mochi_miu", "⋆˙⟡♡₊˚⊹Sick Bunny ASMR ♫୨୧♡₍ ⑅ᐢ..ᐢ₎ [18+]", "ASMR", 1),
               ("kick:cristravels", "kick", "cristravels", "Kochi, India 🇮🇳 (Last day in India)", "IRL", 1),
               ("kick:kaashplays", "kick", "kaashplays", "BIGG BOSS WATCH PARTY - SUPPORT SCOUTOP", "Just Chatting", 1),
               ("kick:bgmiguy", "kick", "bgmiguy", "FFWS watch party 🇧🇩", "Free Fire", 1)])
c.execute("INSERT INTO sc_daily VALUES ('2026-11-01','kick:bgmiguy','BGMI',50,0,60,10)"); c.commit()
scene._KNOWN["at"] = 0
scene.mark_known_india()
got = dict(c.execute("SELECT sid, india FROM sc_channels").fetchall())
assert got == {"twitch:mochi_miu": 0, "kick:cristravels": 0, "kick:kaashplays": 1, "kick:bgmiguy": 0}, got
print("INDIA RECHECK OK")
# every flag has a reason in words; 'Indian Ocean' is a place; tags count only when they name an Indian language
w = lambda **k: scene.india_why({"sid": "twitch:w", "platform": "twitch", "name": "w", **k})
assert w(title="GTA 6 DAY ONE from Seychelles 🏝️ Indian Ocean stand up") == (False, "nothing Indian found")
assert w(title="GTA 6", tags="English Hindi")[0] is False          # a tag alone doesn't decide (drtyeyeball)
assert w(title="GTA 6", tags="English Indian Desi")[0] is False
assert w(title="Bigg Boss watch party")[1] == "title: 'Bigg Boss'"
assert scene.india_why({"sid": "yt:x", "platform": "youtube", "title": "", "name": "x"}, "IN") == (True, "YouTube channel country: India")
print("REASONS OK")
# event trackers: only official channels and streams about the Indian event count; the reason names the source
from tracker import events as ev_
ev_._db()
c.executemany("INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind) VALUES (?,?,?,?,?,?)",
              [("cegc", "twitch:greek", "Greek", "twitch:greek", "🚨 NA LCQ MP FINALS WATCH PARTY 🚨", "watch party"),
               ("cegc", "kick:wp1", "wp1", "kick:wp1", "CEGC WATCHPARTY w WP1", "watch party")]); c.commit()
scene._KNOWN["at"] = 0
k = scene.india_known()
assert "twitch:greek" not in k and "kick:wp1" in k, k
assert scene.india_why({"sid": "kick:wp1", "platform": "kick", "title": "GTA 6", "name": "wp1"}, None, k) == \
    (True, "streamed the CEGC event ('CEGC WATCHPARTY w WP1')")
assert scene.india_why({"sid": "twitch:greek", "platform": "twitch", "title": "🚨 NA LCQ MP FINALS WATCH PARTY 🚨", "name": "Greek"}, None, k)[0] is False
print("EVENT SOURCES OK")
