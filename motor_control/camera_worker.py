#!/usr/bin/env python3
"""Camera worker for the FLASH motor_control web app.

Runs as a child process of app.py and is the ONLY thing that opens the camera.
Writes JPEG frames to stdout as <4-byte big-endian length><jpeg bytes>.
Status and errors go to stderr, one line each.

Keeping the camera in its own process means a wedged camera (cable glitch,
camera knocked loose) can always be cleared by killing this process: the
kernel releases the camera lock when the process dies, and the web server,
serial link and motor positions are untouched.
"""

import os
import signal
import struct
import sys

import simplejpeg
from picamera2 import Picamera2, Preview

WIDTH = int(sys.argv[1]) if len(sys.argv) > 1 else 640
HEIGHT = int(sys.argv[2]) if len(sys.argv) > 2 else 480
JPEG_QUALITY = int(sys.argv[3]) if len(sys.argv) > 3 else 80
# Sensor model this app must use, e.g. "ov5647". Empty = first camera (single-camera Pi).
# On a Pi shared with DoseCam this MUST be set, so a missing FLASH camera can never
# cause the worker to open DoseCam's IMX296 instead.
CAMERA_MODEL = os.environ.get("FLASH_CAMERA_MODEL", "").strip().lower()

_stop = False


def _on_term(_signum, _frame):
    global _stop
    _stop = True


def log(message):
    sys.stderr.write(f"camera_worker: {message}\n")
    sys.stderr.flush()


def pick_camera():
    """Index of the camera to open, chosen by sensor model when one is configured."""
    cameras = Picamera2.global_camera_info()
    found = ", ".join(f"{i}:{c.get('Model', '?')}" for i, c in enumerate(cameras)) or "none"
    if not cameras:
        raise RuntimeError("no cameras detected")
    if not CAMERA_MODEL:
        return 0, cameras[0].get("Model", "?"), found
    for index, info in enumerate(cameras):
        if str(info.get("Model", "")).lower() == CAMERA_MODEL:
            return index, info.get("Model"), found
    raise RuntimeError(f"camera model {CAMERA_MODEL} not detected (found {found})")


def main():
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)
    out = sys.stdout.buffer

    index, model, found = pick_camera()
    camera = Picamera2(index)
    try:
        camera.start_preview(Preview.NULL)
        # XBGR8888 = R,G,B,X bytes in memory, the same format the original OpenCV path used
        config = camera.create_video_configuration(main={"size": (WIDTH, HEIGHT), "format": "XBGR8888"})
        camera.configure(config)
        camera.start()
        log(f"READY {WIDTH}x{HEIGHT} camera {index} ({model}); detected {found}")
        while not _stop:
            frame = camera.capture_array()
            data = simplejpeg.encode_jpeg(frame, quality=JPEG_QUALITY, colorspace="RGBX")
            out.write(struct.pack(">I", len(data)))
            out.write(data)
            out.flush()
    except BrokenPipeError:
        pass  # parent went away
    finally:
        try:
            camera.stop()
        except Exception:
            pass
        try:
            camera.close()
        except Exception:
            pass
        log("closed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # report the real reason to the parent, then exit non-zero
        log(f"ERROR {type(exc).__name__}: {exc}")
        sys.exit(1)
