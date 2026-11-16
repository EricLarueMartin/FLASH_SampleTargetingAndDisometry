> **Moved (2026-11-16):** this guide now lives in the combined repository `FLASH_SampleTargetingAndDisometry`. Paths below such as `DDG/`, `tools/`, `deploy/` refer to the old `SynchronizedCameraDosimeter` layout; see the top-level `README.md` for where each now lives. The install path on the Pi is unchanged.

# Synchronized Camera Dosimeter

Scintillation-light camera dosimetry system for the Duke FELL FLASH experiment. The architecture uses a control computer, an external-trigger camera, and a delayed shutter pulse generator. The current prototype uses a Raspberry Pi 5, an InnoMaker GS Camera Module for Raspberry Pi with IMX296 mono sensor and external trigger support, and an Adafruit Feather HUZZAH ESP8266 to generate the delayed camera shutter signal.

This repository is expected to be used by multiple people and multiple AI assistants. Keep `README.md` current for stable operator/developer information, and use `AGENT.md` for detailed handoff notes and change history.

## Purpose

The goal is to measure dose-related scintillation light from samples placed near the spectrometer area after the first acceleration stage, around 30 MeV electron energy. The important requirement is synchronization to accelerator timing: the camera should be armed first, then each external timing pulse should produce one camera exposure.

The expected experiment trigger is the laser charging/timing signal that arrives some microseconds before RF power is applied. The current bench trigger path uses Raspberry Pi GPIO26 as a test pulse into the same ESP8266/camera trigger chain.

## Hardware Setup

Set up and verify the physical system before installing or changing software.

Hardware architecture:

- Control computer. Prototype: Raspberry Pi 5 with Raspberry Pi OS. A Pi 4 or similar Linux single-board computer should also be workable if it supports the camera stack, GPIO, serial, and storage throughput.
- External-trigger camera. Prototype: InnoMaker GS Camera Module for Raspberry Pi with IMX296 mono sensor and external trigger support.
- Lens. Prototype: manual-focus/manual-zoom lens.
- Delayed shutter pulse generator. Prototype: Adafruit Feather HUZZAH ESP8266. An ESP32 or other microcontroller/timing device should also be workable if it can accept a timing input, apply a programmable delay, and generate a programmable-width camera shutter pulse.
- USB cable from the control computer to the pulse generator for power and serial control.
- Camera trigger cable pair.
- Jumper wires for the prototype Pi GPIO26 to ESP8266 GPIO12 test trigger and ESP8266 GPIO15 to Pi GPIO16 monitor.

The pulse generator is not merely copying the input pulse after a delay. It accepts an input edge, waits the configured delay, then generates a new camera shutter pulse with its own configured width.

Camera identity expected by the current software:

- Camera detected as `imx296 [1456x1088 10-bit MONO]`.
- Sensor dimensions: `1456 x 1088`.
- Raw stream mode used by the app: `1456:1088:10:U`.
- Raw stream row stride: `2944` bytes.
- Raw stream frame size: `3,203,072` bytes.

Current prototype ESP8266 wiring:

- ESP8266 GPIO12: input from Raspberry Pi GPIO26 test trigger.
- ESP8266 GPIO13: camera trigger output to camera `Trig+` / `XTR`.
- ESP8266 GPIO14: optoisolated laser charging/timing input. The current optoisolator inverts the positive source pulse, so configure the ESP input as active LOW/falling-edge.
- ESP8266 GPIO15: monitor/test output to Raspberry Pi GPIO16.
- ESP8266 ground: connected to optoisolator J2 pin 1 (`GND2`). Camera J3 `Trig-` returns separately to Raspberry Pi physical pin 39 ground.
- ESP8266 USB: connected to the Pi for power and serial control.

Physical wire positions as last confirmed on 2026-09-15:

