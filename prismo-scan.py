#!/usr/bin/env python3
# PRISMO's eye: reads QR codes and barcodes off the camera (zbar, no AI) and sends each new one to oracle,
# which hands it to the mac or windows pc that was used last.
# small frames, few per second, so the zero 2 w stays cool. live frames only while someone is looking.
#   python3 prismo-scan.py            (runs as the prismo-scan service)
#   python3 prismo-scan.py test TEXT  (sends TEXT as if it was scanned, no camera needed)
import ctypes
import ctypes.util
import io
import json
import os
import sys
import threading
import time
import urllib.request

HOME = os.path.expanduser("~")
ORACLE = os.environ.get("PRISMO_ORACLE", "https://132-226-199-122.sslip.io")
KEY_FILE = os.path.join(HOME, "prismo", "scan-key")
CAM_JPG, CAM_WANT = "/dev/shm/prismo-cam.jpg", "/dev/shm/prismo-cam-want"
FPS = 5          # scans per second while idle
MOTION = 0.04    # share of the picture that has to change to count as movement
EYE_EVERY = 45   # at most one snapshot to the eye every this many seconds
SAME_AGAIN = 8   # the same code counts again only after it was out of view this long (s)
PIEZO_PIN = 19


def key():
    with open(KEY_FILE) as f:
        return f.read().strip()


def send(text, kind):
    body = json.dumps({"text": text, "type": kind, "at": time.time()}).encode()
    req = urllib.request.Request(ORACLE + "/scan/push", data=body,
                                 headers={"Content-Type": "application/json", "X-Scan-Key": key()})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())


# --- zbar straight through ctypes, nothing to pip install ---

class Zbar:
    def __init__(self):
        lib = ctypes.CDLL(ctypes.util.find_library("zbar") or "libzbar.so.0")
        P = ctypes.c_void_p
        for name, res, args in [
            ("zbar_image_scanner_create", P, []),
            ("zbar_image_scanner_set_config", ctypes.c_int, [P, ctypes.c_int, ctypes.c_int, ctypes.c_int]),
            ("zbar_image_create", P, []),
            ("zbar_image_set_format", None, [P, ctypes.c_ulong]),
            ("zbar_image_set_size", None, [P, ctypes.c_uint, ctypes.c_uint]),
            ("zbar_image_set_data", None, [P, P, ctypes.c_ulong, P]),
            ("zbar_scan_image", ctypes.c_int, [P, P]),
            ("zbar_image_first_symbol", P, [P]),
            ("zbar_symbol_next", P, [P]),
            ("zbar_symbol_get_data", ctypes.c_char_p, [P]),
            ("zbar_symbol_get_data_length", ctypes.c_uint, [P]),
            ("zbar_symbol_get_type", ctypes.c_int, [P]),
            ("zbar_get_symbol_name", ctypes.c_char_p, [ctypes.c_int]),
        ]:
            f = getattr(lib, name)
            f.restype, f.argtypes = res, args
        self.z = lib
        self.scanner = lib.zbar_image_scanner_create()
        lib.zbar_image_scanner_set_config(self.scanner, 0, 0, 1)  # every symbology on
        lib.zbar_image_scanner_set_config(self.scanner, 64, 4, 1)  # QR: raw bytes, no shift-jis guessing
        for addon in (2, 5):  # EAN-2/EAN-5 add-ons: only ever false hits
            lib.zbar_image_scanner_set_config(self.scanner, addon, 0, 0)
        self.image = lib.zbar_image_create()
        lib.zbar_image_set_format(self.image, int.from_bytes(b"Y800", "little"))

    def scan(self, gray, w, h):
        z = self.z
        buf = (ctypes.c_char * len(gray)).from_buffer(gray)
        z.zbar_image_set_size(self.image, w, h)
        z.zbar_image_set_data(self.image, ctypes.addressof(buf), len(gray), None)
        out = []
        if z.zbar_scan_image(self.scanner, self.image) > 0:
            s = z.zbar_image_first_symbol(self.image)
            while s:
                raw = ctypes.string_at(z.zbar_symbol_get_data(s), z.zbar_symbol_get_data_length(s))
                kind = z.zbar_get_symbol_name(z.zbar_symbol_get_type(s)).decode()
                out.append((fix_text(raw), kind))
                s = z.zbar_symbol_next(s)
        return out


