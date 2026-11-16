# Combining FLASH and DoseCam on one Raspberry Pi

Branch `combine-single-pi`. Nothing here is deployed. `master` is what runs today:
> **Access-day procedure superseded 2026-10-16** by `docs/ROADMAP_INTEGRATED_RIG.md`,
> which folds the delay generator into the stepper ESP32 and retires the ESP8266.
> This document remains the reference for the fallback configuration (ESP8266 kept,
> DoseCam on its own Pi) and for the verified-from-source compatibility findings.

FLASH on elm-ioc-00, DoseCam on pi-06-ioc.

**Host decided 2026-10-16: elm-ioc-00.** It keeps the stepper ESP32 and the OV5647
positioner camera where they are; the IMX296, the ESP8266 shutter generator and the
DoseCam software move to it. pi-06-ioc is left powered down and untouched as the
fallback, so the old split setup can be restored by moving two cables back.

Merged `master` into this branch on 2026-10-16, so it now carries the 2026-10-14
DoseCam work: `beam_fit.py`, `static/beamfit.js`, the Options dose-calibration tab,
the 200 us / 100 us timing defaults, and the matching `DDG.ino` boot defaults. The
merge was clean - the branch touched `camera_core.py` around lines 23-120 and the
rpicam call sites; `master` touched only the `esp_delay_us` default at line 601.

## Progress log - combine onto pi-06-ioc (2026-10-26)

Operator decision 2026-10-26: **pi-06-ioc is the combined host** (reverses the
2026-10-16 choice below; moving the actuator is fewer wires). Working handoff: the
"FLASH: combine actuator + DoseCam on pi-06-ioc - handoff" doc. The step list further
down was written for elm-ioc-00 as host; its compatibility findings are symmetric.

Hardware verification, 2026-10-26 ~14:15-14:25, no motor commands sent:

| Check | Result | Status |
| --- | --- | --- |
| Reach the Pi | `codex@pi-06-ioc` through daffy, host key accepted | verified |
| DoseCam idle before changes | `/api/acquisition/status` Idle | verified |
| ESP8266 (CP2104, `ttyUSB0`) | `/api/esp_status`: enabled=0, delay 200 us, width 100 us, before and after reboot | verified |
| ESP32 steppers (`/dev/serial/by-id/usb-1a86_USB_Single_Serial_5185027606-if00` -> `ttyACM0`) | read-only `UPDATE`/`GETENABLED`/`GETPOS`/`LIST`: 2 steppers, both DISABLED, positions 0 (zeroed by the move), before and after reboot | verified |
| ESP32 settings | `LIST` dump saved as `StepperController/flashed_settings_20261026.json` (passwords redacted) | verified |
| Backups | `/home/codex/backups/config.txt.pre-combine-20261026_141622`, `dose_cam_code.pre-combine-20261026_141622.tgz` (1.6 MB, code only); 10/13 captures (10 files, 132 MB) copied to `SynchronizedCameraDosimeter/captures_backup_20261013/`, sha256 match | verified |
| Boot config | added `dtoverlay=ov5647,cam1` after `dtoverlay=imx296,always-on,cam0`; rebooted 14:21 | verified |
| Both cameras enumerate | `rpicam-hello --list-cameras`: 0 = imx296 (cam0, csi 1f00110000), 1 = ov5647 (cam1, csi 1f00128000) | verified |
| Stills from each | `rpicam-still --camera 0` and `--camera 1`: real images (copies in `Claude outputs/combine_20261026_cam*.jpg`) | verified |
| **Both cameras at once** | `rpicam-vid` on both for 10 s concurrently: cam0 291 frames = 30.0 fps, cam1 305 frames = 31.8 fps, both exit 0, no errors, dose-cam stayed active | **verified - the plan's main open risk** |
| Services after reboot | dose-cam, nginx, dosecam-wifi-isolation active | verified |
| ESP32 USB stability | 28 re-enumerations in the first ~4 min of the 13:28 boot (operator seating cables?), none after the 14:21 reboot | observed |

