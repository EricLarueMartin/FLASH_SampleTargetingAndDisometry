#!/usr/bin/env bash
set -euo pipefail

base_url="http://127.0.0.1:8000"
base_name='runA\sample1'

post_json() {
  local path="$1"
  local body="$2"
  printf "%s " "$path"
  curl -sS --max-time 30 \
    -H "Content-Type: application/json" \
    -d "$body" \
    "$base_url$path"
  printf "\n"
}

post_json "/api/set_delay" '{"delay_us":5}'
post_json "/api/set_width" '{"width_us":100}'
post_json "/api/active_level" '{"level":0}'
post_json "/api/enable_output" '{}'
post_json "/api/autosave" '{"enabled":true,"base":"runA\\sample1","include_log":true}'
capture_json=$(curl -sS --max-time 45 -H "Content-Type: application/json" -d '{}' "$base_url/api/capture")
echo "/api/capture $capture_json"

curl -sS --max-time 10 "$base_url/api/files" -o /tmp/dose_cam_files.json
python3 - <<'PY'
import json
data = json.load(open("/tmp/dose_cam_files.json"))
print("files", len(data["files"]))
for item in data["files"][:5]:
    print(item["path"], item["size"])
PY

first_path=$(python3 - <<'PY'
import json
data = json.load(open("/tmp/dose_cam_files.json"))
for item in data["files"]:
    if item["path"].startswith("runA/sample1_") and item["path"].endswith(".jpg"):
        print(item["path"])
        break
PY
)

test -n "$first_path"
curl -sS --max-time 10 -G --data-urlencode "path=$first_path" "$base_url/api/files/download" -o /tmp/dose_cam_one_file.jpg
ls -l /tmp/dose_cam_one_file.jpg

curl -sS --max-time 10 -G --data-urlencode "base=$base_name" "$base_url/api/files/download_all" -o /tmp/dose_cam_base_files.zip
unzip -l /tmp/dose_cam_base_files.zip
