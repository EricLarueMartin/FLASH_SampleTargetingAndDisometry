#!/usr/bin/env bash
set -u

out=${OUT:-/tmp/rpicam_trigger_probe.jpg}
log=${LOG:-/tmp/rpicam_trigger_probe.log}
trigger=/sys/module/imx296/parameters/trigger_mode
esp=/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0
delay_us=${DELAY_US:-5}
width_us=${WIDTH_US:-10000}
raw_arg=()
if [ "${RAW:-0}" = "1" ]; then
  raw_arg=(--raw)
fi
encoding_arg=()
if [ -n "${ENCODING:-}" ]; then
  encoding_arg=(--encoding "$ENCODING")
fi
timeout_ms=${TIMEOUT_MS:-15000}
trigger_after_s=${TRIGGER_AFTER_S:-3}
burst_count=${BURST_COUNT:-1}
burst_interval_s=${BURST_INTERVAL_S:-0.05}

cleanup() {
  stty -F "$esp" 115200 2>/dev/null || true
  printf 'E0\n' > "$esp" 2>/dev/null || true
  sudo sh -c "echo 0 > $trigger" || true
}
trap cleanup EXIT

rm -f "$out" "$log"

echo "setting kernel trigger mode"
sudo sh -c "echo 1 > $trigger"
cat "$trigger"

echo "configuring ESP"
python3 - <<'PY'
import os
import serial, time
p = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
delay_us = int(os.environ.get("DELAY_US", "5"))
width_us = int(os.environ.get("WIDTH_US", "10000"))
with serial.Serial(p, 115200, timeout=0.5) as ser:
    time.sleep(2)
    ser.read(512)
    for cmd in ["E0", f"D{delay_us}", f"W{width_us}", "L0", "E1"]:
        ser.write((cmd + "\n").encode())
        ser.flush()
        time.sleep(0.15)
        print(cmd, "->", ser.read(512).decode(errors="replace").strip())
PY

echo "starting rpicam-still"
rpicam-still \
  -n \
  -t "$timeout_ms" \
  --shutter 1000 \
  --gain 1 \
  --awbgains 1,1 \
  --immediate \
  "${encoding_arg[@]}" \
  "${raw_arg[@]}" \
  -o "$out" > "$log" 2>&1 &
pid=$!

sleep "$trigger_after_s"
echo "pulsing GPIO26 into ESP"
python3 - <<'PY'
import os
from gpiozero import LED
import time

count = int(os.environ.get("BURST_COUNT", "1"))
interval_s = float(os.environ.get("BURST_INTERVAL_S", "0.05"))
pin = LED(26)
try:
    for _ in range(count):
        pin.on()
        time.sleep(0.001)
        pin.off()
        if count > 1:
            time.sleep(interval_s)
finally:
    pin.close()
print(f"{count} GPIO26 pulse(s) sent")
PY

wait "$pid"
rc=$?
echo "rpicam-still exit=$rc"
ls -l "$out" 2>/dev/null || true
ls -l "${out%.*}.dng" 2>/dev/null || true
tail -80 "$log"
exit "$rc"