Findings to act on:

- **ESP8266 input polarity resets to HIGH (rising edge) at boot.** The opto path needs
  LOW (falling edge). `dose_cam.py` sets it only through a UI endpoint, so after any
  ESP8266 reset the trigger edge silently reverts - the same class of fault as the
  pre-10/14 delay default. Fix by changing the `DDG.ino` boot default or having dose_cam
  send `I0` with every configure; until then, set it in the UI before beam.
- **The ESP32's flashed settings enable Wi-Fi and a soft access point** (`LATTESMC`).
  Whether the build actually starts Wi-Fi is unconfirmed - pi-06-ioc's radio is in
  hotspot mode and cannot scan. Check with a phone near the rig.
- Flashed limit pins: X low 34 / high 39, Y low 36 / high 4. GPIO34/36/39 have no
  internal pulls (see `DDG_ON_ESP32.md`).
- The OV5647's ribbon is visible at the top-left of the IMX296 frame; it is clear of the
  10/13 beam spot, but confirm it is not new in the DoseCam background.

Not yet done: model-based camera selection in DoseCam (`camera_core.py` from this
branch), motor_control install on :8081, Python deps (cv2, gevent, flask_socketio,
gevent-websocket missing), stepper position restore, the pending 10/26 DoseCam deploy,
re-pointing the flash plugin.

### Merged site, Run page, Settings page - deployed 2026-10-26 ~16:20

One web site on port 80 (nginx), four pages sharing a nav bar:

| Path | Served by | What |
| --- | --- | --- |
| `/` | dose-cam (Flask, 127.0.0.1:8000) | DoseCam, unchanged apart from the nav bar in `setup.html` |
| `/motion/` | motor_control (gevent, **127.0.0.1:8081**) | OV5647 positioning camera, manual moves, holder loadout, null adjust, Y trim, terminal |
| `/run/` | motor_control | select targets on the loadout map, pulses x delay per target (badge on each), **Plan path** (arrows, order numbers, ends at access), **Run**, **ABORT**, live log |
| `/settings/` | motor_control | live firing route (ringop@host, key, host key, read-only test), PV value, settle / tolerance / DoseCam capture |

Code: `camera_stream/` (`app.py`, `stepper_link.py`, `sequencer.py`, `firing.py`,
`ca_tool.py`, `loadout.py`, `static/geometry.js`, `templates/run.html`,
`templates/settings.html`); deploy files in `deploy/combined-pi/` and
`deploy/fire-gateway/`. The loadout (holder types, null adjust, Y trim, access
position, target selections) is now stored server-side in
`~test/.config/flash/loadout.json`, shared by every browser.

Run behaviour:

- Path: nearest-neighbour + 2-opt + or-opt (exact for <= 7 targets), start fixed at
  the current position, end fixed at access. Cost = move time of the slower axis
  (trapezoid, 3200 steps/s, 1600 steps/s^2 read from the controller).
- Per target: MOVEABS both axes, confirm arrival by polling UPDATE (position within
  tolerance, speed 0), settle, optional DoseCam arm (one frame per pulse), fire,
  DoseCam finalize; then back to access. Motors must already be ENABLED (never
  auto-enabled). Stopped short / disabled / no reply -> STOP ALL and the run ends.
  ABORT -> STOP ALL, stage stays where it is.
- **Pulse timing runs off a clock, not a chain of sleeps:** pulse k at t0 + k*delay
  on a monotonic clock, so send time and wake-up jitter never accumulate; N pulses
  span (N-1)*delay. Each pulse logs its offset, lateness and round trip; each target
  ends with first-to-last time vs scheduled.
- Modes: Simulate (no writes), Assisted (shows the equivalent `repeatPut.sh` line and
  waits for "Fired - continue" / "Skip"), Live (type the PV name to confirm).
