#!/usr/bin/env bash
set -u

out=${OUT:-/tmp/rpicam_raw_probe.raw}
log=${LOG:-/tmp/rpicam_raw_probe.log}
trigger=/sys/module/imx296/parameters/trigger_mode
esp=/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0

cleanup() {
  stty -F "$esp" 115200 2>/dev/null || true
  printf 'E0\n' > "$esp" 2>/dev/null || true
  sudo sh -c "echo 0 > $trigger" || true
}
trap cleanup EXIT

rm -f "$out" "$log"

sudo sh -c "echo 1 > $trigger"
echo "kernel trigger_mode=$(cat "$trigger")"

python3 - <<'PY'
import os
import serial
import time

p = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
delay_us = int(os.environ.get("DELAY_US", "5"))
width_us = int(os.environ.get("WIDTH_US", "100"))
with serial.Serial(p, 115200, timeout=0.5) as ser:
    time.sleep(2)
    ser.read(512)
    for cmd in ["E0", f"D{delay_us}", f"W{width_us}", "L0", "E1"]:
        ser.write((cmd + "\n").encode())
        ser.flush()
        time.sleep(0.15)
        print(cmd, "->", ser.read(512).decode(errors="replace").strip())
PY

rpicam-raw \
  -n \
  -t 15000 \
  --frames 1 \
  --mode 1456:1088:10:P \
  --shutter 1000 \
  --gain 1 \
  --awbgains 1,1 \
  -o "$out" > "$log" 2>&1 &
pid=$!

sleep 3
python3 - <<'PY'
from gpiozero import LED
import time
pin = LED(26)
pin.on()
time.sleep(0.001)
pin.off()
pin.close()
print("GPIO26 pulse sent")
PY

wait "$pid"
rc=$?
echo "rpicam-raw exit=$rc"
ls -l "$out" 2>/dev/null || true
tail -100 "$log"
exit "$rc"
