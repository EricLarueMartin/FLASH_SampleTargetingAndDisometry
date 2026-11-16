# Target test — 1 October 2026

Exploratory spot-shape analysis of a 0.5 mm polycarbonate sheet backed with
aluminum tape, and a few-mm scintillator of unknown type backed with Rosco black
wrap. Both runs: 200 µs delay, 100 µs gate. No dark frames, dose normalization,
mm scale or viewing-angle correction yet.

Figure: `spot_shape_20261001.png`. Numbers: `summary_20261001.json`.

## Runs

| Run | Target | Delay/gate (µs) | Frames | Used |
|---|---|---|---:|---|
| `Scint/run_20261001_194704_633291_000002` | scintillator | 200/100 | 165 | main |
| `Al_PC/run_20261001_194433_457037_000001` | PC + Al | 200/100 | 138 | main |
| `Al_PC/run_20261001_195317_467474_000005` | PC + Al | 220/100 | 112 | cross-check |
| `scint/run_20261001_195109_910461_000003` | scintillator | 200/50 | 22 | no spot in any frame |
| `scint/run_20261001_195132_973084_000004` | scintillator | 220/50 | 133 | not analysed further |

## Method

R16 decode as in 20260918: shift the left-aligned 10-bit values down six bits,
drop the row padding, rotate 180°. Per-pulse amplitude comes from a fixed-shape
Gaussian matched filter. Shapes come from free 2D rotated-Gaussian fits.

The target was moved during both main runs, and the amplitude series shows
smooth ramps rather than random beam-off frames (figure panels e and f).
Frames with the target out of the beam are used as the background reference.
That is a target-out reference, not a dark frame. Scintillator: 76 of 165
frames well hit. PC: 67 well-placed frames, and the first ~48 frames show no
spot.

## Results

**Scintillator, per pulse** (76 well-hit frames, median ± MAD):

- σ 34.3 × 19.0 px (FWHM 81 × 45 px), axis 72.7° ± 0.9°.
- Pulse-to-pulse σ scatter ±0.57 px (about 2–3%).
- Centroid scatter 1.2 px in x and 3.0 px in y. That includes real
  beam/target motion, so it is an upper bound on the measurement error.
- Integrated light varies ±5% pulse to pulse.
- Peak 206 DN raw over a 60.3 DN black level, so 146 DN net = **15% of the
  ADC range above black**. The maximum peak was 226 DN raw. The 630–680 DN frame
  maxima are single-pixel sensor hits, not spot light.
- Matched-filter single-shot S/N ≈ 70.

**Polycarbonate**:

- Mean of 67 pulses: peak 1.36 DN net, σ 34 × 20 px, 75°.
- The 220 µs run gives 1.49 DN and 31 × 19 px at 73°.
- Same position and shape as the scintillator spot, so both targets are
  imaging the beam, not a target artifact.
- ~~Single-shot S/N ≈ 9~~ — superseded 2026-10-02. With a hit-clipped reference,
  row destriping and hit masking, single-pulse amplitude S/N ≈ 71 (null-frame
  scatter) and widths to ±0.3–0.5 px. See the pulse-by-pulse report below.
- PC peak light ≈ 1.1% of the scintillator.

**Edge glow**: the scintillator's polished edges light up strongly from light
piping. Keep the analysis region away from them, or blacken the edges.

## Exposure projection for FLASH (10–20× light)

- **Scintillator**: 146 DN net would become 1,460–2,920 DN, above the 963 DN
  range. To keep the peak at ≤ 60% of range, reduce collected light 2.5–5×
  (about 1.3–2.3 stops). Do not set the aperture from frame maxima; they are
  sensor hits.
- **PC**: 1.4 DN would become 14–28 DN. If noise-limited, single-shot S/N would
  be about 90–180, enough for per-pulse shape. The aperture choice conflicts
  between the two targets.

## Still needed

- Dark frames at the same mode, delay and gate, lens capped, ~100 frames, to
  separate black level, row banding and hot pixels from room light.
- A pixel scale and viewing-angle correction. The scintillator outline is a
  skewed quadrilateral, so the camera views the target obliquely and the
  ellipse is partly projection. Photograph a printed grid at the target plane.
- Analog gain is not recorded in the capture JSON; add it.

Scripts: `../../../tools/analyze_20261001_targets.py` (survey / look / full
stages, run on the Pi), `scripts/pc_check.py`, `scripts/pc_blocks.py`,
`scripts/singleshot.py`, `scripts/make_figure.py`. Raw intermediate arrays are
in the git-ignored `dose_cam/captures/analysis/20261001/`.

## Pulse-by-pulse analysis (added 2 October 2026)

Report: `DoseCam_pulse_analysis_20261001.pdf`, covering the scintillator, the polycarbonate
with a full background budget, and a comparison of the two on the same beam.

- `pulse_fits/`: scintillator, 73 fully-on pulses. Heatmap and residual contact sheets,
  goodness-of-fit charts, one image per pulse, CSV, scripts.
- `pc_fits/`: polycarbonate, 56 pulses (200 µs) + 112 (220 µs) + 42 null frames, plus
  background figures, the same per-pulse outputs, CSV, scripts.
- `profile_comparison_20261001.png` and `comparison/`: identical processing of both mean
  spots.

Key results (status: verified on this data set, no dark frames yet):

- The two targets give the same spot to a few percent: σ 34.8 × 18.9 px (scintillator) vs
  34.0 × 19.2 px (PC 3 min earlier), angle 73.3° vs 72.6°. That is less than the beam's
  own drift between the two PC runs, 4% / 10% over 9 min.
- Scintillator: the Gaussian explains 99.5% of the variance inside 3σ. There is a
  systematic misfit of about 2% of peak, the same in every pulse: a skew across the
  short axis.
- PC: χ²ᵥ 1.02 / 0.99 against a background-only floor of 1.00.
- Background: pedestal bursts of 0.6–1.0 DN in 9–13% of frames. Target-out frames carry
  about 17× more radiation hits, so a plain-mean reference would be biased by +0.16 DN;
  the reference is now hit-clipped. About 0.13 DN of correlated background remains
  unattributed.
