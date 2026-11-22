#!/usr/bin/env python3
"""PRISMO's brain on oracle. small local models through ollama, speech through faster-whisper.
  eye:    the pi sends a snapshot when something moves. moondream says what it sees, qwen decides
          if that's worth a push (and writes it). push with the picture through ntfy.
  voice:  the app sends a voice note. whisper writes it down, qwen splits it into reminders with dates.
  check:  once a day: PRISMO's numbers next to the last two weeks. rules find what's off,
          qwen says it in one or two sentences. no findings, no push.
runs on 127.0.0.1:8790, server.py relays /ai/* to it (scan key).
"""
import base64
import collections
import datetime as dt
import json
import os
import re
import statistics
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
AI = os.path.join(HOME, "ai")
EYE = os.path.join(AI, "eye")
YT = os.path.join(HOME, "ytmp34")
OLLAMA = "http://127.0.0.1:11434"
PI = os.environ.get("YTMP34_PI_STATUS", "").rsplit("/", 1)[0]  # http://100.x.y.z:8780
PI_DAY = PI.rsplit(":", 1)[0] + ":8781" if PI else ""
TEXT, VISION = "qwen2.5:3b", "moondream"

os.makedirs(EYE, exist_ok=True)
brain = threading.Lock()  # one model at a time: 2 cores, no point in more


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, data):
    with open(path + ".tmp", "w") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def get_json(url, timeout=15, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout) as r:
        return json.loads(r.read())


def ollama(model, prompt, system="", images=None, as_json=False, timeout=240):
    body = {"model": model, "prompt": prompt, "system": system, "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 2048}}
    if images:
        body["images"] = images
    if as_json:
        body["format"] = "json"
    req = urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with brain:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read())["response"].strip()
    if as_json:
        m = re.search(r"\{.*\}", out, re.S)
        return json.loads(m.group(0) if m else out)
    return out


# --- pushes (same ntfy topic as everything else, always max priority) ---

def topic():
    try:
        with open(os.path.join(YT, "ntfy")) as f:
            return next((t.strip() for t in f if t.strip()), "")
    except OSError:
        return ""


def h(s):
    # headers are latin-1 only; ntfy understands encoded words for umlauts and emoji
    return "=?UTF-8?B?" + base64.b64encode(s.encode()).decode() + "?="


