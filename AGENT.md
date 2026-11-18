# Agent handoff

Read `README.md` first (layout and install paths), then the logs in `docs/history/`:

- `docs/history/DOSECAM_AGENT_LOG.md` — DoseCam change history and hardware notes (was `SynchronizedCameraDosimeter/AGENT.md`).
- `docs/history/COMBINE_SINGLE_PI.md` — combining positioner + DoseCam on `pi-06-ioc`, merged site, Run/Settings pages, environment variables.
- `docs/ROADMAP_INTEGRATED_RIG.md`, `docs/FARADAY_CUP_DIGITIZER.md`, `docs/REMOTE_ACCESS.md`.

Append new entries here (newest first) with date, status (verified / not verified / deployed), files, and rollback.

## 2026-11-18 — standard masking procedure footnote

- Status: presentation wording verified locally and prepared for the authorized
  Pages publication workflow. No fits, calibration values or device changes.
- Added the requested asterisk to masking/fit choices: variation from selecting
  different procedures can be eliminated by using one standard procedure for
  camera calibration against film and later measurements. A common amplitude
  scale shift is absorbed by that calibration.
- Files: docs/slides/2026-11-dosecam-film/index.html;
  docs/analysis/20261116_film_comparison/README.md; this log.
- Validation: wording review, Git whitespace and browser layout checks.
- Rollback: revert this documentation commit; no device rollback.

## 2026-11-18 — film workbook SD and absolute-dose uncertainty

- Status: read-only workbook/source audit and presentation correction prepared
  for the authorized Pages publication workflow; no measurement, calibration,
  application or hardware changes. Input workbook is unchanged and unpublished.
- Film41_Scintillation.xlsx supplies intensity SD, not a complete standard-dose
  uncertainty budget. Replaced the prior supplied 1.9–2.4% interpretation with
  ~3% k=1 as an explicitly provisional literature benchmark. No film error bars
  or total from overlapping uncertainty contributions are invented.
- Cited primary EBT-XD budgets (Jung 2025 and Raj 2024) and AAPM TG-235. The
  ~2.8% illustration excludes Jung's 2% delivery-stability term. Documented
  protocol/dose limits, SD semantics and shared calibration-scale covariance.
- Files: docs/slides/2026-11-dosecam-film/{index.html,research.html};
  docs/analysis/20261116_film_comparison/{README.md,RESEARCH.md}; this log.
- Validation: workbook cell/OD checks, primary budget review, source arithmetic,
  companion regeneration, local links, Git whitespace and slide-layout checks.
- Rollback: revert this documentation commit; no device rollback.

## 2026-11-17 — camera fit-error and noise-accounting audit

- Status: read-only reanalysis of archived parameters and background captures;
  documentation update prepared for authorized Pages publication. No refitting,
  camera implementation changes, calibration changes or device operations.
- Reconstructed the exact current plain-Jacobian residual-scaled covariance
  for the four plotted baseline fits. Peak standard errors are 0.1602, 0.1664,
  0.1480 and 0.1531 DN (0.379, 0.388, 0.349 and 0.370%). Added nominal 1-sigma
  errors to the comparison table and a reproducible script/CSV/JSON audit.
- Replaced separate photon/read rows with one combined 0.35–0.39% nominal
  camera fit contribution. These residual-based errors already combine noise;
  photon/background diagnostics are not added again. Masking sensitivity is
  not assumed independent for a quadrature total. Documented covariance limits.
- At the gain proxy, independent photon projection is about 0.12–0.13%.
  Background projection from 34 Alanine frames, after the same 40 DN median
  despiking and quadratic baseline, is about 0.12–0.13%. Their ~0.18% conditional
  diagnostic is not added to the combined fit term. Rechecked pixel-background
  RMS is 0.5078 DN; quantization is already included in this measured quantity.
- Files: docs/slides/2026-11-dosecam-film/{index.html,research.html};
  docs/analysis/20261116_film_comparison/{README.md,RESEARCH.md,
  scripts/fit_noise_audit.py,scripts/fit_noise_audit.json,
  scripts/peak_fit_uncertainty.csv}; this log.
