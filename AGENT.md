# Agent handoff

Read `README.md` first (layout and install paths), then the logs in `docs/history/`:

- `docs/history/DOSECAM_AGENT_LOG.md` — DoseCam change history and hardware notes (was `SynchronizedCameraDosimeter/AGENT.md`).
- `docs/history/COMBINE_SINGLE_PI.md` — combining positioner + DoseCam on `pi-06-ioc`, merged site, Run/Settings pages, environment variables.
- `docs/ROADMAP_INTEGRATED_RIG.md`, `docs/FARADAY_CUP_DIGITIZER.md`, `docs/REMOTE_ACCESS.md`.

Append new entries here (newest first) with date, status (verified / not verified / deployed), files, and rollback.

## 2026-11-17 — direct slide link before approved initial push

- Status: README link verified against the docs layout; Eric explicitly
  approved the full initial public push, including existing project history.
- Added a direct GitHub Pages link to the five-slide DoseCam presentation in
  the root README, retaining the documentation-site link and main/docs source.
- Files: README.md and this log. No hardware or application changes.
- Rollback: revert this README-link commit without rewriting published history.

## 2026-11-17 — publish reviewed DoseCam slides and research

- Status: local checks verified; commit and push to the specified GitHub
  repository's main branch authorized by Eric. No hardware deployment.
- Confirmed origin matches EricLarueMartin/FLASH_SampleTargetingAndDisometry
  and the remote has no refs; the first push includes the existing consolidation
  commit as well as the current documentation changes.
- Publish the five-slide deck, styles, source citations, QE figure, companion
  research page, reproducible calculation/JSON, analysis README and handoff log.
- Exclude local downloaded paper/page-render reading copies via .gitignore;
  retain publisher citations. Mark the original research handoff as historical
  and document the calculation's NumPy >=2.0 requirement.
- Validation: five-slide structure, local links, calculation output consistency,
  companion HTML regeneration and Git whitespace checks. Day/night visual QA
  was completed on 16 November.
- Rollback: revert this documentation commit to restore the previous deck;
  preserve the consolidation history and unrelated work. No hardware rollback.

## 2026-11-16 — alignment examples and rounded tilt threshold

- Status: local presentation update, visually verified in day/night mode;
  **not deployed**.
- Per Eric, slide 4 now states that up to approximately 12 degrees of sheet
  tilt leaves the primary cone above the escape limit. The source footnote
  gives the calculated 11.8-degree boundary at n = 1.585 and retains the
  smooth, parallel-face assumptions.
- Added slide 5 and its outline link for planned alignment use. Enlarged the
  existing A1/A3 panels of 20261014/positions_suppressed.png using SVG crops,
  preserving the original pixels. Labeled visible target features without
  asserting they are Sharpie; no archived note identifies the recalled test.
- Linked the original analysis image, processing archive and new provenance
  notes. Disclosed smoothing, separate contrast stretches and the masked beam
  region; no quantitative tracking precision is claimed.
- Files: docs/slides/2026-11-dosecam-film/{index.html,style.css};
  docs/analysis/20261116_film_comparison/README.md; this log. Raw data,
  measured doses, calibration and deployed acquisition software unchanged.
- Rollback: remove only the alignment section/nav/style additions, restore
  the prior tilt sentence and deck-count wording, and remove this entry;
  preserve unrelated work. No hardware rollback is needed.

## 2026-11-16 — balanced film-rate caveat on error slide

- Status: local slide wording update, content reviewed and browser layout
  visually verified; **not deployed**.
- Per Eric, replaced the prominent "unvalidated at 40 Gy/pulse" film warning
  with a minor rate caveat. The row states that EBT-XD evidence is mixed and
  no rate-related bias is established for this run.
- Added linked references on both sides: Del Sarto (2025) and Cayley (2025)
  report overresponse; Szpala (2021) and Schott (2026) report no dependence.
  Footer notes different conditions/methods and Schott's lower pulse-dose range.
- Files: docs/slides/2026-11-dosecam-film/index.html and this log. No changes
  to dose values, calibration, the other error rows or the four-slide structure.
- Rollback: restore only the film row/source paragraph and this entry, preserving
  unrelated work. No hardware or deployed rollback is needed.

## 2026-11-16 — film equivalence, target quality and simpler TIR slide

- Status: local presentation/documentation update, content reviewed and visually
  verified in day/night mode; **not deployed**.
- Per Eric, treat all film wells on the same basis. Removed the row-offset
  hypothesis, subgroup attribution and scanner-row checks; no measured dose or
  calibration value was changed.
- Error slide now highlights likely nonuniformity of the PC/aluminum-tape
  target and changing optical response as the spot moves; magnitude is unmeasured.
- Removed camera-viewing-angle rays and calculations from the Cherenkov slide.
  The primary cone exceeds the PC–air critical angle regardless of camera view.
  Retained the smooth, parallel-interface qualification and source links.
- Files: slide index.html and regenerated research.html; analysis README.md
  and RESEARCH.md. Four-slide structure, outline and day/night mode retained.
