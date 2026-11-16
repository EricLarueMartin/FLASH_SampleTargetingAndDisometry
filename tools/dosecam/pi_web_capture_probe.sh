#!/usr/bin/env bash
set -euo pipefail

base="http://127.0.0.1:8000"

post_json() {
  local path="$1"
  local body="$2"
  printf "%s " "$path"
  curl -sS --max-time 30 \
    -H "Content-Type: application/json" \
    -d "$body" \
    "$base$path"
  printf "\n"
}

curl -sS --max-time 10 -o /tmp/dose_cam_web_home.html -w "home %{http_code} %{size_download}\n" "$base/"
post_json "/api/set_delay" '{"delay_us":5}'
post_json "/api/set_width" '{"width_us":100}'
post_json "/api/active_level" '{"level":0}'
post_json "/api/enable_output" '{}'
post_json "/api/autosave" '{"enabled":true,"base":"webtest","include_log":false}'
post_json "/api/capture" '{}'
curl -sS --max-time 10 -o /tmp/dose_cam_web_preview.jpg -w "preview %{http_code} %{size_download}\n" "$base/api/preview.jpg"
ls -l /tmp/dose_cam_web_preview.jpg
find /home/codex/SynchronizedCameraDosimeter/dose_cam/captures -maxdepth 1 -type f -name 'webtest_*.jpg' -printf '%f %s\n' | tail -5
