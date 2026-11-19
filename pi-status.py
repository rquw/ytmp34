#!/usr/bin/env python3
# tells oracle what the pi is up to (for pie mode on the site).
# listens only on the pi's tailscale address, so only devices in the tailnet can ask.
#   python3 pi-status.py --host 100.x.y.z --port 8780
import argparse
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
SERVICES = ["ytmp34", "ytmp34-proxy", "untis-watch.timer", "tailscaled", "ytmp34-update.timer"]


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
    while True:
        time.sleep(1)
        c, n, d = cpus(), net(), disk()
        pct = [round(100 * (1 - (b[1] - a[1]) / (b[0] - a[0])), 1) if b[0] - a[0] else 0.0 for a, b in zip(pc, c)]
        live.update(cpu=pct[0] if pct else 0.0, cores=pct[1:],
                    net={"rx": n[0] - pn[0], "tx": n[1] - pn[1], "rx_total": n[0], "tx_total": n[1]},
                    io={"read": d[0] - pd[0], "write": d[1] - pd[1]})
        pc, pn, pd = c, n, d


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
            "proxy_clients": proxy_clients(), "untis": untis(),
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
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/status":
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(status(), ensure_ascii=False).encode()
        self.send_response(200)
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
    threading.Thread(target=sample, daemon=True).start()
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
