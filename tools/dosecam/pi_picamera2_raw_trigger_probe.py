import os
import threading
import time

from gpiozero import LED
from libcamera import Transform
from picamera2 import Picamera2
import numpy as np
import serial
import tifffile

ESP_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
TRIGGER_MODE = "/sys/module/imx296/parameters/trigger_mode"
OUT = "/tmp/picamera2_raw_trigger_probe.tiff"
WIDTH, HEIGHT = 1456, 1088


def set_trigger_mode(value):
    os.system(f"sudo sh -c 'echo {int(value)} > {TRIGGER_MODE}'")


def log(*args):
    print(*args, flush=True)


def esp_cmd(ser, cmd):
    ser.write((cmd + "\n").encode())
    ser.flush()
    time.sleep(0.15)
    log(cmd, "->", ser.read(512).decode(errors="replace").strip())


def trigger_burst(delay_s=0.25, count=100):
    time.sleep(delay_s)
    pin = LED(26)
    for _ in range(count):
        pin.on()
        time.sleep(0.001)
        pin.off()
        time.sleep(0.050)
    pin.close()
    log(f"sent {count} Pi->ESP trigger pulses")


def to_dn10(raw):
    if raw.dtype == np.uint8:
        if raw.shape[1] < WIDTH * 2:
            raise RuntimeError(f"Raw byte row is too short: {raw.shape}")
        arr = raw[:, : (raw.shape[1] // 2) * 2].view("<u2")
        arr = arr[:, :WIDTH]
    else:
        arr = raw.astype(np.uint16, copy=False)
        arr = arr[:HEIGHT, :WIDTH]

    arr = arr.astype(np.uint16, copy=False)
    log("decoded", arr.shape, arr.dtype, int(arr.min()), int(arr.max()))
    if arr.max() > 4095:
        arr = arr >> 6
    return np.clip(arr, 0, 1023).astype(np.uint16)


def main():
    picam2 = None
    try:
        with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
            time.sleep(2)
            ser.read(512)
            for cmd in ["E0", "D5", "W100", "L0", "E1"]:
                esp_cmd(ser, cmd)

        set_trigger_mode(1)
        picam2 = Picamera2()
        cfg = picam2.create_still_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
            raw={"size": (WIDTH, HEIGHT), "format": "R16"},
            transform=Transform(),
        )
        log(cfg)
        picam2.configure(cfg)
        picam2.set_controls({
            "AeEnable": False,
            "AnalogueGain": 1.0,
            "ExposureTime": 100,
            "FrameDurationLimits": (33333, 33333),
        })
        threading.Thread(target=trigger_burst, daemon=True).start()
        log("starting camera while trigger burst is pending")
        picam2.start()
        log("camera started")
        t0 = time.monotonic()
        raw = picam2.capture_array("raw")
        log("capture elapsed", time.monotonic() - t0)
        log("raw", raw.shape, raw.dtype, int(raw.min()), int(raw.max()))
        dn = to_dn10(raw)
        log("dn", dn.shape, dn.dtype, int(dn.min()), int(dn.max()))
        try:
            tifffile.imwrite(OUT, dn, photometric="minisblack", compression="zlib")
        except Exception as exc:
            log("zlib compression failed, writing uncompressed:", exc)
            tifffile.imwrite(OUT, dn, photometric="minisblack")
        log("wrote", OUT, os.path.getsize(OUT))
    finally:
        if picam2 is not None:
            try:
                picam2.stop()
            except Exception:
                pass
        set_trigger_mode(0)
        try:
            with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
                esp_cmd(ser, "E0")
        except Exception as exc:
            log("ESP disable failed:", exc)


if __name__ == "__main__":
    main()
