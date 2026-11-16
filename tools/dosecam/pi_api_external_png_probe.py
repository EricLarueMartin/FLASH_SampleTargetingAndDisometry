import json
import threading
import time
import urllib.request

from gpiozero import LED


BASE_URL = "http://127.0.0.1:8000"


def post(path, obj, timeout=90):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=timeout).read().decode()


def pulse_external_test_input(delay_s=3.0):
    time.sleep(delay_s)
    pin = LED(26)
    try:
        pin.on()
        time.sleep(0.001)
        pin.off()
    finally:
        pin.close()
    print("external test pulse sent on GPIO26")


def main():
    print(post("/api/set_delay", {"delay_us": 5}))
    print(post("/api/set_width", {"width_us": 100}))
    print(post("/api/active_level", {"level": 0}))
    print(post(
        "/api/autosave",
        {"enabled": True, "base": "external/pngtest", "include_log": True},
    ))

    trigger = threading.Thread(target=pulse_external_test_input, daemon=True)
    trigger.start()
    print(post("/api/capture", {"trigger_source": "external", "timeout_s": 20}, timeout=40))
    trigger.join(timeout=1)


if __name__ == "__main__":
    main()
