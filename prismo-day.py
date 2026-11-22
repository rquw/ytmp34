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


# --- the day as steps: what to do when. the button and the pushes both read this ---

_cache = {}


def cached(key, fn, ttl=60):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val


def plans(day, ttl=60):
    m = cached((day, "m"), lambda: morning(day), ttl)
    a = cached((day, "a"), lambda: afternoon(day), ttl) if m.get("school") else None
    return m, a


def short_line(l):
    return l["line"].replace("Tram ", "Bim ")


def where(l):
    if "Tiefgescho" in l["from"]:
        return "unten im Tiefgeschoß"
    return "Gleis %s" % l["plat"] if l.get("plat") else ""


def ride_steps(conn, pushes=True):
    steps, legs = [], conn["legs"]
    for i, l in enumerate(legs):
        dep = l["dep_rt"] or l["dep"]
        nxt = legs[i + 1] if i + 1 < len(legs) else None
        arr, _ = guess(l, "arr")
        if i == 0:
            detail = where(l)
            if nxt and trains(conn) > 1 and mins(arr - dep) >= 15 and not short_line(nxt).startswith("Bim"):
                detail += (", " if detail else "") + "schlaf, ich weck dich %s" % hm(arr - dt.timedelta(minutes=4))
            steps.append({"t": dep, "icon": "🚋" if short_line(l).startswith("Bim") else "🚆",
                          "head": "%s %s" % (short_line(l), hm(dep)), "detail": detail, "push": False, "lead": 0})
        else:
            prev = legs[i - 1]
            prev_arr, _ = guess(prev, "arr")
            city = short_line(l).startswith(("Bim", "Bus")) and short_line(l) != "Bus 440"
            place_name = prev["to"].split(" (")[0].replace("Linz/Donau ", "Linz ").replace(" Bahnhof", "").replace(" Bahnhst", "")
            t = max(prev_arr - dt.timedelta(minutes=3), (prev["dep_rt"] or prev["dep"]) + dt.timedelta(minutes=1))
            steps.append({"t": t, "icon": "🚋" if city else "🔁",
                          "head": "%s %s: %s %s" % ("Raus in" if city else "Umsteigen in", place_name, short_line(l), hm(dep)),
                          "detail": where(l), "push": pushes and not city, "lead": 0, "loud": True})
    return steps


def pick_home(a):
    return next((o for o in a["options"] if o["rule"] and o["rule"].get("sure")), a["options"][-1])


def timeline(day, ttl=60):
    m, a = plans(day, ttl)
    steps = []
    if m.get("best"):
        b = m["best"]
        ride = m["comfy"] if m["advice"] == "stay" and m["comfy"] else b
        stop = STOP_NAME[b["stop"]]
        who = m["who"] if b["stop"] == "bf" else "%s (oder %s zu Fuß)" % (m["who"], hm(m["walk_leave"]))
        steps.append({"t": m["wake"], "icon": "⏰", "head": "Aufstehen", "detail": "um %s los" % hm(m["leave"]), "push": True, "kind": "wake"})
        steps.append({"t": m["leave"], "icon": "🚗", "head": "Los mit %s" % who,
                      "detail": "%s, %s %s" % (stop, short_line(b["legs"][0]), hm(first_dep(b))), "push": True, "lead": 2})
        rides = ride_steps(ride)
        if ride is not b:
            rides[0]["detail"] = "durchschlafen, %s ist %s 😴" % (m["teacher"], m["mood"])
        steps += rides
        steps.append({"t": ride["exp"], "icon": "🏫", "head": "%d min zur %s" % (m["walk"], (m["first"]["rooms"] or ["Klasse"])[0]),
                      "detail": describe(cfg(), m["first"]), "push": False})
    if a and a["options"]:
        o = pick_home(a)
        other = [x for x in a["options"] if x is not o and hm(x["conn"]["exp"]) != hm(o["conn"]["exp"])]
        detail = "%s %s, Ternberg %s" % (short_line(o["conn"]["legs"][0]), hm(first_dep(o["conn"])), hm(o["conn"]["exp"]))
        if other:
            x = other[0]
            detail += "\n(%s: um %s raus = Ternberg %s)" % (x["rule"]["note"] if x["rule"] else "oder", hm(x["leave"]), hm(x["conn"]["exp"]))
        steps.append({"t": o["leave"], "icon": "🔔", "head": "Raus aus der Klasse", "detail": detail, "push": True, "lead": 5})
        steps += ride_steps(o["conn"], pushes=False)
        steps.append({"t": o["conn"]["exp"], "icon": "🏠", "head": "Ternberg an", "detail": "", "push": False})
    steps.sort(key=lambda s: s["t"])
    return steps


