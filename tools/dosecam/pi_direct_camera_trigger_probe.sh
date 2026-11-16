#!/usr/bin/env bash
set -u

out=/tmp/pi_direct_camera_trigger_probe.jpg
log=/tmp/pi_direct_camera_trigger_probe.log
trigger=/sys/module/imx296/parameters/trigger_mode
direct_gpio=26

cleanup() {
  sudo sh -c "echo 0 > $trigger" || true
}
trap cleanup EXIT

rm -f "$out" "$log"

echo "Expected temporary wiring:"
echo "  Pi GPIO${direct_gpio} -> camera J3 pin 2 Trig+ / XTR"
echo "  Pi GND or shared ESP/Pi GND -> camera J3 pin 1 Trig- / GND"
echo

echo "setting kernel trigger mode"
sudo sh -c "echo 1 > $trigger"
cat "$trigger"

echo "starting rpicam-still"
rpicam-still \
  -n \
  -t 15000 \
  --shutter 1000 \
  --gain 1 \
  --awbgains 1,1 \
  --immediate \
  -o "$out" > "$log" 2>&1 &
pid=$!

sleep 3
echo "sending direct active-low GPIO${direct_gpio} pulse"
python3 - <<PY
from gpiozero import DigitalOutputDevice
import time

pin = DigitalOutputDevice(${direct_gpio}, active_high=True, initial_value=True)
time.sleep(0.1)
pin.off()   # drive low: active camera trigger
time.sleep(0.010)
pin.on()    # return high: inactive
pin.close()
print("direct GPIO pulse sent")
PY

wait "$pid"
rc=$?
echo "rpicam-still exit=$rc"
ls -l "$out" 2>/dev/null || true
tail -80 "$log"
exit "$rc"
