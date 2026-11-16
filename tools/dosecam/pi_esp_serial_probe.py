import time

import serial

PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"


def send(ser, cmd, wait=0.2):
    ser.write((cmd + "\n").encode())
    ser.flush()
    time.sleep(wait)
    reply = ser.read(1024).decode(errors="replace").strip()
    print(f"{cmd} -> {reply or '<no reply>'}")


with serial.Serial(PORT, 115200, timeout=0.5) as ser:
    time.sleep(2.0)
    boot = ser.read(2048).decode(errors="replace").strip()
    print("boot:", boot or "<no boot text>")
    for cmd in ["?", "E0", "D5", "W10000", "L0", "E1", "T", "?", "E0"]:
        send(ser, cmd)
