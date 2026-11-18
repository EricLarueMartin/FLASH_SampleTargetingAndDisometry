# DoseCam vs EBT-XD film — 4-pulse comparison (analysis 16 Nov 2026)

Data: `PolyAlDosCal_20261013_161112_732305_000006.raw` (4 frames, delay 200 µs, gate 100 µs,
gain 1, 10-bit), 0.5 mm polycarbonate sheet backed with aluminum tape. Background reference:
median of the 34 frames of `Alanine_20261013_145026_730724_000002.raw` (same gate, 100 µs delay,
beam outside the gate). Film: EBT-XD lot 06092501, well_041, 24 h curve, reported
peak doses supplied by Julia Sherman (2026-10-18/21). On 2026-11-18 Eric supplied
`Film41_Scintillation.xlsx`: it contains intensity standard deviations, not a
complete dose-uncertainty budget. This supersedes the earlier assumption that
1.9–2.4% represented supplied standard dose uncertainties. The slide uses **~3%
(k = 1) only as a literature benchmark**, not a verified uncertainty for these
40 Gy measurements; see [workbook audit and published budgets](RESEARCH.md#workbook-audit-and-absolute-dose-uncertainty-2026-11-18).
Frame → well order **B1, A1, A2, A3** is taken as correct for this comparison
(per E. Martin, 2026-11-16).

Figures: `frames.png` (the four pulses, same colour scale, fitted 1σ/2σ ellipses),
`compare.png` (camera vs film per well). Scripts in `scripts/` (set `DOSECAM_CAPTURES`).

## Research update — 2026-11-16

[Review of the error sources, production re-fits and primary literature](REVIEW_uncertainties.md).
The review of revision `2323b09` gives the threshold sensitivity for the production
fitter, the scope of the four-shot comparison, and the HIGS alanine and OSLD results.

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
nested model `be8cead4-aaac-45fb-b7e0-ac6393ba87d1.f3d`, member
`FusionAssetName[Active]/Previews/big.png`. The archive identifies FLASH Core XY,
version 23, created 17 November 2026 at 18:15 EST. The 1024×1024 image is copied byte for byte
to the deck's `img/corexy_cad.png`; SHA-256:
`61e1e402747028d2de66927c96650e4e73b30828b68a814704044025d1e1c63e`.
The slide crops surrounding white space for display. It is a CAD preview of
the rail/belt assembly and three holders, not an installed-stage photograph.
The updated model includes the user's MakerBeam dummy and linked
`LM8UUonMakerBeamXL` v3 bracket component. Bracket fit and strength have not
been assessed for the presentation. The repository CAD matches the updated
`FLASH/FLASH Core XY.f3z` export byte for byte; archive SHA-256:
`34c3a2f023a999bdfcf550c61bba87ddbf163a7a9297ad3eabb01be80cceda88`.
Containment inside a frame and reduced susceptibility to bumps
are the user's design goals, not measured performance claims. CoreXY is the
belt-kinematics name; physical user coordinates remain X and Z.

### CoreXY torque estimate

Slide 6 uses an **itemized moving-mass estimate of 2.42936 kg**, rounded to
**2.43 kg**, from the components listed by E. Martin. The shifted holder group
is **0.814 kg** and the balanced moving hardware is **1.61536 kg**. The
user-reported printed bearing brackets contribute 24 g in total. Small
hardware allowances are identified below.

For the endpoint torque budget, use the user's centre-of-mass model: the
three holders, their tubes/mice and the two rail carriages form one shifted
group, shared approximately **70/30** at maximum displacement. All other
listed moving hardware is balanced and shared **50/50**. This is the requested
endpoint-reaction planning approximation; the actual assembly has not been
weighed or tested for running torque.

#### Shifted holder group

| Component | Count | Planning mass each | Combined mass | Basis |
|---|---:|---:|---:|---|
| Printed holders | 3 | 75 g | 225 g | E. Martin's estimate and geometry check below |
| Adult mice | 9 | 30 g | 270 g | [JAX C57BL/6J body-weight data](https://www.jax.org/jax-mice-and-services/strain-data-sheet-pages/body-weight-chart-000664): 12-week males average 29.3 ± 2.3 g |
| Empty 50 mL plastic tubes with caps | 9 | 15 g | 135 g | [SARSTEDT 62.548.101](https://sustainability.sarstedt.com/en/US/c/life-science/sample-handling/reagent-and-centrifuge-tubes/p/screw-cap-tubes-with-conical-base/62.548.101): product weight 14.9 g, rounded to 15 g |
| MGN15H rail carriages | 2 | 92 g | 184 g | [HIWIN technical catalog](https://hiwin.com/wp-content/uploads/2026/08/HIWIN-Linear-Guideway-Catalog-1.pdf#page=91), printed p. 88 / PDF p. 91: block weight 0.092 kg |
| **Shifted group** | | | **814 g = 0.814 kg** | |

The mouse value is a representative adult planning assumption. JAX's same
reference gives 12-week females 21.7 ± 1.5 g and 24-week males 35.3 ± 3.9 g.
Tube and carriage masses use reference models; the actual installed models
and animal cohort are not identified. Counts follow the user's configuration.

#### Balanced moving hardware

| Component | Quantity | Mass basis | Combined mass | Source / status |
|---|---:|---:|---:|---|
| MakerBeamXL extrusion | 1200 mm total | 0.297 g/mm | 356.4 g | [MakerBeam manufacturer specifications](https://www.makerbeam.com/blogs/makerbeam/specifications-makerbeam-and-openbeam/) for the 15 × 15 mm XL profile |
| MGN15 rail | 1000 mm | 1.06 kg/m | 1060 g | [HIWIN catalog](https://hiwin.com/wp-content/uploads/2026/08/HIWIN-Linear-Guideway-Catalog-1.pdf#page=91), same table as the MGN15H blocks |
| Small GT2 idler pulleys | 4 | 5 g allowance each | 20 g | Rounded reference allowance; a [Purecrea 20-tooth, 6 mm belt-width idler](https://www.bastelgarage.ch/gt2-idler-pulley-for-20-teeth-3mm-bore) is listed at 3.7 g; actual pulley model unconfirmed |
| 2GT belt | 3.2 m | Assume 6 mm width; 1.3 g/(mm width × m length) | 24.96 g | [Gates U508 unit-mass table](https://www.gates.com/content/dam/documents-library/catalogs/U508-manual-kr.pdf); 3.2 × 6 × 1.3 |
| LM8UU bearings | 4 | 17 g each | 68 g | [ISK manufacturer specification](https://iskbearing.com/product-details/lm8uu), 8 × 15 × 24 mm |
| Printed bearing brackets | All | 24 g total | 24 g | E. Martin's reported printed mass |
| MakerBeamXL steel L / right-angle brackets | 4 | 13 g reference allowance each | 52 g | [OEM steel bracket, article 101732](https://www.makerbeam.com/makerbeam-makerbeam-xl-right-angle-bracket-12p.html); [distributor product datasheet](https://www.berrybase.at/en/product-datasheet/019bc1e6847770ffa036fba1d40740db/create) lists 13 g for the 45 × 45 × 1.5 mm bracket; actual bracket variant unconfirmed |
| Additional fasteners | All | 10 g allowance | 10 g | Planning allowance for the user's additional few grams |
| **Balanced hardware** | | | **1615.36 g = 1.61536 kg** | |

These quantities comprise the user's listed moving hardware. The rail is
counted once in the balanced group, and its two carriages once in the shifted
group. The complete estimated moving mass is therefore
`0.814 + 1.61536 = 2.42936 kg`.

#### Endpoint load and torque calculation

For support span `L` and shifted-group COM at `x` from the far support,
moment balance gives `R_near=m_s*g*x/L` and
`R_far=m_s*g*(1-x/L)`. The user's 70/30 estimate corresponds to `x=0.70*L`.
With balanced mass `m_b` and shifted mass `m_s`, use:

- Heavier side: `m_near=m_b/2+0.70*m_s = 1.37748 kg-equivalent`.
- Lighter side: `m_far=m_b/2+0.30*m_s = 1.05188 kg-equivalent`.

Their sum is the complete **2.42936 kg** moving mass. The endpoint forces are
approximately **13.51 N and 10.32 N**.

Using `g=9.80665 m/s²`, CAD belt-path radius `r=0.00638 m`, assumed drive
efficiency `eta=0.80` and the requested **2× margin**, calculate
`T_required=2*m_equivalent*g*r/eta`:

| Motor side | Gravity torque before margin | Required torque with 2× margin |
|---|---:|---:|
| Heavier | 0.107730 N·m | **0.215460 N·m**, rounded to **0.22 N·m** |
| Lighter | 0.082265 N·m | **0.164531 N·m**, rounded to **0.16 N·m** |

Against the **0.45 N·m rated holding** reference, the heavier side has
approximately **4.18× static gravity margin**, provided the actual phase
excitation delivers that holding torque. Acceleration, additional drag, belt
preload and motor/driver speed-torque performance remain to be checked.
Changing the mouse assumption from 30 g to 20–40 g each changes the heavier
motor's 2× requirement by about ±0.0099 N·m with the balanced inventory fixed.
Small hardware allowances are much less influential than the rail and profile
masses. These are gravity-load estimates, not measured running payload ratings.

#### Motor and driver reference

Per E. Martin, assume **STEPPERONLINE 17HS15-1504S-X1**. Its
[manufacturer specifications](https://www.omc-stepperonline.com/3pcs-nema-17-bipolar-45ncm-63-74oz-in-1-5a-42x42x39mm-4-wires-w-1m-pin-connector-3-17hs15-1504s-x1)
and [datasheet](https://omc-stepperonline.com/download/17HS15-1504S-X1.pdf) give
**45 N·cm = 0.45 N·m rated holding torque at 1.5 A/phase**. The purchased driver
is the [EASON TB6600 module](https://www.amazon.com/dp/B08SG7L54W), with the
user-specified **12 V / 5 A supply**. Its label includes a 1.5 A current setting;
actual phase-current calibration and standby behaviour are unverified.

The exact motor's [manufacturer torque–speed curve](https://files.omc-stepperonline.com/17HS15-1504S-X1_Torque_Curve.pdf)
states **DM542T, 24 V, 1.69 A and 2000 pulses/revolution**. It is a speed sweep
under those conditions, which differ from the 12 V EASON setup. The rated
holding reference does not establish available running torque or a speed limit.
No private purchase receipts or account details are published.

Holder mass cross-check: the user supplied surface area `A=55,227 mm²`, solid
CAD volume `V=98,627 mm³`, two walls of `0.45+0.42=0.87 mm`, and 15% infill.
A first-order equivalent uniform shell gives `V_shell≈A*t=48,047 mm³` and
`V_plastic≈V_shell+0.15*(V-V_shell)=55,634 mm³` (55.6 cm³). At an **assumed**
plastic density of 1.2–1.3 g/cm³ this is roughly **67–72 g per holder**. This
is only a rough consistency check: real top/bottom skins, overlapping shells,
geometry, supports and slicing rules can change the result. The slide retains
the user's approximately 75 g planning estimate, rather than claiming a
measured or slicer-calculated mass.

### Existing Run GUI example

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

## Uncertainty and sensitivity summary

| Source | Estimate | Basis |
|---|---|---|
| Camera peak fit, combined statistics | **0.35–0.39% nominal 1σ** | Residual-scaled covariance of the archived fits; photon, read/background and other residual noise are already included. No separate photon/read term is added; see the [audit](scripts/fit_noise_audit.json) |
| Hit-masking / fit-method choice* | ~1 % sensitivity | Amplitude moves 1–2 % between masking thresholds (`scripts/robust.py`); a common scale shift is absorbed by calibration against film |
| PC / Al-tape target | Likely nonuniform; contribution unmeasured | Tape surface, contact and local reflectivity can vary. The ~9 px spot drift can sample a different optical response; no quantitative target uncertainty has been established |
| Gate timing | Not expected to contribute appreciably | Operator scanned delay and duration to full-signal plateaus, then selected operating margins much larger than expected jitter; no numerical percent bound assigned |
| Film dose reference | **~3% (k = 1) literature benchmark** | The workbook supplies intensity SD, not the complete dose uncertainty. A published EBT-XD budget gives ~2.8% excluding delivery stability; protocol dependent, not verified at our 40 Gy. See [audit and sources](RESEARCH.md#workbook-audit-and-absolute-dose-uncertainty-2026-11-18) |
| Film rate response | Mixed evidence; minor caveat | Studies disagree within different tested conditions; no rate-related bias is established for this run. See [research](RESEARCH.md#5-ebt-xd-at-40-gy) |

*Variation from choosing different masking/fit procedures can be eliminated by
using one standard procedure for camera calibration against film and all
subsequent measurements.

The camera fit term is one combined contribution, not the quadrature sum of
the empirical covariance and the component model checks below. Masking-method
sensitivity and target nonuniformity are not established independent random
terms, so no total is formed by summing these rows. No film-row effect is
assigned or subtracted. A film-calibration scale error is shared across the
wells: it affects the absolute DoseCam calibration, not independent well-to-well
scatter. Do not add a whole published film uncertainty budget to the workbook
intensity SD; their reading/nonuniformity contributions can overlap.

## Camera peak-fit error and noise accounting

The current fitter minimizes unweighted DN residuals with a `soft_l1` robust
loss; it does **not** assign each pixel a Poisson-plus-read variance. Its reported
parameter covariance uses the plain model Jacobian at the solution:
`C = s² * inv(J.T @ J)`, where `s² = sum(residual²)/(N_pixels-7)`.
The fitted peak's nominal standard error is `sqrt(C[0,0])`. The ROI-border
noise estimate is used for the reported reduced-chi-squared diagnostic, not
as a pixel weighting map. Source: `dose_cam/beam_fit.py`, `fit_gaussian()` and
`_param_errors()`.

Reconstructing exactly this covariance from the archived four baseline-fit
parameters, ROI dimensions and residual RMS gives:

| Well | Fitted peak (DN) | Nominal peak SE (DN) | Relative SE | Recorded reduced chi-squared |
|---|---:|---:|---:|---:|
| B1 | 42.2357 | 0.1602 | 0.379% | 1.2519 |
| A1 | 42.9171 | 0.1664 | 0.388% | 1.2262 |
| A2 | 42.4502 | 0.1480 | 0.349% | 1.0593 |
| A3 | 41.4009 | 0.1531 | 0.370% | 1.0006 |

No new peak fit or calibration is performed. See the reproducible
[audit script](scripts/fit_noise_audit.py), [machine-readable audit](scripts/fit_noise_audit.json)
and [peak-error CSV](scripts/peak_fit_uncertainty.csv). These errors correspond
to the same archived amplitudes shown on the comparison slide. No separate
correlation correction is applied to this nominal covariance.

This covariance is an **independent-pixel approximation**, not an exact
robust-estimator/spatial-covariance calculation. It also does not jointly
propagate the polynomial-baseline fit. Hence the slide calls these errors
**nominal 1σ**, rather than a validated full camera accuracy.

### Component checks, not additional budget terms

At the **10.7 e-/DN gain proxy**, the four fitted spots contain **1.82–2.04
million signal electrons**, over equivalent Gaussian areas `2*pi*sx*sy` of
approximately **3970–4482 pixels**. Peak pixels contain approximately
**443–459 electrons**, with **1.97–2.00 DN** photon RMS. The full 1.58-million
pixel sensor area is not the area occupied by the beam spot.

For a linearized plain least-squares amplitude influence vector
`h = J * inv(J.T @ J) * e_A`, propagate photon variance as
`u_A,ph² = sum(h_i² * signal_i/gain)`. This gives **0.121–0.127%** peak SE,
including the free spot-shape parameters. It is different from the ideal
Poisson-weighted information floor in the next section.

The 34 no-beam Alanine frames give **0.5078 DN pixel RMS** using the existing
four-iteration 3.5-sigma-clipped consecutive-pair variance method. This is a
measured background/dark value including quantization and correlated
background, not a pure electronic-read-noise calibration. Its independent-white
pixel projection would be only approximately **0.036–0.038%** peak SE.
Projection of the actual frames after the same 40 DN positive-hit despiking
and quadratic baseline subtraction instead gives **0.124–0.133%** peak SE,
showing the importance of spatial/temporal structure.

Combining those conditional photon and measured-background projections gives
approximately **0.18%** as a diagnostic. They do not uniquely partition the
observed signal-frame residuals: gain is a manufacturer-camera proxy, the
background sample is finite and taken with the beam outside the gate, and
conditioning/model residuals add other effects. **None of these diagnostic
values is added to the 0.35–0.39% empirical fit-covariance contribution.**

## Photon-count noise

Use **10.7 e-/DN** as a proxy from the Teledyne FLIR monochrome IMX296 EMVA data,
with **8–12 e-/DN** as an engineering sensitivity interval. The manufacturer
reports a 10-bit ADC, 10,276-electron saturation and 4.69-electron read noise.
Our gain is not measured. The rechecked background RMS is 0.508 DN and already
includes quantization and correlated background; no separate quantization term
is added to it. A photon-transfer curve is still required to calibrate gain.

For the measured 180,000 DN integrated spot, N = 1.926 million electrons. Shot
noise is 4.72% on a 42 DN peak pixel, 0.472% for an ideal constant-peak 10 x 10
camera window, and 0.072% for the whole spot. The ideal Poisson-weighted
free-shape Gaussian peak floor is 1.42/sqrt(N) = **0.102%**; over g = 8–12
it is **0.097–0.118%**. These idealized values are context, not additional
contributions to the residual-based fit error used on the slide.

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