- Rollback: restore only these wording/graphic changes and this dated entry;
  preserve unrelated work. No hardware or deployed rollback is needed.

## 2026-11-16 — gate-containment clarification and accepted well mapping

- Status: local documentation/slides update; **not deployed**.
- Eric clarified that delay and duration were scanned to full-signal plateaus,
  with the chosen capture margins much larger than expected jitter. Updated
  system/timing and error-source slides: gate timing is not expected to
  contribute appreciably; no invented jitter value or clipping percentage.
- Timing graphic now places a clearly schematic light pulse inside the gate,
  rather than drawing the old coarse 200–225 us interval on the leading edge.
- Per user instruction, take B1, A1, A2, A3 mapping as correct. Removed mapping
  error from the error table and unconfirmed-mapping caveats / next checks.
- User further specified that no scintillation/Cherenkov separation measurements
  are planned. Simplified the Cherenkov slide to expected internal reflection
  and removed separation experiments from the active research recommendations.
- Files: slide index.html, style.css (table wrapping) and regenerated research.html;
  analysis README.md and RESEARCH.md. No acquisition, calibration or hardware changes.
- Rollback: restore only these wording/graphic changes and this dated entry;
  preserve the preceding four-slide structure and unrelated work.

## 2026-11-16 — four-slide presentation revision

- Status: local presentation visually verified in day/night mode; **not deployed**. No calibration, hardware,
  Pi/SSH, motor, accelerator PV or GitHub changes.
- User requested exactly four slides: (1) DoseCam and gun-cycle synchronization,
  (2) all four fitted beam images plus individual camera/film measurements,
  (3) error sources, (4) Cherenkov light. Preserved outline, day/night mode,
  source links and the separate research notes; no Fano-factor discussion.
- Timing graphic distinguishes the laser-charging reference, ESP delay, XTR gate
  and inferred beam-light arrival window; it does not claim a measured gun width.
- Restored existing frames.png and precise data table without changing figures
  or calibration. Clarified that film A-row 0.18% is relative sample SD, not range.
- Files: docs/slides/2026-11-dosecam-film/{index.html,style.css,research.html};
  analysis README.md and RESEARCH.md (updated obsolete slide reference).
- Rollback: restore the prior presentation HTML/CSS and this dated entry, keeping
  unrelated edits and the research artifacts.

## 2026-11-16 — sourced film / photon / light-mechanism review

- Status: local analysis and slides verified; **not deployed**. No Pi/SSH, hardware,
  accelerator PV, motor, GitHub push or calibration-default changes.
- Replaced the eight-slide intro-heavy deck with five focused slides, including
  an editable optical-geometry graphic, visible linked references, the mono
  IMX296 QE plot, left outline and persistent day/night mode. User requested
  removal of the Fano-factor discussion.
- Primary-cone trapping verified from PDG Eq. 35.5 plus Snell's law; this does not
  quantify all Cherenkov from secondaries/roughness. User supplied near-normal
  sheet, 30-degree camera view and Arducam 8–50 mm lens. Undoped PC scintillation:
  Nakamura et al., doi:10.5453/jhps.49.98. Component percentages remain conditional.
- Gain proxy 10.7 e-/DN, engineering interval 8–12, from Teledyne FLIR IMX296 mono
  EMVA. Fitted-peak shot floor 0.102% (0.097–0.118% interval).
- Film absolute uncertainty remains unresolved at 40 Gy/pulse. Del Sarto et al.,
  doi:10.3389/fphy.2025.1474416, reports possible high-rate bias. Existing 3% film
  / 3.19% total code allowances remain provisional; DN/Gy = 1.0563 unchanged.
- Files: docs/slides/2026-11-dosecam-film/{index.html,style.css,research.html,img/imx296_mono_qe.png};
  docs/analysis/20261116_film_comparison/{README.md,RESEARCH.md,light_budget.json,
  scripts/light_budget.py,scripts/render_research.py,sources/}.
- Sources, assumptions and reproducible numbers: RESEARCH.md and light_budget.py.
- Rollback: restore the edited tracked HTML, analysis README and this entry from
  the prior revision, preserving unrelated work; remove only the newly added
  research assets if desired. No deployed rollback is needed.

## 2026-11-16 — repository consolidation and film-comparison slides

- Created this repository from the `FLASH` working tree (`combine-single-pi` working copy, 2026-11-16) and
  `SynchronizedCameraDosimeter`, re-laid out by function (see README table). Fresh history: the old history
  stays in `FLASH/.git` (OneDrive had most of its objects cloud-only, so it could not be read for import).
- Redacted three plaintext passwords in `firmware/StepperController/MyConfig.h` (Wi-Fi client, soft AP, web
  login). The original file in the old `FLASH/StepperController/` still has them.
- Added `docs/analysis/20261116_film_comparison/` and slides `docs/slides/2026-11-dosecam-film/`
  (reveal.js 5.1.0 vendored in `docs/slides/vendor/`, no CDN needed).
- Nothing deployed; no Pi, motor, or PV changes.
