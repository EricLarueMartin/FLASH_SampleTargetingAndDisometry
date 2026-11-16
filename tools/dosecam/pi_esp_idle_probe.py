import time

from gpiozero import Button
import serial

ESP_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
PI_MONITOR_GPIO = 16


def send(ser, cmd, wait=0.15):
    ser.write((cmd + "\n").encode())
    ser.flush()
    time.sleep(wait)
    print(f"{cmd} -> {ser.read(1024).decode(errors='replace').strip() or '<no reply>'}")


with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
    time.sleep(2)
    ser.read(2048)
    for cmd in ["L0", "E0", "?"]:
        send(ser, cmd)

monitor = Button(PI_MONITOR_GPIO, pull_up=False, bounce_time=None)
time.sleep(0.1)
print(f"GPIO{PI_MONITOR_GPIO} monitor is_pressed={monitor.is_pressed}")
monitor.close()
