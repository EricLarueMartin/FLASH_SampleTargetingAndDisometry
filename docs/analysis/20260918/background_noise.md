# Gate-width background and temporal noise

Analysis of 544 B2 RAW frames across 17 runs. All values are 10-bit digital counts (DN), not electrons. Unpack left-aligned RAW with a six-bit shift; discard row padding; rotate 180 degrees. Reproduce with `tools/analyze_background_noise.py`. Detailed per-frame and per-run results: `background_noise.json`.

## Literature

- [Raspberry Pi IMX296 external trigger documentation](https://www.raspberrypi.com/documentation/accessories/camera.html#external-trigger-on-the-global-shutter-camera): exposure equals actual XTR low pulse duration plus **14.26 microseconds**. Here actual pulse duration is assumed equal to the configured ESP width; no precision timing measurement accompanies the files.
- [Raspberry Pi/libcamera black-level correction](https://patchwork.libcamera.org/patch/17459/): IMX296 black level is **60 in 10-bit**. This is a pedestal, NOT 60 counts of ambient light and NOT 60 counts RMS noise. Actual black baseline can differ slightly with camera conditions.
- [FLIR IMX296 EMVA measurements](https://softwareservices.flir.com/FFY-U3-16S2/latest/EMVA/EMVA.html): at 20 C, mono camera temporal dark noise is 0.45 DN (4.81 electrons), with gain 10.78 electrons/ADU and 10-bit ADC. This independently agrees in order of magnitude with the measured floor. It is a different camera implementation, not a calibration of this camera's gain or dark current; do not transfer its electron conversion uncritically.
- [EMVA 1288 linear standard](https://www.emva.org/wp-content/uploads/EMVA1288Linear_4.0Release.pdf): exposure-dependent dark signal requires dark acquisitions; noise variance and mean must be treated separately.

## Cleanest comparison: fixed delay 200 microseconds, same B2 target

Background patch immediately left of the target, display coordinates x=560:680, y=380:620 (28,800 full-resolution pixels). Mean uses spatial outlier rejection per frame, then an arithmetic mean across all frames: bright lighting phases are retained, particle-hit outliers rejected.

| Gate (us) | Exposure (us) | Frames | Mean RAW DN | Above nominal 60 | Frame-mean SD (DN) | Residual pixel RMS (DN) |
|---|---|---|---|---|---|---|
| 100 | 114.26 | 8 | 60.275 | 0.275 | 0.422 | 0.487 |
| 150 | 164.26 | 22 | 60.400 | 0.400 | 0.358 | 0.539 |
| 200 | 214.26 | 26 | 60.588 | 0.588 | 0.374 | 0.596 |
| 300 | 314.26 | 4 | 60.812 | 0.812 | 0.183 | 0.661 |

Equal-weight regression of these four run means:

    mean background DN = 59.969 + 2.726 * exposure_ms
    residual variance DN^2 = 0.128 + 1.003 * exposure_ms

Thus the exposure-independent residual RMS extrapolates to 0.357 DN, versus 0.487 DN measured at gate100. These are exploratory intercepts, not calibrated read-noise specifications. The exposure-dependent variance is about half the measured gate100 near-target variance; removing illumination would not remove the fixed floor. Only four frames constrain the widest gate, and illumination phase/drift is not controlled.

Two other patches (x160:400,y160:400 and x1040:1280,y720:960) give mean slopes 5.084 and 2.063 DN/ms, respectively; zero-exposure noise intercepts 0.455 and 0.496 DN RMS. Regional dependence is consistent with scene illumination, but not enough to isolate dark current. A reasonable description of the effective independent-pixel floor is roughly **0.35-0.5 DN RMS**. It includes read/conversion and quantization noise, potentially residual artifacts; correlated noise has been removed, not measured by this floor.

## Supporting width groups, all B2 delays pooled

| Gate (us) | Frames | Near-target mean DN | Residual pixel RMS DN |
|---|---|---|---|
| 50 | 116 | 60.087 | 0.457 |
| 100 | 18 | 60.204 | 0.480 |
| 150 | 22 | 60.400 | 0.539 |
| 200 | 26 | 60.588 | 0.596 |
| 300 | 29 | 60.803 | 0.647 |
| 400 | 5 | 61.127 | 0.690 |
| 500 | 328 | 62.767 | 0.713 |

The early 500-us series is inconsistent with the near-target trend and the scene/target position differs; it must not anchor a single near-target slope. Its distant lower-right patch is 61.177 DN, continuing the general increasing-background trend. Pooling delays is secondary evidence, not a controlled exposure experiment.

## Noise estimator and limitations

Disjoint adjacent-frame differences remove stable fixed-pattern noise. Within each 16x16 block, subtract the difference median to remove local common-mode brightness changes, reject large difference outliers, and divide difference variance by two. Average pair variances before taking the square root. Uses full-resolution pixels, not the earlier 4x4 image cache. Five-sigma-style clipping uses a preliminary central standard deviation with a 0.5-DN minimum; this is a robust practical estimate, not a formal EMVA-compliant measurement. It excludes radiation-hit tails and spatially coherent fluctuations. Pair correlations or structured noise can bias the independent-noise estimate.

Distant upper-left/lower-right frame means correlate at r=0.955-0.996 in the 100/150/200-us fixed-delay runs. Near-target frame means fluctuate by approximately 0.36-0.42 DN RMS in those runs, despite averaging 28,800 pixels. Independent pixel noise would average to only about 0.003 DN, so these changes are strongly coherent. PWM/lighting flicker is plausible, but a global electronic black-level fluctuation can also produce coherence. No PWM frequency can be inferred confidently from these records.

Model: mean = offset + (light + dark-current rate)*exposure. Variance additionally contains read/conversion/quantization noise, photon/dark shot noise, coherent lighting/electronic fluctuations, and occasional radiation hits. The width sweep identifies an exposure-dependent component but **cannot separate light from leakage current**, or read noise from ADC noise, without additional controls. No defensible electron-per-second dark-current number follows from these data. Pedestal subtraction alone does not remove noise.

## Follow-up measurement

At unchanged gain, aperture and approximately constant temperature, collect roughly 50-100 frames at each width with lens capped, beam off; repeat lens open with lights off and lights on. Randomize/interleave widths to reduce drift and PWM phase bias. Dark mean/variance versus exposure isolates dark current and the fixed floor; longer capped exposures may be needed to resolve small leakage current. Open-minus-capped isolates optical background. Compare capped frame-wide fluctuations to distinguish electronic common-mode changes from lighting. Beam-on capped controls can separately assess radiation-related sensor events. No hardware settings were changed for this analysis.
