import threading
import time
import os

from gpiozero import Button, LED
import serial

ESP_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
PI_TRIGGER_GPIO = 26
PI_MONITOR_GPIO = 16


def send(ser, cmd, wait=0.15):
    ser.write((cmd + "\n").encode())
    ser.flush()
    time.sleep(wait)
    reply = ser.read(1024).decode(errors="replace").strip()
    print(f"{cmd} -> {reply or '<no reply>'}")


def pulse_pi_trigger(width_s=0.001, wait_s=0.25):
    time.sleep(wait_s)
    pin = LED(PI_TRIGGER_GPIO)
    pin.on()
    time.sleep(width_s)
    pin.off()


def capture_monitor_edges(timeout_s=2.0):
    events = []
    monitor = Button(PI_MONITOR_GPIO, pull_up=False, bounce_time=None)

    def rising():
        events.append(("rising", time.monotonic()))
        print(f"monitor edge: rising {events[-1][1]:.9f}")

    def falling():
        events.append(("falling", time.monotonic()))
        print(f"monitor edge: falling {events[-1][1]:.9f}")

    monitor.when_pressed = rising
    monitor.when_released = falling

    worker = threading.Thread(target=pulse_pi_trigger, daemon=True)
    worker.start()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and len(events) < 2:
        time.sleep(0.001)

    monitor.close()
    return events


def main():
    width_us = int(os.environ.get("WIDTH_US", "10000"))
    delay_us = int(os.environ.get("DELAY_US", "5"))
    try:
        with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
            time.sleep(2.0)
            ser.read(2048)
            for cmd in ["E0", f"D{delay_us}", f"W{width_us}", "L0", "E1", "?"]:
                send(ser, cmd)

        events = capture_monitor_edges()

        if len(events) >= 2:
            width_us = (events[1][1] - events[0][1]) * 1_000_000.0
            print(f"observed monitor pulse width: {width_us:.1f} us")
        else:
            print(f"observed {len(events)} monitor edges; expected 2")
            raise SystemExit(1)
    finally:
        with serial.Serial(ESP_PORT, 115200, timeout=0.5) as ser:
            send(ser, "E0")


if __name__ == "__main__":
    main()
