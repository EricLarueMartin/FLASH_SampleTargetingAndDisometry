# DoseCam vs EBT-XD film — 4-pulse comparison (analysis 16 Nov 2026)

Data: `PolyAlDosCal_20261013_161112_732305_000006.raw` (4 frames, delay 200 µs, gate 100 µs,
gain 1, 10-bit), 0.5 mm polycarbonate sheet backed with aluminum tape. Background reference:
median of the 34 frames of `Alanine_20261013_145026_730724_000002.raw` (same gate, 100 µs delay,
beam outside the gate). Film: EBT-XD lot 06092501, well_041, 24 h curve, peak = max over a
10 px window (Julia Sherman, 2026-10-18/21). Frame → well order **B1, A1, A2, A3** is taken as correct for this comparison
(per E. Martin, 2026-11-16).

Figures: `frames.png` (the four pulses, same colour scale, fitted 1σ/2σ ellipses),
`compare.png` (camera vs film per well). Scripts in `scripts/` (set `DOSECAM_CAPTURES`).

## Research update — 2026-11-16

[Full sourced research](RESEARCH.md) and [seven-slide presentation](../../slides/2026-11-dosecam-film/index.html).
The current deck has seven slides: system and
timing; all four fitted beam images with camera / film doses; error sources;
Cherenkov internal reflection; fiducial positioning; the CoreXY frame replacement;
and automated position-and-dose plans.
A left outline, linked references and
persistent day/night mode are included. Detailed light-yield and uncertainty
calculations remain in the research notes.

## Alignment image provenance

Slide 5 enlarges the A1 and A3 panels of the existing
[positions_suppressed.png](../20261014/positions_suppressed.png), without
resynthesizing their image content. These are zero-based frames 1 and 3 of
`PolyAlDosCal_20261013_161112_732305_000006.raw`, the same four-pulse run
used for the film comparison: 200 µs delay, 100 µs gate. Original raw files and
JSON metadata remain in `FLASH/SynchronizedCameraDosimeter/captures_backup_20261013/`.

Archived `shift.py` in [analysis_scripts.tgz](../20261014/analysis_scripts.tgz)
replaces positive outliers exceeding a 3×3 median by more than 40 DN,
masks the central beam inside 3.5 fitted sigma, subtracts a frame median and
applies Gaussian smoothing (sigma 6 px), with a separate percentile contrast
stretch for each panel. The white masked area and cyan beam-location ellipses
are processing overlays. Both displayed panels use the same pixel-coordinate
crop. Their brightness is not a quantitative light-yield comparison.

The dark parallel features in A1 and bright L-shaped structure in A3 are
visible target/holder features. No archived note identifies them as Sharpie;
the operator's recalled Sharpie observation is not attributed to these images.
Per E. Martin's update on 17 November, the plan is to add dedicated fiducial
features at known target positions. These will calibrate image scale,
orientation and perspective, and monitor the target relative to the fitted
beam centroid and a reference pose. Existing contrast images are not images
of installed fiducials. Tracking and alignment precision are not yet validated.

The separate room-light targeting photograph on slide 1 comes from
`PolyAlDosCal_20261013_160908_654522_000004.raw`, one 1000 µs targeting
exposure with 100 µs delay. It is not a 100 µs dosimetry pulse image.

## Rig upgrade slides

Slide 6 uses an unchanged embedded PNG from `hardware/cad/FLASH Core XY.f3z`:
nested model `222bcf11-8163-4af9-8acd-932c9e2ee0e9.f3d`, member
`FusionAssetName[Active]/Previews/big.png`. The archive identifies FLASH Core XY,
version 21, created 17 November 2026 at 17:21 EST. The 1024×1024 image is copied byte for byte
to the deck's `img/corexy_cad.png`; SHA-256:
`633a7ae2d9a11a2cc87a90516e60dd6b45c730243396ef50fb6d5f49d152c9f0`.
The slide crops surrounding white space for display. It is a CAD preview of
the rail/belt assembly and central holder, not an installed-stage photograph.
The updated model includes the user's MakerBeam dummy and linked
`LM8UUonMakerBeamXL` v3 bracket component. Bracket fit and strength have not
been assessed for the presentation. The repository CAD matches the updated
`FLASH/FLASH Core XY.f3z` export byte for byte; archive SHA-256:
`4d5fa97f0efcc5aef2e06e8aae687f19eb3103e3714cf5ca4348d0f1404b5c5d`.
Containment inside a frame and reduced susceptibility to bumps
are the user's design goals, not measured performance claims. CoreXY is the
belt-kinematics name; physical user coordinates remain X and Z.

