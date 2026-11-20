# ytmp34 server (yt-dlp + ffmpeg)
# env: YTMP34_COOKIES, YTMP34_MAX, YTMP34_PROXY
# phone alerts: put an ntfy.sh topic name in a file called "ntfy" next to this file
import argparse
import copy
import hmac
import html
import json
import os
import re
import shutil
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yt_dlp

HERE = os.path.dirname(os.path.abspath(__file__))
COOKIES = os.environ.get("YTMP34_COOKIES", "")
SLOTS = int(os.environ.get("YTMP34_MAX", "3"))
# send youtube traffic through another machine, e.g. a home pi (socks5h://100.x.y.z:1080),
# so youtube sees a home ip and doesn't ask for cookies
PROXY = os.environ.get("YTMP34_PROXY", "")

# limits so the server doesn't fall over
MAX_LENGTH = {"mp3": 2 * 3600, "mp4": 3600}
MAX_SIZE = {"mp3": 400 * 2**20, "mp4": 1536 * 2**20}
MAX_WAITING = 10
PER_IP_AT_ONCE = 2
PER_IP_HOUR = {"dl": 30, "info": 60}
MIN_FREE_DISK = 3 * 2**30

lock = threading.Condition()  # guards all the state below
last_active = {}  # tab id -> last time the person did something
busy = {}  # tab id -> downloads in progress
running = {}  # job -> (start, estimate)
waiting = []  # [(job, estimate)], first in line first
per_ip = defaultdict(int)
hits = defaultdict(deque)
speed = {"mp3": [4.0, 3.0], "mp4": [3.0, 5.0]}  # seconds overhead, seconds per video minute (learned)
info_cache = {}
cookies_ok = True

# all-time totals for the counter on the site
TOTALS = os.path.join(HERE, "totals.json")
try:
    with open(TOTALS) as f:
        totals = json.load(f)
except (OSError, ValueError):
    totals = {"videos": 0, "bytes": 0}


def count_done(size):
    with lock:
        totals["videos"] += 1
        totals["bytes"] += size
        with open(TOTALS + ".tmp", "w") as f:
            json.dump(totals, f)
        os.replace(TOTALS + ".tmp", TOTALS)

# tags + thumbnail as cover art
TAGS_AND_COVER = [
    {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
    {"key": "FFmpegMetadata"},
    {"key": "EmbedThumbnail"},
]

FORMATS = {
    "mp3": {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            *TAGS_AND_COVER,
        ],
    },
    "mp4": {
        # h264/aac, max 1080p
        "format": "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4][height<=1080]/bv*[height<=1080]+ba/b",
        "merge_output_format": "mp4",
        "postprocessors": TAGS_AND_COVER,
    },
}

ERRORS = [
    (("confirm you", "not a bot"), "cookies",
     "YouTube is blocking the server: its cookies have expired. Export fresh ones."),
    (("private video",), "private", "That video is private."),
    (("confirm your age", "age-restricted", "inappropriate for some users"), "age",
     "That video is age-restricted and the server's account can't open it."),
    (("members-only", "join this channel"), "members", "That video is for channel members only."),
    (("live event will begin", "premieres in", "is_live", "this live event"), "live",
     "That's a live stream or premiere that hasn't finished yet. Try again once it's over."),
    (("too long",), "long", "That video is too long. MP3 works up to 2 hours, MP4 up to 1 hour."),
    (("too big",), "big", "That file would be too big. MP3 works up to 400 MB, MP4 up to 1.5 GB."),
    (("not available in your country", "geo restrict"), "geo", "That video isn't available in the server's country."),
    (("video unavailable", "video is unavailable", "has been removed", "does not exist", "account associated"),
     "gone", "That video is unavailable or was removed."),
    (("unsupported url", "is not a valid url", "unable to download webpage"), "url",
     "That doesn't look like a working video link."),
]

