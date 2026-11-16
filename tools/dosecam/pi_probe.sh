#!/usr/bin/env bash
set -u

echo "== identity =="
hostname
whoami
id

echo "== usb serial =="
lsusb
ls -l /dev/serial/by-id /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true

echo "== camera list =="
rpicam-hello --list-cameras || true

echo "== python imports =="
python3 - <<'PY'
mods = ["serial", "picamera2", "flask", "gpiozero", "numpy", "tifffile", "matplotlib"]
for mod in mods:
    try:
        __import__(mod)
        print(f"{mod}: ok")
    except Exception as exc:
        print(f"{mod}: missing/error: {exc}")
PY

echo "== esp8266 serial probe =="
python3 - <<'PY'
import time

try:
    import serial
except Exception as exc:
    print(f"pyserial unavailable: {exc}")
    raise SystemExit(0)

port = "/dev/ttyUSB0"
try:
    ser = serial.Serial(port, 115200, timeout=0.5)
except Exception as exc:
    print(f"open {port} failed: {exc}")
    raise SystemExit(0)

with ser:
    time.sleep(2.0)
    initial = ser.read(512)
    if initial:
        print("initial:", initial.decode(errors="replace").strip())
    for cmd in (b"E0\n", b"D123\n", b"W20\n"):
        ser.write(cmd)
        ser.flush()
        time.sleep(0.2)
        reply = ser.read(512)
        print(cmd.decode().strip(), "->", reply.decode(errors="replace").strip() or "<no reply>")
PY

echo "== camera still smoke test =="
rm -f /tmp/dose_cam_probe.jpg
rpicam-still -n -t 1000 --width 640 --height 480 -o /tmp/dose_cam_probe.jpg
rc=$?
echo "rpicam-still exit: $rc"
ls -l /tmp/dose_cam_probe.jpg 2>/dev/null || true
