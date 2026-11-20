#!/usr/bin/env python3
# tells oracle what the pi is up to (for pie mode on the site).
# listens only on the pi's tailscale address, so only devices in the tailnet can ask.
#   python3 pi-status.py --host 100.x.y.z --port 8780
import argparse
import json
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
            "prismo-watchdog.timer", "prismo-briefing.timer"]


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
    # the briefing + watchdog (prismo.py) state, for pie mode
    st = load(os.path.join(HOME, "prismo", "state.json"), {}) or {}
    return {"briefing": st.get("briefing"),
            "sites": {n: {k: v.get(k) for k in ("ok", "took", "checked", "down_since", "url", "error")}
                      for n, v in (st.get("sites") or {}).items()}}


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
        "pet": pet_status(int(temp) / 1000 if temp.isdigit() else None, load1,
                          float(read("/proc/uptime", "0").split()[0])),
    }


# ---------------------------------------------------------------------------------------------
# PRISMO the pet: lives on the pi, its heart is the green LED. food = converted videos (+ snacks),
# love = being petted. both slowly go down. actions come in from pie mode (via oracle, password checked there).

LED = "/sys/class/leds/ACT"
LED_DEFAULT = "actpwr"
PET = os.path.join(HOME, "prismo", "pet.json")
ORACLE_PING = "https://132-226-199-122.sslip.io/ping"
pet_lock = threading.Lock()
led_busy = {"what": None, "until": 0}
pet_saved = {"at": 0}

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


def pet_load():
    p = load(PET, None) or {}
    now = time.time()
    p.setdefault("born", now); p.setdefault("food", 70.0); p.setdefault("love", 70.0)
    p.setdefault("xp", 0); p.setdefault("pets", 0); p.setdefault("snacks", []); p.setdefault("events", [])
    p.setdefault("updated", now); p.setdefault("videos", None); p.setdefault("checked_videos", 0)
    return p


def pet_save(p):
    tmp = PET + ".tmp"
    with open(tmp, "w") as f:
        json.dump(p, f, ensure_ascii=False)
    os.replace(tmp, PET)


def pet_event(p, text):
    p["events"] = (p["events"] + [{"at": time.time(), "text": text}])[-12:]


def pet_tick(p):
    # hunger and loneliness grow over time; converted videos are food
    now = time.time()
    hours = max(0.0, (now - p["updated"]) / 3600)
    p["food"] = max(0.0, p["food"] - 3.0 * hours)
    p["love"] = max(0.0, p["love"] - 2.5 * hours)
    p["updated"] = now
    if now - p["checked_videos"] > 60:
        p["checked_videos"] = now
        try:
            with urllib.request.urlopen(ORACLE_PING, timeout=5) as r:
                videos = json.loads(r.read()).get("videos", 0)
            if p["videos"] is not None and videos > p["videos"]:
                n = videos - p["videos"]
                p["food"] = min(100.0, p["food"] + 8 * n)
                p["xp"] += 3 * n
                pet_event(p, f"hat {n} {'Video' if n == 1 else 'Videos'} gefressen 🎵😋")
            p["videos"] = videos
        except Exception:
            pass
    p["snacks"] = [t for t in p["snacks"] if now - t < 3600]


def pet_view(p, temp, load1, uptime):
    hour = time.localtime().tm_hour
    asleep = hour >= 23 or hour < 6
    level = int((p["xp"] / 5) ** 0.5) + 1
    mood = min(p["food"], p["love"])
    if uptime < 300:
        face, state = "🥱", "gerade aufgewacht"
    elif temp and temp > 65:
        face, state = "🥵", "schwitzt"
    elif asleep and not led_busy["what"]:
        face, state = "😴", "schläft"
    elif load1 > 2.5:
        face, state = "😵‍💫", "arbeitet hart"
    elif mood > 70:
        face, state = "🥰", "super happy"
    elif mood > 45:
        face, state = "😊", "zufrieden"
    elif mood > 20:
        face, state = "😕", "braucht Aufmerksamkeit"
    else:
        face, state = "😭", "fühlt sich vergessen"
    return {"face": face, "state": state, "asleep": asleep, "food": round(p["food"], 1), "love": round(p["love"], 1),
            "level": level, "xp": p["xp"], "pets": p["pets"], "age_days": int((time.time() - p["born"]) // 86400),
            "snacks_left": max(0, 3 - len(p["snacks"])), "events": p["events"][::-1][:8],
            "led": {"what": led_busy["what"], "left": max(0, round(led_busy["until"] - time.time(), 1))}}


def pet_action(body):
    action = body.get("action")
    with pet_lock:
        p = pet_load()
        pet_tick(p)
        if led_busy["what"] and action in ("pet", "morse", "wave"):
            return 409, {"error": "PRISMO ist gerade beschäftigt ✨", "left": round(led_busy["until"] - time.time(), 1)}
        if action == "pet":
            p["love"] = min(100.0, p["love"] + 15)
            p["pets"] += 1
            p["xp"] += 1
            pet_event(p, "wurde gestreichelt 💜")
            secs = led_play(heartbeat(), "herzklopfen")
            msg = "PRISMO schnurrt. Sein Licht klopft wie ein Herz 💓"
        elif action == "snack":
            if len(p["snacks"]) >= 3:
                return 429, {"error": "Genug Snacks für diese Stunde 🍪🚫"}
            p["snacks"].append(time.time())
            p["food"] = min(100.0, p["food"] + 10)
            p["xp"] += 1
            pet_event(p, "hat einen Snack bekommen 🍪")
            secs = led_play([(False, 0.2), (True, 0.08), (False, 0.08)] * 6, "mampft")
            msg = "Mampf mampf 🍪"
        elif action == "wave":
            secs = led_play([(False, 0.2)] + [(True, 0.05), (False, 0.05)] * 20, "winkt")
            pet_event(p, "hat ins Zimmer gewinkt 👋")
            msg = "PRISMO blinkt wie wild 👋"
        elif action == "morse":
            text = re.sub(r"[^A-Za-z0-9ÄÖÜäöü?! ]", "", str(body.get("text", ""))).strip()[:24]
            if not text:
                return 400, {"error": "Nur Buchstaben, Zahlen, ? und ! (max. 24)"}
            secs = led_play(morse_steps(text), "morst „%s“" % text)
            p["xp"] += 2
            pet_event(p, "hat „%s“ gemorst 📡" % text)
            msg = "PRISMO morst „%s“ in dein Zimmer 📡" % text
        else:
            return 400, {"error": "unbekannte Aktion"}
        pet_save(p)
        return 200, {"ok": True, "message": msg, "seconds": round(secs, 1)}


def pet_status(temp, load1, uptime):
    with pet_lock:
        p = pet_load()
        pet_tick(p)
        if time.time() - pet_saved["at"] > 60:  # don't wear out the sd card: save at most once a minute
            pet_save(p)
            pet_saved["at"] = time.time()
        return pet_view(p, temp, load1, uptime)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
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
        code, out = pet_action(body)
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
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
