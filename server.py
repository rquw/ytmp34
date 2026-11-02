# ytmp34 server (yt-dlp + ffmpeg)
# env: YTMP34_COOKIES, YTMP34_MAX
import argparse
import html
import json
import os
import re
import shutil
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yt_dlp

COOKIES = os.environ.get("YTMP34_COOKIES", "")
MAX_CONCURRENT = threading.Semaphore(int(os.environ.get("YTMP34_MAX", "3")))

# live stats for dev mode, memory only
stats_lock = threading.Lock()
visitors = {}  # random tab id -> last ping
converting = 0


def stats(visitor=""):
    now = time.time()
    with stats_lock:
        if visitor:
            visitors[visitor[:32]] = now
        for v, seen in list(visitors.items()):
            if now - seen > 75:
                del visitors[v]
        return {"visitors": len(visitors), "converting": converting}


def count_converting(n):
    global converting
    with stats_lock:
        converting += n

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

MAX_LENGTH = {"mp3": 2 * 3600, "mp4": 3600}

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


def friendly(msg):
    low = msg.lower()
    for needles, code, text in ERRORS:
        if any(n in low for n in needles):
            return code, text
    return "other", re.sub(r"^\[\w+\] [\w-]+: ", "", msg)[:300]


def download(url, fmt, workdir):
    rejected = []

    def check(info, *, incomplete=False):
        if info.get("is_live"):
            rejected.append("is_live")
        elif (info.get("duration") or 0) > MAX_LENGTH[fmt]:
            rejected.append("too long")
        return rejected[-1] if rejected else None

    opts = {
        "match_filter": check,
        **FORMATS[fmt],
        "outtmpl": os.path.join(workdir, "%(title).150B.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "writethumbnail": True,
        "restrictfilenames": False,
        "windowsfilenames": True,
    }
    if COOKIES and os.path.exists(COOKIES):
        opts["cookiefile"] = COOKIES
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    if rejected:
        raise RuntimeError(rejected[-1])
    files = [f for f in os.listdir(workdir) if f.endswith("." + fmt)]
    if not files:
        raise RuntimeError("no output file produced")
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

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        self.direct = q.get("direct") == "1"
        if u.path == "/ping":
            return self.json(200, {"ok": True, "yt_dlp": yt_dlp.version.__version__, **stats(q.get("v", ""))})
        if u.path != "/dl":
            return self.fail(404, {"error": "not found"})

        url, fmt = q.get("url", ""), q.get("fmt", "mp3")
        if fmt not in FORMATS or not url.startswith(("http://", "https://")):
            return self.fail(400, {"error": "bad url or format"})

        workdir = tempfile.mkdtemp(prefix="ytmp34-")
        count_converting(1)
        try:
            with MAX_CONCURRENT:
                path = download(url, fmt, workdir)
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
        except Exception as e:
            msg = str(e).replace("\x1b[0;31mERROR:\x1b[0m ", "").replace("ERROR: ", "")
            print("download failed: %s" % msg)
            code, text = friendly(msg)
            try:
                self.fail(500, {"error": text, "code": code})
            except Exception:
                pass
        finally:
            count_converting(-1)
            shutil.rmtree(workdir, ignore_errors=True)

    def log_message(self, fmt, *args):
        print("%s %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    print("ytmp34 server on http://%s:%d  (yt-dlp %s)" % (a.host, a.port, yt_dlp.version.__version__))
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
