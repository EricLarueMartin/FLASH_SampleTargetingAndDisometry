#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$HOME/bin"
if ! command -v arduino-cli >/dev/null 2>&1; then
  tmp_deb="/tmp/arduino-cli_arm64.deb"
  curl -fsSL \
    https://github.com/arduino/arduino-cli/releases/download/v1.5.1/arduino-cli_1.5.1-1_arm64.deb \
    -o "$tmp_deb"
  sudo apt-get install -y "$tmp_deb"
fi

export PATH="$HOME/bin:$PATH"
arduino-cli version

arduino-cli config init --overwrite
arduino-cli config set board_manager.additional_urls \
  https://arduino.esp8266.com/stable/package_esp8266com_index.json
arduino-cli core update-index
arduino-cli core install esp8266:esp8266
arduino-cli board list
arduino-cli board listall huzzah
