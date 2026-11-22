#!/usr/bin/env python3
# tells oracle what the pi is up to (for pie mode on the site).
# listens only on the pi's tailscale address, so only devices in the tailnet can ask.
#   python3 pi-status.py --host 100.x.y.z --port 8780
import argparse
import json
import math
import os
import re
import urllib.request
import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
SERVICES = ["ytmp34", "ytmp34-proxy", "untis-watch.timer", "tailscaled", "ytmp34-update.timer",
            "prismo-watchdog", "prismo-briefing.timer", "prismo-scan", "prismo-day"]


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def load(path, default=None):
    try:
        return json.loads(read(path)) if read(path) else default
    except ValueError:
        return default


def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def memory():
    m = {}
    for line in read("/proc/meminfo").splitlines():
        k, _, v = line.partition(":")
        m[k] = int(v.split()[0]) * 1024
    return {"total": m.get("MemTotal", 0), "available": m.get("MemAvailable", 0),
            "swap_total": m.get("SwapTotal", 0), "swap_free": m.get("SwapFree", 0)}


def wifi():
    # /proc/net/wireless: "wlan0: 0000   58.  -52.  -256 ..."
    for line in read("/proc/net/wireless").splitlines()[2:]:
        parts = line.split()
        if len(parts) > 3:
            return {"iface": parts[0].rstrip(":"), "quality": float(parts[2].rstrip(".")),
                    "dbm": float(parts[3].rstrip("."))}
    return None


def proxy_clients():
    # open connections through the oracle proxy right now
    out = sh("ss", "-Htn", "state", "established", "( sport = :1080 )")
    return len(out.splitlines()) if out else 0


def untis():
    d = os.path.join(HOME, "untis-watch")
    cfg = load(os.path.join(d, "config.json"), {}) or {}
    state = load(os.path.join(d, "state.json"), {}) or {}
    pushes = load(os.path.join(d, "pushes.json"), []) or []
    lessons = sorted((state.get("lessons") or {}).values(), key=lambda l: l["start"])
    now = time.strftime("%Y-%m-%dT%H:%M")
    upcoming = [l for l in lessons if (l.get("end") or l["start"]).rstrip("Z") > now]
    return {
        "class": cfg.get("class"), "ignore": cfg.get("ignore", []), "checked": state.get("checked"),
        "fails": state.get("fails", 0), "lessons": len(lessons),
        "next": upcoming[0] if upcoming else None,
        "irregular": [l for l in upcoming if l.get("status") != "REGULAR"][:12],
        "pushes": pushes[-8:][::-1],
    }


live = {"cpu": 0.0, "cores": [], "net": {"rx": 0, "tx": 0}, "io": {"read": 0, "write": 0}}


def sample():
    # once a second in the background: cpu (total + per core), network and sd card rates
    def cpus():
        out = []
        for line in read("/proc/stat").splitlines():
            if not line.startswith("cpu"):
                break
            f = [int(x) for x in line.split()[1:]]
            out.append((sum(f), f[3] + f[4]))  # total, idle + iowait
        return out

    def net():
        rx = tx = 0
        for line in read("/proc/net/dev").splitlines()[2:]:
            name, _, rest = line.partition(":")
            if name.strip() == "lo":
                continue
            f = rest.split()
            rx, tx = rx + int(f[0]), tx + int(f[8])
        return rx, tx

    def disk():
        # sectors read/written on the sd card (512 bytes each)
        for line in read("/proc/diskstats").splitlines():
            f = line.split()
            if len(f) > 9 and f[2] == "mmcblk0":
                return int(f[5]) * 512, int(f[9]) * 512
        return 0, 0

    pc, pn, pd = cpus(), net(), disk()
    tick, cpu_sum, rx_sum, tx_sum = 0, 0.0, 0, 0
    while True:
        time.sleep(1)
        c, n, d = cpus(), net(), disk()
        pct = [round(100 * (1 - (b[1] - a[1]) / (b[0] - a[0])), 1) if b[0] - a[0] else 0.0 for a, b in zip(pc, c)]
        live.update(cpu=pct[0] if pct else 0.0, cores=pct[1:],
                    net={"rx": n[0] - pn[0], "tx": n[1] - pn[1], "rx_total": n[0], "tx_total": n[1]},
                    io={"read": d[0] - pd[0], "write": d[1] - pd[1]})
        tick += 1
        cpu_sum += live["cpu"]; rx_sum += live["net"]["rx"]; tx_sum += live["net"]["tx"]
        if tick >= 300:
            history_add(cpu_sum / tick, rx_sum, tx_sum)
            tick, cpu_sum, rx_sum, tx_sum = 0, 0.0, 0, 0
        pc, pn, pd = c, n, d