Slide 7 shows the existing Run GUI with an illustrative two-plate plan:
six selected positions, twelve programmed pulses and 1000 ms spacing.
`examples/run-plan.html` reuses the actual `motor_control/templates/run.html`
HTML/CSS, `nav.css`, and the existing geometry/map/table renderers. Its route
comes from the existing pure movement planner. The mock selections and time
estimates do not represent a measurement or an executed run. Network/API/socket
code is removed, controls are disabled, and its content-security policy blocks
network connections. `img/run_plan_gui.png` is a browser screenshot of this
offline page; the slide crops it to emphasize the route, controls and table.

The current
`motor_control/sequencer.py` accepts positions, pulse counts and delays. It
moves, checks arrival and settles, optionally arms DoseCam, requests the pulse
sequence, finalizes the capture and continues to the next target, then parks.
It records run events and firing requests; it does not stop on a measured-Gy
threshold or perform fiducial checks. Those are planned extensions.
The 26 October commissioning log documents simulator tests and deployment
without real motor moves or PV writes; its live firing route was marked
as not configured at that time. The slides do not imply that end-to-end automatic beam
delivery or Gy feedback has been commissioned. No live controls were used
or changed to prepare these slides.

## Light-mechanism conclusions

- Replace the unsupported “mostly Cherenkov” claim with an unresolved mixture.
  PC scintillation is demonstrated in the literature. In the user's near-normal
  beam geometry, the ideal 51-degree primary cone is trapped at the 39-degree
  PC-air limit even after flat Al reflection. Secondary light and roughness remain.
- A QE-weighted, equal-throughput calculation gives approximately 70/30
  scintillation/Cherenkov. This is a conditional benchmark, not a measured split.
  Lens UV transmission and foil redistribution are unmeasured. A worked rough-Al
  scenario gives 73/27; alternate assumptions reverse the split. These exploratory
  estimates remain in the notes; no component-separation measurements are planned.
  The presentation simply notes expected primary-cone internal reflection.
- Gain proxy: 10.7 e-/DN; sensitivity interval 8–12, not a confidence interval.
- No apparatus-specific 1-sigma film absolute uncertainty was established.
  A 2025 study reports possible FLASH bias; the existing code's provisional 3.0%
  film / 3.19% total numbers remain unchanged and must not be advertised as validated.
- No deployment, Pi access, PV changes or GitHub push.

## Gate containment — operator confirmation, 2026-11-16

Eric scanned both gate delay and gate duration until the captured signal stopped
changing, then placed the operating settings well inside the full-capture limits.
He reports margins much larger than the expected jitter. This supports full-pulse
light capture and makes gate clipping an unlikely contributor to the observed
scatter. The approximately 200–225 us arrival interval from earlier coarse scans
is not a precision boundary or a measured gun pulse width. No numerical jitter,
scintillation decay constant or percentage clipping bound is inferred here; the
observed plateau is the direct evidence for adequate integration.

## Comparison

Calibration (unchanged, deployed default): **1.0563 DN/Gy** = mean fitted peak 42.25 DN / mean
film peak 40.00 Gy. Camera amplitudes are the deployed-code fits in
`../20261014/crosscal_fits_PolyAlDosCal_000006.csv` (baseline mode).

| Pulse | Well | Camera peak (DN) | Camera (Gy) | Film (Gy) | Camera − film |
|---|---|---:|---:|---:|---:|
| 1 | B1 | 42.24 | 39.99 | 40.94 | −2.3 % |
| 2 | A1 | 42.92 | 40.63 | 39.61 | +2.6 % |
| 3 | A2 | 42.45 | 40.19 | 39.75 | +1.1 % |
| 4 | A3 | 41.40 | 39.19 | 39.70 | −1.3 % |

- Scatter of camera/film: **2.2 % (1σ, n = 4, 3 dof)**; rms residual 1.9 %. Camera and film are
  uncorrelated (r = −0.06): the ratio scatter equals the quadrature sum of the two separate
  spreads (1.50 % ⊕ 1.57 % = 2.17 %).
- All film wells are treated on the same basis, without a row-dependent offset
  or correction (per E. Martin, 2026-11-16).
