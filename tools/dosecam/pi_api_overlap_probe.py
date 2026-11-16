import json
import threading
import time
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000"


def post(path, obj, timeout=90):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        return urllib.request.urlopen(req, timeout=timeout).read().decode()
    except urllib.error.HTTPError as exc:
        return exc.read().decode()


def capture_external():
    print("first:", post("/api/capture", {"trigger_source": "external", "timeout_s": 30}, timeout=45))


def main():
    thread = threading.Thread(target=capture_external)
    thread.start()
    time.sleep(1)
    print("second:", post("/api/capture", {"trigger_source": "external", "timeout_s": 30}, timeout=5))
    print("cancel:", post("/api/capture/cancel", {}))
    thread.join(timeout=10)


if __name__ == "__main__":
    main()