HISTORY = os.path.join(HOME, "prismo", "history.json")
history = []  # [time, cpu %, temp °C, rx bytes, tx bytes] every 5 minutes, last 24 h


def history_load():
    global history
    h = load(HISTORY, []) or []
    history = [x for x in h if time.time() - x[0] < 86400]


def history_add(cpu_avg, rx, tx):
    temp = read("/sys/class/thermal/thermal_zone0/temp", "0").strip()
    history.append([int(time.time()), round(cpu_avg, 1), int(temp) / 1000 if temp.isdigit() else None, rx, tx])
    del history[:-288]
    if len(history) % 6 == 0:  # every 30 minutes
        try:
            with open(HISTORY + ".tmp", "w") as f:
                json.dump(history, f)
            os.replace(HISTORY + ".tmp", HISTORY)
        except OSError:
            pass


THROTTLE = {0: "undervoltage", 1: "freq_capped", 2: "throttled", 3: "soft_temp_limit"}


def throttled():
    # vcgencmd get_throttled -> which power/heat problems happen now, and which happened since boot
    raw = sh("vcgencmd", "get_throttled").replace("throttled=", "")
    try:
        v = int(raw, 16)
    except ValueError:
        return None
    return {"raw": raw, "now": [n for b, n in THROTTLE.items() if v >> b & 1],
            "since_boot": [n for b, n in THROTTLE.items() if v >> (b + 16) & 1]}


def vc(*args, strip=""):
    out = sh("vcgencmd", *args)
    try:
        return float(out.split("=")[-1].rstrip(strip))
    except ValueError:
        return None


def top_processes():
    out = sh("ps", "-eo", "comm,%cpu,%mem,rss", "--sort=-%cpu", "--no-headers")
    procs = []
    for line in out.splitlines()[:6]:
        f = line.split()
        if len(f) >= 4:
            procs.append({"name": f[0], "cpu": float(f[1]), "mem": float(f[2]), "rss": int(f[3]) * 1024})
    return procs


STATIC = {}


def static():
    # things that don't change while running
    if not STATIC:
        os_name = next((l.split("=", 1)[1].strip('"') for l in read("/etc/os-release").splitlines()
                        if l.startswith("PRETTY_NAME=")), "?")
        STATIC.update(os=os_name, kernel=os.uname().release, core_count=os.cpu_count(),
                      python=sh("python3", "--version").replace("Python ", ""),
                      boot=time.time() - float(read("/proc/uptime", "0").split()[0]))
    return STATIC


slow = {"at": 0, "data": {}}


def slow_parts():
    # systemctl/ss/vcgencmd/ps are slowish on a pi zero: refresh them at most every 5 s
    if time.time() - slow["at"] > 5:
        slow["data"] = {
            "services": {s: sh("systemctl", "is-active", s) or "unknown" for s in SERVICES},
            "proxy_clients": proxy_clients(), "untis": untis(), "prismo": prismo(),
            "throttle": throttled(),
            "volts": vc("measure_volts", "core", strip="V"),
            "arm_clock": vc("measure_clock", "arm"), "core_clock": vc("measure_clock", "core"),
            "gpu_temp": vc("measure_temp", strip="'C"),
            "ssid": sh("iwgetid", "-r") or None,
            "processes": sum(1 for d in os.listdir("/proc") if d.isdigit()),
            "top": top_processes(),
        }
        slow["at"] = time.time()
    return slow["data"]


