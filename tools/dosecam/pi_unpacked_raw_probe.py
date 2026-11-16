import os
import subprocess
import time

import serial

PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
OUT = "/tmp/rpicam_u_test.raw"
LOG = "/tmp/rpicam_u_test.log"


def set_trigger_mode(enabled):
    value = "1" if enabled else "0"
    subprocess.run(
        ["sudo", "sh", "-c", f"echo {value} > /sys/module/imx296/parameters/trigger_mode"],
        check=True,
    )


def configure_esp():
    with serial.Serial(PORT, 115200, timeout=0.5) as ser:
        time.sleep(0.2)
        ser.read(1024)
        for cmd in ("E0", "D5", "W200", "L0", "E1"):
            ser.write((cmd + "\n").encode())
            ser.flush()
            time.sleep(0.05)


def disable_esp():
    with serial.Serial(PORT, 115200, timeout=0.5) as ser:
        time.sleep(0.1)
        ser.write(b"E0\n")
        ser.flush()


def pulse_gpio26():
    subprocess.run(["pinctrl", "set", "26", "op", "dh"], check=True)
    time.sleep(0.001)
    subprocess.run(["pinctrl", "set", "26", "op", "dl"], check=True)


def main():
    for path in (OUT, LOG):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    proc = None
    try:
        set_trigger_mode(True)
        configure_esp()
        cmd = [
            "rpicam-raw",
            "-n",
            "--frames",
            "1",
            "--mode",
            "1456:1088:10:U",
            "--shutter",
            "200",
            "--gain",
            "1",
            "--awbgains",
            "1,1",
            "-o",
            OUT,
        ]
        with open(LOG, "wb") as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)

        time.sleep(1.0)
        pulse_gpio26()
        deadline = time.time() + 5
        while time.time() < deadline:
            if os.path.exists(OUT) and os.path.getsize(OUT):
                break
            time.sleep(0.1)

        if proc.poll() is None:
            proc.terminate()
            time.sleep(0.5)
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)

        size = os.path.getsize(OUT) if os.path.exists(OUT) else 0
        print("return", proc.poll(), "size", size)
        with open(LOG, errors="replace") as f:
            print(f.read()[-1200:])
    finally:
        if proc and proc.poll() is None:
            proc.kill()
        try:
            set_trigger_mode(False)
        except Exception:
            pass
        try:
            disable_esp()
        except Exception:
            pass
        subprocess.run(["pinctrl", "set", "26", "ip", "pn"], check=False)


if __name__ == "__main__":
    main()
