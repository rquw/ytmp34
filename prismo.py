#!/usr/bin/env python3
"""PRISMO's little jobs on the pi. pushes go to the same ntfy topic as the untis watcher.

  python3 prismo.py briefing   # morning push: weather, rain warning, untis changes today, prismo status
  python3 prismo.py watchdog   # checks the sites (a timer runs this every minute), pushes when one goes down / comes back
  python3 prismo.py status     # print what the watchdog knows

config.json next to this file (not in the repo):
  {"place": "Zuhause", "lat": 48.0, "lon": 14.3,
   "sites": [{"name": "ytmp34", "url": "https://.../ping"}, {"name": "faight", "url": "...", "every": 60, "timeout": 120, "fails": 2}]}
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
STATE = os.path.join(HERE, "state.json")
UNTIS = os.path.expanduser("~/untis-watch")
FAILS_BEFORE_ALERT = 3  # one slow answer isn't an outage

WEATHER = {0: ("☀️", "sonnig"), 1: ("🌤️", "fast sonnig"), 2: ("⛅", "teils bewölkt"), 3: ("☁️", "bewölkt"),
           45: ("🌫️", "Nebel"), 48: ("🌫️", "Reifnebel"), 51: ("🌦️", "Nieselregen"), 53: ("🌦️", "Nieselregen"),
           55: ("🌧️", "starker Niesel"), 56: ("🧊", "gefrierender Niesel"), 57: ("🧊", "gefrierender Niesel"),
           61: ("🌧️", "leichter Regen"), 63: ("🌧️", "Regen"), 65: ("🌧️", "starker Regen"),
           66: ("🧊", "Eisregen"), 67: ("🧊", "Eisregen"), 71: ("🌨️", "leichter Schnee"), 73: ("🌨️", "Schnee"),
           75: ("❄️", "starker Schnee"), 77: ("🌨️", "Schneegriesel"), 80: ("🌦️", "Regenschauer"),
           81: ("🌧️", "Regenschauer"), 82: ("⛈️", "heftige Schauer"), 85: ("🌨️", "Schneeschauer"),
           86: ("❄️", "Schneeschauer"), 95: ("⛈️", "Gewitter"), 96: ("⛈️", "Gewitter mit Hagel"), 99: ("⛈️", "Gewitter mit Hagel")}
SNOW = {71, 73, 75, 77, 85, 86}


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "prismo"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def push(title, message, urgent=False, tags=None):
    cfg = load(os.path.join(UNTIS, "config.json"), {})
    body = {"topic": cfg["topic"], "title": title, "message": message, "priority": 5, "tags": tags or []}
    req = urllib.request.Request(cfg.get("ntfy", "https://ntfy.sh"), json.dumps(body).encode(), {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20).read()
    # same log as the untis watcher, so pie mode shows these too
    log = os.path.join(UNTIS, "pushes.json")
    pushes = load(log, [])[-19:] + [{"at": dt.datetime.now().isoformat(timespec="seconds"), "title": title,
                                     "message": message, "urgent": urgent}]
    save(log, pushes)


def dur(s):
    s = int(s)
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return f"{d} T {h} Std" if d else f"{h} Std {m} Min" if h else f"{m} Min" if m else f"{s} s"


# --- morning briefing ---

def weather(cfg):
    q = urllib.parse.urlencode({
        "latitude": cfg["lat"], "longitude": cfg["lon"], "timezone": "Europe/Vienna", "forecast_days": 1,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunset",
        "hourly": "precipitation_probability,weather_code,temperature_2m"})
    w = get_json("https://api.open-meteo.com/v1/forecast?" + q)
    d = w["daily"]
    icon, text = WEATHER.get(d["weather_code"][0], ("🌡️", "?"))
    lines = [f"{icon} {cfg.get('place', 'Heute')}: {text}, {round(d['temperature_2m_min'][0])}° bis {round(d['temperature_2m_max'][0])}°"]
    # the first hour between 6 and 20 with a real chance of rain/snow
    h = w["hourly"]
    wet = [(t[11:16], p, c) for t, p, c in zip(h["time"], h["precipitation_probability"], h["weather_code"])
           if 6 <= int(t[11:13]) <= 20 and (p or 0) >= 50]
    if wet:
        start, p, code = wet[0]
        if code in SNOW:
            lines.append(f"🌨️ Schnee ab {start} ({p} %): warm anziehen 🧣")
        else:
            lines.append(f"🌧️ Regen ab {start} ({p} %): nimm einen Schirm ☔")
    elif (d["precipitation_probability_max"][0] or 0) >= 30:
        lines.append(f"🌂 vielleicht ein paar Tropfen ({d['precipitation_probability_max'][0]} %)")
    else:
        lines.append("🌂 kein Regen in Sicht")
    morning = [t for tm, t in zip(h["time"], h["temperature_2m"]) if tm[11:13] == "07"]
    if morning and morning[0] <= 0:
        lines.append(f"🥶 um 7 Uhr nur {round(morning[0])}°: Mütze!")
    lines.append(f"🌇 Sonnenuntergang {d['sunset'][0][11:16]}")
    return icon, lines


def untis_today():
    state = load(os.path.join(UNTIS, "state.json"), {})
    today = dt.date.today().isoformat()
    labels = {"CANCELLED": "❌ Entfällt", "ADDITIONAL": "➕ Zusätzlich", "SUBSTITUTION": "🔄 Vertretung",
              "ROOMSUBSTITUTION": "🚪 Raumänderung", "SHIFT": "🔀 Verschoben", "EXAM": "📝 Prüfung",
              "IRREGULAR": "🔄 Geändert", "EVENT": "📅 Veranstaltung"}
    out = []
    for l in sorted((state.get("lessons") or {}).values(), key=lambda l: l["start"]):
        if l["start"].startswith(today) and l.get("status", "REGULAR") != "REGULAR":
            room = f" · Raum {', '.join(l['rooms'])}" if l.get("rooms") else ""
            out.append(f"{labels.get(l['status'], '•')}: {l['start'][11:16]} {l['subject']}{room}")
    return out


def prismo_line(state):
    bits = []
    try:
        up = float(open("/proc/uptime").read().split()[0])
        temp = int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000
        bits.append(f"🍓 PRISMO läuft seit {dur(up)}, {temp:.0f} °C")
    except (OSError, ValueError):
        pass
    cfg = load(CONFIG, {})
    oracle = next((s for s in cfg.get("sites", []) if s["name"].lower().startswith("oracle")), None)
    if oracle:
        try:
            info = get_json(oracle["url"])
            videos = info.get("videos", 0)
            last = state.get("videos_yesterday")
            if last is not None:
                n = videos - last
                bits.append(f"🎵 gestern {n} {'Video' if n == 1 else 'Videos'} konvertiert")
            state["videos_yesterday"] = videos
        except Exception:
            bits.append("🦁 Oracle antwortet nicht 😠")
    down = [n for n, s in state.get("sites", {}).items() if s.get("down_since")]
    bits.append("🐕 alle Seiten online" if not down else "🚨 offline: " + ", ".join(down))
    return bits


def briefing():
    cfg = load(CONFIG, {})
    state = load(STATE, {})
    lines, icon = [], "☀️"
    try:
        icon, lines = weather(cfg)
    except Exception as e:
        lines.append(f"🌡️ Wetter gerade nicht abrufbar ({str(e)[:60]})")
    changes = untis_today()
    if changes:
        lines += ["", "📚 heute anders:"] + changes
    lines += [""] + prismo_line(state)
    day = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][dt.date.today().weekday()]
    push(f"{icon} Guten Morgen! Schönen {day}", "\n".join(lines), tags=["sunrise"])
    state["briefing"] = {"at": dt.datetime.now().isoformat(timespec="seconds"), "text": "\n".join(lines)}
    save(STATE, state)
    print("\n".join(lines))


# --- watchdog ---

def check(site):
    start = time.time()
    try:
        req = urllib.request.Request(site["url"], headers={"User-Agent": "prismo-watchdog"})
        with urllib.request.urlopen(req, timeout=site.get("timeout", 15)) as r:
            r.read(2048)
            return r.status < 400, round(time.time() - start, 2), None
    except Exception as e:
        return False, round(time.time() - start, 2), str(e)[:120]


def watchdog():
    cfg = load(CONFIG, {})
    state = load(STATE, {})
    sites = state.setdefault("sites", {})
    minute = int(time.time() // 60)
    for site in cfg.get("sites", []):
        if minute % site.get("every", 1):
            continue  # render apps only hourly: every check wakes them for 15 min and render's free plan has 750 h/month
        s = sites.setdefault(site["name"], {"fails": 0})
        ok, took, err = check(site)
        now = time.time()
        s.update(checked=now, ok=ok, took=took, error=err, url=site["url"])
        if ok:
            if s.get("down_since"):
                push(f"✅ {site['name']} ist wieder online", f"war {dur(now - s['down_since'])} weg. PRISMO hat aufgepasst 🐕",
                     tags=["white_check_mark"])
            s.update(fails=0, down_since=None, last_ok=now)
        else:
            s["fails"] = s.get("fails", 0) + 1
            need = site.get("fails", FAILS_BEFORE_ALERT)
            if s["fails"] == need:
                s["down_since"] = now - 60 * site.get("every", 1) * (need - 1)
                push(f"🚨 {site['name']} ist offline!", f"{site['url']}\n{err or 'antwortet nicht'}", urgent=True, tags=["rotating_light"])
    save(STATE, state)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "briefing":
        briefing()
    elif cmd == "watchdog":
        watchdog()
    else:
        print(json.dumps(load(STATE, {}), ensure_ascii=False, indent=1))