def prismo():
    # the briefing + watchdog (prismo.py) state, for pie mode. the watcher keeps the live copy in ram (/dev/shm)
    st = load(os.path.join(HOME, "prismo", "state.json"), {}) or {}
    sites = st.get("sites") or {}
    try:
        if time.time() - os.path.getmtime(WATCH_LIVE) < 300:
            sites = (load(WATCH_LIVE, {}) or {}).get("sites") or sites
    except OSError:
        pass
    keys = ("ok", "took", "checked", "down_since", "url", "error", "hist", "n", "n_ok")
    return {"briefing": st.get("briefing"), "sites": {n: {k: v.get(k) for k in keys} for n, v in sites.items()}}


WATCH_LIVE = "/dev/shm/prismo-watch.json"


def status():
    load1, load5, load15 = os.getloadavg()
    disk = shutil.disk_usage("/")
    temp = read("/sys/class/thermal/thermal_zone0/temp", "0").strip()
    freq = read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "").strip()
    fmax = read("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", "").strip()
    return {
        "host": socket.gethostname(),
        "model": read("/proc/device-tree/model").strip("\x00\n"),
        "time": time.time(),
        "uptime": float(read("/proc/uptime", "0").split()[0]),
        "load": [load1, load5, load15],
        "cpu": live["cpu"], "cores": live["cores"],
        "cpu_temp": int(temp) / 1000 if temp.isdigit() else None,
        "freq_mhz": int(freq) / 1000 if freq.isdigit() else None,
        "freq_max_mhz": int(fmax) / 1000 if fmax.isdigit() else None,
        "net": live["net"], "io": live["io"],
        "memory": memory(),
        "disk": {"total": disk.total, "free": disk.free},
        "wifi": wifi(),
        **static(),
        **slow_parts(),
        "led": {"what": led_busy["what"], "left": max(0, round(led_busy["until"] - time.time(), 1))},
        "planes": planes_view(),
        "net_watch": net_view(),
    }


# ---------------------------------------------------------------------------------------------
# PRISMO's green LED: pie mode can make it beat like a heart, blink or morse a message into the room.

LED = "/sys/class/leds/ACT"
LED_DEFAULT = "actpwr"
led_busy = {"what": None, "until": 0}

MORSE = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..",
         "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
         "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..",
         "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
         "7": "--...", "8": "---..", "9": "----.", "Ä": ".-.-", "Ö": "---.", "Ü": "..--", "?": "..--..", "!": "-.-.--"}


def led_write(name, value):
    try:
        with open(os.path.join(LED, name), "w") as f:
            f.write(value)
        return True
    except OSError:
        return False


def led_play(steps, what):
    # steps: [(on?, seconds), ...]. runs in a thread, then gives the LED back to the system
    def run():
        led_write("trigger", "none")
        try:
            for on, sec in steps:
                led_write("brightness", "1" if on else "0")
                time.sleep(sec)
        finally:
            led_write("trigger", LED_DEFAULT)  # back to "on, blinks with sd activity"
            led_busy.update(what=None, until=0)
    total = sum(sec for _, sec in steps)
    if led_busy["what"]:
        return 0  # one light show at a time
    led_busy.update(what=what, until=time.time() + total)
    threading.Thread(target=run, daemon=True).start()
    return total


def morse_steps(text, unit=0.18):
    steps = [(False, 0.6)]
    for word in text.upper().split():
        for ch in word:
            for sym in MORSE.get(ch, ""):
                steps += [(True, unit if sym == "." else unit * 3), (False, unit)]
            steps.append((False, unit * 2))  # gap between letters (3 units in total)
        steps.append((False, unit * 4))  # gap between words (7 units)
    return steps


def heartbeat(n=4):
    steps = [(False, 0.3)]
    for _ in range(n):
        steps += [(True, 0.12), (False, 0.12), (True, 0.12), (False, 0.6)]
    return steps


