import json
import os
import urllib.request


BASE_URL = "http://127.0.0.1:8000"
CAPTURE_ROOT = "/home/codex/SynchronizedCameraDosimeter/dose_cam/captures"


def post(path, obj, timeout=30):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        return urllib.request.urlopen(req, timeout=timeout).read().decode()
    except Exception as exc:
        if hasattr(exc, "read"):
            return exc.read().decode()
        raise


def main():
    probe_dir = os.path.join(CAPTURE_ROOT, "delete_probe")
    probe_file = os.path.join(probe_dir, "subdir", "test.txt")
    os.makedirs(os.path.dirname(probe_file), exist_ok=True)
    with open(probe_file, "w", encoding="ascii") as f:
        f.write("test")

    print(post("/api/files/delete", {"path": "delete_probe/subdir/test.txt", "type": "file"}))
    print("file_exists_after_delete=", os.path.exists(probe_file))

    with open(probe_file, "w", encoding="ascii") as f:
        f.write("test")
    print(post("/api/files/delete", {"path": "delete_probe", "type": "directory"}))
    print("dir_exists_after_delete=", os.path.exists(probe_dir))

    print(post("/api/files/delete", {"path": "", "type": "directory"}))


if __name__ == "__main__":
    main()
