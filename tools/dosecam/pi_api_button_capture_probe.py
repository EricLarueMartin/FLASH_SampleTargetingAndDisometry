import json
import urllib.request


BASE_URL = "http://127.0.0.1:8000"


def post(path, obj, timeout=60):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=timeout).read().decode()


def main():
    print(post("/api/set_delay", {"delay_us": 5}))
    print(post("/api/set_width", {"width_us": 100}))
    print(post("/api/active_level", {"level": 0}))
    print(post("/api/autosave", {"enabled": True, "base": "button/pngtest", "include_log": True}))
    print(post("/api/capture", {"trigger_source": "pi_test_png", "timeout_s": 20}))


if __name__ == "__main__":
    main()