- On the short Feather header, counting from the battery-connector end: three empty pins, white optoisolator signal wire from J2 pin 2 on GPIO14, brown/white wire on GPIO12, white wire on GPIO13 to camera `Trig+` / `XTR`, then green/white wire on GPIO15.
- On the other Feather header, counting from the USB-connector end: reset pin empty, grey optoisolator VCC wire from J2 pin 3 on 3V3, one NC pin empty, then black optoisolator J2 pin 1 ground wire on GND.
- On the Raspberry Pi GPIO header, viewed from above with the USB/Ethernet connectors at the right: the even-pin row is away from the PCB and the odd-pin row is next to the PCB. On the odd/PCB row, pin 39 is the black camera `Trig-` ground and pin 37 / GPIO26 is brown/white to ESP GPIO12. On the even/outer row, pin 36 / GPIO16 is green/white from ESP GPIO15.
- On the camera, viewed from the back/component side with the ribbon cable pointing down, use J3 for the external shutter trigger; J2 is the strobe header. The white wire is J3 `Trig+` / `XTR`. The black wire is J3 `Trig-` / ground, is closest to the camera PCB edge, and returns to Raspberry Pi physical pin 39 ground.

Pi GPIO behavior:

- GPIO26 is a bench/test trigger input into the ESP8266, not a separate camera trigger source.
- GPIO26 idles low with pulldown and sends a low-high-low pulse.
- GPIO16 can monitor the ESP8266 output path during bench tests.
- The optoisolated laser-input path was bench-verified on 2026-08-26 using Analog Discovery 2 W2. A 100 us positive W2 pulse at the AD2's 5.0 V maximum triggered the active-low ESP GPIO14 input, produced a GPIO15/Pi GPIO16 monitor pulse, and produced one camera frame per separately armed trial. The AD2 cannot generate the originally proposed 5.5 V level; its reported W1/W2 amplitude maximum is 5.0 V.
- The corrected J2 wiring was re-verified on 2026-09-15: J2 pin 2 white to ESP GPIO14, J2 pin 3 grey to ESP 3V3, and J2 pin 1 black to ESP ground. One 4.999 V, 100 us W2 pulse produced one camera frame and one GPIO16 monitor pulse measuring about 898.8 us for a configured 1000 us ESP gate.

Camera trigger behavior:

- The camera is always triggered through its external trigger input.
- The ESP8266 camera output is fixed active low.
- ESP8266 input trigger polarity is configurable from the Options tab. Active high means rising edge triggers the delay; active low means falling edge triggers it.

Reference links:

- Camera purchase candidate: `https://www.amazon.com/dp/B093BY2TK2`.
- Lens purchase candidate: `https://www.amazon.com/dp/B08PYMBX9T`.
- Camera manual in repo: `ComponentManuals/CAM-IMX296RAW-UserManual-V2.0.pdf`.
- Raspberry Pi external trigger documentation: `https://www.raspberrypi.com/documentation/accessories/camera.html#external-trigger-on-the-global-shutter-camera`.
- Raspberry Pi Global Shutter Camera product page: `https://www.raspberrypi.com/products/raspberry-pi-global-shutter-camera/`.

## Software Installation

These instructions assume the hardware above is connected. Paths below use the existing deployment convention:

```text
/home/codex/SynchronizedCameraDosimeter
```

Use a different username/path only if you also update `deploy/systemd/dose-cam.service`.

### Option A: AI-Assisted Install

Give an AI/coding agent SSH access to the Pi and this repository, then ask it to:

1. Read `README.md` and `AGENT.md`.
2. Confirm the hardware is visible:

   ```bash
   rpicam-hello --list-cameras
   ls -l /dev/serial/by-id/
   cat /sys/module/imx296/parameters/trigger_mode
   ```

3. Install the required OS packages from the manual install section.
4. Put the repository at `/home/codex/SynchronizedCameraDosimeter`.
5. Create `/home/codex/SynchronizedCameraDosimeter/dose_cam/captures/default`.
6. Install and start the systemd/nginx service files from `deploy/`.
7. Flash or verify the ESP8266 firmware in `DDG/DDG.ino`.
8. Run the verification commands in the bench-test section.
9. Update `AGENT.md` with exact commands, observed IP address, service state, ESP status, and any deviations.

Do not let the AI connect facility timing signals or change accelerator controls. Facility-side trigger wiring and signal conditioning require local approval.

### Option B: Manual Install