- Live route: SSH to a control-room account the IOC already lets write (ringop).
  One session per run; on the far end `deploy/fire-gateway/flash_fire_gw.py` is the
  forced command (only `check` and a `serve` loop of `put <allowed value>`), keeps the
  PV connected and puts without callback like caput. No ACF change, no EPICS write
  access on the Pi. Set up from the Settings page; see `deploy/fire-gateway/README.md`.
  **Not configured yet**, so Live is unavailable.
- DoseCam Wi-Fi hotspot (192.168.50.0/24): can watch and ABORT; cannot plan, start,
  continue, set access, or change settings (nginx map + app check).
- Manual serial commands are blocked during a run except STOP/UPDATE/GET*.

Verified on pi-06-ioc, 2026-10-26 16:17-16:25, **no motor moves, no PV writes**:
motor_control active and enabled; ESP32 connected through the by-id path (both motors
DISABLED, positions 0, max speed 3200, accel 1600 read back); OV5647 streaming through
`/motion/video_feed` at 31.9 fps with correct colours (`simplejpeg`, no OpenCV);
`BST:INJ:START` read through cr-01-ioc (192.168.16.41): connected, value 0, enum
["", "Start"], access **READ** from this host as expected; nginx `-t` ok and all four
pages, static files, Socket.IO and the APIs answer through port 80; dose-cam restarted
idle and serves the nav bar. Backups: `/home/codex/backups/nginx-dose-cam.pre-merge-20261026_161714`,
`setup.html.pre-merge-20261026_161714`.

Tested off the rig (container, stepper emulator on a pty): plan/run/abort/assisted/
limit-stop paths, hotspot refusal, input validation, the absolute pulse clock through
a stub gateway (40 x 0.1 s and 10 x 0.25 s: first-to-last error 0.0 ms, lateness max
0.1 ms), and the gateway's refusal of anything but `check`/`serve`/allowed puts.

Still open: access (park) position not set (jog left/up, "Set access = current
position"); stepper positions are 0 after the move (SETPOS or re-home before using
the map); ESP8266 input polarity is HIGH (Run page pre-flight offers the fix);
gateway host/key for live firing; re-point the flash plugin at pi-06-ioc.

## Why it works

| Concern | Finding | How established |
| --- | --- | --- |
| Two cameras | Pi 5 has two CSI connectors and runs two cameras at once. | Platform |
| External trigger | DoseCam enables trigger mode through `/sys/module/imx296/parameters/trigger_mode`, a parameter of the **imx296 driver only**. The OV5647 is a different driver and keeps free-running. Never make the second camera an IMX296 as well. | Source + driver model |
| Pi GPIO | FLASH uses **none**. `camera_stream/app.py` and `camera_worker.py` import no GPIO library (no gpiozero / lgpio / RPi.GPIO) and reference no pin numbers. DoseCam needs GPIO26, pin 39 ground, and optionally GPIO16. No collision. | Read both files, 2026-10-16 |
| ESP8266 serial | The by-id path hardcodes the CP2104's **own** serial number (`..._023312DB-if00-port0`), not a host path, so it follows the board to the new Pi unchanged. Falls back to `/dev/ttyUSB0`. | `dose_cam.py:122`, `camera_core.py:647,667` |
| ESP32 serial | Already parameterised: `FLASH_SERIAL_PORT`, default `/dev/ttyACM0`. | `app.py:28` |
| Two serial devices | ESP32 adapter enumerates as `ttyACM*` (CDC-ACM), CP2104 as `ttyUSB*` (cp210x). Different drivers, no renumbering collision. | Device class |
| Web ports | motor_control binds :80 today via the `port80.conf` drop-in. DoseCam wants nginx on :80 -> Flask :8000. FLASH moves to **8081**; the capability drop-in is then unnecessary. | `camera_stream/motor_control.service.d/port80.conf` |
| Camera selection | Each app opens its camera **by sensor model**, never by index, and errors out rather than falling back to the other camera. 8/8 tests pass post-merge (2026-10-16). | `tools/test_camera_selection.py` |
| Load | A 640x480 MJPEG preview beside DoseCam's raw captures is well within a Pi 5. DoseCam spools to `/dev/shm/dose_cam` first (512 MB min free), so burst writes do not hit the boot media directly. | `camera_core.py` RAM_SPOOL_* |