def in_min(t, now):
    n = mins(t - now)
    return "jetzt" if n <= 0 else "in %d min" % n if n < 90 else "um %s" % hm(t)


def next_step(now):
    today = now.date()
    steps = timeline(today, ttl=900) if school_day(today) else []
    nxt = [s for s in steps if s["t"] > now]
    if not nxt:
        d = next_school_day(today)
        if not d:
            return "Keine Schule in Sicht 🎉"
        return "Heute nichts mehr.\n\n" + day_summary(d)
    n = nxt[0]
    lines = ["%s %s (%s)" % (n["icon"], n["head"], in_min(n["t"] - dt.timedelta(minutes=n.get("lead", 0)), now))]
    if n["detail"]:
        lines.append(n["detail"])
    if len(nxt) > 1:
        lines += ["", "danach %s %s %s" % (hm(nxt[1]["t"]), nxt[1]["icon"], nxt[1]["head"])]
    return "\n".join(lines)


def day_summary(d):
    m, a = plans(d, ttl=900)
    if not m.get("school"):
        return "Keine Schule 🎉"
    if not m.get("best"):
        return "%s\n%s" % (describe(cfg(), m["first"]), m.get("error", ""))
    b = m["best"]
    today = dt.date.today()
    when = "Heute" if d == today else "Morgen" if d == today + dt.timedelta(days=1) else DAYS[d.weekday()]
    lines = ["%s: %s" % (when, describe(cfg(), m["first"]))]
    gone = [s for s in m["skipped"] if s["status"] == "CANCELLED"]
    if gone:
        lines.append("❌ davor entfällt (%s)" % ", ".join(hm(s["start"]) for s in gone))
    lines.append("⏰ %s   🚗 %s mit %s" % (hm(m["wake"]), hm(m["leave"]), m["who"]))
    ride = "🚆 %s %s" % (short_line(b["legs"][0]), hm(first_dep(b)))
    if m["advice"] == "switch":
        ride += ", 🔁 %s %s" % (b["legs"][0]["to"].split(" ")[0], short_line(b["legs"][1]))
    elif m["advice"] == "stay":
        ride += ", durchschlafen ok 😴"
    lines.append(ride)
    used = m["comfy"] if m["advice"] == "stay" and m["comfy"] else b
    lines.append("🏫 %s in der Klasse" % hm(used["exp"] + dt.timedelta(minutes=m["walk"])))
    if a and a["options"]:
        o = pick_home(a)
        lines.append("🏠 raus %s, Ternberg %s" % (hm(o["leave"]), hm(o["conn"]["exp"])))
    return "\n".join(lines)


def compact(x):
    return " → ".join("%s %s" % (short_line(l), hm(l["dep_rt"] or l["dep"])) for l in x["legs"])


def home_now(lat=None, lon=None):
    """fastest way home from here, right now"""
    now = dt.datetime.now().replace(second=0, microsecond=0)
    here = (lat, lon) if lat is not None else None
    if here and dist(here, TERNBERG) < 2500:
        return "Du bist eh schon in Ternberg 😄"
    at_school = not here or dist(here, SCHOOL) < 700
    walk = 5 if at_school else 0
    try:
        found = [x for x in trips("goethe" if at_school else here, "bf", now + dt.timedelta(minutes=walk), n=4) if judge(x)]
    except Exception as e:
        return "ÖBB antwortet nicht (%s)" % e
    if not found:
        return "Keine Verbindung gefunden"
    found.sort(key=lambda x: (x["exp"], -first_dep(x).timestamp()))
    best = {}
    for x in found:  # per arrival time keep the one you can leave latest for
        best.setdefault(hm(x["exp"]), x)
    found = sorted(best.values(), key=lambda x: x["exp"])
    lines = []
    for i, x in enumerate(found[:2]):
        go = first_dep(x) - dt.timedelta(minutes=walk + (x["walk_first"] or 0))
        lines.append("%s los %s, Ternberg %s" % ("🏃" if i == 0 else "oder", in_min(go, now), hm(x["exp"])))
        lines.append("   " + compact(x))
    return "\n".join(lines)