#### 1. Prepare The Pi

Install OS packages:

```bash
sudo apt update
sudo apt install -y git nginx python3-flask python3-serial python3-gpiozero python3-numpy python3-pil python3-picamera2 python3-tifffile rpicam-apps
```

Confirm the camera is detected:

```bash
rpicam-hello --list-cameras
```

Expected camera identity is an IMX296 mono sensor with 1456 x 1088 resolution.

Confirm the external-trigger kernel control exists:

```bash
cat /sys/module/imx296/parameters/trigger_mode
```

The app sets this to `1` while armed and restores it to `0` afterward.

#### 2. Put The Code On The Pi

If the repo is already in the `codex` home directory:

```bash
cd /home/codex/SynchronizedCameraDosimeter
```

For a fresh clone after this project is pushed to GitHub:

```bash
cd /home/codex
git clone https://github.com/EricLarueMartin/SynchronizedCameraDosimeter.git
cd SynchronizedCameraDosimeter
```

Create the capture directory:

```bash
mkdir -p /home/codex/SynchronizedCameraDosimeter/dose_cam/captures/default
```

#### 3. Install The Web Service

Install the systemd service and nginx site from the repo templates:

```bash
sudo cp deploy/systemd/dose-cam.service /etc/systemd/system/dose-cam.service
sudo cp deploy/nginx/dose-cam /etc/nginx/sites-available/dose-cam
sudo ln -sf /etc/nginx/sites-available/dose-cam /etc/nginx/sites-enabled/dose-cam
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl daemon-reload
sudo systemctl enable dose-cam.service nginx.service
sudo systemctl restart dose-cam.service nginx.service
```

Check service status:

```bash
systemctl is-active dose-cam.service nginx.service
ss -ltnp | grep -E ':80|:8000|:22'
```

Expected result:

- `dose-cam.service` active.
- `nginx.service` active.
- nginx listening on port `80`.
- Flask/Python listening on port `8000`.

#### 4. Program The ESP8266 Firmware

The firmware is in:

```text
DDG/DDG.ino
```

The prototype Pi previously used Arduino CLI plus ESP8266 core to flash the Feather HUZZAH over USB. The helper script is:

```bash
tools/pi_install_arduino_cli.sh
```

After the toolchain is installed, compile/upload the sketch for the prototype Adafruit Feather HUZZAH ESP8266 over the CP2104 USB serial adapter. The expected serial device is:

```text
/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0
```

Fallback device:

```text
/dev/ttyUSB0
```

Verify the ESP answers status commands:

```bash
python3 tools/pi_esp_serial_probe.py
```

The status line should include fields like `enabled`, `armed`, `delay_us`, `width_us`, `input_active_level`, and `camera_active_level=LOW`.

#### 5. Bench-Test Before Beamline Use

Verify the Pi-to-ESP monitor loop:

```bash
python3 tools/pi_esp_gpio_loop_probe.py
```

Verify camera detection and basic dependencies:

```bash
bash tools/pi_probe.sh
```

With the camera and ESP trigger wiring connected, open the web UI and do a targeting capture:

1. Open `http://<pi-host-or-ip>/`.
2. Set Capture mode to `Targeting`.
3. Use a wide targeting gate, for example `1000 us`.
4. Press `Capture`.
5. Confirm the preview updates and frame stats appear.

For raw acquisition testing:

1. Set Save base, normally `default/run`.
2. Set Max frames.
3. Press `Arm`.
4. Wait until status says `Armed`.
5. In Targeting mode, `Capture` sends a test trigger and updates preview.
6. In Dosimetry mode while armed, `Capture` sends one test trigger without refreshing the preview, allowing repeated test triggers into the same run.
7. Press `Stop / Finalize`.
8. Check the Files tab for `.raw` and `.json` output.

## Timing Model

Normal timing chain:

1. Pi test pulse or laser charging/timing pulse reaches the ESP8266 input.
2. ESP8266 waits the configured delay.
3. ESP8266 drives the camera trigger output active low.
4. Camera exposes during the external trigger gate.
5. Raw frame is written by the running `rpicam-raw` acquisition process.