- Validation: two independent numerical/source audits, script covariance match
  to beam_fit._param_errors, background conditioning/projection checks,
  companion regeneration, local links, Git whitespace and browser layout QA.
- Rollback: revert this documentation/analysis commit; no hardware rollback.

## 2026-11-17 — supplied film uncertainties treated as standard uncertainties

- Status: presentation/notes correction prepared for authorized Pages
  publication. No measurement values, calibration constants or device changes.
- Per Eric, treat the supplied 1.9–2.4% film uncertainties as standard
  uncertainties (1 sigma, k=1). Renamed the film row on the error-sources
  slide and removed the pixel/selected-maximum discussion. No independent
  film fit error or goodness-of-fit value is inferred from camera fit outputs.
- Updated the film-data footnote and current analysis/research notes to the
  same convention; regenerated the companion research HTML. Rate-response
  literature remains mixed evidence and a minor caveat for these measurements.
- Files: docs/slides/2026-11-dosecam-film/{index.html,research.html};
  docs/analysis/20261116_film_comparison/{README.md,RESEARCH.md}; this log.
- Validation: supplied-data/source review, matching uncertainty wording,
  companion regeneration, local links, Git whitespace and slide layout checks.
- Rollback: revert this documentation commit; no application/hardware rollback.

## 2026-11-17 — itemized complete moving-mass budget

- Status: sourced slide 6 and analysis revision prepared for authorized Pages
  publication. No device operations or driver-setting changes.
- Replaced the 3 kg assumption with the user's complete moving inventory.
  Shifted holders/contents/carriages remain 814 g. Balanced hardware totals
  1615.36 g: 1200 mm MakerBeamXL 356.4 g; 1 m MGN15 rail 1060 g;
  4 pulleys 20 g allowance; 3.2 m x 6 mm 2GT belt 24.96 g; 4 LM8UU 68 g;
  printed bearing brackets 24 g reported by Eric; 4 steel L brackets 52 g
  reference allowance; additional fasteners 10 g allowance.
- Complete moving estimate is 2429.36 g (~2.43 kg). Under the requested
  70/30 shifted-group and 50/50 balanced-group model, equivalent loads are
  1.37748 / 1.05188 kg. With 80% efficiency, 6.38 mm pulley radius and 2x
  margin, required torques are 0.215460 / 0.164531 N·m (~0.22 / 0.16).
- Added all component mass sources/allowances and removed the unnecessary
  driver-excitation discussion from the presentation and current analysis.
  Kept the 0.45 N·m rated holding reference and the published curve conditions.
- Files: docs/slides/2026-11-dosecam-film/index.html;
  docs/analysis/20261116_film_comparison/README.md; this log.
- Validation: independent calculator/source review, load conservation, local
  links and seven-slide checks, Git whitespace checks and browser layout QA.
- Rollback: revert this documentation commit; no hardware/application rollback.

## 2026-11-17 — estimated loaded-holder and carriage masses

- Status: sourced slide 6 and calculation update prepared for authorized Pages
  publication. No device operations or changes to driver settings.
- Estimated the shifted group from 3 x 75 g printed holders, 9 x 30 g adult
  mice (JAX representative C57BL/6J weight), 9 x 15 g empty capped 50 mL
  tubes (SARSTEDT product mass 14.9 g), and 2 x 92 g MGN15H carriages
  (HIWIN catalog). Total shifted mass is 0.814 kg; balanced mass is 2.186 kg
  within the unchanged 3 kg assumed total. Reference models remain estimates.
- Applied Eric's 70/30 split only to the shifted group, and 50/50 to the rest.
  Equivalent loads are 1.6628 and 1.3372 kg. At r=6.38 mm and assumed 80%
  efficiency, torque with 2x margin is 0.2601 and 0.2092 N·m, rounded to
  0.26 / 0.21 on the slide. Preserved the 0.45 N·m rated holding reference.
- Added primary mass citations on the slide and a sourced mass table plus
  arithmetic in the analysis notes. No private purchasing details published.