## Pinout

### Raspberry Pi 40-pin header on elm-ioc-00

Three pins, and that is all either application touches. Orientation: board viewed
from above, USB/Ethernet at right; the odd-numbered row is the one next to the PCB
edge.

| Pi physical pin | BCM | Direction | Goes to | Wire | Required |
| --- | --- | --- | --- | --- | --- |
| 37 | GPIO26 | Pi output | ESP8266 GPIO12 | brown/white | **Yes** - the Capture test pulse in Targeting and Dosimetry modes |
| 36 | GPIO16 | Pi input | ESP8266 GPIO15 | green/white | Optional - monitor only, used by bench probes, not by the service |
| 39 | GND | - | Camera J3 `Trig-` | black | **Yes** - trigger return |

Verified free: nothing in `camera_stream/` claims any GPIO, so pins 36, 37 and 39
are available on elm-ioc-00 as they are on pi-06-ioc.

### ESP8266 Feather HUZZAH - unchanged, moves as a unit

Nothing on the ESP8266 side changes. Bench-verified 2026-09-15; repeated here so the
board can be re-landed without re-deriving it.

| ESP8266 pin | Signal | Connects to | Wire |
| --- | --- | --- | --- |
| GPIO14 | Laser charge trigger in, **active LOW / falling edge** (the opto inverts) | OptoIsolator J2 pin 2 | white |
| GPIO12 | Pi bench trigger in | Pi pin 37 / GPIO26 | brown/white |
| GPIO13 | Camera shutter out, **active LOW** | Camera J3 `Trig+` / XTR | white |
| GPIO15 | Monitor out | Pi pin 36 / GPIO16 | green/white |
| 3V3 | Opto supply | OptoIsolator J2 pin 3 | grey |
| GND | Opto ground | OptoIsolator J2 pin 1 | black |

Header order, component side, battery-connector end at left: three empty pins, then
GPIO14, GPIO12, GPIO13, GPIO15. Other header from the USB end: reset (empty), 3V3,
one empty, GND.

Camera, viewed from the back with the ribbon down: J3 is the external trigger header
(J2 is strobe, unused). `Trig-` is the contact closest to the camera PCB edge and
returns to Pi pin 39.

USB: the CP2104 goes to any free USB-A port on elm-ioc-00.

### CSI connectors

| Camera | Connector | Note |
| --- | --- | --- |
| OV5647 (FLASH positioner) | CAM/DISP **1** | Already there. Do not disturb - the cable is long and runs near metal. |
| IMX296 (DoseCam) | CAM/DISP **0** | Free connector. |

The Pi 5 uses the narrow 22-pin FFC, so bring the 15-to-22-pin adapter cable with the
camera. Confirm the assignment after boot with `sudo dmesg | grep -i 'Using sensor'`.

## Procedure

Keep the stepper motors **disabled** throughout.

1. **Record FLASH stepper positions** from the web UI, or `UPDATE` in the Terminal
   tab. Last known (2026-10-12): motor 0 = **134620**, motor 1 = **0**. The ESP32 is
   not being moved this time, but the Pi gets rebooted, which zeroes both counters.
2. **Survey elm-ioc-00** (read-only):
   ```bash
   grep -nE 'camera_auto_detect|dtoverlay' /boot/firmware/config.txt
   sudo dmesg | grep -i 'Using sensor'
   ls -l /dev/serial/by-id/ ; lsusb
   df -h / /dev/shm ; lsblk -o NAME,SIZE,ROTA,TRAN
   id test; id codex
   dpkg -l | grep -E 'rpicam-apps|python3-picamera2|nginx|nftables|network-manager'
   python3 -c "import flask, gevent, cv2, picamera2, gpiozero, serial" && echo ok
   ```
   This answers the remaining open questions below. In particular: a free USB-A port
   (elm-ioc-00 carries `dtoverlay=dwc2,dr_mode=host`, which suggests the ESP32 may be
   on the USB-C port), disk headroom for captures, and whether `codex` exists.
