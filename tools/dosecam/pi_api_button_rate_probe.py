import argparse
import json
import time
import urllib.request


BASE_URL = "http://127.0.0.1:8000"


def post(path, obj, timeout=60):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=10)
    args = parser.parse_args()

    print(post("/api/set_delay", {"delay_us": 5}))
    print(post("/api/set_width", {"width_us": 100}))
    print(post("/api/active_level", {"level": 0}))
    print(post("/api/autosave", {"enabled": False, "base": "rate/api", "include_log": False}))

    results = []
    t0 = time.monotonic()
    for i in range(args.frames):
        f0 = time.monotonic()
        try:
            result = post("/api/capture", {"trigger_source": "pi_test_png", "timeout_s": 20}, timeout=60)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        elapsed = time.monotonic() - f0
        results.append((elapsed, result))
        print(f"{'OK' if result.get('ok') else 'FAIL'} frame={i} elapsed={elapsed:.3f}s {result}", flush=True)

    total = time.monotonic() - t0
    ok_count = sum(1 for _, r in results if r.get("ok"))
    ok_elapsed = [elapsed for elapsed, r in results if r.get("ok")]
    mean = sum(ok_elapsed) / len(ok_elapsed) if ok_elapsed else 0
    print("SUMMARY")
    print(f"frames={args.frames} ok={ok_count} failed={args.frames - ok_count}")
    print(f"total_elapsed_s={total:.3f}")
    print(f"mean_success_elapsed_s={mean:.3f}")
    print(f"throughput_total_fps={ok_count / total if total else 0:.3f}")
    print(f"throughput_mean_fps={1 / mean if mean else 0:.3f}")


if __name__ == "__main__":
    main()
