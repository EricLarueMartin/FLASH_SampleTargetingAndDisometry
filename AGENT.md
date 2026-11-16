# Agent handoff

Read `README.md` first (layout and install paths), then the logs in `docs/history/`:

- `docs/history/DOSECAM_AGENT_LOG.md` — DoseCam change history and hardware notes (was `SynchronizedCameraDosimeter/AGENT.md`).
- `docs/history/COMBINE_SINGLE_PI.md` — combining positioner + DoseCam on `pi-06-ioc`, merged site, Run/Settings pages, environment variables.
- `docs/ROADMAP_INTEGRATED_RIG.md`, `docs/FARADAY_CUP_DIGITIZER.md`, `docs/REMOTE_ACCESS.md`.

Append new entries here (newest first) with date, status (verified / not verified / deployed), files, and rollback.

## 2026-11-16 — repository consolidation and film-comparison slides

- Created this repository from the `FLASH` working tree (`combine-single-pi` working copy, 2026-11-16) and
  `SynchronizedCameraDosimeter`, re-laid out by function (see README table). Fresh history: the old history
  stays in `FLASH/.git` (OneDrive had most of its objects cloud-only, so it could not be read for import).
- Redacted three plaintext passwords in `firmware/StepperController/MyConfig.h` (Wi-Fi client, soft AP, web
  login). The original file in the old `FLASH/StepperController/` still has them.
- Added `docs/analysis/20261116_film_comparison/` and slides `docs/slides/2026-11-dosecam-film/`
  (reveal.js 5.1.0 vendored in `docs/slides/vendor/`, no CDN needed).
- Nothing deployed; no Pi, motor, or PV changes.
