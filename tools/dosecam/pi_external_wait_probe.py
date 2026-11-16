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

WIDTH, HEIGHT = 1456, 1088
PI_TRIGGER_GPIO = 26


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
    t0 = time.monotonic()
    trig.on()
    time.sleep(width_us / 1_000_000.0)
    trig.off()
    print(f"gpio pulse issued at t+{time.monotonic() - t0:.6f}s from pulse-thread start")


def main():
    wait_s = 10.0
    exposure_width_us = 50
    delay_us = 5

    print("configuring ESP8266")
    with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
        time.sleep(2.0)
        ser.read(512)
        esp_cmd(ser, "E0")
        esp_cmd(ser, f"D{delay_us}")
        esp_cmd(ser, f"W{exposure_width_us}")
        esp_cmd(ser, "L0")
        esp_cmd(ser, "E1")

    print("configuring camera")
    picam2 = Picamera2()
    cfg = picam2.create_still_configuration(
        main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
        raw={"size": (WIDTH, HEIGHT), "format": "R16"},
        transform=Transform(),
    )
    picam2.configure(cfg)
    picam2.set_controls({
        "SyncMode": 1,
        "AeEnable": False,
        "FrameDurationLimits": (33333, 33333),
    })
    picam2.start()
    time.sleep(0.5)

    worker = threading.Thread(target=pulse_after, args=(wait_s,), daemon=True)
    worker.start()

    print("capture_array waiting for external trigger")
    t0 = time.monotonic()
    raw = picam2.capture_array("raw")
    elapsed = time.monotonic() - t0
    print(f"capture returned after {elapsed:.3f}s")
    print(f"raw shape={raw.shape} dtype={raw.dtype} min={raw.min()} max={raw.max()}")

    picam2.stop()
    with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
        esp_cmd(ser, "E0")


if __name__ == "__main__":
    main()