3. **Bring the DoseCam software over.** Copy `SynchronizedCameraDosimeter/dose_cam/`
   from this branch, plus `deploy/nginx/`, `deploy/systemd/`, `deploy/dosecam-wifi.nft`.
   Also copy `~/.config/dosecam/dn_calibration.json` from pi-06-ioc - it lives outside
   the repo deliberately (writable by the service, survives a code rollback) and is
   **not** in git. It is currently empty pending the film cross-cal, but copy it
   anyway so the Options tab has its file.
   ```bash
   python3 tools/test_camera_selection.py    # 8 tests, must pass
   ```
4. **Move FLASH off port 80**:
   ```bash
   sudo install -d /etc/systemd/system/motor_control.service.d
   sudo cp deploy/combined-pi/motor_control.service.d/combined.conf \
           /etc/systemd/system/motor_control.service.d/
   sudo rm /etc/systemd/system/motor_control.service.d/port80.conf   # no longer needed
   ```
   Fill in `FLASH_SERIAL_PORT` in `combined.conf` from step 2's `/dev/serial/by-id/`
   listing (the entry pointing at `ttyACM*`).
5. **Install the FLASH camera-selection code**: copy `camera_stream/app.py`,
   `camera_worker.py` and `templates/index.html` from this branch over the deployed
   copies. Keep a `.pre-combined` backup beside each, the convention already used
   there, and install with `sudo install -o test -g test -m 644`.
6. **Set camera overlays**: apply `deploy/combined-pi/config.txt.snippet`. Back up
   `config.txt` first.
7. **Power down**, connect the IMX296 to CAM/DISP 0 and the ESP8266's USB lead, land
   the three Pi header wires from the pinout above, power up.
8. **Check both cameras**:
   ```bash
   rpicam-hello --list-cameras                 # expect imx296 and ov5647
   # both at once, in separate processes - the one thing not verifiable in advance:
   rpicam-hello -n -t 10000 --camera 0 & rpicam-hello -n -t 10000 --camera 1; wait
   ```
   If the second process fails with "busy", the two cameras share a locked device and
   the plan needs rework. Stop and roll back.
9. **Check trigger isolation**: with the FLASH stream running, arm DoseCam (it sets
   `trigger_mode=1`) and confirm the FLASH preview keeps its frame rate.
10. `sudo systemctl daemon-reload`, restart `motor_control`, enable and start
    `dose-cam` and `nginx`.
11. **Restore stepper positions** without moving the motors, in the Terminal tab:
    `SETPOS 0 134620`, `SETPOS 1 0` (or the values from step 1), then `GETPOS 0`,
    `GETPOS 1`. `SETPOS` re-origins the counter only.
12. **Check the Reset camera button**: press it with a DoseCam acquisition armed. It
    must not list DoseCam or `rpicam-raw`. `curl -s localhost:8081/camera/holders`
    should show only FLASH's `camera_worker.py`.
13. **Run a DoseCam GPIO26 test acquisition** while someone watches the FLASH feed.
    Confirm `/api/esp_status` reports delay 200 us / width 100 us after an ESP reset.
14. **Update access**: tunnel, `REMOTE_ACCESS.md`, and both plugins' host config.
    ```powershell
    ssh -N -L 8080:192.168.16.117:80 -L 8081:192.168.16.117:8081 -L 2222:192.168.16.117:22 test@daffy.fel.duke.edu
    ```
    DoseCam at `http://localhost:8080`, FLASH at `http://localhost:8081`. Both plugins
    can now share one tunnel - the host-key clash between them goes away, because
    there is only one host.
15. Merge the branch: `git checkout master && git merge combine-single-pi`.

## Rollback

