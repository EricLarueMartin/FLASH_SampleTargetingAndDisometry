import argparse
import os
import subprocess
import threading
import time

import serial


ESP_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
TRIGGER_MODE = "/sys/module/imx296/parameters/trigger_mode"


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, **kwargs)


def set_trigger_mode(enabled):
    value = "1" if enabled else "0"
    run(["sudo", "sh", "-c", f"echo {value} > {TRIGGER_MODE}"], timeout=5)


def configure_esp(delay_us, width_us):
    with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
        time.sleep(2)
        ser.read(1024)
        for cmd in ["E0", f"D{delay_us}", f"W{width_us}", "L0", "E1"]:
            ser.write((cmd + "\n").encode())
            ser.flush()
            time.sleep(0.12)
            print(cmd, "->", ser.read(512).decode(errors="replace").strip(), flush=True)


def pulse_burst(frames, fps, start_delay_s):
    time.sleep(start_delay_s)
    interval_s = 1.0 / fps
    t0 = time.monotonic()
    try:
        for _ in range(frames):
            subprocess.run(["pinctrl", "set", "26", "op", "dh"], check=True)
            time.sleep(0.001)
            subprocess.run(["pinctrl", "set", "26", "op", "dl"], check=True)
            next_t = t0 + interval_s * (_ + 1)
            delay = next_t - time.monotonic()
            if delay > 0:
                time.sleep(delay)
    finally:
        subprocess.run(["pinctrl", "set", "26", "ip", "pn"], check=False)
    print(f"sent {frames} GPIO26 pulses at target {fps} fps", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--fps", type=float, default=50.0)
    parser.add_argument("--start-delay-s", type=float, default=0.5)
    parser.add_argument("--esp-delay-us", type=int, default=5)
    parser.add_argument("--esp-width-us", type=int, default=100)
    parser.add_argument("--exposure-us", type=int, default=100)
    parser.add_argument("--mode", default="1456:1088:10:P")
    parser.add_argument("--out", default="/tmp/rpicam_raw_burst.raw")
    parser.add_argument("--log", default="/tmp/rpicam_raw_burst.log")
    parser.add_argument("--timeout-s", type=float, default=10.0)
    args = parser.parse_args()

    for path in (args.out, args.log):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    configure_esp(args.esp_delay_us, args.esp_width_us)
    set_trigger_mode(True)
    cmd = [
        "rpicam-raw",
        "-n",
        "--frames", str(args.frames),
        "--mode", args.mode,
        "--shutter", str(args.exposure_us),
        "--gain", "1",
        "--awbgains", "1,1",
        "-o", args.out,
    ]
    t0 = time.monotonic()
    proc = None
    try:
        with open(args.log, "wb") as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            trigger_thread = threading.Thread(
                target=pulse_burst,
                args=(args.frames, args.fps, args.start_delay_s),
                daemon=True,
            )
            trigger_thread.start()
            try:
                proc.wait(timeout=args.timeout_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            trigger_thread.join(timeout=2)
    finally:
        set_trigger_mode(False)
        try:
            with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
                ser.write(b"E0\n")
                ser.flush()
        except Exception as exc:
            print("ESP disable failed:", exc, flush=True)

    elapsed = time.monotonic() - t0
    size = os.path.getsize(args.out) if os.path.exists(args.out) else 0
    print("SUMMARY")
    print(f"returncode={proc.returncode if proc else None}")
    print(f"elapsed_s={elapsed:.3f}")
    print(f"output={args.out}")
    print(f"output_bytes={size}")
    print(f"log={args.log}")
    if os.path.exists(args.log):
        with open(args.log, "r", errors="replace") as f:
            print("LOG_TAIL")
            print("".join(f.readlines()[-40:]))


if __name__ == "__main__":
    main()
