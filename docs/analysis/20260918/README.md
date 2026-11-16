# Filament comparison — 18 September 2026

Exploratory relative collected-light comparison; no independent dose normalization.

## Method

All six comparison runs use 200 us delay and 100 us gate. Decode R16 by shifting the left-aligned 10-bit values six bits; exclude row padding; rotate 180 degrees to match the UI. Average 4x4 pixels, form a temporal median per run to suppress sparse radiation-hit specks/tracks, and fit a robust local background plane around the target.

Use the same elliptical aperture centered at binned (200,125), radii (18,27), equivalent to full-resolution (800,500) and radii (72,108). Background uses an outer ellipse of radii (43,48), excluding an inner ellipse of (25,35), with iterative 3-MAD outlier rejection. Sum signed residuals, multiplying by 16 to recover original-pixel integrated DN units. Do not clip negative residuals.

As a cross-check, subtract a median of ten off-time B2 frames at 1/100 and 100/100 us before fitting the local residual background. These are not beam-off references for each individual material. Nearby on-time frames all contain target light, so using those as dark frames would remove the signal.

| Position | Material | Frames | Net integrated DN | Relative to A1 | Off-time-subtracted DN |
|---|---|---:|---:|---:|---:|
| A1 | SUNLU transparent PETG | 85 | 33330 | 1.00 | 32966 |
| A2 | Bambu transparent brown PETG | 6 | 30471 | 0.91 | 30107 |
| A3 | SUNLU transparent orange PETG | 20 | 70966 | 2.13 | 70601 |
| B1 | IEMAI transparent ocean blue PLA | 5 | 39529 | 1.19 | 39165 |
| B2 | Bambu transparent pink PETG | 8 | 49067 | 1.47 | 48702 |
| B3 | Bambu transparent teal PETG | 8 | 13211 | 0.40 | 12847 |

Ranking remains A3 > B2 > B1 > A1 > A2 > B3 for smaller/larger apertures (radii 12/18, 18/27, 24/36). Frame-to-frame scatter is reported in comparison.json, but is not an uncertainty on intrinsic material yield: beam dose, optical alignment, thickness, dye absorption, and collection efficiency are unnormalized.

## Timing and interpretation

At 300 us gate, B2 net integrated DN is about 50,789 at delay 220 us, 1,389 at 230 us, and 618 at 250 us. At 200 us delay, gates 100/150/200/300 us give about 49,067/50,257/50,762/52,084 DN-pixels. Most collected light therefore falls within the 100 us gate; nominal optical shutoff bracket is between the 220 and 230 us start settings, subject to latency/jitter and changing beam conditions. This is not a nanosecond lifetime measurement.

The prompt signal is compatible with Cherenkov light and fast fluorescence/scintillation. Brightness rankings alone do not determine the Cherenkov fraction. Colored filament may change absorption, wavelength shifting, scattering and light extraction. A known-clear undyed reference with matched geometry, angular/spectral measurements, and independent pulse-charge or dose normalization would distinguish the mechanisms better.

The comparison image uses the same false-color scale for all six panels (0–20 net DN per 4x4-averaged pixel). It is not a spectral/color measurement. Temporal medians remove many transient sensor-hit artifacts; single-pixel maxima should not be used as the light-yield estimator.

Outputs: background_subtracted.png, frame_overview.png (58–90 DN display), timing_medians.png (0–20 net DN), comparison.json, timing.json. Reproduce with tools/analyze_laser_input.py and NumPy/Pillow.