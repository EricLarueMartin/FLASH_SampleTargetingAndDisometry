# DoseCam vs EBT-XD film — 4-pulse comparison (analysis 16 Nov 2026)

Data: `PolyAlDosCal_20261013_161112_732305_000006.raw` (4 frames, delay 200 µs, gate 100 µs,
gain 1, 10-bit), 0.5 mm polycarbonate sheet backed with aluminum tape. Background reference:
median of the 34 frames of `Alanine_20261013_145026_730724_000002.raw` (same gate, 100 µs delay,
beam outside the gate). Film: EBT-XD lot 06092501, well_041, 24 h curve, peak = max over a
10 px window (Julia Sherman, 2026-10-18/21). Frame → well order B1, A1, A2, A3 is the recorded
order and has **not** been independently confirmed.

Figures: `frames.png` (the four pulses, same colour scale, fitted 1σ/2σ ellipses),
`compare.png` (camera vs film per well). Scripts in `scripts/` (set `DOSECAM_CAPTURES`).

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
- Film A row (A1–A3) agrees to **0.18 %**; film B row (B1, B2) sits **+3.4 %** above it.
  Removing that row offset leaves 1.6 % scatter. A-row only: 1.9 % — essentially all camera-side.
- Camera A1→A3 falls monotonically (42.92 → 42.45 → 41.40 DN) while the spot centroid drifts
  ~9 px right/up.

## Where the scatter comes from (1σ, per pulse, % of dose)

| Source | Estimate | Basis |
|---|---|---|
| Photon (photo-electron) statistics, fitted peak | 0.10–0.25 % | 0.36–1.8 M photo-electrons in the spot (2–10 e⁻/DN); Fisher-matrix error of a free-shape 2D Gaussian |
| Read noise + prompt sensor hits, fitted peak | ≈0.2–0.4 % | Fit statistical error from residuals (0.05 DN ≈ 0.12 % white-noise; ~0.36 % with correlated-noise estimate) |
| Hit-masking / fit-method choice | ~1 % (mostly common-mode) | Amplitude moves 1–2 % between masking thresholds (`scripts/robust.py`) |
| Target non-uniformity (Al tape, PC, viewing angle) | ~0.5–2 % (untested) | Pixel-scale light structure ~10 % rms that does not repeat pulse to pulse (frame-to-frame correlation 0.0–0.36) |
| Gate timing | ≪ 0.5 % | Light arrives ~200–225 µs after the trigger edge, inside the 200–300 µs gate |
| Film: per-pixel noise | 1.9–2.4 % per pixel; ~0.2–0.5 % for the 10 px window peak (biased slightly high by the max) | Julia's numbers |
| Film: B-row vs A-row offset | 3.4 % (row-systematic) | Scanner lateral response or real dose difference — open question |
| Film: absolute accuracy at ~40 Gy | ~3 % (provisional) | Common-mode: moves the calibration constant, not the scatter |
| Frame ↔ well assignment | unknown | Recorded order only |

Reading: photon statistics are ~10× too small to explain anything. Film can explain the B1
outlier (row offset) but not the A-row spread, because the film A row is flat to 0.2 %. The
remaining ~1.8 % is on the camera/target side, and the evidence points to the target (moving
textured tape / PC patch) and analysis choices rather than the camera's own noise.

## Photon statistics and Fano factor

- Integrated spot signal ≈ 2π·A·σx·σy ≈ 1.8 × 10⁵ DN. IMX296 at analogue gain 1 in 10-bit mode:
  conversion gain not yet measured cleanly. Dark-frame temporal noise 0.58 DN (→ ~4–5 e⁻/DN if
  read noise ~2 e⁻); a sensor-class ~10 ke⁻ full well over 963 DN gives ≤ 10 e⁻/DN. A photon-transfer
  attempt on these four frames is dominated by prompt sensor hits and target texture and only
  brackets the gain loosely (≈1.5–6 e⁻/DN). All conclusions hold anywhere in 2–10 e⁻/DN.
- Per pixel at the peak (42 DN ≈ 90–420 e⁻) shot noise is 5–11 %; a 10×10 px window 0.5–1.1 %;
  the whole-spot Gaussian fit 0.1–0.25 %.
- Fano factor: the light is mostly Cherenkov in PC (n ≈ 1.585; ~15 visible photons per electron
  in 0.5 mm, Poisson per electron). Each pixel collects ~10⁻⁵ detected photons per beam electron
  (~10⁷ electrons cross the area one pixel sees at 40 Gy). Binomial thinning gives
  F = 1 + p·(Var N/⟨N⟩ − 1), so F − 1 ≲ 10⁻⁴ even if the per-electron yield were strongly
  super-Poisson (Landau-like scintillation). Photo-electron generation by visible photons is
  Poisson. **F = 1 to well below the percent level**; to explain the observed 1.5–1.8 % camera
  spread with photon noise would need F ≈ 50–100.
- The non-Poisson term that does matter is prompt radiation hits on the sensor: 2.6 % of pixels
  in beam-gated frames sit > 20 DN above their 5×5 median, vs 0.03 % with the gate 100 µs early.
  They are masked in the fit; the mask choice is the ~1 % method systematic above.

## Next checks

1. Confirm the frame ↔ well order (time stamps or a deliberate skip pulse).
2. Ask Julia about scanner lateral-response correction for the B row and a film dose uncertainty.
3. Fix the PC/Al target relative to the camera (or flat-field it): image an LED-lit or
   beam-integrated flat to measure the light-yield map, and repeat with ≥10 pulses on one patch.
4. Dark/flat frames at gain 1 for a clean photon-transfer curve (gain in e⁻/DN).
5. Second dose level for linearity; record analogue gain in the capture JSON.
