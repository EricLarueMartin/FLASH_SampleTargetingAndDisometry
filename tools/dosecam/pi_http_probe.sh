#!/usr/bin/env bash
set -u

base="http://127.0.0.1:8000"

post_json() {
  path="$1"
  body="$2"
  printf "%s " "$path"
  curl -sS --max-time 10 \
    -H "Content-Type: application/json" \
    -d "$body" \
    "$base$path"
  printf "\n"
}

echo "== home =="
curl -sS --max-time 10 -o /tmp/dose_cam_home.html -w "%{http_code} %{size_download}\n" "$base/"

echo "== esp api =="
post_json "/api/disable_output" "{}"
post_json "/api/set_delay" '{"delay_us":150}'
post_json "/api/set_width" '{"width_us":25}'
post_json "/api/active_level" '{"level":0}'
post_json "/api/enable_output" "{}"

echo "== capture via pi gpio -> esp8266 -> camera trigger =="
curl -sS --max-time 5 \
  -H "Content-Type: application/json" \
  -d '{"exposure_us":0}' \
  "$base/api/capture" || true
printf "\n"
post_json "/api/disable_output" "{}"