pi-06-ioc is untouched. Move the IMX296, the ESP8266 and its three Pi header wires
back, boot it, and it is the system of 2026-10-14. On elm-ioc-00, restore `config.txt`,
restore the `.pre-combined` backups, put `port80.conf` back and remove `combined.conf`.
With a single camera the branch's code behaves identically to `master` anyway, so a
partial rollback is safe.

DoseCam-side rollbacks on pi-06-ioc, unchanged: `bash /home/codex/backups/restore_dose_cam.sh`
(web app) and `bash /home/codex/backups/restore_esp_firmware.sh` (full 4 MB pre-2026-10-14
flash image). **These scripts live on pi-06-ioc only** - copy them to elm-ioc-00 along
with the code if you want the same rollback path there.

## Open hardware questions for the setup day

Answered by step 2; none of them block moving the cables.

1. Free USB-A port on elm-ioc-00, and whether the ESP32 currently sits on USB-C.
2. Disk headroom and media type. A run directory is around 2 GiB; raw frames are
   3,203,072 bytes each. `/dev/shm` spooling protects the write path, but the boot
   media still has to hold the runs.
3. Whether `rpicam-apps`, `python3-picamera2`, `gpiozero`, `nginx`, `nftables` and
   NetworkManager are installed on elm-ioc-00.
4. Account layout: FLASH runs as `test`, DoseCam as `codex`. Either create `codex`
   on elm-ioc-00 or re-path the dose-cam unit to `test`.
5. Whether the DoseCam Wi-Fi hotspot and its nftables isolation are wanted on
   elm-ioc-00 at all - elm-ioc-00 sits on the device network behind daffy and may not
   need the AP.
6. Camera cable reach from CAM/DISP 0 to the beam view position.

## Verified in simulation (2026-10-12, re-run 2026-10-16 after the merge)

Fake Picamera2 with the IMX296 enumerated first and a process named `rpicam-raw`
holding its lock:

- FLASH opened camera 1 (ov5647) and streamed while "DoseCam" held camera 0.
- Before FLASH had streamed, DoseCam was listed but not stoppable; a forced reset left
  it running. After FLASH streamed, DoseCam was not listed at all.
- A stray program on the FLASH camera was listed, stoppable, and stopped; DoseCam was
  untouched.
- With the OV5647 absent: clear error, no attempt on the IMX296, page offers no Stop.
- The full single-camera suite still passes with the variables unset.

Not verifiable without hardware: two libcamera processes on one Pi 5 (step 8), and
everything in "Open hardware questions".

## Environment variables

| Variable | Service | Combined-Pi value | Unset behaviour |
| --- | --- | --- | --- |
| `FLASH_HTTP_HOST` | motor_control | `127.0.0.1` (behind nginx) | `0.0.0.0` |
| `FLASH_HTTP_PORT` | motor_control | `8081` | `80` |
| `FLASH_CAMERA_MODEL` | motor_control | `ov5647` | first camera |
| `FLASH_PROTECTED_PROCESSES` | motor_control | `rpicam-,dose_cam` | none protected |
| `FLASH_SERIAL_PORT` | motor_control | `/dev/serial/by-id/...` | `/dev/ttyACM0` |
| `FLASH_DOSECAM_URL` | motor_control | `http://127.0.0.1:8000` | same |
| `FLASH_RUN_DENY_NETS` | motor_control | `192.168.50.0/24` | same |
| `FLASH_LOADOUT`, `FLASH_SETTINGS`, `FLASH_RUN_DIR` | motor_control | (default) | `~/.config/flash/loadout.json`, `~/.config/flash/settings.json`, `~/flash_runs` |
| `EPICS_CA_AUTO_ADDR_LIST` / `EPICS_CA_ADDR_LIST` | motor_control | `NO` / `192.168.16.41` (cr-01-ioc) | broadcast (boostinj also answers) |
| `DOSECAM_CAMERA_MODEL` | dose-cam | (default) | `imx296` |
| `DOSECAM_CAMERA_INDEX` | dose-cam | (unset) | choose by model |
| `DOSECAM_CAL_PATH` | dose-cam | (default) | `~/.config/dosecam/dn_calibration.json` |
