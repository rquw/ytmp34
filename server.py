"""ytmp34 server: tiny yt-dlp backend for rquw.github.io/ytmp34.

Runs the same on a Windows PC or a Raspberry Pi. Needs Python 3.9+, yt-dlp, ffmpeg.

    python server.py                      # local only, http://127.0.0.1:8765
    python server.py --host 0.0.0.0       # reachable on your network (e.g. on a Pi)
    YTMP34_KEY=secret python server.py    # require ?key=secret (use when exposing it publicly)
    YTMP34_COOKIES=cookies.txt ...        # YouTube cookies (needed on cloud servers YouTube calls bots)
    YTMP34_MAX=1 ...                      # parallel downloads (default 3; use 1 on a 1 GB machine)
"""
import argparse
import json
import os
import re
import shutil
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yt_dlp

KEY = os.environ.get("YTMP34_KEY", "")
COOKIES = os.environ.get("YTMP34_COOKIES", "")
MAX_CONCURRENT = threading.Semaphore(int(os.environ.get("YTMP34_MAX", "3")))

# Title/artist tags + the video thumbnail as cover art, so files look right in music apps.
# YouTube thumbnails are WebP, which MP3/MP4 cover art can't hold, so convert to JPEG first.
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
        # H.264 + AAC plays everywhere (Windows, phones, editors); capped at 1080p for speed.
        "format": "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4][height<=1080]/bv*[height<=1080]+ba/b",
        "merge_output_format": "mp4",
        "postprocessors": TAGS_AND_COVER,
    },
}

# yt-dlp error text -> (code, message the site shows). First match wins.
ERRORS = [
    (("confirm you", "not a bot"), "cookies",
     "YouTube is blocking the server: its cookies have expired. Export fresh ones (see the README)."),
    (("private video",), "private", "That video is private."),
    (("confirm your age", "age-restricted", "inappropriate for some users"), "age",
     "That video is age-restricted and the server's account can't open it."),
    (("members-only", "join this channel"), "members", "That video is for channel members only."),
    (("live event will begin", "premieres in", "is_live", "this live event"), "live",
     "That's a live stream or premiere that hasn't finished yet. Try again once it's over."),
    (("not available in your country", "geo restrict"), "geo", "That video isn't available in the server's country."),
    (("video unavailable", "video is unavailable", "has been removed", "does not exist", "account associated"),
     "gone", "That video is unavailable or was removed."),
    (("unsupported url", "is not a valid url", "unable to download webpage"), "url",
     "That doesn't look like a working video link."),
]


def friendly(msg):
    low = msg.lower()
    for needles, code, text in ERRORS:
        if any(n in low for n in needles):
            return code, text
    return "other", re.sub(r"^\[\w+\] [\w-]+: ", "", msg)[:300]


def download(url, fmt, workdir):
    opts = {
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

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if KEY and q.get("key") != KEY:
            return self.json(401, {"error": "wrong key"})
        if u.path == "/ping":
            return self.json(200, {"ok": True, "yt_dlp": yt_dlp.version.__version__})
        if u.path != "/dl":
            return self.json(404, {"error": "not found"})

        url, fmt = q.get("url", ""), q.get("fmt", "mp3")
        if fmt not in FORMATS or not url.startswith(("http://", "https://")):
            return self.json(400, {"error": "bad url or format"})

        workdir = tempfile.mkdtemp(prefix="ytmp34-")
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
                self.json(500, {"error": text, "code": code})
            except Exception:
                pass
        finally:
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
