# Handoff: web research to firm up the DoseCam noise and film numbers

> Historical request, superseded by [RESEARCH.md](RESEARCH.md), the current
> [analysis README](README.md), and the revised slide deck. The mechanism,
> film-row and uncertainty assumptions below record the original questions;
> they are not the current conclusions or instructions.

**For:** an AI assistant with web search and access to this repository
**From:** Claude (Cowork session, 2026-11-16), for Eric Martin, Duke FEL Lab
**Repo:** `FLASH\SampleTargetingAndDosimetry` (local, OneDrive) → remote
`https://github.com/EricLarueMartin/FLASH_SampleTargetingAndDisometry` (branch `main`, commit `922cb25`; Eric pushes)

## Why this exists

A slide deck and analysis comparing DoseCam (camera dosimetry) to EBT-XD film were written
without web access. Two numbers in them are placeholders that need sourced values:

1. **Camera conversion gain (e⁻/DN)**, currently given as a range "2–10 e⁻/DN". It drives the
   photon-count (shot) noise estimates.
2. **EBT-XD film absolute dose uncertainty at ~40 Gy**, currently "3 % (provisional, typical
   value)". It drives the ±3.19 % calibration uncertainty in the code and the slides.

Fix both with cited sources, update the files listed below, and report what changed.

## Background you need

- **DoseCam:** a Raspberry Pi 5 with the Raspberry Pi Global Shutter Camera (**Sony IMX296LLR**, mono,
  1456×1088, 3.45 µm pixels). It is captured through `rpicam-raw` in mode `1456:1088:10:U`
  (10-bit, stored left-aligned in 16-bit and decoded with `>> 6`), with `--gain 1`
  (analogue gain 1.0) and `--awbgains 1,1`. The exposure is an external-trigger (XTR) gate of 100 µs.
- **Measured on our data:**
  - Black level is ~60 DN.
  - Dark-frame temporal noise is **0.58 DN rms** per pixel (100 µs gate, no beam light).
  - The usable range above black is ~963 DN.
- **Target:** a 0.5 mm polycarbonate sheet backed with aluminum tape, hit by ~30 MeV electrons. The
  light is mostly Cherenkov (n ≈ 1.585), so it is blue-weighted.
- **Signal:** the fitted 2D Gaussian peak is ~42 DN and the integrated spot is ≈ 1.8 × 10⁵ DN per
  pulse, at ~40 Gy peak dose per pulse.
- **Film:** Ashland GafChromic **EBT-XD**, lot 06092501, read on a flatbed scanner 24 h
  post-irradiation by Julia Sherman. The dose statistic is the max over a 10 px window. Per-pixel
  dose noise is 1.9–2.4 %. Wells A1–A3 agree to 0.18 %, and wells B1–B2 read +3.4 % above row A.
  We suspect the scanner lateral-response artifact.

Read first: `docs/analysis/20261116_film_comparison/README.md` and the slides in
`docs/slides/2026-11-dosecam-film/index.html`.

## Research questions (cite a source for every number)

### Q1. IMX296 conversion gain at analogue gain 1.0, 10-bit (highest priority)
- Find the saturation capacity (full well, e⁻), temporal dark noise (e⁻) and QE at ~400–500 nm.
  Use EMVA 1288 data sheets from cameras built on the IMX296, for example Teledyne FLIR
  Blackfly S BFS-U3-16S2M, Allied Vision Alvium 1800 U-158m, Basler, Lucid, The Imaging Source,
  plus the Sony IMX296LLR product brief.
- Find how the **Raspberry Pi / libcamera imx296 driver** maps analogue gain 1.0 to the ADC. Is
  10-bit full scale at gain 1.0 equal to the full well, or is it clipped below it? Sources:
  the libcamera `imx296.json` tuning file, the Linux `imx296.c` driver, Raspberry Pi docs and forums.
  Note that the vendor EMVA data is often 12-bit; convert it to 10-bit DN.
- Sanity check: read noise (e⁻) ÷ e⁻/DN, combined in quadrature with 0.29 DN of quantization
  noise, should land near our **0.58 DN**. Say whether it does.
- **Deliverable:** a best estimate of e⁻/DN at gain 1.0, 10-bit, with an uncertainty range and sources.

### Q2. EBT-XD dose uncertainty at ~40 Gy
- Give the manufacturer's dynamic range and optimum range. Is 40 Gy near the top, where the
  response flattens and dose uncertainty grows?