The Raspberry Pi IMX296 external-trigger documentation says exposure is controlled by the XTR low pulse width plus about `14.26 us`. Raspberry Pi's product page lists practical exposure times as low as `30 us`, so the application enforces a conservative minimum gate width of `30 us`.

Timing controls:

- Delay: shared ESP delay from input trigger edge to camera shutter pulse.
- Targeting gate width: wide camera trigger pulse for aiming/focusing/targeting images.
- Dosimetry gate width: tighter camera trigger pulse for beam/scintillation data.
- Minimum gate width: `30 us`, enforced in the HTML, browser JavaScript, Flask API, and backend acquisition logic.

## Web UI

The live app is served by Flask behind nginx. The UI has three tabs.

The UI uses browser storage only to remember convenience settings such as rotation, preview drag mode, delete confirmation, and targeting/dosimetry gate widths. Browser storage is optional: if Firefox or a locked-down control-room profile refuses `localStorage`, Capture and Arm should still work, but those convenience settings may reset on page reload.

Capture tab:

- `Save base`: base name for saved acquisition files. Defaults to `default/run`, placing routine captures in the `default` subdirectory. May include subdirectories using `/` or `\`; paths are normalized under `dose_cam/captures/`. The folder icon opens a directory picker restricted to the capture save root and its subdirectories; choosing a folder sets the base to `<folder>/run`.
- `Capture mode`: `Targeting`, `Dosimetry`, or `Focusing (live video)`. Targeting and Dosimetry choose the corresponding gate-width profile. Selecting Focusing automatically disables external-trigger mode and starts a free-running 12 fps MJPEG preview, using the Targeting gate-width value as the video frame shutter time; selecting either acquisition mode stops it. Focusing mode displays a contrast-normalized edge-detail score, the best score seen in the current session, and a relative meter; adjust the lens to maximize the score, then move back toward the recorded peak if the score falls.
- `Max frames`: max frames for an armed run. The raw acquisition process is launched with no app timeout, so sparse external triggers should continue until this count is reached or `Stop / Finalize` is pressed.
- `Expected max rate (fps)`: intended external trigger rate, typically up to 50 fps.
- `Save rpicam log`: include the `rpicam-raw` log file. This defaults off to reduce routine file clutter.
- `Arm`: starts a background externally triggered raw acquisition and waits for external pulses.
- `Capture`: in Targeting mode, sends one Pi GPIO26 test trigger through the ESP/camera trigger path and updates the preview. In Dosimetry mode while armed, sends one test trigger into the active acquisition without changing the displayed preview, so repeated clicks can test multi-frame capture.
- `Update Image`: refreshes the preview from the newest complete raw frame without sending a trigger.
- `Stop / Finalize`: stops the active acquisition.
- `Download Run Files`: zips/downloads files matching the current save base.

Files tab:

- Browse saved files under `dose_cam/captures/`.
- Enter and leave folders like a normal file explorer.
- Download individual files.
- Download a `.raw` file as a PNG ZIP: one autoscaled PNG per complete frame, plus the matching metadata JSON when present. This is a convenience export only; use the `.raw` data for quantitative dosimetry.
- Open a saved `.raw` file in the built-in frame viewer and inspect frames with First/Previous/specific-frame/Next/Last controls, zoom-window dragging, and raw DN statistics shown beside the image.
- Open `.json`, `.log`, and `.txt` files in the built-in text viewer.
- Download a directory as a ZIP.
- Download a directory as a PNG ZIP; each `.raw` stream becomes its own subdirectory in the archive, with the matching metadata JSON included when present.
- Delete files or folders.
- `Confirm before delete` is checked by default; uncheck it for rapid cleanup. Backend path-safety checks still prevent deleting outside the capture root or deleting the capture root itself.

Options tab:

- `Image rotation`: rotates browser preview/export images only. Saved raw data stays in sensor coordinates.
- `Preview drag action`: choose zoom-window dragging or native browser image dragging.
- `Delay (us)`: ESP delay before the camera trigger pulse.
- `Targeting gate width (us)`: targeting profile, minimum `30 us`.
- `Dosimetry gate width (us)`: dosimetry profile, minimum `30 us`.
- Timing values are programmed automatically before Arm and Capture. There are no separate timing apply buttons.
- `Shutter output enabled`: when enabled, ESP trigger inputs generate delayed camera shutter output. Capture and Arm enable this for normal operation.
- `Input trigger active high`: ESP input polarity; loaded from the ESP status on page load.

### Wi-Fi and phone focusing

Options → Wi-Fi supports two mutually exclusive modes on `wlan0`:

- **Host Wi-Fi access point:** enter a hotspot network name (SSID), an 8–63 character password, and a private IPv4 address. The default is `DoseCam` at `192.168.50.1`; a /24 subnet and automatic phone address assignment are used. Connect your phone to that network, keep the connection when it reports no Internet, and open `http://192.168.50.1/`. Select Focusing under Capture.
- **Connect to another Wi-Fi:** enter a personal WPA/WPA2 network's SSID and password. Its DHCP server assigns the Pi's address, which is displayed with a camera-page link. Enterprise authentication and captive portals are not handled by these controls.
- Switch either active mode off to disable the Wi-Fi radio. Apply buttons save and activate the corresponding mode. Only the selected DoseCam profile autoconnects on subsequent boots. Ethernet retains priority.
- Leave a password blank to reuse the saved password for the same SSID. Passwords are stored by NetworkManager and never returned by the status API or saved in browser storage. A failed network join attempts to restore the previous DoseCam connection.
- Changing the hotspot name/password/IP or mode can disconnect the phone; reconnect using the new settings. The hotspot name is its SSID, not the Pi's system hostname (`pi-06-ioc`).