def push(title, message, image=None, tags=""):
    t = topic()
    if not t:
        print("push: %s | %s" % (title, message), flush=True)
        return
    try:
        if image:
            req = urllib.request.Request("https://ntfy.sh/" + t, data=image, method="PUT", headers={
                "Title": h(title), "Message": h(message), "Priority": "5", "Filename": "prismo.jpg", "Tags": tags})
        else:
            req = urllib.request.Request("https://ntfy.sh", data=json.dumps(
                {"topic": t, "title": title, "message": message, "priority": 5,
                 "tags": [x for x in tags.split(",") if x]}).encode(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        print("push failed: %s" % e, flush=True)


# --- the eye ---

SIGHTINGS = os.path.join(AI, "sightings.json")
sightings = collections.deque(load(SIGHTINGS, []), maxlen=40)
eye_queue = collections.deque(maxlen=3)
eye_wake = threading.Event()
last_push = {"at": 0}

EYE_SYSTEM = """Du bist das Auge von PRISMO, einem kleinen Computer in Fabios Zimmer in Ternberg.
Fabio hat einen kleinen Hund namens Lenny (Biewer Yorkshire). Die Kamera schaut in sein Zimmer.
Du bekommst eine Bildbeschreibung (englisch) und entscheidest, ob Fabio das wissen will.
Interessant: Menschen im Zimmer während Fabio weg ist, Lenny an lustigen oder verbotenen Orten,
Licht/Bildschirm brennt obwohl niemand da ist, etwas fällt um, Rauch, offenes Fenster bei Regen.
Langweilig: leeres Zimmer, Licht und Schatten, Fabio selbst wenn er daheim ist, kleine Bewegungen.
Antworte NUR als JSON: {"seeing": ["max 5 Dinge, deutsch"], "interesting": true/false,
"howmuch": 0-100, "say": "ein kurzer deutscher Satz für die Push-Nachricht, mit einem passenden Emoji"}"""


def where_is_fabio():
    if not PI_DAY:
        return "unbekannt"
    try:
        return "daheim" if get_json(PI_DAY + "/day/where", timeout=5).get("home") else "unterwegs"
    except Exception:
        return "unbekannt"


def eye_worker():
    while True:
        eye_wake.wait()
        eye_wake.clear()
        while eye_queue:
            img, motion, at = eye_queue.popleft()
            try:
                look(img, motion, at)
            except Exception as e:
                print("eye: %s" % e, flush=True)


def look(img, motion, at):
    b64 = base64.b64encode(img).decode()
    caption = ollama(VISION, "Describe this photo of a room in one or two sentences. Mention any people, animals, "
                             "lights, screens and anything unusual.", images=[b64], timeout=180)
    fabio = where_is_fabio()
    recent = [s["say"] for s in list(sightings)[-3:]]
    t = dt.datetime.fromtimestamp(at)
    prompt = ("Zeit: %s %s Uhr\nFabio ist gerade: %s\nBewegung im Bild: %d %%\nLetzte Meldungen: %s\n"
              "Bildbeschreibung: %s" % (["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][t.weekday()], t.strftime("%H:%M"),
                                        fabio, round(motion * 100), "; ".join(recent) or "keine", caption))
    j = ollama(TEXT, prompt, system=EYE_SYSTEM, as_json=True)
    howmuch = max(0, min(100, int(j.get("howmuch", 0) or 0)))
    sid = str(int(at * 1000))
    with open(os.path.join(EYE, sid + ".jpg"), "wb") as f:
        f.write(img)
    s = {"id": sid, "at": at, "caption": caption, "seeing": j.get("seeing", [])[:5], "interesting": bool(j.get("interesting")),
         "howmuch": howmuch, "say": str(j.get("say", ""))[:140], "fabio": fabio, "pushed": False}
    # he's away: lower bar. same thing again within 10 min: only if it's really big
    bar = 55 if fabio == "unterwegs" else 75
    if s["interesting"] and howmuch >= bar and (time.time() - last_push["at"] > 600 or howmuch >= 90):
        push("👁️ PRISMO sieht was", s["say"], image=img, tags="eyes")
        last_push["at"] = time.time()
        s["pushed"] = True
    sightings.append(s)
    save(SIGHTINGS, list(sightings))
    keep = {x["id"] for x in sightings}
    for name in os.listdir(EYE):
        if name[:-4] not in keep:
            os.remove(os.path.join(EYE, name))
    print("eye: %s (%d %%) %s" % (s["say"], howmuch, "PUSH" if s["pushed"] else ""), flush=True)


# --- voice notes ---

_whisper = {"m": None}

VOICE_SYSTEM = """Du machst aus Fabios Sprachnotiz iPhone-Erinnerungen. Fabio ist Schüler (HTL Linz).
Regeln:
- Jede eigene Sache wird eine eigene Erinnerung. "und", "außerdem", "noch was" trennen Sachen.
- Titel kurz und klar, deutsch, wie Fabio es sagen würde, ohne Füllwörter ("äh", "PRISMO").
- Datum: nur wenn er eines nennt oder meint (Wochentag, morgen, übermorgen, nächste Woche, Uhrzeit).
  Wochentage sind immer der nächste solche Tag ab heute. Ohne Uhrzeit: 17:00.
  Bei Tests/Checks/Prüfungen/Abgaben an einem Tag: Erinnerung am Vorabend 18:00, Titel z. B. "Mathe-Check morgen: lernen".
- Nichts dazuerfinden, keine Erinnerungen die er nicht gesagt hat.
Antworte NUR als JSON: {"reminders": [{"title": "...", "due": "YYYY-MM-DDTHH:MM" oder null, "notes": "" }]}"""


def transcribe(path):
    if _whisper["m"] is None:
        from faster_whisper import WhisperModel
        _whisper["m"] = WhisperModel("small", device="cpu", compute_type="int8", download_root=os.path.join(AI, "whisper"))
    with brain:
        segs, _ = _whisper["m"].transcribe(path, language="de", vad_filter=True, beam_size=1)
        return " ".join(s.text.strip() for s in segs).strip()


def voice(audio, name):
    path = os.path.join(AI, "note" + os.path.splitext(name or "x.m4a")[1])
    with open(path, "wb") as f:
        f.write(audio)
    text = transcribe(path)
    os.remove(path)
    if not text:
        return {"text": "", "reminders": []}
    now = dt.datetime.now()
    days = ", ".join("%s=%s" % (["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][(now + dt.timedelta(days=i)).weekday()],
                                (now + dt.timedelta(days=i)).strftime("%Y-%m-%d")) for i in range(1, 8))
    prompt = "Jetzt: %s, %s Uhr\nNächste Tage: %s\nSprachnotiz: \"%s\"" % (
        now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), days, text)
    j = ollama(TEXT, prompt, system=VOICE_SYSTEM, as_json=True)
    out = []
    for r in j.get("reminders", [])[:10]:
        title = str(r.get("title", "")).strip()
        due = r.get("due")
        if due:
            try:
                due = dt.datetime.fromisoformat(str(due)[:16]).strftime("%Y-%m-%dT%H:%M")
            except ValueError:
                due = None
        if title:
            out.append({"title": title[:120], "due": due, "notes": str(r.get("notes") or "")[:300]})
    return {"text": text, "reminders": out}


# --- daily self-check ---

HEALTH = os.path.join(AI, "health.json")

CHECK_SYSTEM = """Du bist PRISMOs Hausmeister. Fabio betreibt einen Raspberry Pi (PRISMO) daheim und einen
Oracle-Server (ytmp34, ein YouTube-Konverter). Du bekommst Auffälligkeiten, die schon sicher erkannt wurden,
mit Zahlen. Erklär sie in 1-2 kurzen deutschen Sätzen, konkret, mit den Zahlen und der wahrscheinlichen Ursache
und was er tun soll. Kein Gelaber. Antworte NUR als JSON: {"title": "max 5 Wörter mit Emoji", "message": "..."}"""


def journal_warnings(unit, since="-24h"):
    try:
        out = subprocess.run(["journalctl", "-u", unit, "--since", since, "-p", "warning", "-o", "cat", "--no-pager"],
                             capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
        return out
    except Exception:
        return []


def collect():
    today = {"date": dt.date.today().isoformat()}
    notes = []
    key = open(os.path.join(YT, "scan")).read().strip()
    try:
        st = get_json("http://127.0.0.1:8765/scan/status", timeout=20, headers={"X-Scan-Key": key})
    except Exception as e:
        st = {}
        notes.append("Oracle-Status nicht abrufbar: %s" % e)
    o, p = st.get("oracle") or {}, st.get("pi") or {}
    recent = o.get("recent") or []
    took = [r["took"] / max(r["duration"] / 60, 1) for r in recent if r.get("duration")]
    today.update(conversions=(o.get("totals") or {}).get("videos", 0), yt_ok=bool(o.get("youtube_ok")),
                 secs_per_min=round(statistics.median(took), 1) if took else None,
                 yt_errors=len(o.get("errors") or []),
                 oracle_disk_free=round((o.get("disk") or {}).get("free", 0) / 1e9, 1))
    if p:
        hist = st.get("history") or []
        temps = [x[2] for x in hist if len(x) > 2 and x[2]]
        net = p.get("net_watch") or {}
        day0 = time.time() - 86400
        outs = [x for x in net.get("outages", []) if x[1] > day0]
        speeds = [x[1] for x in net.get("speeds", []) if x[0] > day0 and x[1] > 0]
        sites = (p.get("prismo") or {}).get("sites") or {}
        today.update(pi_online=True, pi_temp_max=max(temps) if temps else p.get("cpu_temp"),
                     pi_disk_free=round((p.get("disk") or {}).get("free", 0) / 1e9, 1),
                     outages=len(outs), outage_min=round(sum(b - a for a, b in outs) / 60),
                     speed_down=round(statistics.median(speeds), 1) if speeds else None,
                     sites_down=[n for n, s in sites.items() if not s.get("ok")],
                     services_off=[n for n, v in (p.get("services") or {}).items()
                                   if v != "active" and n != "prismo-scan"],
                     untis_fails=(p.get("untis") or {}).get("fails", 0), throttle=p.get("throttle"))
        try:
            hw = get_json(PI + "/health", timeout=20)
            today.update(pi_warnings=hw.get("warnings", 0), pi_failed=hw.get("failed", []))
            notes += ["Pi: " + l for l in hw.get("lines", [])[-15:]]
        except Exception:
            pass
    else:
        today.update(pi_online=False)
    ow = journal_warnings("ytmp34")
    today["oracle_warnings"] = len(ow)
    notes += ["Oracle: " + l[:160] for l in ow[-15:]]
    return today, notes


def findings(today, past):
    """plain rules decide whether something's off. the model only puts it into words"""
    f = []

    def med(key):
        vals = [d[key] for d in past[-7:] if isinstance(d.get(key), (int, float))]
        return statistics.median(vals) if len(vals) >= 3 else None

    if not today.get("pi_online", True):
        f.append("PRISMO hat beim Check nicht geantwortet")
    if today.get("pi_temp_max") and today["pi_temp_max"] >= 75:
        f.append("PRISMO war heute bis %.0f °C heiß" % today["pi_temp_max"])
    if (today.get("pi_disk_free") or 99) < 2:
        f.append("PRISMOs SD-Karte hat nur noch %.1f GB frei" % today["pi_disk_free"])
    if (today.get("oracle_disk_free") or 99) < 5:
        f.append("Oracle hat nur noch %.1f GB frei" % today["oracle_disk_free"])
    if today.get("outages", 0) >= 3 or today.get("outage_min", 0) >= 30:
        f.append("Internet daheim %d× weg, zusammen %d min" % (today["outages"], today["outage_min"]))
    m = med("speed_down")
    if m and today.get("speed_down") and today["speed_down"] < m * 0.5:
        f.append("Internet nur %.0f statt sonst %.0f Mbit/s" % (today["speed_down"], m))
    m = med("secs_per_min")
    if m and today.get("secs_per_min") and today["secs_per_min"] > m * 2:
        f.append("Konvertieren dauert %.1f s pro Videominute statt sonst %.1f" % (today["secs_per_min"], m))
    if not today.get("yt_ok", True):
        f.append("YouTube blockiert den Server (Cookies/Proxy)")
    if today.get("services_off"):
        f.append("Dienste aus: %s" % ", ".join(today["services_off"]))
    if today.get("sites_down"):
        f.append("Seiten offline: %s" % ", ".join(today["sites_down"]))
    if today.get("untis_fails", 0) >= 6:
        f.append("Untis-Abfrage schlägt seit %d Versuchen fehl" % today["untis_fails"])
    for key, label in (("pi_warnings", "PRISMO"), ("oracle_warnings", "Oracle")):
        m = med(key)
        if today.get(key, 0) >= 20 and (m is None or today[key] > max(m * 3, 20)):
            f.append("%s hat heute %d Warnungen im Log (sonst %s)" % (label, today[key], int(m) if m is not None else "?"))
    if today.get("pi_failed"):
        f.append("Abgestürzte Dienste auf PRISMO: %s" % ", ".join(today["pi_failed"]))
    return f


def check(force=False):
    today, notes = collect()
    past = [d for d in load(HEALTH, []) if d.get("date") != today["date"]]
    f = findings(today, past)
    save(HEALTH, (past + [today])[-30:])
    result = {"today": today, "findings": f, "pushed": False}
    if f:
        prompt = "Auffälligkeiten:\n- %s\n\nLetzte 7 Tage (Zahlen):\n%s\n\nLog-Zeilen:\n%s" % (
            "\n- ".join(f), json.dumps(past[-7:], ensure_ascii=False)[:2500], "\n".join(notes[-20:])[:2500])
        try:
            j = ollama(TEXT, prompt, system=CHECK_SYSTEM, as_json=True)
            title, msg = str(j.get("title") or "🩺 PRISMO-Check"), str(j.get("message") or "; ".join(f))
        except Exception:
            title, msg = "🩺 PRISMO-Check", "; ".join(f)
        push(title[:60], msg[:500], tags="stethoscope")
        result.update(pushed=True, title=title, message=msg)
    elif force:
        result["message"] = "Alles normal, nichts zu melden ✅"
    return result


def check_loop():
    while True:
        now = dt.datetime.now()
        if now.hour == 19 and now.minute == 30:
            try:
                print("check: %s" % check(), flush=True)
            except Exception as e:
                print("check failed: %s" % e, flush=True)
            time.sleep(70)
        time.sleep(30)


# --- http, localhost only; server.py does the key check and relays /ai/* ---

class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self, limit):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(min(n, limit))

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == "/see":
                img = self.body(3 * 2**20)
                eye_queue.append((img, float(self.headers.get("X-Motion") or 0), time.time()))
                eye_wake.set()
                return self.reply(202, {"ok": True})
            if u.path == "/voice":
                return self.reply(200, voice(self.body(15 * 2**20), self.headers.get("X-Filename", "note.m4a")))
        except Exception as e:
            return self.reply(500, {"error": str(e)[:200]})
        self.reply(404, {"error": "not found"})

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if u.path == "/sightings":
                return self.reply(200, [{k: v for k, v in s.items() if k != "caption"} for s in reversed(sightings)])
            if u.path.startswith("/img/"):
                sid = re.sub(r"[^0-9]", "", u.path[5:])
                with open(os.path.join(EYE, sid + ".jpg"), "rb") as f:
                    return self.reply(200, f.read(), "image/jpeg")
            if u.path == "/check":
                return self.reply(200, check(force=q.get("run") == "1") if q.get("run") == "1" else
                                  {"history": load(HEALTH, [])[-14:]})
        except FileNotFoundError:
            return self.reply(404, {"error": "weg"})
        except Exception as e:
            return self.reply(500, {"error": str(e)[:200]})
        self.reply(404, {"error": "not found"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=eye_worker, daemon=True).start()
    threading.Thread(target=check_loop, daemon=True).start()
    print("prismo-ai on 127.0.0.1:8790", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8790), Handler).serve_forever()