def home_plan():
    today = dt.date.today()
    if not school_day(today):
        return "Heute keine Schule 🎉"
    _, a = plans(today, ttl=900)
    if not a or not a["options"]:
        return "Heimweg: nichts gefunden"
    lines = ["Letzte Stunde bis %s%s" % (hm(a["last"]["end"]), " (%s)" % a["teacher"] if a["teacher"] else "")]
    seen, same = set(), False
    for o in a["options"]:
        if hm(o["conn"]["exp"]) in seen:
            same = True
            continue
        seen.add(hm(o["conn"]["exp"]))
        lines.append("%s raus %s: Ternberg %s" % ("🏃" if o["rule"] else "🔔", hm(o["leave"]), hm(o["conn"]["exp"])))
        lines.append("   " + compact(o["conn"]))
        if o["rule"]:
            lines.append("   " + o["rule"]["note"])
    if same:
        lines.append("(früher gehen bringt heute nix, gleicher Zug)")
    return "\n".join(lines)


LINE_DIRS = ("Steyr", "Garsten", "Ternberg", "Weyer", "Kleinreifling", "Losenstein", "Großraming")


def next_trains(lat=None, lon=None):
    """just the next departures that matter from where he is"""
    now = dt.datetime.now().replace(second=0, microsecond=0)
    here = (lat, lon) if lat is not None else None
    in_ternberg = here is None or dist(here, TERNBERG) < 2500
    if in_ternberg or (here and dist(here, SCHOOL) < 700):
        stops = [("bf", None), ("schulen", None)] if in_ternberg else [("hbf", LINE_DIRS)]
        rows = []
        for stop, dirs in stops:
            try:
                r = mgate({"meth": "StationBoard", "req": {"type": "DEP", "stbLoc": place(stop), "maxJny": 30,
                                                          "date": now.strftime("%Y%m%d"), "time": now.strftime("%H%M%S"), "dur": 180}})
            except Exception as e:
                return "ÖBB antwortet nicht (%s)" % e
            prods = r["common"]["prodL"]
            for j in r.get("jnyL", []):
                d = j.get("dirTxt", "")
                if dirs and not any(w in d for w in dirs):
                    continue
                st = j["stbStop"]
                base = dt.datetime.strptime(j["date"], "%Y%m%d").date()
                s, rt = htime(base, st.get("dTimeS")), htime(base, st.get("dTimeR"))
                late = mins(rt - s) if rt else 0
                cncl = j.get("isCncl") or st.get("dCncl")
                name = prods[j["prodX"]].get("name", "?").split(" (")[0]
                rows.append((s, "%s %s → %s%s" % (hm(s), name, d.replace(" Bahnhof", "").replace("Linz/Donau Hbf", "Linz"),
                                                   " ❌" if cncl else " (+%d)" % late if late >= 2 else "")))
        rows = sorted(set(rows))
        head = "Ab Ternberg:" if in_ternberg else "Ab Linz Hbf Richtung Steyr:"
        return "\n".join([head] + [r[1] for r in rows[:6]]) if rows else "Gerade fährt nix 💤"
    try:
        found = [x for x in trips(here, "bf", now, n=4) if judge(x)]
    except Exception as e:
        return "ÖBB antwortet nicht (%s)" % e
    return "\n".join(["Nach Ternberg:"] + ["%s (an %s)" % (compact(x), hm(x["exp"])) for x in found[:4]]) or "Nix gefunden"


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
TERNBERG = (47.9430, 14.3590)


def answer(mode, lat=None, lon=None):
    # the menu texts can be anything, so go by keywords
    mode = (mode or "jetzt").lower()
    today = dt.date.today()
    if "heim" in mode or "home" in mode:
        return home_now(lat, lon)
    if "zug" in mode or "züge" in mode or "bahn" in mode:
        return next_trains(lat, lon)
    if "linz" in mode:
        return linz_answer()
    if "morgen" in mode:
        d = next_school_day(today)
        return day_summary(d) if d else "Keine Schule in Sicht 🎉"
    if "stunden" in mode or "heute" in mode:
        if not school_day(today):
            d = next_school_day(today)
            return "Heute keine Schule 🎉" + ("\n\nNächster Schultag:\n" + day_summary(d) if d else "")
        return day_summary(today) + "\n\n" + home_plan()
    return next_step(dt.datetime.now().replace(second=0, microsecond=0))