- Files: docs/slides/2026-11-dosecam-film/index.html;
  docs/analysis/20261116_film_comparison/README.md; this log.
- Validation: source review, independent mass/load arithmetic, local-link and
  seven-slide checks, Git whitespace checks and slide layout review.
- Rollback: revert this documentation commit; no hardware/application rollback.

## 2026-11-17 — STEPPERONLINE assumption, EASON current and endpoint allowance

- Status: sourced analysis and slide 6 update prepared for authorized Pages
  publication. No hardware or driver settings changed.
- Per Eric, assume STEPPERONLINE 17HS15-1504S-X1, 0.45 N·m holding at
  1.5 A/phase. Removed the alternative Twotrees comparison from the slide.
- Identified the cheaper purchased EASON TB6600 driver from the saved record;
  checked its public seller photographs. Eric specifies a 12 V, 5 A supply.
  The label has a 1.5 A nominal / 1.7 A peak setting. Checked Toshiba excitation
  tables: holding uses fixed phase-current commands, so no blanket sine-RMS
  torque derating is justified. Retained 0.45 N·m as rated holding reference.
  The installed IC, actual phase current and standby reduction are unknown;
  advertised 1/32 and ADMD features suggest TB67S109A, without proving identity.
- Located the exact motor's manufacturer speed curve: DM542T, 24 V,
  1.69 A, 2000 pulses/revolution. No current sweep or matching 12 V EASON
  curve found; no running speed/torque rating is invented from it.
- For the endpoint load budget, Eric specifies treating loaded holders and
  rail carriages as a shifted COM with approximately 70/30 endpoint reactions;
  all other moving hardware remains balanced 50/50. With shifted mass m_s,
  heavier-side equivalent mass is 1.5+0.2*m_s kg and the 2× torque budget is
  0.234624+0.0312832*m_s N·m. Since m_s cannot exceed the assumed 3 kg total,
  the conservative upper bound is 0.3285 N·m, not the full-weight one-motor case.
  Exact shifted mass and endpoint geometry remain unmeasured. Documented this
  as the user's COM planning approximation and preserved current caveats.
- Files: docs/slides/2026-11-dosecam-film/index.html;
  docs/analysis/20261116_film_comparison/README.md; this log.
- Validation: primary-source and independent physics/arithmetic review,
  seven-slide/local-link and Git whitespace checks, slide layout review.
- Rollback: revert this documentation commit. No device or application rollback.

## 2026-11-17 — sourced torque estimate and three-holder CoreXY v23

- Status: documentation and CAD preview verified locally in day/night mode;
  prepared for the existing authorized GitHub Pages publication workflow.
- Slide 6 assumes 3 kg total moving mass, equal two-motor load sharing,
  a 6.38 mm belt-path radius and 80% efficiency. The gravity estimate is
  0.117 N·m per motor, or approximately 0.24 N·m with a 2× margin.
- Cited manufacturer specifications for Twotrees 17HS4401 (at least
  0.42 N·m) and STEPPERONLINE 17HS15-1504S-X1 (0.45 N·m), both explicitly
  holding ratings at 1.5 A/phase. Installed motor identity and running-torque
  performance remain unverified; no hardware sufficiency claim is made.
- Replaced the CAD archive and unchanged embedded preview with Eric's v23
  export showing three holders. Uses Eric's revised estimate of about 75 g
  each (225 g total), included in the assumed 3 kg. Documented the rough
  uniform-shell/infill calculation from the supplied geometry and its limits.
- Files: hardware/cad/FLASH Core XY.f3z;
  docs/slides/2026-11-dosecam-film/{index.html,style.css,img/corexy_cad.png};
  docs/analysis/20261116_film_comparison/README.md; this log.
- Validation: independent arithmetic/source review, CAD and preview hashes,
  seven-slide/local-link checks, Git whitespace checks and browser layout QA.
  No device operations or application changes.
- Rollback: revert this commit to restore the previous archive and slides;
  no physical hardware or application rollback is needed.

## 2026-11-17 — refreshed CoreXY v21 and existing GUI example