def fix_text(raw):
    # QR codes are utf-8 most of the time, old ones latin-1
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


# --- piezo: a short chirp per scan (KY-006 on GPIO19) ---

def chirp(ok=True):
    def run():
        try:
            import lgpio
            h = lgpio.gpiochip_open(0)
            try:
                lgpio.gpio_claim_output(h, PIEZO_PIN)
                for f, t in ([(2000, 0.06), (3000, 0.09)] if ok else [(400, 0.25)]):
                    lgpio.tx_pwm(h, PIEZO_PIN, f, 50)
                    time.sleep(t)
                lgpio.tx_pwm(h, PIEZO_PIN, 0, 0)
                lgpio.gpio_write(h, PIEZO_PIN, 0)
            finally:
                lgpio.gpiochip_close(h)
        except Exception:
            pass  # no piezo, no sound
    threading.Thread(target=run, daemon=True).start()


def to_eye(jpeg, motion):
    def run():
        try:
            req = urllib.request.Request(ORACLE + "/ai/see", data=jpeg, headers={
                "Content-Type": "image/jpeg", "X-Scan-Key": key(), "X-Motion": "%.3f" % motion})
            urllib.request.urlopen(req, timeout=20).read()
        except Exception as e:
            print("eye send failed: %s" % e, flush=True)
    threading.Thread(target=run, daemon=True).start()


def main():
    import numpy as np
    from picamera2 import Picamera2
    from libcamera import Transform

    zbar = Zbar()
    cam = Picamera2()
    W, H = 640, 480
    # mounted upside down in the case, so turn the picture around
    cfg = cam.create_video_configuration(main={"size": (W, H), "format": "RGB888"},
                                         lores={"size": (W, H), "format": "YUV420"},
                                         transform=Transform(hflip=1, vflip=1),
                                         controls={"FrameRate": 10}, buffer_count=2)
    cam.configure(cfg)
    cam.start()
    print("prismo-scan running, sending to %s" % ORACLE, flush=True)

    last_text, last_seen = None, 0.0
    bg, moving, last_eye, started = None, 0, 0.0, time.time()
    while True:
        t0 = time.time()
        watching = False
        try:
            watching = t0 - os.path.getmtime(CAM_WANT) < 5
        except OSError:
            pass

        if watching:
            req = cam.capture_request()
            try:
                yuv = req.make_array("lores")
                buf = io.BytesIO()
                req.make_image("main").save(buf, format="JPEG", quality=70)
            finally:
                req.release()
            with open(CAM_JPG + ".tmp", "wb") as f:
                f.write(buf.getvalue())
            os.replace(CAM_JPG + ".tmp", CAM_JPG)
        else:
            yuv = cam.capture_array("lores")
        gray = bytearray(yuv[:H, :W].tobytes())  # the Y plane is already a grayscale picture

        # movement: a tiny 80x60 copy against a slowly adapting background
        small = yuv[:H:8, :W:8].astype(np.float32)
        if bg is None:
            bg = small
        frac = float((np.abs(small - bg) > 25).mean())
        bg = bg * 0.9 + small * 0.1
        moving = moving + 1 if frac > MOTION else 0
        if moving >= 2 and t0 - last_eye > EYE_EVERY and t0 - started > 15:
            last_eye = t0
            req = cam.capture_request()
            try:
                buf = io.BytesIO()
                req.make_image("main").save(buf, format="JPEG", quality=80)
            finally:
                req.release()
            to_eye(buf.getvalue(), frac)

        for text, kind in zbar.scan(gray, W, H)[:1]:
            if text == last_text and t0 - last_seen < SAME_AGAIN:
                last_seen = t0
                continue
            last_text, last_seen = text, t0
            print("scanned %s: %s" % (kind, text[:120]), flush=True)
            try:
                r = send(text, kind)
                chirp(bool(r.get("to")))
            except Exception as e:
                print("send failed: %s" % e, flush=True)
                chirp(False)

        # faster while someone watches live, slow and cheap otherwise
        time.sleep(max(0.0, (1 / (8 if watching else FPS)) - (time.time() - t0)))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "test":
        print(send(" ".join(sys.argv[2:]), "TEST"))
    else:
        main()