def warm(now):
    # keep today's and the next school day's plan ready, so the button answers instantly
    for d in {now.date(), next_school_day(now.date())}:
        if d and school_day(d):
            plans(d, ttl=600)


def now_answer(lat=None, lon=None):
    c = cfg()
    now = dt.datetime.now().replace(second=0, microsecond=0)
    today = now.date()
    here = (lat, lon) if lat is not None else None
    home = home_coords()
    # anywhere in ternberg counts as home: from there it's always the same trip
    at_home = here is None or dist(here, TERNBERG) < 2500 or bool(home and dist(here, home) < 1500)
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

    if at_home:
        # nothing left today: show the next school day
        d = next_school_day(today)
        if not d:
            return "Keine Schule in Sicht 🎉"
        when = "Morgen" if d == today + dt.timedelta(days=1) else "%s %s." % (DAYS[d.weekday()], d.strftime("%d.%m"))
        return "%s:\n%s" % (when, morning_text(morning(d)))

    if lessons and now < lessons[-1]["end"] and here and dist(here, SCHOOL) < 700:
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
    _cache.pop((day, "m"), None)
    _cache.pop((day, "a"), None)
    if key not in s:
        push("🌙 Morgen", day_summary(day), ["calendar"])
        mark(key, hm(p["wake"]))
    elif s[key] != hm(p["wake"]):
        push("🔄 Neuer Plan für morgen", day_summary(day), ["warning"])
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
        if was and now >= p["wake"] and (was != sig or abs(late - s.get(k + ":late", 0)) >= 3):
            _cache.pop((today, "m"), None)
            if first["cncl"] or was != sig:
                msg = "Neuer Plan: %s %s, los um %s" % (short_line(first), hm(first_dep(b)), hm(p["leave"]))
            else:
                msg = "%s %s hat +%d, los um %s" % (short_line(first), hm(first["dep"]), late, hm(p["leave"]))
            push("🚆 Verspätung" if late >= 3 and was == sig else "❌ Zug fällt aus", msg, ["warning"])
        mark(k + ":sig", sig)
        mark(k + ":late", late)
        if p["wake"] > now:
            mark(k + ":wake", hm(p["wake"]))

def wake_lines(day):
    m, a = plans(day, ttl=60)
    if not m.get("best"):
        return None, []
    b = m["best"]
    f = b["legs"][0]
    late = mins(f["dep_rt"] - f["dep"]) if f["dep_rt"] else 0
    gone = [s for s in m["skipped"] if s["status"] == "CANCELLED"]
    lines = [describe(cfg(), m["first"])]
    lines.append("🚗 %s mit %s, %s %s %s" % (hm(m["leave"]), m["who"], short_line(f), hm(f["dep"]),
                                         "+%d ⚠️" % late if late >= 2 else "pünktlich ✅"))
    if m["advice"] == "switch":
        lines.append("🔁 in %s umsteigen, ich weck dich" % f["to"].split(" ")[0])
    elif m["advice"] == "stay":
        lines.append("😴 durchschlafen ok (%s)" % m["teacher"])
    if a and a["options"]:
        o = pick_home(a)
        lines.append("🏠 raus %s, Ternberg %s" % (hm(o["leave"]), hm(o["conn"]["exp"])))
    if gone:
        title = "⏰ Guten Morgen! %s. Stunde entfällt" % ".+".join(str(i + 1) for i in range(len(gone)))
    else:
        title = "⏰ Guten Morgen! Normaler Tag"
    return title, lines


def wake_briefing(day):
    # the old 06:08 briefing (weather, prismo) now comes with the day plan, right when he gets up
    title, lines = wake_lines(day)
    if not title:
        return
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prismo_main", os.path.join(P, "prismo.py"))
        pm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pm)
        pm.briefing(top=lines, title=title)
    except Exception as e:
        print("briefing via prismo.py failed: %s" % e, flush=True)
        push(title, "\n".join(lines), ["sunrise"])