- Camera A1→A3 falls monotonically (42.92 → 42.45 → 41.40 DN) while the spot centroid drifts
  ~9 px right/up.

## Where the scatter comes from (1σ, per pulse, % of dose)

| Source | Estimate | Basis |
|---|---|---|
| Photon statistics, fitted peak | ~0.102%; 0.097–0.118% over gain sensitivity interval | 1.93 M photoelectrons at 10.7 e-/DN; ideal Poisson Gaussian floor, not total fit uncertainty; [vendor proxy](https://softwareservices.flir.com/FFY-U3-16S2-DL/latest/EMVA/EMVA.html) |
| Read noise + prompt sensor hits, fitted peak | ≈0.2–0.4 % | Fit statistical error from residuals (0.05 DN ≈ 0.12 % white-noise; ~0.36 % with correlated-noise estimate) |
| Hit-masking / fit-method choice | ~1 % (mostly common-mode) | Amplitude moves 1–2 % between masking thresholds (`scripts/robust.py`) |
| PC / Al-tape target | Likely nonuniform; contribution unmeasured | Tape surface, contact and local reflectivity can vary. The ~9 px spot drift can sample a different optical response; no quantitative target uncertainty has been established |
| Gate timing | Not expected to contribute appreciably | Operator scanned delay and duration to full-signal plateaus, then selected operating margins much larger than expected jitter; no numerical percent bound assigned |
| Film: per-pixel noise | 1.9–2.4%; window-maximum uncertainty unresolved | Window definition, smoothing and correlations are required; cannot infer the maximum error by averaging |
| Film: absolute accuracy at ~40 Gy/pulse | Not validated | Common calibration uncertainty plus possible rate bias; see [research](RESEARCH.md#5-ebt-xd-at-40-gy). Existing 3% code allowance remains provisional |

Reading: the ideal photon shot-noise floor is far below the observed scatter.
The aluminum-tape target is likely nonuniform, so spot motion can change the
collected light even at the same dose. Variation can also include analysis and
real beam changes; four frames do not establish their individual contributions.
No film-row effect is assigned or subtracted.

## Photon-count noise

Use **10.7 e-/DN** as a proxy from the Teledyne FLIR monochrome IMX296 EMVA data,
with **8–12 e-/DN** as an engineering sensitivity interval. The manufacturer
reports a 10-bit ADC, 10,276-electron saturation and 4.69-electron read noise.
Our gain is not measured. With quantization added separately, the proxy predicts
0.525 DN dark noise, compared with measured 0.58 DN; some EMVA definitions already
include quantization. A photon-transfer curve is still required.

For the measured 180,000 DN integrated spot, N = 1.926 million electrons. Shot
noise is 4.72% on a 42 DN peak pixel, 0.472% for an ideal constant-peak 10 x 10
camera window, and 0.072% for the whole spot. The ideal free-shape Gaussian peak
error is 1.42/sqrt(N) = **0.102%**; over g = 8–12 it is **0.097–0.118%**.
These are model floors and do not include sensor hits or a fitted background.

The light-mechanism and Fano-factor assertions in the earlier version were
removed. The user requested dropping the Fano-factor discussion. Neither that
discussion nor a Cherenkov-dominance assumption is needed for the shot-noise estimate.

## Sources

- [Full references, optical geometry verification and film limitations](RESEARCH.md).
- [Nakamura et al. (2014): undoped PC scintillation](https://www.jstage.jst.go.jp/article/jhps/49/2/49_98/_pdf).
- [Teledyne FLIR mono IMX296 EMVA and QE curve](https://softwareservices.flir.com/FFY-U3-16S2-DL/latest/EMVA/EMVA.html).
- [PDG detector review, Cherenkov Eq. 35.5](https://pdg.lbl.gov/2024/reviews/rpp2024-rev-particle-detectors-accel.pdf).
- [Del Sarto et al. (2025): EBT-XD rate-dependence study](https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2025.1474416/full).

## Next checks

1. Obtain the film absolute dose uncertainty and rate-validation information.
2. Fix the PC/Al target relative to the camera (or flat-field it): image an LED-lit or
   beam-integrated flat to measure the light-yield map, and repeat with ≥10 pulses on one patch.
3. Dark/flat frames at gain 1 for a clean photon-transfer curve (gain in e⁻/DN).
4. Second dose level for linearity; record analogue gain in the capture JSON.
