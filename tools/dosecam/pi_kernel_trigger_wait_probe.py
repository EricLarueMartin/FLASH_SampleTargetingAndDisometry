import os
import threading
import time

from gpiozero import LED
from libcamera import Transform
from picamera2 import Picamera2
import serial

ESP_PORT = (
    "/dev/serial/by-id/"
    "usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
)
TRIGGER_MODE = "/sys/module/imx296/parameters/trigger_mode"
WIDTH, HEIGHT = 1456, 1088
PI_TRIGGER_GPIO = 26


def set_trigger_mode(value):
    rc = os.system(f"sudo sh -c 'echo {int(value)} > {TRIGGER_MODE}'")
    if rc:
        raise RuntimeError(f"failed to set trigger_mode={value}")
    with open(TRIGGER_MODE, "r", encoding="ascii") as f:
        print(f"kernel trigger_mode={f.read().strip()}")


def esp_cmd(ser, cmd):
    ser.write((cmd + "\n").encode())
    ser.flush()
    time.sleep(0.15)
    reply = ser.read(512).decode(errors="replace").strip()
    print(f"{cmd} -> {reply or '<no reply>'}")


def pulse_after(delay_s, width_us=100):
    time.sleep(delay_s)
    trig = LED(PI_TRIGGER_GPIO)
    print(f"pulsing GPIO{PI_TRIGGER_GPIO} after {delay_s:.3f}s wait")
    trig.on()
    time.sleep(width_us / 1_000_000.0)
    trig.off()
    print("gpio pulse issued")


def main():
    wait_s = float(os.environ.get("WAIT_S", "10.0"))
    exposure_width_us = int(os.environ.get("WIDTH_US", "50"))
    delay_us = int(os.environ.get("DELAY_US", "5"))
    picam2 = None

    try:
        print(f"test settings: wait_s={wait_s} delay_us={delay_us} width_us={exposure_width_us}", flush=True)
        set_trigger_mode(1)

        print("configuring ESP8266", flush=True)
        with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
            time.sleep(2.0)
            ser.read(512)
            esp_cmd(ser, "E0")
            esp_cmd(ser, f"D{delay_us}")
            esp_cmd(ser, f"W{exposure_width_us}")
            esp_cmd(ser, "L0")
            esp_cmd(ser, "E1")

        print("configuring camera", flush=True)
        picam2 = Picamera2()
        cfg = picam2.create_still_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
            raw={"size": (WIDTH, HEIGHT), "format": "R16"},
            transform=Transform(),
        )
        picam2.configure(cfg)
        picam2.set_controls({
            "AeEnable": False,
            "ExposureTime": 30,
            "FrameDurationLimits": (33333, 33333),
        })
        picam2.start()
        time.sleep(0.5)

        worker = threading.Thread(target=pulse_after, args=(wait_s,), daemon=True)
        worker.start()

        print("capture_array waiting for kernel external trigger", flush=True)
        t0 = time.monotonic()
        raw = picam2.capture_array("raw")
        elapsed = time.monotonic() - t0
        print(f"capture returned after {elapsed:.3f}s")
        print(f"raw shape={raw.shape} dtype={raw.dtype} min={raw.min()} max={raw.max()}")
    finally:
        if picam2 is not None:
            try:
                picam2.stop()
            except Exception:
                pass
        try:
            with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
                esp_cmd(ser, "E0")
        except Exception as exc:
            print(f"ESP disable failed: {exc}")
        set_trigger_mode(0)


if __name__ == "__main__":
    main()