def led_action(body):
    action = body.get("action")
    if action in TUNES:
        return piezo_play(action)
    if led_busy["what"]:
        return 409, {"error": "Das Licht ist gerade beschäftigt ✨", "left": round(led_busy["until"] - time.time(), 1)}
    if action in ("heart", "pet"):
        secs, msg = led_play(heartbeat(), "Herzschlag"), "Das Licht klopft wie ein Herz 💓"
    elif action == "wave":
        secs, msg = led_play([(False, 0.2)] + [(True, 0.05), (False, 0.05)] * 20, "blinkt"), "Das Licht blinkt wie wild 👋"
    elif action == "morse":
        text = re.sub(r"[^A-Za-z0-9ÄÖÜäöü?! ]", "", str(body.get("text", ""))).strip()[:24]
        if not text:
            return 400, {"error": "Nur Buchstaben, Zahlen, ? und ! (max. 24)"}
        secs, msg = led_play(morse_steps(text), "morst „%s“" % text), "Das Licht morst „%s“ in dein Zimmer 📡" % text
    else:
        return 400, {"error": "unbekannte Aktion"}
    return 200, {"ok": True, "message": msg, "seconds": round(secs, 1)}


# ---------------------------------------------------------------------------------------------
# internet watch: a ping every 30 s (outages), a small speed test every 3 hours. kept for 7 days

NET = os.path.join(HOME, "prismo", "net.json")
NET_STATE = {"online": True, "ping": None}


def ping_ms(host):
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", "2", host], capture_output=True, text=True, timeout=5)
        m = re.search(r"time=([0-9.]+)", r.stdout)
        return float(m.group(1)) if r.returncode == 0 and m else None
    except Exception:
        return None


def speedtest():
    t = time.time()
    ua = {"User-Agent": "Mozilla/5.0 (PRISMO)"}
    with urllib.request.urlopen(urllib.request.Request("https://speed.cloudflare.com/__down?bytes=10000000", headers=ua), timeout=60) as r:
        n = len(r.read())
    down = n * 8 / (time.time() - t) / 1e6
    data = os.urandom(2000000)
    t = time.time()
    req = urllib.request.Request("https://speed.cloudflare.com/__up", data=data, method="POST", headers=ua)
    urllib.request.urlopen(req, timeout=60).read()
    up = len(data) * 8 / (time.time() - t) / 1e6
    return round(down, 1), round(up, 1)


def netwatch():
    net = load(NET, {}) or {}
    net.setdefault("speeds", [])
    net.setdefault("outages", [])
    net["speeds"] = [x for x in net["speeds"] if x[1] > 0]
    retry = 0
    while True:
        now = time.time()
        p = ping_ms("1.1.1.1") or ping_ms("8.8.8.8")
        NET_STATE.update(online=p is not None, ping=p)
        changed = False
        if p is None and not net.get("down_since"):
            net["down_since"], changed = now, True
        elif p is not None and net.get("down_since"):
            if now - net["down_since"] >= 60:
                net["outages"] = (net["outages"] + [[net["down_since"], now]])[-50:]
            net["down_since"], changed = None, True
        last = net["speeds"][-1][0] if net["speeds"] else 0
        if p is not None and now - last > 3 * 3600 and now > retry:
            try:
                down, up = speedtest()
                net["speeds"] = [s for s in net["speeds"] if now - s[0] < 7 * 86400] + [[now, down, up, p]]
                changed = True
            except Exception as e:
                print("speedtest: %s" % e, flush=True)
                retry = now + 900
        if changed:
            with open(NET + ".tmp", "w") as f:
                json.dump(net, f)
            os.replace(NET + ".tmp", NET)
        time.sleep(30)


def net_view():
    net = load(NET, {}) or {}
    return {"online": NET_STATE["online"], "ping": NET_STATE["ping"], "down_since": net.get("down_since"),
            "speeds": net.get("speeds", [])[-56:], "outages": net.get("outages", [])[-20:]}


# ---------------------------------------------------------------------------------------------
# the piezo (KY-006 on GPIO19): little sounds from the app

TUNES = {"find": [(2600, 0.12), (0, 0.08)] * 6,
         "chime": [(1047, 0.12), (1319, 0.12), (1568, 0.12), (2093, 0.3)],
         "siren": [(f, 0.03) for f in list(range(800, 2400, 80)) + list(range(2400, 800, -80))] * 2}
piezo_busy = {"until": 0}