- Status: local slides visually verified in day/night mode, ready for the
  existing GitHub Pages publication workflow. No device operations.
- Replaced hardware/cad/FLASH Core XY.f3z with Eric's newer export from the
  parent FLASH folder; hashes match. Main design v21 includes the MakerBeam
  dummy, central holder and LM8UUonMakerBeamXL v3 component. Copied its embedded
  preview unchanged and updated slide 6/provenance. No bracket fit/strength
  validation is implied.
- Per Eric, slide 7 now shows the existing Run GUI and movement planning,
  replacing the generic sequence diagram. The example uses six illustrative
  selected targets, twelve pulses and 1000 ms spacing, with a route generated
  by the existing pure planner.
- Preserved the actual template/styles/map/table renderers in a self-contained
  offline example. Removed API/socket code, disabled action controls and blocked
  network connections with CSP. Captured its screenshot for the slide; no
  acquisition, motion, firing or live web-service changes occurred.
- Files: hardware/cad/FLASH Core XY.f3z; slide index.html/style.css,
  img/{corexy_cad.png,run_plan_gui.png}, examples/run-plan.html;
  docs/analysis/20261116_film_comparison/README.md; this log.
- Validation: CAD/preview checksums, source/provenance review, offline example
  connection checks, seven-slide/local-link checks, Git whitespace checks and
  browser layout review. Slide 7 remains open for Eric's review.
- Rollback: revert this commit to restore the prior archive, preview and slides;
  no physical hardware or application rollback is needed.

## 2026-11-17 — restore automatic Pages publication

- Status: static deployment workflow prepared for the existing public site.
- After aa28e63 was pushed, the public deck still had five slides. Read-only
  GitHub Pages settings showed Source = GitHub Actions, while the repository
  had no workflow; the last successful deployment was 680ba77.
- Added .github/workflows/pages.yml based on GitHub's official static Pages
  starter workflow. Publishes only docs/ on matching main pushes or manual
  dispatch; permissions are contents:read, pages:write and id-token:write.
- Kept the existing github-pages environment and Actions source setting.
  Updated the root README to describe this publishing configuration.
- Files: .github/workflows/pages.yml, README.md and this log.
- Validation: official starter comparison, workflow structure and Git whitespace
  checks. Deployment completion and the public seven-slide HTML are checked
  after pushing. No hardware or live application changes.
- Rollback: revert this workflow commit to stop automatic publication; no
  repository visibility, credential or hardware changes were made.

## 2026-11-17 — CoreXY, automated runs and DoseCam fiducials

- Status: seven-slide presentation visually verified in day/night mode;
  documentation update only, prepared for the authorized GitHub push.
- Added slide 6: replace the actuator with CoreXY-style motion contained
  inside a frame, reducing exposure to accidental bumps. Uses the unchanged
  embedded preview from FLASH Core XY.f3z v15 (8 November), with provenance
  and source links. Physical coordinates remain X and Z.
- Added slide 7: define positions and prescribed dose, plan pulse count/spacing,
  then move, settle, capture and fire in sequence. Distinguishes existing
  position/pulse/timing code from planned dose feedback and fiducial checks;
  live firing commissioning is not established by the recorded emulator tests.
- Updated slide 5 with planned fiducial features at known target positions
  for image calibration, reference-pose monitoring and drift/rotation detection.
  Corrected the roadmap's superseded claim that DoseCam cannot show features.
- Updated seven-link outline, slide metadata, root README, docs index and
  analysis/provenance notes; existing dose measurements/calibration unchanged.
- Files: README.md, docs/index.html, docs/ROADMAP_INTEGRATED_RIG.md,
  docs/analysis/20261116_film_comparison/README.md,
  docs/slides/2026-11-dosecam-film/{index.html,style.css,img/corexy_cad.png},
  and this log.
- Validation: source/code review, seven-slide outline and local-link checks,
  preview PNG checksum, Git whitespace check and browser visual review.
- Rollback: revert this documentation commit; no hardware, live controls,
  application behavior or beam operations were changed.

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
