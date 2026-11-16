#!/usr/bin/env bash
set -u

out=/tmp/pi_direct_camera_burst_probe.jpg
log=/tmp/pi_direct_camera_burst_probe.log
trigger=/sys/module/imx296/parameters/trigger_mode
direct_gpio=26

cleanup() {
  sudo sh -c "echo 0 > $trigger" || true
}
trap cleanup EXIT

rm -f "$out" "$log"

echo "Expected temporary wiring:"
echo "  Pi GPIO${direct_gpio} -> camera J3 pin 2 Trig+ / XTR"
echo "  Pi GND -> camera J3 pin 1 Trig- / GND"
echo

sudo sh -c "echo 1 > $trigger"
echo "kernel trigger_mode=$(cat "$trigger")"

rpicam-still \
  -n \
  -t 10000 \
  --shutter 1000 \
  --gain 1 \
  --awbgains 1,1 \
  --immediate \
  -o "$out" > "$log" 2>&1 &
pid=$!

sleep 2
echo "sending active-low GPIO${direct_gpio} trigger burst"
python3 - <<PY
from gpiozero import DigitalOutputDevice
import time

pin = DigitalOutputDevice(${direct_gpio}, active_high=True, initial_value=True)
time.sleep(0.1)
for i in range(80):
    pin.off()
    time.sleep(0.010)
    pin.on()
    time.sleep(0.040)
pin.close()
print("sent 80 active-low pulses")
PY

wait "$pid"
rc=$?
echo "rpicam-still exit=$rc"
ls -l "$out" 2>/dev/null || true
tail -120 "$log"
exit "$rc"