def piezo_play(name):
    try:
        import lgpio
    except ImportError:
        return 503, {"error": "kein Piezo-Treiber (lgpio fehlt)"}
    if time.time() < piezo_busy["until"]:
        return 409, {"error": "PRISMO piept gerade schon 🔊"}
    notes = TUNES[name]
    piezo_busy["until"] = time.time() + sum(t for _, t in notes)

    def run():
        try:
            h = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(h, 19)
            for f, t in notes:
                lgpio.tx_pwm(h, 19, f, 50 if f else 0)
                time.sleep(t)
            lgpio.tx_pwm(h, 19, 0, 0)
            lgpio.gpio_write(h, 19, 0)
            lgpio.gpiochip_close(h)
        except Exception as e:
            print("piezo: %s" % e, flush=True)
    threading.Thread(target=run, daemon=True).start()
    return 200, {"ok": True, "message": "PRISMO piept 🔊"}


# ---------------------------------------------------------------------------------------------
# planes over PRISMO: live ADS-B positions from adsb.lol (free, no key), routes from adsbdb.com.
# pie mode only ever gets positions relative to home (km east / north), never the home coordinates.
# a push when one flies (nearly) straight over the house.

PLANE_SOURCES = ["https://api.adsb.lol/v2/point/{lat}/{lon}/{nm}", "https://api.airplanes.live/v2/point/{lat}/{lon}/{nm}"]
PLANES = {"at": 0, "list": [], "error": None, "radius": 50, "today": set(), "day": None, "overhead": None, "pushed": {}, "last_push": 0}
ROUTES = {}  # callsign -> (fetched at, route or None)
TYPES = {"A19N": "Airbus A319neo", "A20N": "Airbus A320neo", "A21N": "Airbus A321neo", "A318": "Airbus A318", "A319": "Airbus A319",
         "A320": "Airbus A320", "A321": "Airbus A321", "A332": "Airbus A330-200", "A333": "Airbus A330-300", "A339": "Airbus A330neo",
         "A343": "Airbus A340-300", "A359": "Airbus A350-900", "A35K": "Airbus A350-1000", "A388": "Airbus A380", "BCS1": "Airbus A220-100",
         "BCS3": "Airbus A220-300", "B737": "Boeing 737-700", "B738": "Boeing 737-800", "B739": "Boeing 737-900", "B38M": "Boeing 737 MAX 8",
         "B39M": "Boeing 737 MAX 9", "B744": "Boeing 747-400", "B748": "Boeing 747-8", "B752": "Boeing 757-200", "B763": "Boeing 767-300",
         "B772": "Boeing 777-200", "B77L": "Boeing 777-200LR", "B77W": "Boeing 777-300ER", "B778": "Boeing 777-8", "B788": "Boeing 787-8",
         "B789": "Boeing 787-9", "B78X": "Boeing 787-10", "E190": "Embraer 190", "E195": "Embraer 195", "E290": "Embraer E190-E2",
         "E295": "Embraer E195-E2", "E75L": "Embraer 175", "CRJ9": "Bombardier CRJ900", "CRJ7": "Bombardier CRJ700", "DH8D": "Dash 8-400",
         "AT76": "ATR 72-600", "AT75": "ATR 72-500", "AT45": "ATR 42-500", "C172": "Cessna 172", "C152": "Cessna 152", "P28A": "Piper Cherokee",
         "DA40": "Diamond DA40", "DA42": "Diamond DA42", "EC35": "Hubschrauber EC135", "EC45": "Hubschrauber H145", "PC12": "Pilatus PC-12",
         "C56X": "Cessna Citation Excel", "GLF6": "Gulfstream G650", "CL35": "Challenger 350", "C17": "Boeing C-17", "A400": "Airbus A400M"}


def plane_config():
    cfg = load(os.path.join(HOME, "prismo", "config.json"), {}) or {}
    return cfg.get("lat"), cfg.get("lon"), cfg.get("planes") or {}


def get_json(url, timeout=8):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "prismo-radar"}), timeout=timeout) as r:
        return json.loads(r.read())