ERROR_PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ytmp34: download failed</title>
<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#0e0e10;color:#ececf1;
font:16px/1.5 system-ui,sans-serif;padding:16px;box-sizing:border-box"><main style="max-width:480px">
<h1 style="font-size:22px;margin:0 0 12px">Couldn't download that</h1><p style="color:#ff3b3b">{}</p>
<p><a href="javascript:history.back()" style="color:inherit">&larr; Back to the video</a></p></main>"""


class Fail(Exception):
    def __init__(self, code, text):
        super().__init__(text)
        self.code, self.text = code, text


def friendly(msg):
    msg = msg.replace("\x1b[0;31mERROR:\x1b[0m ", "").replace("ERROR: ", "")
    low = msg.lower()
    for needles, code, text in ERRORS:
        if any(n in low for n in needles):
            return code, text
    return "other", re.sub(r"^\[\w+\] [\w-]+: ", "", msg)[:300]


# --- phone alerts when the cookies stop working ---

def notify(title, msg):
    # the "ntfy" file holds one topic per line; json so titles can have emoji
    try:
        with open(os.path.join(HERE, "ntfy")) as f:
            topics = [t.strip() for t in f if t.strip()]
    except OSError:
        return
    for topic in topics:
        try:
            body = json.dumps({"topic": topic, "title": title, "message": msg, "priority": 5}).encode()  # always max: shows on top
            req = urllib.request.Request("https://ntfy.sh", data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print("notify failed: %s" % e)


def cookies_state(ok):
    global cookies_ok
    with lock:
        changed, cookies_ok = ok != cookies_ok, ok
    if changed and ok:
        notify("ytmp34 works again", "YouTube accepts the cookies again.")
    elif changed:
        notify("ytmp34: cookies expired", "YouTube is blocking the server. Export fresh cookies and run the refresh command.")


def watch_cookies():
    time.sleep(60)
    while True:
        try:
            get_info("https://www.youtube.com/watch?v=jNQXAC9IVRw", fresh=True)
            cookies_state(True)
        except Exception as e:
            if friendly(str(e))[0] == "cookies":
                cookies_state(False)
        time.sleep(6 * 3600)


# --- stats for dev mode, memory only ---

def stats(tab="", active=False):
    now = time.time()
    with lock:
        if tab and active:
            last_active[tab] = now
        for v, seen in list(last_active.items()):
            if now - seen > 60:
                del last_active[v]
        users = {v for v, seen in last_active.items() if now - seen <= 5} | set(busy)
        converting = len(running) + len(waiting)
        anonymous = max(0, converting - sum(busy.values()))  # bookmark downloads have no tab id
        return {"active": len(users) + anonymous, "converting": converting, "videos": totals["videos"], "bytes": totals["bytes"]}


def mark_busy(tab, n):
    if not tab:
        return
    with lock:
        busy[tab] = busy.get(tab, 0) + n
        if not busy[tab]:
            del busy[tab]


# --- pie mode: a status page for the owner, behind a password ---
# the password lives only in a file called "pie" next to this file (never in the repo).
# YTMP34_PI_STATUS: the pi's status url over tailscale, e.g. http://100.x.y.z:8780/status

STARTED = time.time()
PI_STATUS = os.environ.get("YTMP34_PI_STATUS", "")
recent = deque(maxlen=10)  # last conversions, memory only
errors = deque(maxlen=10)
pie_fails = defaultdict(deque)  # ip -> times of wrong passwords
pie_all_fails = deque()


def pie_check(ip, pw):
    # 4 digits are easy to guess, so: 5 wrong per ip per 15 min, and 20 wrong in total per hour locks everyone out
    try:
        with open(os.path.join(HERE, "pie")) as f:
            secret = f.read().strip()
    except OSError:
        return False, 0
    now = time.time()
    with lock:
        mine = pie_fails[ip]
        while mine and now - mine[0] > 900:
            mine.popleft()
        while pie_all_fails and now - pie_all_fails[0] > 3600:
            pie_all_fails.popleft()
        if len(mine) >= 5:
            return False, int(900 - (now - mine[0]))
        if len(pie_all_fails) >= 20:
            return False, int(3600 - (now - pie_all_fails[0]))
        if secret and hmac.compare_digest(pw.encode(), secret.encode()):
            return True, 0
        mine.append(now)
        pie_all_fails.append(now)
        return False, 0


cpu_now = {"pct": 0.0}


def sample_cpu():
    # cpu use over the last second, measured in the background for pie mode
    def stat():
        with open("/proc/stat") as f:
            v = [int(x) for x in f.readline().split()[1:]]
        return sum(v), v[3] + v[4]
    prev = stat()
    while True:
        time.sleep(1)
        cur = stat()
        dt, di = cur[0] - prev[0], cur[1] - prev[1]
        cpu_now["pct"] = round(100 * (1 - di / dt), 1) if dt else 0.0
        prev = cur


def machine():
    mem = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, _, v = line.partition(":")
            mem[k] = int(v.split()[0]) * 1024
    with open("/proc/uptime") as f:
        uptime = float(f.read().split()[0])
    disk = shutil.disk_usage("/")
    return {"uptime": uptime, "load": os.getloadavg(), "cpus": os.cpu_count(), "cpu": cpu_now["pct"],
            "memory": {"total": mem.get("MemTotal", 0), "available": mem.get("MemAvailable", 0)},
            "disk": {"total": disk.total, "free": disk.free}}


def proxy_ok():
    if not PROXY:
        return None
    host, _, port = PROXY.split("://")[-1].rpartition(":")
    try:
        socket.create_connection((host, int(port)), timeout=3).close()
        return True
    except OSError:
        return False


pie_seen = {"at": 0, "running": False}
pie_cache = {"pi": None, "pi_error": "not checked yet", "proxy_ok": None, "history": []}


def pie_poller():
    # asks the pi every second, but only while someone has pie mode open, so /pie answers instantly
    # even when the pi is unplugged (no waiting for timeouts)
    n = 0
    while time.time() - pie_seen["at"] < 30:
        pi, err = None, None
        if PI_STATUS:
            try:
                full = n % 60 == 0  # the 24 h history only once a minute
                with urllib.request.urlopen(PI_STATUS + ("?full=1" if full else ""), timeout=3) as r:
                    pi = json.loads(r.read())
                if full:
                    pie_cache["history"] = pi.pop("history", [])
            except Exception as e:
                err = str(e)[:200]
        pie_cache.update(pi=pi, pi_error=err, proxy_ok=proxy_ok())
        n += 1
        time.sleep(1)
    with lock:
        pie_seen["running"] = False


def watch_pi():
    # oracle keeps an eye on the pi: the pi can't send a push about itself being dead
    if not PI_STATUS:
        return
    fails, down_since = 0, None
    while True:
        try:
            urllib.request.urlopen(PI_STATUS, timeout=10).read()
            if down_since:
                notify("✅ PRISMO ist wieder da", "war %d Min weg. Oracle hat aufgepasst 🦁" % ((time.time() - down_since) // 60))
            fails, down_since = 0, None
        except Exception:
            fails += 1
            if fails == 5:  # 5 minutes without an answer
                down_since = time.time() - 240
                notify("🚨 PRISMO ist offline!", "Der Pi antwortet seit 5 Minuten nicht. Strom? WLAN? 🔌")
        time.sleep(60)


def pie_action(body):
    # pet / snack / wave / morse: forwarded to the pi, which plays it on its LED
    if not PI_STATUS:
        return 503, {"error": "kein Pi eingerichtet"}
    data = json.dumps({"action": str(body.get("action"))[:16], "text": str(body.get("text", ""))[:40]}).encode()
    req = urllib.request.Request(PI_STATUS.rsplit("/", 1)[0] + "/action", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except ValueError:
            return e.code, {"error": "PRISMO hat komisch geantwortet"}
    except Exception:
        return 504, {"error": "PRISMO antwortet nicht 💤"}


def pie_status():
    with lock:
        pie_seen["at"] = time.time()
        start = not pie_seen["running"]
        pie_seen["running"] = True
    if start:
        threading.Thread(target=pie_poller, daemon=True).start()
        time.sleep(0.8)  # first open: give the pi a moment so the page doesn't start with "offline"
    pi, pi_error = pie_cache["pi"], pie_cache["pi_error"]
    with lock:
        queue = {"running": len(running), "waiting": len(waiting), "slots": SLOTS}
        rec, errs = list(recent), list(errors)
    return {"now": time.time(), "oracle": {**machine(), "server_uptime": time.time() - STARTED,
                                         "yt_dlp": yt_dlp.version.__version__, "youtube_ok": cookies_ok,
                                         "proxy": bool(PROXY), "proxy_ok": pie_cache["proxy_ok"], "queue": queue,
                                         "totals": totals, "recent": rec, "errors": errs, **stats()},
            "pi": pi, "pi_error": pi_error}


# --- rate limits and the queue ---

def allowed(ip, kind):
    now = time.time()
    with lock:
        d = hits[(ip, kind)]
        while d and now - d[0] > 3600:
            d.popleft()
        if len(d) >= PER_IP_HOUR[kind]:
            return False
        d.append(now)
        return True


def estimate(fmt, duration):
    overhead, per_minute = speed[fmt]
    return overhead + per_minute * duration / 60


def learn(fmt, duration, took):
    if duration < 60:
        return
    with lock:
        overhead, per_minute = speed[fmt]
        sample = max(0.5, (took - overhead) / (duration / 60))
        speed[fmt][1] = per_minute * 0.7 + sample * 0.3


def wait_time():
    # call with lock held: when would a new job get a free slot?
    now = time.time()
    slots = [max(0, est - (now - start)) for start, est in running.values()]
    slots = sorted(slots + [0] * (SLOTS - len(slots)))
    for _, est in waiting:
        slots[0] += est
        slots.sort()
    return slots[0]


def enqueue(job, est):
    with lock:
        waiting.append((job, est))
        while waiting[0][0] is not job or len(running) >= SLOTS:
            lock.wait()
        waiting.pop(0)
        running[job] = (time.time(), est)
        lock.notify_all()


def finish(job):
    with lock:
        running.pop(job, None)
        lock.notify_all()


# --- yt-dlp ---

def base_opts():
    opts = {"noplaylist": True, "quiet": True, "no_warnings": True, "noprogress": True}
    if COOKIES and os.path.exists(COOKIES):
        opts["cookiefile"] = COOKIES
    if PROXY:
        opts["proxy"] = PROXY
    return opts


def get_info(url, fresh=False):
    # looked up once for the estimate, reused for the download so youtube only gets asked once
    now = time.time()
    with lock:
        for k, (t, _) in list(info_cache.items()):
            if now - t > 600:
                del info_cache[k]
        if url in info_cache and not fresh:
            return info_cache[url][1]
    with yt_dlp.YoutubeDL(base_opts()) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
    with lock:
        info_cache[url] = (now, info)
    return info


def problem(info, fmt):
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        return "is_live"
    if (info.get("duration") or 0) > MAX_LENGTH[fmt]:
        return "too long"


class Log:
    def __init__(self):
        self.lines = []

    def debug(self, msg):
        self.lines.append(msg)

    info = warning = error = debug


def download(info, fmt, workdir):
    log = Log()
    opts = {
        **base_opts(),
        **FORMATS[fmt],
        "outtmpl": os.path.join(workdir, "%(title).150B.%(ext)s"),
        "writethumbnail": True,
        "windowsfilenames": True,
        "max_filesize": MAX_SIZE[fmt],
        "logger": log,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.process_ie_result(copy.deepcopy(info), download=True)
    files = [f for f in os.listdir(workdir) if f.endswith("." + fmt)]
    if not files:
        raise RuntimeError("too big" if any("max-filesize" in l for l in log.lines) else "no output file produced")
    return os.path.join(workdir, files[0])


class Handler(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Expose-Headers", "Content-Disposition, Content-Length")

    def json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def fail(self, code, body):
        # bookmarks open this directly, so show a page instead of json
        if not self.direct:
            return self.json(code, body)
        data = ERROR_PAGE.format(html.escape(body["error"])).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def ip(self):
        # caddy adds the real address last
        return (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[-1].strip()

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        self.direct = q.get("direct") == "1"
        if u.path == "/ping":
            return self.json(200, {"ok": True, "yt_dlp": yt_dlp.version.__version__, **stats(q.get("v", "")[:32], q.get("a") == "1")})
        if u.path not in ("/info", "/dl"):
            return self.fail(404, {"error": "not found"})

        url, fmt = q.get("url", ""), q.get("fmt", "mp3")
        if fmt not in FORMATS or not url.startswith(("http://", "https://")):
            return self.fail(400, {"error": "bad url or format"})
        if u.path == "/info":
            return self.info(url, fmt)
        self.dl(url, fmt, q.get("v", "")[:32])

    def do_POST(self):
        self.direct = False
        if urllib.parse.urlparse(self.path).path != "/pie":
            return self.json(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 1000)) or b"{}")
            pw = body.get("pw", "")
        except ValueError:
            body, pw = {}, ""
        ok, wait = pie_check(self.ip(), str(pw))
        if not ok:
            return self.json(403, {"error": "wrong" if not wait else "locked", "wait": wait})
        if body.get("action"):
            return self.json(*pie_action(body))
        out = pie_status()
        if body.get("full"):
            out["history"] = pie_cache["history"]
        self.json(200, out)

    def lookup(self, url, fmt):
        try:
            info = get_info(url)
        except Exception as e:
            code, text = friendly(str(e))
            if code == "cookies":
                cookies_state(False)
            return None, (code, text)
        cookies_state(True)
        p = problem(info, fmt)
        return info, (friendly(p) if p else None)

    def info(self, url, fmt):
        if not allowed(self.ip(), "info"):
            return self.json(429, {"error": "Slow down a bit: too many lookups in the last hour.", "code": "rate"})
        info, err = self.lookup(url, fmt)
        if err:
            return self.json(500, {"error": err[1], "code": err[0]})
        with lock:
            wait, ahead = wait_time(), len(waiting)
        duration = info.get("duration") or 0
        self.json(200, {"title": info.get("title") or "", "duration": duration,
                        "estimate": round(estimate(fmt, duration)), "wait": round(wait), "ahead": ahead})

    def dl(self, url, fmt, tab):
        ip = self.ip()
        with lock:
            full, mine = len(waiting) >= MAX_WAITING, per_ip[ip] >= PER_IP_AT_ONCE
        if full:
            return self.fail(503, {"error": "The server is busy right now. Try again in a minute.", "code": "busy"})
        if mine:
            return self.fail(429, {"error": "You already have 2 conversions going. Wait for one to finish.", "code": "rate"})
        if not allowed(ip, "dl"):
            return self.fail(429, {"error": "Slow down a bit: you can convert up to 30 videos per hour.", "code": "rate"})
        if shutil.disk_usage(tempfile.gettempdir()).free < MIN_FREE_DISK:
            return self.fail(503, {"error": "The server is short on space right now. Try again later.", "code": "busy"})

        with lock:
            per_ip[ip] += 1
        mark_busy(tab, 1)
        workdir = tempfile.mkdtemp(prefix="ytmp34-")
        job = object()
        try:
            info, err = self.lookup(url, fmt)
            if err:
                raise Fail(*err)
            duration = info.get("duration") or 0
            enqueue(job, estimate(fmt, duration))
            try:
                start = time.time()
                try:
                    path = download(info, fmt, workdir)
                except Exception as e:
                    # the cached lookup's video links can go stale (403): look it up again once
                    if "403" not in str(e):
                        raise
                    info = get_info(url, fresh=True)
                    path = download(info, fmt, workdir)
                learn(fmt, duration, time.time() - start)
            finally:
                finish(job)
            name = os.path.basename(path)
            self.send_response(200)
            self.cors()
            self.send_header("Content-Type", "audio/mpeg" if fmt == "mp3" else "video/mp4")
            self.send_header("Content-Length", str(os.path.getsize(path)))
            self.send_header(
                "Content-Disposition",
                "attachment; filename=\"%s\"; filename*=UTF-8''%s"
                % (name.encode("ascii", "replace").decode().replace('"', "'"), urllib.parse.quote(name)),
            )
            self.end_headers()
            with open(path, "rb") as f:
                shutil.copyfileobj(f, self.wfile, 1 << 20)
            count_done(os.path.getsize(path))
            with lock:
                recent.appendleft({"title": info.get("title") or name, "fmt": fmt, "size": os.path.getsize(path),
                                   "duration": duration, "took": round(time.time() - start, 1), "at": time.time()})
        except Exception as e:
            print("download failed: %s" % e)
            code, text = (e.code, e.text) if isinstance(e, Fail) else friendly(str(e))
            with lock:
                errors.appendleft({"code": code, "text": text[:200], "fmt": fmt, "at": time.time()})
            if code == "cookies":
                cookies_state(False)
            try:
                self.fail(500, {"error": text, "code": code})
            except Exception:
                pass
        finally:
            with lock:
                per_ip[ip] -= 1
                if not per_ip[ip]:
                    del per_ip[ip]
            mark_busy(tab, -1)
            shutil.rmtree(workdir, ignore_errors=True)

    def log_message(self, fmt, *args):
        print("%s %s" % (self.ip(), fmt % args))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    print("ytmp34 server on http://%s:%d  (yt-dlp %s)" % (a.host, a.port, yt_dlp.version.__version__))
    threading.Thread(target=watch_cookies, daemon=True).start()
    threading.Thread(target=sample_cpu, daemon=True).start()
    threading.Thread(target=watch_pi, daemon=True).start()
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
