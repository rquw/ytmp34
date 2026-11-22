#!/usr/bin/env python3
"""PRISMO plans fabio's school day: untis (what's on, who teaches it), ÖBB live data and its own
delay history. it knows when to get up, when to leave, whether to switch trains in St. Valentin
and when to go home. everything personal lives in ~/prismo/day.json, not in the repo.
  python3 prismo-day.py serve --host 100.x.y.z   (the prismo-day service, port 8781, tailnet only)
  python3 prismo-day.py plan [2026-11-23]        (print a day's plan)
  python3 prismo-day.py now [lat lon]            (what the action button answers)
"""
import datetime as dt
import json
import math
import os
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
P = os.path.join(HOME, "prismo")
CFG_FILE = os.path.join(P, "day.json")
STATE_FILE = os.path.join(P, "day-state.json")
DB_FILE = os.path.join(P, "day.db")
UNTIS = os.path.join(HOME, "untis-watch")

STOP = {"bf": "1241511", "schulen": "415226", "goethe": "491016", "hbf": "8100013"}
STOP_NAME = {"bf": "Ternberg Bf", "schulen": "Ternberg Schulen", "goethe": "Goethekreuzung"}

DEFAULTS = {
    "normal_wake": "06:07",
    "prep": 12,            # minutes from alarm to out of the door
    "car": 4,              # home -> ternberg bf / schulen
    "margin": 2,           # at the stop before departure
    "walk_schulen": 10,    # on foot to ternberg schulen
    "dad_until": "06:35",  # later than this, dad is gone: mom drives
    "room_walk": {"HA DG": 6, "HU": 6, "HO": 6, "HA": 5, "": 5},  # goethekreuzung <-> room
    "tolerance": {"devil": 0, "moderate": 7, "okay": 5, "fine": 8, "chill": 12, "very chill": 15},
    "teachers": {},        # "Mo Sozial": "FIEDP" (weekday + start of the subject name)
    "moods": {},           # "FIEDP": "moderate"
    "early": [],           # {"teacher": "AUERH", "at": "14:50", "sure": true, "note": "..."}
}
DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