def linz_answer():
    """the phone just arrived at linz hbf: which tram, and on time?"""
    now = dt.datetime.now().replace(second=0, microsecond=0)
    today = now.date()
    lessons = [l for l in untis_lessons(today) if l["end"] > now] if today.weekday() < 5 else []
    if not lessons or lessons[0]["start"] > now + dt.timedelta(hours=3):
        return ""  # not on the way to school: stay quiet
    c = cfg()
    nxt = lessons[0]
    walk = room_walk(c, nxt)
    try:
        found = [x for x in trips("hbf", "goethe", now, n=3) if judge(x)]
    except Exception as e:
        return "ÖBB antwortet nicht (%s)" % e
    if not found:
        return ""
    x = min(found, key=lambda x: x["exp"])
    l = x["legs"][0]
    at_class = x["exp"] + dt.timedelta(minutes=walk)
    late = mins(at_class - nxt["start"])
    t = teacher(c, nxt)
    lines = ["🚋 %s %s, %s" % (short_line(l), hm(l["dep_rt"] or l["dep"]), where(l) or "zu Fuß")]
    if late <= 0:
        lines.append("🏫 %s in der %s, pünktlich ✅" % (hm(at_class), (nxt["rooms"] or ["Klasse"])[0]))
    else:
        lines.append("🏫 %s, %d min zu spät%s" % (hm(at_class), late, " bei %s (%s)" % (t, c["moods"].get(t, "?")) if t else ""))
    return "\n".join(lines)


def watch_steps(now):
    # one push per thing to do, right when it's time: the plan as a guided tour
    today = now.date()
    if not school_day(today):
        return
    steps = timeline(today, ttl=600)
    if any(s["push"] and 0 <= mins(s["t"] - now) <= 25 for s in steps):
        steps = timeline(today, ttl=60)  # something's coming up: keep it live
    s = state()
    for i, st in enumerate(steps):
        if not st["push"]:
            continue
        k = "%s:step:%s:%s" % (today.isoformat(), st["head"].split(" ")[0], hm(st["t"])[:4])
        due = st["t"] - dt.timedelta(minutes=st.get("lead", 0))
        if due <= now < st["t"] + dt.timedelta(minutes=3) and not s.get(k) and st.get("kind") == "wake":
            mark(k)
            wake_briefing(today)
            s = state()
            continue
        if due <= now < st["t"] + dt.timedelta(minutes=3) and not s.get(k):
            body = [st["detail"]] if st["detail"] else []
            if i + 1 < len(steps):
                n = steps[i + 1]
                body.append("danach %s %s %s" % (hm(n["t"]), n["icon"], n["head"]))
            title = "%s %s" % (st["icon"], st["head"])
            if st.get("lead"):
                title += " (in %d min)" % max(mins(st["t"] - now), 0)
            push(title, "\n".join(body), ["rotating_light"] if st.get("loud") else [])
            mark(k)
            s = state()


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
            if 5 <= now.hour < 10:
                watch_morning(now)
            if 5 <= now.hour < 20:
                watch_steps(now)
            if now.minute % 5 == 0:
                warm(now)
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
                return self.reply(200, answer(q.get("mode"), f(lat), f(lon)))
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
        threading.Thread(target=warm, args=(dt.datetime.now(),), daemon=True).start()
        print("prismo-day on %s:8781" % host, flush=True)
        ThreadingHTTPServer((host, 8781), Handler).serve_forever()
    elif cmd == "plan":
        show_plan(dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else next_school_day(dt.date.today() - dt.timedelta(days=1)))
    elif cmd == "now":
        print(now_answer(*(float(x) for x in sys.argv[2:4])) if len(sys.argv) > 3 else now_answer())
    elif cmd == "alarm":
        print(alarm_answer())
    elif cmd == "steps":
        d = dt.date.fromisoformat(sys.argv[2])
        for st in timeline(d):
            print("%s %s %s%s | %s" % (hm(st["t"]), st["icon"], st["head"], " [push]" if st["push"] else "", st["detail"].replace("\n", " ")))
        print()
        print(day_summary(d))
        if len(sys.argv) > 3:  # pretend it's this time: what does the button say?
            print()
            print(next_step(dt.datetime.combine(d, dt.time(int(sys.argv[3][:2]), int(sys.argv[3][3:5])))))
    elif cmd == "ask":
        print(answer(sys.argv[2], *(float(x) for x in sys.argv[3:5])) if len(sys.argv) > 4 else answer(sys.argv[2]))