def plane_route(cs, budget):
    hit = ROUTES.get(cs)
    if hit and time.time() - hit[0] < 6 * 3600:
        return hit[1]
    if budget[0] <= 0 or not re.fullmatch(r"[A-Z]{3}[0-9A-Z]{1,5}", cs):
        return hit[1] if hit else None
    budget[0] -= 1
    route = None
    try:
        fr = get_json("https://api.adsbdb.com/v0/callsign/" + cs, 6).get("response", {}).get("flightroute") or {}
        o, d = fr.get("origin") or {}, fr.get("destination") or {}
        route = {"airline": (fr.get("airline") or {}).get("name"), "iata": fr.get("callsign_iata"),
                 "from": o.get("municipality") or o.get("name"), "from_code": o.get("iata_code"),
                 "to": d.get("municipality") or d.get("name"), "to_code": d.get("iata_code")}
    except Exception:
        pass
    ROUTES[cs] = (time.time(), route)
    if len(ROUTES) > 3000:
        for k in sorted(ROUTES, key=lambda k: ROUTES[k][0])[:1000]:
            del ROUTES[k]
    return route


def plane_push(p):
    title = "✈️ Gerade über dir: " + (p.get("airline") or "") + " " + (p.get("iata") or p.get("cs") or p["id"])
    lines = []
    if p.get("from") and p.get("to"):
        lines.append(f"{p['from']} → {p['to']}")
    if p.get("type"):
        lines.append(p["type"] + (f" ({p['reg']})" if p.get("reg") else ""))
    lines.append(f"{p['alt']:,} m hoch · {p['speed']} km/h".replace(",", "."))
    msg = "\n".join(lines)
    try:
        cfg = load(os.path.join(HOME, "untis-watch", "config.json"), {}) or {}
        body = {"topic": cfg["topic"], "title": title.strip(), "message": msg, "priority": 5, "tags": ["airplane"]}
        urllib.request.urlopen(urllib.request.Request(cfg.get("ntfy", "https://ntfy.sh"), json.dumps(body).encode(),
                                                      {"Content-Type": "application/json"}), timeout=15).read()
        log = os.path.join(HOME, "untis-watch", "pushes.json")
        pushes = (load(log, []) or [])[-19:] + [{"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "title": title.strip(), "message": msg, "urgent": False}]
        with open(log + ".tmp", "w") as f:
            json.dump(pushes, f, ensure_ascii=False, indent=1)
        os.replace(log + ".tmp", log)
    except Exception:
        pass


def planes_loop():
    while True:
        lat0, lon0, pc = plane_config()
        if lat0 is None:
            PLANES["error"] = "keine Position in config.json"
            time.sleep(60)
            continue
        radius = float(pc.get("radius_km", 50))
        every = float(pc.get("every_s", 8))
        # the api only gets the position rounded to ~1 km
        q = {"lat": round(lat0, 2), "lon": round(lon0, 2), "nm": int(radius / 1.852) + 3}
        data, err = None, None
        for src in PLANE_SOURCES:
            try:
                data = get_json(src.format(**q))
                break
            except Exception as e:
                err = str(e)[:120]
        if data is None:
            PLANES["error"] = err
            time.sleep(every * 2)
            continue
        budget = [3]  # at most 3 new route lookups per round, adsbdb is a free service
        kx, ky = 111.32 * math.cos(math.radians(lat0)), 110.574
        out, now = [], time.time()
        today = time.strftime("%Y-%m-%d")
        if PLANES["day"] != today:
            PLANES["day"], PLANES["today"] = today, set()
        for a in data.get("ac") or []:
            if a.get("lat") is None or a.get("lon") is None or (a.get("seen_pos") or 0) > 60:
                continue
            x, y = (a["lon"] - lon0) * kx, (a["lat"] - lat0) * ky
            dist = math.hypot(x, y)
            if dist > radius:
                continue
            ground = a.get("alt_baro") == "ground"
            alt = 0 if ground else int((a.get("alt_baro") or a.get("alt_geom") or 0) * 0.3048)
            cs = (a.get("flight") or "").strip()
            p = {"id": a.get("hex"), "cs": cs, "reg": a.get("r"), "type": TYPES.get(a.get("t"), a.get("desc") or a.get("t")),
                 "op": a.get("ownOp"), "x": round(x, 2), "y": round(y, 2), "dist": round(dist, 1), "alt": alt,
                 "speed": int((a.get("gs") or 0) * 1.852), "track": round(a.get("track") or a.get("true_heading") or 0),
                 "climb": round((a.get("baro_rate") or a.get("geom_rate") or 0) * 0.00508, 1), "age": round(a.get("seen_pos") or 0, 1),
                 "ground": ground, "squawk": a.get("squawk")}
            r = plane_route(cs, budget) if cs else None
            if r:
                p.update({k: v for k, v in r.items() if v})
            out.append(p)
            PLANES["today"].add(p["id"])
            # straight over the house? closest point on its path during the next round
            v = p["speed"] / 3600
            vx, vy = v * math.sin(math.radians(p["track"])), v * math.cos(math.radians(p["track"]))
            t = max(0.0, min(every + 2, -(x * vx + y * vy) / (vx * vx + vy * vy))) if v else 0.0
            closest = min(dist, math.hypot(x + vx * t, y + vy * t))
            night = pc.get("night", [22, 7])
            h = time.localtime().tm_hour
            quiet = night and (h >= night[0] or h < night[1])
            if (closest <= float(pc.get("push_km", 2.5)) and not ground and p["id"] not in PLANES["pushed"]
                    and now - PLANES["last_push"] > 60 * float(pc.get("push_gap_min", 15)) and not quiet):
                PLANES["pushed"][p["id"]] = now
                PLANES["last_push"] = now
                PLANES["overhead"] = {**p, "at": now}
                threading.Thread(target=plane_push, args=(p,), daemon=True).start()
        PLANES["pushed"] = {k: t for k, t in PLANES["pushed"].items() if now - t < 7200}
        out.sort(key=lambda p: p["dist"])
        PLANES.update(at=now, list=out[:60], error=None, radius=radius)
        time.sleep(every)


def planes_view():
    o = PLANES["overhead"]
    return {"at": PLANES["at"], "radius": PLANES["radius"], "list": PLANES["list"], "error": PLANES["error"],
            "today": len(PLANES["today"]), "overhead": o if o and time.time() - o["at"] < 3600 else None}


# camera (prismo-scan.py owns it). it only writes frames while someone looks, so we touch a flag file
CAM_JPG, CAM_WANT = "/dev/shm/prismo-cam.jpg", "/dev/shm/prismo-cam-want"
SCAN_KEY = os.path.join(HOME, "prismo", "scan-key")


def cam_frame():
    with open(CAM_WANT, "w"):
        pass
    for _ in range(15):  # first look: give the scanner a moment to start writing
        try:
            if time.time() - os.path.getmtime(CAM_JPG) < 2:
                with open(CAM_JPG, "rb") as f:
                    return f.read()
        except OSError:
            pass
        time.sleep(0.1)
    return None


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, code, data, kind):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/cam.jpg":
            frame = cam_frame()
            return self.send_bytes(200, frame, "image/jpeg") if frame else self.send_bytes(503, b"no camera", "text/plain")
        if self.path == "/scan-key":
            # oracle picks this up once. tailnet only, like everything here
            key = read(SCAN_KEY).strip()
            return self.send_bytes(200, key.encode(), "text/plain") if key else self.send_bytes(404, b"", "text/plain")
        if self.path not in ("/status", "/status?full=1"):
            self.send_response(404)
            self.end_headers()
            return
        out = status()
        if self.path.endswith("full=1"):
            out["history"] = history
        data = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/action":
            self.send_response(404)
            self.end_headers()
            return
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 2000)) or b"{}")
        except ValueError:
            body = {}
        code, out = led_action(body)
        data = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, default=8780)
    a = p.parse_args()
    os.makedirs(os.path.join(HOME, "prismo"), exist_ok=True)
    history_load()
    threading.Thread(target=sample, daemon=True).start()
    threading.Thread(target=planes_loop, daemon=True).start()
    threading.Thread(target=netwatch, daemon=True).start()
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
