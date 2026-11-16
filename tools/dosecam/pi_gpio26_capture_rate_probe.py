import argparse
import os
import shutil
import subprocess
import time

from gpiozero import LED
import serial


ESP_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
TRIGGER_MODE = "/sys/module/imx296/parameters/trigger_mode"
OUT_DIR = "/tmp/dose_cam_rate_probe"


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


def pulse_gpio26(width_s=0.001):
    pin = LED(26)
    try:
        pin.on()
        time.sleep(width_s)
        pin.off()
    finally:
        pin.close()


def capture_one(index, arm_delay_s, timeout_s, exposure_us, encoding):
    out = os.path.join(OUT_DIR, f"frame_{index:04d}.{encoding}")
    log = os.path.join(OUT_DIR, f"frame_{index:04d}.log")
    cmd = [
        "rpicam-still",
        "-n",
        "-t", str(int(timeout_s * 1000)),
        "--shutter", str(int(exposure_us)),
        "--gain", "1",
        "--awbgains", "1,1",
        "--immediate",
        "--encoding", encoding,
        "-o", out,
    ]
    t0 = time.monotonic()
    with open(log, "wb") as log_file:
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
        time.sleep(arm_delay_s)
        pulse_gpio26()
        try:
            proc.wait(timeout=timeout_s + 5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    elapsed = time.monotonic() - t0
    size = os.path.getsize(out) if os.path.exists(out) else 0
    ok = proc.returncode == 0 and size > 0
    tail = ""
    if not ok and os.path.exists(log):
        with open(log, "r", errors="replace") as f:
            tail = "".join(f.readlines()[-12:]).strip()
    return {
        "index": index,
        "ok": ok,
        "returncode": proc.returncode,
        "elapsed_s": elapsed,
        "size": size,
        "out": out,
        "tail": tail,
    }


def run_series(frames, arm_delay_s, delay_us, width_us, exposure_us, encoding, timeout_s):
    os.makedirs(OUT_DIR, exist_ok=True)
    configure_esp(delay_us, width_us)
    set_trigger_mode(True)
    results = []
    t0 = time.monotonic()
    try:
        for i in range(frames):
            result = capture_one(i, arm_delay_s, timeout_s, exposure_us, encoding)
            results.append(result)
            status = "OK" if result["ok"] else "FAIL"
            print(
                f"{status} frame={i} elapsed={result['elapsed_s']:.3f}s "
                f"size={result['size']} rc={result['returncode']}",
                flush=True,
            )
            if not result["ok"]:
                print(result["tail"], flush=True)
    finally:
        set_trigger_mode(False)
        try:
            with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
                ser.write(b"E0\n")
                ser.flush()
        except Exception as exc:
            print("ESP disable failed:", exc, flush=True)

    total = time.monotonic() - t0
    ok_count = sum(1 for r in results if r["ok"])
    intervals = [r["elapsed_s"] for r in results if r["ok"]]
    mean = sum(intervals) / len(intervals) if intervals else 0.0
    fps_total = ok_count / total if total > 0 else 0.0
    fps_mean = 1.0 / mean if mean > 0 else 0.0
    print("SUMMARY")
    print(f"frames={frames} ok={ok_count} failed={frames - ok_count}")
    print(f"arm_delay_s={arm_delay_s} esp_delay_us={delay_us} esp_width_us={width_us}")
    print(f"encoding={encoding} exposure_us={exposure_us}")
    print(f"total_elapsed_s={total:.3f}")
    print(f"mean_success_elapsed_s={mean:.3f}")
    print(f"throughput_total_fps={fps_total:.3f}")
    print(f"throughput_mean_fps={fps_mean:.3f}")
    print(f"output_dir={OUT_DIR}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--arm-delay-s", type=float, default=0.5)
    parser.add_argument("--esp-delay-us", type=int, default=5)
    parser.add_argument("--esp-width-us", type=int, default=100)
    parser.add_argument("--exposure-us", type=int, default=100)
    parser.add_argument("--encoding", choices=["png", "jpg"], default="png")
    parser.add_argument("--timeout-s", type=float, default=10)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    if args.clean and os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)

    run_series(
        frames=args.frames,
        arm_delay_s=args.arm_delay_s,
        delay_us=args.esp_delay_us,
        width_us=args.esp_width_us,
        exposure_us=args.exposure_us,
        encoding=args.encoding,
        timeout_s=args.timeout_s,
    )


if __name__ == "__main__":
    main()
