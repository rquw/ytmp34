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


cpu = {"pct": 0.0}


def sample_cpu():
    # cpu use over the last second, measured in the background so requests stay cheap
    def stat():
        f = [int(x) for x in read("/proc/stat").splitlines()[0].split()[1:]]
        return sum(f), f[3] + f[4]  # total, idle + iowait
    prev = stat()
    while True:
        time.sleep(1)
        cur = stat()
        dt, di = cur[0] - prev[0], cur[1] - prev[1]
        cpu["pct"] = round(100 * (1 - di / dt), 1) if dt else 0.0
        prev = cur


slow = {"at": 0, "data": {}}


def slow_parts():
    # systemctl/ss/vcgencmd are slowish on a pi zero: refresh them at most every 5 s
    if time.time() - slow["at"] > 5:
        slow["data"] = {"services": {s: sh("systemctl", "is-active", s) or "unknown" for s in SERVICES},
                        "proxy_clients": proxy_clients(), "untis": untis(),
                        "throttled": sh("vcgencmd", "get_throttled").replace("throttled=", "") or None}
        slow["at"] = time.time()
    return slow["data"]


def status():
    load1, load5, load15 = os.getloadavg()
    disk = shutil.disk_usage("/")
    temp = read("/sys/class/thermal/thermal_zone0/temp", "0").strip()
    return {
        "host": socket.gethostname(),
        "model": read("/proc/device-tree/model").strip("\x00\n"),
        "time": time.time(),
        "uptime": float(read("/proc/uptime", "0").split()[0]),
        "load": [load1, load5, load15],
        "cpu": cpu["pct"],
        "cpu_temp": int(temp) / 1000 if temp.isdigit() else None,
        "memory": memory(),
        "disk": {"total": disk.total, "free": disk.free},
        "wifi": wifi(),
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
    threading.Thread(target=sample_cpu, daemon=True).start()
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
