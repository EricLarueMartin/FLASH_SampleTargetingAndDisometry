# FLASH Sample Targeting and Dosimetry

One device, one repository: the XY sample positioner and the DoseCam per-pulse beam
imager for the Duke FEL Lab FLASH rig (linac low-energy spectrometer, ~30 MeV electrons).
Both run on one Raspberry Pi 5 (`pi-06-ioc`) behind a single nginx site:
`/` DoseCam, `/motion/` positioning camera and manual moves, `/run/` automatic
position-and-fire, `/settings/` firing route.

This repository replaces the separate `SynchronizedCameraDosimeter` repository and the
`FLASH` working repository (motion code, stepper firmware, deploy files).

**Slides and documentation** (GitHub Pages, source `main` → `/docs`):

- [DoseCam slides: dosimetry, fiducial positioning, CoreXY and automated runs](https://ericlaruemartin.github.io/FLASH_SampleTargetingAndDisometry/slides/2026-11-dosecam-film/)
- [All project slides and documentation](https://ericlaruemartin.github.io/FLASH_SampleTargetingAndDisometry/)

## Layout

| Path | What | Came from |
|---|---|---|
| `dose_cam/` | DoseCam Flask app (IMX296 external-trigger capture, beam fit, Files viewer). Its README is the full DoseCam operator/developer guide. | `SynchronizedCameraDosimeter/dose_cam`, `README.md` |
| `motor_control/` | Positioner web app: shared OV5647 camera stream, stepper link, loadout map, Run sequencer, firing gateway client | `FLASH/camera_stream` |
| `firmware/DDG/` | ESP8266 delayed shutter-pulse generator (Arduino sketch) | `SynchronizedCameraDosimeter/DDG` |
| `firmware/StepperController/` | ESP32 stepper controller (Arduino sketch). Passwords in `MyConfig.h` are redacted — set them before flashing. | `FLASH/StepperController` |
| `hardware/OptoIsolator/` | KiCad opto-isolator board for the laser charging pulse input | `SynchronizedCameraDosimeter/OptoIsolator` |
| `hardware/cad/` | Positioner / holder CAD (STEP, Fusion `.f3z`) | `FLASH/*.step`, `*.f3z` |
| `hardware/manuals/` | Component manuals | `SynchronizedCameraDosimeter/ComponentManuals` |
| `deploy/dosecam/` | DoseCam systemd, nginx, Wi-Fi isolation firewall | `SynchronizedCameraDosimeter/deploy` |
| `deploy/combined-pi/` | Combined-Pi additions: motor_control service + drop-in, merged nginx site, `config.txt` snippet | `FLASH/deploy/combined-pi` |
| `deploy/fire-gateway/` | Forced-command SSH gateway for live firing | `FLASH/deploy/fire-gateway` |
| `tools/dosecam/` | Bench probes, analysis scripts, tests for DoseCam | `SynchronizedCameraDosimeter/tools` |
| `tools/faraday_cup/` | Faraday-cup digitizer bench tools | `FLASH/fc_digitizer/tools` |
| `docs/` | GitHub Pages root: slides, analysis notes, wiring diagrams, roadmap, history logs | both |
| `docs/history/` | Detailed change logs: `DOSECAM_AGENT_LOG.md` (was `AGENT.md`), `COMBINE_SINGLE_PI.md` | both |

## Install paths on the Pi are unchanged

The deployed services still run from their old install locations — this reorganisation
changes the repository only:

- DoseCam: `/home/codex/SynchronizedCameraDosimeter/dose_cam` (`dose-cam.service`, nginx :80 → Flask :8000)
- Positioner: `/home/test/camera_stream` (`motor_control.service`, 127.0.0.1:8081)

When redeploying from this repo, copy `dose_cam/` and `motor_control/` to those paths (or
update the unit files in `deploy/` together with the new paths).
Paths such as `DDG/DDG.ino` or `tools/…` inside `dose_cam/README.md` refer to the old
repository layout; use the table above.

## Safety

This system interfaces with accelerator timing and controls. Do not connect facility timing
signals, change beamline hardware, or write accelerator PVs without approval from responsible
Duke/FELL personnel. Treat dose output as experimental until calibrated.
