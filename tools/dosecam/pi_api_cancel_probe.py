import json
import threading
import time
import urllib.request


BASE_URL = "http://127.0.0.1:8000"


def post(path, obj, timeout=90):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=timeout).read().decode()


def capture_external():
    try:
        print(post("/api/capture", {"trigger_source": "external", "timeout_s": 30}, timeout=45))
    except Exception as exc:
        print(f"capture exception: {exc}")


def main():
    thread = threading.Thread(target=capture_external)
    thread.start()
    time.sleep(2)
    print(post("/api/capture/cancel", {}))
    thread.join(timeout=10)


if __name__ == "__main__":
    main()