- Give published total (absolute) dose uncertainty for EBT-XD at 20–50 Gy, for red-channel and
  multichannel readout, using a 24 h curve on a flatbed scanner.
- Give the magnitude of the **lateral response artifact** at ~40 Gy versus distance from the
  scanner centre. Could it plausibly produce a +3.4 % row-to-row offset?
- Check EBT-XD **dose-rate independence at FLASH / ultra-high dose rates** (pulsed electrons,
  ~40 Gy per µs-scale pulse). Is the film trustworthy here?
- **Deliverable:** a defensible 1σ film absolute uncertainty (%) for our conditions, with sources,
  and a one-line verdict on the B-row offset.

### Q3. Confirm the photon-statistics argument (lower priority)
- The claim: detected photo-electron counts are Poisson (Fano factor ≈ 1), because binomial
  thinning with a tiny detection probability p gives F = 1 + p(Var N/⟨N⟩ − 1). Here
  p ≈ 10⁻⁵ detected photons per beam electron per pixel. Find a textbook or paper reference for
  thinned or compound-Poisson photon counting, and say whether anything in the literature
  contradicts it for Cherenkov light.
- Find a Frank–Tamm photon yield for polycarbonate (n ≈ 1.585) in the visible band, as a reference
  for "~15 photons per electron in 0.5 mm".
- Find any known intrinsic fluorescence of polycarbonate under electron irradiation.

## Then update these files

Recompute using these formulas, with g = e⁻/DN from Q1:
- Total photo-electrons in the spot: N = 1.8 × 10⁵ × g
- Shot noise on the fitted peak (free-shape 2D Gaussian): ≈ 1.42 / √N
- Peak pixel: 1/√(42 g)
- 10×10 px window: 1/√(4200 g)
- Whole spot: 1/√N

The film-dependent numbers use these formulas:
- New calibration total = √(1.09² + film²) %
- The "Fano needed" value ≈ (1.6 % / fitted-peak shot noise)²

| File | What to change |
|---|---|
| `docs/slides/2026-11-dosecam-film/index.html` | **Slide 7 (Photon-count noise):** replace the 2–10 e⁻/DN range, the table values, and the note "Not yet measured cleanly…" with the sourced gain and recomputed numbers. Update "F ≈ 50–100" to the recomputed value. **Slide 6 (error budget):** update the "Camera — photon statistics" row. Update the "Film — absolute (~40 Gy)" row with Q2, and the B-row comment if Q2 settles it. **Slide 5:** update the "±3.2 %" KPI and its label ("1.1 % stat ⊕ 3 % film absolute (provisional)"). |
| `docs/analysis/20261116_film_comparison/README.md` | Make the same updates in the error-budget table and in the "Photon statistics and Fano factor" section. Add a **Sources** section with links. |
| `dose_cam/beam_fit.py` | Update `DEFAULT_CALIBRATION` (`err_sys_pct`, `dn_per_gy_err_pct`, and the `note` string) and the comment block above it (lines ~30–47), which says "PROVISIONAL 3.0 %". **Change code only if Q2 gives a sourced value**, and keep `dn_per_gy` = 1.0563 unchanged. |
| `AGENT.md` | Add a dated entry (newest first) listing what changed, the sources, and the status "not deployed". |

Render-check the slides after editing: open `index.html` locally, step through all 8 slides, and
check that nothing overflows. The reveal.js library is vendored in `docs/slides/vendor/`, so no CDN is needed.

## Guardrails

- **Do not deploy anything** to the Raspberry Pi (`pi-06-ioc`) and do not SSH to it. Do not touch
  motors, accelerator PVs or EPICS. These are repo edits only.
- **Do not push** to GitHub unless Eric asks you to. Committing locally is fine, with a clear
  message.
- **Mark anything uncertain as uncertain.** If sources disagree, give the range and say which one
  you used and why. Do not invent datasheet numbers. Leave a placeholder and say so instead.
- **Keep the deck brief:** change numbers and wording, and do not add slides.
- The calibration constant (1.0563 DN/Gy) and the per-pulse comparison
  (−2.3 / +2.6 / +1.1 / −1.3 %) come from measured data. They should not change.

## Report back to Eric

Send a short summary. List the gain value used (with sources), the film uncertainty used (with
sources), any changed numbers as old → new, and anything that contradicts the current slides'
conclusions. The conclusion in question: photon noise ≪ observed 2 % scatter, and the scatter is
dominated by film row offset plus target/analysis effects.