Deployment requires NetworkManager, `dnsmasq-base`, and `nftables`, plus permission for the service account to execute `sudo -n nmcli` (the current Pi account already has this permission). Install `deploy/dosecam-wifi.nft` as `/etc/dosecam-wifi.nft` and `deploy/systemd/dosecam-wifi-isolation.service` into `/etc/systemd/system/`, then run `sudo systemctl daemon-reload` and `sudo systemctl enable --now dosecam-wifi-isolation.service` before enabling a hotspot. This dedicated firewall table blocks forwarding between Wi-Fi and other networks while allowing access to services on the Pi. It does not replace other firewall tables.

The controller owns only `dosecam-hotspot` and `dosecam-client` profiles and leaves other saved profiles intact. `/api/wifi` supports GET status and JSON POST mode/settings changes; changes run asynchronously, and status reports progress and errors. NetworkManager provides DHCP for its [shared IPv4 mode](https://www.networkmanager.dev/docs/api/1.46.0/nm-settings-nmcli.html); the isolation service blocks the forwarding that this mode otherwise enables.

## Preview And Dosimetry Values

The browser preview is autoscaled for visibility. It maps each frame's 0.5th to 99.5th percentile range into an 8-bit JPEG preview. Therefore, a short dosimetry gate can look visually similar to a long targeting gate even when the raw counts are much lower.

Saved `.raw` data is not autoscaled. It contains decoded 10-bit DN values in the valid range `0-1023`.

The Capture tab displays linear raw-frame statistics from the latest decoded frame:

- Brightest pixel DN and coordinates.
- Mean DN.
- Median DN.
- 99.9th percentile DN.
- 99th percentile DN.
- Valid range.

Use these stats, not the visual brightness of the autoscaled preview, for quick dosimetry sanity checks. The displayed footnote derives the valid DN range from the active raw camera mode bit depth, currently `0-1023` for 10-bit mode.

## Data Files

ZIP buttons prepare an archive on the Pi's disk before downloading. A shared progress panel shows bytes processed, percentage, current file, file count, and elapsed time, with Cancel compression. When compression finishes the download starts automatically; Download ZIP remains available for retry. Preparation uses DEFLATE level 6, bounded working memory, and ZIP64. Only one preparation runs at a time. Completed temporary archives in `/var/tmp/dosecam-exports` are retained for retry and cleaned after 24 hours when another export starts; cancelled/failed partial archives are removed. Refreshing the browser resumes progress checks where browser storage is available; restarting the web service requires preparing again. RAW ZIPs preserve original files; PNG ZIPs contain display exports. Finalize acquisition before preparing an archive. Older direct ZIP URLs remain available as streaming endpoints.

Saved files are rooted at:

```text
/home/codex/SynchronizedCameraDosimeter/dose_cam/captures/
```

Current high-rate acquisition writes:

- `.raw`: unpacked `R16` raw stream frames.
- `.json`: metadata including raw mode, frame counts, capture mode, delay, and external trigger gate width.
- `.log`: optional `rpicam-raw` log.

The Files tab can view saved `.raw` streams frame by frame and export complete raw streams as PNG ZIP files. These displayed/exported PNG images use the same autoscaling idea as the browser preview so they are easy to inspect visually, but they are not the linear dosimetry data. The frame viewer's numeric statistics are computed from the decoded raw DN values.

To reduce SD-card wear, acquisition spools raw video to RAM under `/dev/shm/dose_cam` when the requested maximum frame count fits with safety headroom. On finalize, the raw file is moved into the normal capture directory and metadata is written. If the requested run is too large for available RAM, acquisition falls back to direct disk capture rather than risking a full RAM filesystem.

Raw stream constants:

- Width: `1456`.
- Height: `1088`.
- Mode: `1456:1088:10:U`.
- Stride: `2944` bytes per row.
- Frame bytes: `3,203,072`.
- DN valid range after decoding: `0-1023`.
- Raw stream samples may be left-shifted in the 16-bit container; the decoder shifts values down to the active 10-bit range before computing previews/statistics.

## Services

Systemd service:

```text
/etc/systemd/system/dose-cam.service
```

Service behavior:

- Runs as user/group `codex`.
- Working directory: `/home/codex/SynchronizedCameraDosimeter/dose_cam`.
- Command: `/usr/bin/python3 /home/codex/SynchronizedCameraDosimeter/dose_cam/dose_cam.py`.
- Starts after `network-online.target`.
- Restarts on failure.

Nginx site:

```text
/etc/nginx/sites-available/dose-cam
/etc/nginx/sites-enabled/dose-cam
```

Nginx listens on port `80` and proxies to Flask on `127.0.0.1:8000`.

Useful status commands on the Pi:

```bash
systemctl is-active dose-cam.service nginx.service
systemctl status dose-cam.service --no-pager -l
ss -ltnp | grep -E ':80|:8000|:22'
cat /sys/module/imx296/parameters/trigger_mode
pinctrl get 26
```

Useful maintenance commands:

```bash
sudo systemctl restart dose-cam.service
sudo journalctl -u dose-cam.service -n 100 --no-pager
curl -s http://127.0.0.1/api/esp_status
curl -s http://127.0.0.1/api/acquisition/status
```

## Current Access

The Raspberry Pi hostname is `pi-06-ioc`.

Known network states:

- Original Duke/FELL network address observed earlier: `10.236.58.53/24`, DHCP.
- Control-system network address observed on 2026-07-23: `192.168.16.62/24`, DHCP, default route via `192.168.16.132`.
- Web UI directly, when reachable on the same network: `http://pi-06-ioc.fel.duke.edu/` or the current IP.
- Web UI through the current SSH tunnel: `http://127.0.0.1:8080/`.

Tunnel command used from a machine that can reach `daffy.fel.duke.edu`:

```bash
ssh -N -L 2222:192.168.16.62:22 -L 8080:192.168.16.62:80 test@daffy.fel.duke.edu
```

After that tunnel is running:

- SSH maintenance path: `codex@127.0.0.1 -p 2222`.
- Automated maintenance from the current Windows workstation uses the local identity file `~/.ssh/shv_bias_filter_agent_ed25519` for the `codex` account. The filename is historical but this is the key authorized on `pi-06-ioc`; `flash_agent_ed25519` is not authorized there.
- Web UI path: `http://127.0.0.1:8080/`.

Do not rely on `.local` or the old IP after moving networks.

## Repository Status

This working tree has a GitHub remote configured:

```text
https://github.com/EricLarueMartin/SynchronizedCameraDosimeter
```

As of 2026-07-27, the repository has an initial `main` commit prepared for GitHub. Runtime captures, preview images, raw data, logs, and Python cache files are intentionally excluded by `.gitignore`.

## Firmware

Prototype ESP8266 firmware lives in:

```text
DDG/DDG.ino
```

Current firmware behavior:

- GPIO12 and GPIO14 are trigger inputs.
- GPIO13 is fixed active-low camera trigger output.
- GPIO15 is monitor output.
- Input trigger polarity is configurable.
- Default input trigger polarity is active high.
- Serial status command reports enabled state, armed state, delay, width, input active level, and camera active level.

Common ESP serial commands:

- `S`: status.
- `D<us>`: set delay.
- `W<us>`: set camera trigger width.
- `E1`: enable camera output.
- `E0`: disable camera output.
- `L1`: input trigger active high.
- `L0`: input trigger active low.
- `T`: software trigger.

## API Notes

Important routes:

- `GET /`: web UI.
- `GET /api/esp_status`: query ESP status over serial.
- `POST /api/set_delay`: set ESP delay.
- `POST /api/set_width`: set ESP gate width; clamps below `30 us`.
- `POST /api/enable_output`: enable ESP shutter output.
- `POST /api/disable_output`: disable ESP shutter output.
- `POST /api/input_trigger_level`: set ESP input polarity.
- `POST /api/acquisition/start`: arm externally triggered raw acquisition.
- `GET /api/acquisition/status`: acquisition status.
- `POST /api/acquisition/stop`: stop/finalize acquisition.
- `POST /api/acquisition/capture_preview`: send one GPIO26 test trigger and update preview.
- `POST /api/acquisition/update_preview`: update preview from newest complete raw frame.
- `GET /api/preview.jpg`: current autoscaled preview image.
- `POST /api/focus/start`, `GET /api/focus/status`, `POST /api/focus/stop`: control the free-running focus preview.
- `GET /api/focus/stream.mjpg`: live MJPEG focus stream used by the Capture tab.
- `GET /api/files`: list saved files/folders.
- `GET /api/files/download`: download one file.
- `GET /api/files/download_dir`: download a folder as ZIP.
- `POST /api/files/delete`: delete a file or folder under the capture root.
- `POST /api/files/mkdir`: create a folder under the capture root.

## Operating Workflow

For targeting:

1. Open the web UI.
2. Set Capture mode to `Targeting`.
3. Use a wide targeting gate width in Options.
4. Press `Capture` to generate a GPIO26 test trigger and update the preview.
5. Adjust the physical lens focus/zoom manually.
6. Use preview zoom if useful.

For dosimetry:

1. Set Capture mode to `Dosimetry`.
2. Set the dosimetry gate width, no lower than `30 us`.
3. Set the delay based on laser charging signal to RF/scintillation timing.
4. Set save base and max frames.
5. Press `Arm`.
6. Let external laser/timing pulses arrive.
7. Watch frame count and linear DN stats.
8. Press `Stop / Finalize` when done.
9. Download files from the Files tab or `Download Run Files`.

## Current Known Limitations

- The preview is autoscaled, so visual brightness is not linear.
- The brightest-pixel and frame-stat display is linear, but it is only a quick diagnostic; calibration is still required for dosimetry.
- The system has been bench-tested through GPIO26 and through the optoisolated GPIO14 laser-input path. Facility timing amplitude, pulse width, impedance, and final connection still require confirmation before accelerator use.
- The camera trigger input is 1.8 V class per Raspberry Pi documentation. Use appropriate level shifting/signal conditioning for facility timing signals.
- The current save format is raw stream plus metadata/log, not a finalized calibrated dose product.
- The Pi being on `fel.epics` depends on network policy/DHCP admission.

## Safety

This system interfaces with accelerator-area timing and radiation experiments. Do not connect to facility timing signals, beamline hardware, or accelerator controls without approval from responsible Duke/FELL personnel. Use proper grounding, isolation, and level shifting. Treat all dosimetry output as experimental until calibrated against trusted instrumentation.