lock = threading.RLock()


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, data):
    with open(path + ".tmp", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def cfg():
    c = dict(DEFAULTS)
    c.update(load(CFG_FILE, {}))
    return c


def hm(t):
    return t.strftime("%H:%M")


def at(day, s):
    return dt.datetime.combine(day, dt.time(int(s[:2]), int(s[3:5])))


def mins(td):
    return int(round(td.total_seconds() / 60))


# --- ÖBB (hafas, the same api the scotty app uses) ---

def mgate(req, timeout=15):
    body = {"lang": "deu", "svcReqL": [req], "ext": "OEBB.1", "ver": "1.41",
            "client": {"id": "OEBB", "type": "IPH", "name": "oebbPROD-ADHOC", "v": "6030600"},
            "auth": {"type": "AID", "aid": "OWDL4fE4ixNiPBBm"}}
    r = urllib.request.Request("https://fahrplan.oebb.at/bin/mgate.exe", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json", "User-Agent": "PRISMO/1.0"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        res = json.loads(f.read())["svcResL"][0]
    if res.get("err") != "OK":
        raise RuntimeError("ÖBB: %s" % (res.get("errTxt") or res.get("err")))
    return res["res"]


def htime(base, s):
    if not s:
        return None
    days = 0
    if len(s) == 8:
        days, s = int(s[:2]), s[2:]
    return dt.datetime.combine(base, dt.time(int(s[:2]), int(s[2:4]))) + dt.timedelta(days=days)


def place(p):
    if isinstance(p, tuple):
        return {"type": "C", "crd": {"x": int(p[1] * 1e6), "y": int(p[0] * 1e6)}}
    return {"type": "S", "extId": STOP.get(p, p)}


def trips(frm, to, when, arrive=False, n=4):
    r = mgate({"meth": "TripSearch", "req": {
        "depLocL": [place(frm)], "arrLocL": [place(to)], "outDate": when.strftime("%Y%m%d"),
        "outTime": when.strftime("%H%M%S"), "outFrwd": not arrive, "numF": n,
        "getPasslist": False, "getPolyline": False, "jnyFltrL": []}})
    prods, locs = r["common"]["prodL"], r["common"]["locL"]
    out = []
    for c in r.get("outConL", []):
        base = dt.datetime.strptime(c["date"], "%Y%m%d").date()
        legs, walk_first, walk_last = [], 0, 0
        for s in c["secL"]:
            if s["type"] != "JNY":
                m = int((s.get("gis") or {}).get("durS", "000000")[2:4] or 0)
                if legs:
                    walk_last += m
                else:
                    walk_first += m
                continue
            walk_last = 0
            j, d, a = s["jny"], s["dep"], s["arr"]
            name = prods[j["prodX"]].get("name", "?")
            plat = d.get("dPlatfR") or d.get("dPlatfS") or (d.get("dPltfR") or d.get("dPltfS") or {}).get("txt")
            legs.append({"name": name, "line": name.split(" (")[0], "dir": j.get("dirTxt", ""),
                         "from": locs[d["locX"]]["name"], "to": locs[a["locX"]]["name"],
                         "dep": htime(base, d.get("dTimeS")), "dep_rt": htime(base, d.get("dTimeR")),
                         "arr": htime(base, a.get("aTimeS")), "arr_rt": htime(base, a.get("aTimeR")),
                         "plat": plat, "cncl": bool(j.get("isCncl") or d.get("dCncl") or a.get("aCncl"))})
        if legs:
            out.append({"legs": legs, "walk_first": walk_first, "walk_last": walk_last,
                        "arr": htime(base, c["arr"].get("aTimeR") or c["arr"].get("aTimeS"))})
            learn_legs(legs)
    return out


# --- the delay history: every train it sees, it remembers how late it was ---

_db = None


def db():
    global _db
    if _db is None:
        _db = sqlite3.connect(DB_FILE, check_same_thread=False)
        _db.execute("create table if not exists obs (date text, name text, stop text, kind text, sched text,"
                    " delay integer, cncl integer, primary key (date, name, stop, kind, sched))")
    return _db


def remember(when, name, stop, kind, rt, cncl):
    if not when or (rt is None and not cncl):
        return
    delay = mins(rt - when) if rt else 0
    with lock:
        db().execute("insert or replace into obs values (?,?,?,?,?,?,?)",
                     (when.date().isoformat(), name, stop, kind, hm(when), delay, int(bool(cncl))))
        db().commit()


def learn_legs(legs):
    for l in legs:
        remember(l["dep"], l["name"], l["from"], "dep", l["dep_rt"], l["cncl"])
        remember(l["arr"], l["name"], l["to"], "arr", l["arr_rt"], l["cncl"])


def history(name, stop, kind, sched):
    """(typical delay, bad-day delay, cancel rate, days seen) for one train at one stop"""
    with lock:
        rows = db().execute("select date, delay, cncl from obs where name=? and stop=? and kind=? and sched=?"
                            " order by date desc limit 60", (name, stop, kind, hm(sched))).fetchall()
    wd = sched.weekday()
    same = [r for r in rows if dt.date.fromisoformat(r[0]).weekday() == wd]
    rows = same if len(same) >= 6 else rows
    if len(rows) < 4:
        return None
    d = sorted(r[1] for r in rows if not r[2])
    if not d:
        return 0, 0, 1.0, len(rows)
    return d[len(d) // 2], d[min(len(d) - 1, int(len(d) * 0.85))], sum(r[2] for r in rows) / len(rows), len(rows)


def board_tick():
    # every few minutes: what's leaving ternberg and what's arriving in linz, for the history
    now = dt.datetime.now()
    for stop, kind in (("bf", "DEP"), ("schulen", "DEP"), ("hbf", "ARR"), ("hbf", "DEP")):
        try:
            r = mgate({"meth": "StationBoard", "req": {"type": kind, "stbLoc": place(stop), "maxJny": 40,
                                                      "date": now.strftime("%Y%m%d"), "time": (now - dt.timedelta(minutes=10)).strftime("%H%M%S"), "dur": 40}})
        except Exception:
            continue
        prods = r["common"]["prodL"]
        for j in r.get("jnyL", []):
            name = prods[j["prodX"]].get("name", "?")
            if stop == "hbf" and not name.startswith(("R 1", "REX 1", "S 1", "IC", "RJ", "WB")):
                continue
            base = dt.datetime.strptime(j["date"], "%Y%m%d").date()
            st = j["stbStop"]
            k = "d" if kind == "DEP" else "a"
            stop_name = {"bf": "Ternberg Bahnhst", "schulen": "Ternberg Schulen", "hbf": "Linz/Donau Hbf"}[stop]
            remember(htime(base, st.get(k + "TimeS")), name, stop_name, "dep" if kind == "DEP" else "arr",
                     htime(base, st.get(k + "TimeR")), j.get("isCncl") or st.get(k + "Cncl"))


# --- untis: what's on, who teaches it, where ---

def untis_lessons(day):
    state = load(os.path.join(UNTIS, "state.json"), {})
    out = []
    for l in (state.get("lessons") or {}).values():
        if not l["start"].startswith(day.isoformat()) or l.get("status") == "CANCELLED":
            continue
        out.append({"start": at(day, l["start"][11:16]), "end": at(day, l["end"][11:16]),
                    "subject": l["subject"], "rooms": l.get("rooms") or [], "status": l.get("status"),
                    "text": l.get("text", "")})
    out.sort(key=lambda l: l["start"])
    return out


def untis_fresh():
    state = load(os.path.join(UNTIS, "state.json"), {})
    try:
        return (dt.datetime.now() - dt.datetime.fromisoformat(state["checked"])).total_seconds() < 3 * 3600
    except (KeyError, ValueError):
        return False


def school_day(day):
    return day.weekday() < 5 and bool(untis_lessons(day))


def teacher(c, l):
    if l["status"] == "SUBSTITUTION":
        return None  # someone else, mood unknown
    wd = DAYS[l["start"].weekday()]
    subj = l["subject"].lower()
    best = None
    for key, t in c["teachers"].items():
        d, _, s = key.partition(" ")
        if subj.startswith(s.lower()):
            if d == wd:
                return t
            best = best or t
    return best


def room_walk(c, l):
    room = (l["rooms"] or [""])[0]
    for prefix in sorted(c["room_walk"], key=len, reverse=True):
        if room.startswith(prefix):
            return c["room_walk"][prefix]
    return 5


def describe(c, l):
    t = teacher(c, l)
    short = next((v for k, v in sorted(c.get("short", {}).items(), key=lambda kv: -len(kv[0]))
                  if l["subject"].startswith(k)), l["subject"].split(" - ")[0].split(",")[0][:24])
    room = (l["rooms"] or [""])[0]
    return "%s %s%s%s" % (hm(l["start"]), short, " bei " + t if t else "", " (%s)" % room if room else "")


# --- judging a connection: live data if there is some, otherwise what PRISMO has learned ---

def guess(leg, kind):
    sched, rt = leg[kind], leg[kind + "_rt"]
    if rt:
        return rt, rt + dt.timedelta(minutes=1)
    stop = leg["from"] if kind == "dep" else leg["to"]
    h = history(leg["name"], stop, kind, sched)
    if h:
        return sched + dt.timedelta(minutes=h[0]), sched + dt.timedelta(minutes=h[1])
    slack = (0, 2) if leg["line"].startswith("Tram") else (1, 4)
    return sched + dt.timedelta(minutes=slack[0]), sched + dt.timedelta(minutes=slack[1])


def judge(conn):
    """expected and pessimistic arrival, or None if a leg is cancelled or a change can't work"""
    exp = worst = None
    for i, leg in enumerate(conn["legs"]):
        if leg["cncl"]:
            return None
        if i:
            dep_exp, _ = guess(leg, "dep")
            if exp and dep_exp < exp:  # the train you need left before you got there
                return None
            if worst and dep_exp < worst:
                conn["tight"] = leg["from"]
        exp, worst = guess(leg, "arr")
    walk = dt.timedelta(minutes=conn.get("walk_last", 0))
    conn["exp"], conn["worst"] = exp + walk, worst + walk
    return conn


def trains(conn):
    # changes that matter: train to train. the tram at the end doesn't count
    def city(line):
        kind, _, num = line.partition(" ")
        return kind == "Tram" or (kind == "Bus" and num.isdigit() and int(num) < 100)
    return sum(1 for l in conn["legs"] if not city(l["line"]))


def first_dep(conn):
    l = conn["legs"][0]
    return l["dep_rt"] or l["dep"]


# --- the plans ---

def leave_for(c, stop, dep):
    """when to leave home for a departure at ternberg bf / schulen, and how"""
    car = dep - dt.timedelta(minutes=c["car"] + c["margin"])
    who = "Papa" if hm(car) <= c["dad_until"] else "Mama"
    alt = None
    if stop == "schulen":
        alt = dep - dt.timedelta(minutes=c["walk_schulen"] + 1)
    return car, who, alt


def morning(day, earliest=None):
    c = cfg()
    lessons = untis_lessons(day)
    if day.weekday() >= 5 or not lessons:
        return {"school": False, "day": day.isoformat()}
    first = lessons[0]
    t = teacher(c, first)
    mood = c["moods"].get(t or "", "unknown")
    walk = room_walk(c, first)
    deadline = first["start"] - dt.timedelta(minutes=walk)  # at the goethekreuzung stop

    cands = []
    for stop in ("bf", "schulen"):
        try:
            found = trips(stop, "goethe", deadline + dt.timedelta(minutes=8), arrive=True, n=4)
            if earliest:
                found += trips(stop, "goethe", earliest, n=3)
        except Exception as e:
            print("trips failed: %s" % e, flush=True)
            continue
        for conn in found:
            # where he actually gets on, not where the search started (hafas likes to walk you to the bus)
            conn["stop"] = "schulen" if "Schulen" in conn["legs"][0]["from"] else "bf"
            if judge(conn) and (not earliest or first_dep(conn) >= earliest):
                cands.append(conn)
    if not cands:
        return {"school": True, "day": day.isoformat(), "first": first, "teacher": t, "mood": mood,
                "error": "keine Verbindung gefunden"}

    on_time = [x for x in cands if x["worst"] <= deadline]
    if on_time:
        best = max(on_time, key=lambda x: (first_dep(x), -len(x["legs"])))
    else:
        best = min(cands, key=lambda x: (x["exp"], len(x["legs"])))

    # same first train, fewer changes, a bit later: the "just stay asleep" option
    comfy = None
    for x in cands:
        if x is not best and x["stop"] == best["stop"] and first_dep(x) == first_dep(best) \
                and trains(x) < trains(best) and x["exp"] > best["exp"]:
            comfy = x if not comfy or x["exp"] < comfy["exp"] else comfy
    if not comfy and trains(best) > 1:
        try:
            for x in trips(best["stop"], "goethe", first_dep(best), n=4):
                if judge(x) and first_dep(x) == first_dep(best) and trains(x) < trains(best):
                    x["stop"] = best["stop"] if not x["walk_first"] else x["stop"] if "stop" in x else best["stop"]
                    comfy = x
                    break
        except Exception:
            pass

    late_best = mins(best["exp"] + dt.timedelta(minutes=walk) - first["start"])
    tol = c["tolerance"].get(mood, 3)
    advice, late_comfy = "go", None
    if comfy:
        late_comfy = mins(comfy["exp"] + dt.timedelta(minutes=walk) - first["start"])
        advice = "stay" if late_comfy <= tol else "switch"
    elif trains(best) > 1:
        advice = "switch"

    dep = first_dep(best)
    leave, who, alt = leave_for(c, best["stop"], dep)
    wake = leave - dt.timedelta(minutes=c["prep"])
    normal = at(day, c["normal_wake"])
    if abs(mins(wake - normal)) <= 2:
        wake = normal  # don't move the alarm for a minute or two
    return {"school": True, "day": day.isoformat(), "first": first, "teacher": t, "mood": mood, "walk": walk,
            "deadline": deadline, "best": best, "comfy": comfy, "advice": advice, "late": late_best,
            "late_comfy": late_comfy, "leave": leave, "who": who, "walk_leave": alt, "wake": wake,
            "normal": normal, "skipped": [l for l in untis_lessons_all(day) if l["start"] < first["start"]]}


def untis_lessons_all(day):
    state = load(os.path.join(UNTIS, "state.json"), {})
    out = [{"start": at(day, l["start"][11:16]), "subject": l["subject"], "status": l.get("status")}
           for l in (state.get("lessons") or {}).values() if l["start"].startswith(day.isoformat())]
    return sorted(out, key=lambda l: l["start"])


def home_options(day, leave, n=2):
    out = []
    for dest in ("bf", "schulen"):
        try:
            for x in trips("goethe", dest, leave, n=3):
                if judge(x):
                    x["dest"] = dest
                    out.append(x)
        except Exception as e:
            print("trips failed: %s" % e, flush=True)
    out.sort(key=lambda x: (x["exp"], len(x["legs"])))
    seen, res = set(), []
    for x in out:
        k = hm(x["exp"])
        if k not in seen:
            seen.add(k)
            res.append(x)
    return res[:n]


def afternoon(day):
    c = cfg()
    lessons = untis_lessons(day)
    if not lessons:
        return None
    last = lessons[-1]
    t = teacher(c, last)
    walk = room_walk(c, last)
    out = {"last": last, "teacher": t, "options": []}
    rule = next((e for e in c["early"] if e.get("teacher") == t and (not e.get("day") or e["day"] == DAYS[day.weekday()])), None)
    times = []
    if rule and at(day, rule["at"]) < last["end"]:
        times.append((at(day, rule["at"]), rule))
    times.append((last["end"], None))
    for leave, r in times:
        opts = home_options(day, leave + dt.timedelta(minutes=walk), n=1)
        if opts:
            out["options"].append({"leave": leave, "rule": r, "conn": opts[0]})
    return out


# --- words ---

def conn_text(x, short=False):
    parts = []
    for l in x["legs"]:
        dep = l["dep_rt"] or l["dep"]
        late = mins(l["dep_rt"] - l["dep"]) if l["dep_rt"] else 0
        s = "%s %s%s" % (l["line"].replace("Tram ", "Bim "), hm(dep), " (+%d)" % late if late >= 2 else "")
        parts.append(s)
    return " → ".join(parts) + ("" if short else " → an %s" % hm(x["exp"]))


def morning_text(p, title=True):
    if not p.get("school"):
        return "Keine Schule 🎉"
    if p.get("error"):
        return "%s: %s" % (describe(cfg(), p["first"]), p["error"])
    c = cfg()
    lines = []
    if title:
        lines.append("1. Stunde: " + describe(c, p["first"]))
    skipped = [s for s in p["skipped"] if s["status"] == "CANCELLED"]
    if skipped:
        lines.append("❌ entfällt davor: " + ", ".join(hm(s["start"]) for s in skipped))
    b = p["best"]
    stop = STOP_NAME[b["stop"]]
    how = p["who"] if b["stop"] == "bf" else "%s (oder %s zu Fuß)" % (p["who"], hm(p["walk_leave"]))
    lines.append("⏰ %s aufstehen, %s los mit %s → %s" % (hm(p["wake"]), hm(p["leave"]), how, stop))
    lines.append("🚆 " + conn_text(b))
    at_class = b["exp"] + dt.timedelta(minutes=p["walk"])
    lines.append("🏫 in der Klasse %s%s" % (hm(at_class), "" if p["late"] <= 0 else " (%d min zu spät)" % p["late"]))
    if p["advice"] == "stay":
        lines.append("😴 sitzen bleiben passt: ca. %d min zu spät, %s ist %s" % (max(p["late_comfy"], 0), p["teacher"], p["mood"]))
    elif p["advice"] == "switch":
        sw = b["legs"][1]
        lines.append("🔁 in %s umsteigen (%s, Gleis %s)%s" % (b["legs"][0]["to"].split(" ")[0], sw["line"], sw["plat"] or "?",
                     ", sitzen bleiben = %d min zu spät bei %s%s" % (p["late_comfy"], p["teacher"], " 😈" if p["mood"] == "devil" else "")
                     if p["late_comfy"] is not None else ""))
    if b.get("tight"):
        lines.append("⚠️ Umstieg in %s wird knapp" % b["tight"])
    return "\n".join(lines)


def afternoon_text(a):
    if not a or not a["options"]:
        return "Heimweg: nichts gefunden"
    lines = ["Letzte Stunde bis %s%s" % (hm(a["last"]["end"]), " bei " + a["teacher"] if a["teacher"] else "")]
    opts = a["options"]
    if len(opts) == 2 and hm(opts[0]["conn"]["exp"]) == hm(opts[1]["conn"]["exp"]):
        opts = opts[1:]  # leaving early gets you home at the same time anyway
        lines.append("(früher gehen bringt heute nichts, gleicher Zug)")
    for o in opts:
        r = o["rule"]
        head = "🏃 um %s gehen (%s)" % (hm(o["leave"]), r.get("note", "")) if r else "🔔 um %s raus" % hm(o["leave"])
        lines.append("%s: %s → Ternberg %s" % (head, conn_text(o["conn"], short=True), hm(o["conn"]["exp"])))
    return "\n".join(lines)


# --- pushes (same ntfy topic as the untis watcher) ---

def push(title, msg, tags=None):
    u = load(os.path.join(UNTIS, "config.json"), {})
    if not u.get("topic"):
        print("push: %s\n%s" % (title, msg), flush=True)
        return
    body = {"topic": u["topic"], "title": title, "message": msg, "priority": 5, "tags": tags or []}
    try:
        req = urllib.request.Request(u.get("ntfy", "https://ntfy.sh"), data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print("push failed: %s" % e, flush=True)


# --- the action button ---

def dist(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742000 * math.asin(math.sqrt(h))


def home_coords():
    pc = load(os.path.join(P, "config.json"), {})
    return (pc["lat"], pc["lon"]) if "lat" in pc else None


SCHOOL = (48.2988, 14.2967)  # around goethestraße 17


def now_answer(lat=None, lon=None):
    c = cfg()
    now = dt.datetime.now().replace(second=0, microsecond=0)
    today = now.date()
    here = (lat, lon) if lat is not None else None
    home = home_coords()
    at_home = here is None or (home and dist(here, home) < 500)
    lessons = untis_lessons(today) if today.weekday() < 5 else []
    out = []

    if lessons and now < lessons[0]["start"] and at_home:
        p = morning(today, earliest=now + dt.timedelta(minutes=c["car"] + 1))
        plan = morning(today)
        if p.get("best"):
            b = p["best"]
            buf = mins(first_dep(b) - now - dt.timedelta(minutes=c["car"]))
            out.append("Jetzt los: %s %s schaffst du (%d min Luft)" % (b["legs"][0]["line"], hm(first_dep(b)), buf))
            out.append(morning_text(p, title=False).split("\n", 1)[-1])
        if plan.get("leave"):
            out.append("Spätestens los: %s (für %s)" % (hm(plan["leave"]), describe(c, plan["first"])))
        return "\n".join(out) or "Keine Verbindung gefunden"

    if lessons and now < lessons[-1]["end"] and not at_home and here and dist(here, SCHOOL) < 700:
        a = afternoon(today)
        return afternoon_text(a)

    # anywhere else: the next ways home (or to school, if it's before school)
    frm = here if here else "bf"
    to = "goethe" if (lessons and now < lessons[0]["start"] and not at_home) else "bf"
    try:
        found = [x for x in trips(frm, to, now, n=4) if judge(x)]
    except Exception as e:
        return "ÖBB antwortet nicht (%s)" % e
    if not found:
        return "Keine Verbindung gefunden"
    out.append("Nach %s:" % ("Linz Schule" if to == "goethe" else "Ternberg"))
    for x in found[:3]:
        walk = " (%d min zu Fuß zur Haltestelle)" % x["walk_first"] if x["walk_first"] else ""
        out.append("%s%s" % (conn_text(x), walk))
    return "\n".join(out)


def alarm_answer():
    """for the iphone shortcut at 05:50: when should the alarm ring today"""
    now = dt.datetime.now()
    day = now.date() if now.hour < 12 else now.date() + dt.timedelta(days=1)
    c = cfg()
    if not untis_fresh():
        return {"alarm": c["normal_wake"], "normal": c["normal_wake"], "why": "Untis gerade nicht aktuell"}
    if not school_day(day):
        return {"alarm": "", "normal": c["normal_wake"], "why": "keine Schule"}
    p = morning(day)
    if not p.get("wake"):
        return {"alarm": c["normal_wake"], "normal": c["normal_wake"], "why": p.get("error", "")}
    return {"alarm": hm(p["wake"]), "normal": c["normal_wake"], "why": describe(c, p["first"])}


# --- the loop: watches the trains, sends the pushes ---

def state():
    return load(STATE_FILE, {})


def mark(key, value=True):
    s = state()
    s[key] = value
    for k in list(s):  # forget old days
        if k[:10].count("-") == 2 and k[:10] < (dt.date.today() - dt.timedelta(days=14)).isoformat():
            del s[k]
    save(STATE_FILE, s)


def next_school_day(after):
    d = after + dt.timedelta(days=1)
    for _ in range(10):
        if school_day(d):
            return d
        d += dt.timedelta(days=1)
    return None


def evening(now):
    day = now.date() + dt.timedelta(days=1)
    if not school_day(day):
        return
    key = day.isoformat() + ":evening"
    p = morning(day)
    if not p.get("wake"):
        return
    s = state()
    if key not in s:
        push("🌙 Morgen (%s)" % DAYS[day.weekday()], morning_text(p), ["calendar"])
        mark(key, hm(p["wake"]))
    elif s[key] != hm(p["wake"]):
        push("🔄 Neuer Plan für morgen", morning_text(p), ["warning"])
        mark(key, hm(p["wake"]))


def watch_morning(now):
    today = now.date()
    if not school_day(today):
        return
    p = morning(today)
    if not p.get("best"):
        return
    k = today.isoformat()
    s = state()
    b = p["best"]
    first = b["legs"][0]
    sig = "%s %s" % (first["name"], hm(first["dep"]))
    late = mins(first["dep_rt"] - first["dep"]) if first["dep_rt"] else 0

    # before leaving: tell if the plan changes (cancelled train, real delay, other connection)
    if now < p["leave"] + dt.timedelta(minutes=2):
        was = s.get(k + ":sig")
        if was and (was != sig or abs(late - s.get(k + ":late", 0)) >= 3):
            push("🚆 Planänderung", morning_text(p), ["warning"])
        mark(k + ":sig", sig)
        mark(k + ":late", late)
        if p["wake"] > now:
            mark(k + ":wake", hm(p["wake"]))

    # on the train: wake him up before st. valentin if switching matters
    if p["advice"] == "switch" and trains(b) > 1 and not s.get(k + ":wakeup"):
        arr, _ = guess(b["legs"][0], "arr")
        if first_dep(b) <= now and arr - dt.timedelta(minutes=4) <= now < arr:
            sw = b["legs"][1]
            push("📢 AUFWACHEN, umsteigen!", "%s in %d min. Raus und rüber in den %s (Gleis %s, ab %s). %s" % (
                b["legs"][0]["to"].split(" ")[0], max(mins(arr - now), 0), sw["line"], sw["plat"] or "?",
                hm(sw["dep_rt"] or sw["dep"]), "%s wartet nicht 😈" % p["teacher"] if p["mood"] == "devil" else ""), ["rotating_light"])
            mark(k + ":wakeup")


def watch_afternoon(now):
    today = now.date()
    lessons = untis_lessons(today) if today.weekday() < 5 else []
    if not lessons:
        return
    k = today.isoformat() + ":home"
    if state().get(k):
        return
    c = cfg()
    last = lessons[-1]
    t = teacher(c, last)
    rule = next((e for e in c["early"] if e.get("teacher") == t and e.get("day", DAYS[today.weekday()]) == DAYS[today.weekday()]), None)
    first_out = at(today, rule["at"]) if rule and at(today, rule["at"]) < last["end"] else last["end"]
    if first_out - dt.timedelta(minutes=20) <= now < last["end"]:
        push("🏠 Heimweg", afternoon_text(afternoon(today)), ["house"])
        mark(k)


def weekly(now):
    k = now.date().isoformat() + ":weekly"
    if state().get(k):
        return
    mark(k)
    week = (now.date() - dt.timedelta(days=7)).isoformat()
    with lock:
        rows = db().execute("select name, sched, count(*), avg(delay), max(delay), sum(cncl) from obs where date>? and"
                            " stop='Ternberg Bahnhst' and kind='dep' and sched between '06:00' and '07:30'"
                            " group by name, sched order by sched", (week,)).fetchall()
    with lock:
        total = db().execute("select count(*) from obs").fetchone()[0]
    lines = ["%s %s: Ø %+.1f min, max +%d%s" % (r[1], r[0].split(" (")[0], r[3] or 0, r[4] or 0,
                                                ", %dx ausgefallen" % r[5] if r[5] else "") for r in rows if r[2] >= 3]
    lines.append("📚 PRISMO kennt jetzt %d Abfahrten" % total)
    push("📊 Deine Züge diese Woche", "\n".join(lines), ["bar_chart"])


def loop():
    last_board = 0
    while True:
        now = dt.datetime.now().replace(microsecond=0)
        try:
            if 5 <= now.hour < 22 and time.time() - last_board > 300:
                board_tick()
                last_board = time.time()
            if now.hour == 21 or (now.hour == 22 and now.minute < 30) or (now.hour == 5 and now.minute >= 40):
                if now.minute % 15 == 0 or (now.hour == 21 and now.minute < 2) or now.hour == 5:
                    evening(now if now.hour >= 12 else now - dt.timedelta(days=1))
            if 5 <= now.hour < 10:
                watch_morning(now)
            if 11 <= now.hour < 19:
                watch_afternoon(now)
            if now.weekday() == 6 and now.hour == 19 and now.minute < 2:
                weekly(now)
        except Exception as e:
            print("loop: %s" % e, flush=True)
        time.sleep(60 - dt.datetime.now().second % 60)


# --- http, only on the tailnet; oracle relays the phone's requests here ---

class Handler(BaseHTTPRequestHandler):
    def reply(self, code, text, kind="text/plain; charset=utf-8"):
        data = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if u.path == "/day/now":
                lat, lon = q.get("lat"), q.get("lon")
                f = lambda v: float(v.replace(",", ".")) if v else None
                return self.reply(200, now_answer(f(lat), f(lon)))
            if u.path == "/day/alarm":
                return self.reply(200, json.dumps(alarm_answer(), ensure_ascii=False), "application/json")
            if u.path == "/day/plan":
                d = dt.date.fromisoformat(q["date"]) if q.get("date") else next_school_day(dt.date.today() - dt.timedelta(days=1))
                text = morning_text(morning(d)) if d else "Keine Schule in Sicht"
                if d:
                    text += "\n\n" + afternoon_text(afternoon(d))
                return self.reply(200, text)
            if u.path == "/day/event":
                e = q.get("e", "")[:20]
                mark(dt.date.today().isoformat() + ":event:" + e, dt.datetime.now().strftime("%H:%M"))
                return self.reply(200, "ok")
        except Exception as e:
            return self.reply(500, "PRISMO: %s" % e)
        self.reply(404, "not found")

    def log_message(self, *a):
        pass


def show_plan(day):
    print(morning_text(morning(day)))
    print()
    print(afternoon_text(afternoon(day)))


if __name__ == "__main__":
    os.makedirs(P, exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "serve":
        host = sys.argv[sys.argv.index("--host") + 1] if "--host" in sys.argv else "127.0.0.1"
        threading.Thread(target=loop, daemon=True).start()
        print("prismo-day on %s:8781" % host, flush=True)
        ThreadingHTTPServer((host, 8781), Handler).serve_forever()
    elif cmd == "plan":
        show_plan(dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else next_school_day(dt.date.today() - dt.timedelta(days=1)))
    elif cmd == "now":
        print(now_answer(*(float(x) for x in sys.argv[2:4])) if len(sys.argv) > 3 else now_answer())
    elif cmd == "alarm":
        print(alarm_answer())
