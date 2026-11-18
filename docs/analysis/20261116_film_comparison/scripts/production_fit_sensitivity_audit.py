"""Read-only sensitivity audit of the four archived DoseCam calibration shots.

Requires NumPy and SciPy. Prints JSON to stdout; never changes captures, fits,
calibration, or application files. Reuses dose_cam.beam_fit conditioning and
fitting, holding the archived ROI fixed and changing only the despike threshold.

Example (the existing Anaconda Python includes SciPy):
  python production_fit_sensitivity_audit.py --captures PATH_TO_BACKUP

Spatial block-score results are diagnostics, not validated coverage intervals:
the single-frame residual contains both random noise and fixed model errors.
The approximate M-estimator sandwich uses the soft-L1 score and its derivative,
with a Gauss-Newton bread (no second-model-derivative Hessian term). It conditions
on the estimated baseline and does not propagate its estimation uncertainty.
"""

import argparse
import csv
import importlib.util
import hashlib
import json
import math
from pathlib import Path
import re
import time

import numpy as np
import scipy


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/analysis/20261014/crosscal_fits_PolyAlDosCal_000006.csv"
CAPTURE = "PolyAlDosCal_20261013_161112_732305_000006.raw"
# Supplied Film41 workbook, ROI mapping B1=4, A1=1, A2=2, A3=3.
FILM_GY = np.array([40.937639, 39.612909, 39.745937, 39.702168])


def read_frames(path):
    raw = np.memmap(path, dtype="<u2", mode="r")
    n = raw.size // (1088 * 1472)
    raw = raw[:n * 1088 * 1472].reshape(n, 1088, 1472)[:, :, :1456]
    return (raw[:, ::-1, ::-1] >> 6).astype(np.float32)


def model_parameters(fit):
    return np.array([fit[key] for key in
                     ["amplitude_dn", "center_x", "center_y", "sigma_x", "sigma_y"]]
                    + [math.radians(fit["theta_deg"]), fit["offset_dn"]])


def model_jacobian(beam, p, X, Y):
    columns = []
    for k in range(len(p)):
        step = 1e-4 * max(1.0, abs(p[k]))
        delta = np.zeros_like(p)
        delta[k] = step
        columns.append(((beam._gauss2d(p + delta, X, Y)
                         - beam._gauss2d(p - delta, X, Y)) / (2 * step)).ravel())
    return np.stack(columns, axis=1)


def block_scores(beam, sub, fit, x, y):
    p = model_parameters(fit)
    ny, nx = sub.shape
    Y, X = np.mgrid[y:y + ny, x:x + nx].astype(float)
    J = model_jacobian(beam, p, X, Y)
    residual = (beam._gauss2d(p, X, Y) - sub).ravel()
    f = 5.0
    psi = residual / np.sqrt(1 + (residual / f) ** 2)
    psi_prime = (1 + (residual / f) ** 2) ** -1.5
    bread = J.T @ (psi_prime[:, None] * J)
    amplitude_direction = np.linalg.solve(bread, np.eye(7)[0])
    influences = ((J @ amplitude_direction) * psi).reshape(ny, nx)
    yy, xx = np.mgrid[:ny, :nx]
    diagnostics = []
    for width in [1, 8, 16, 32]:
        phases = [0] if width == 1 else [0, width // 2]
        values = []
        for dx in phases:
            for dy in phases:
                bx, by = (xx + dx) // width, (yy + dy) // width
                ids = (by * (int(bx.max()) + 1) + bx).ravel()
                scores = np.bincount(ids, weights=influences.ravel())
                se = math.sqrt(float(scores @ scores))
                values.append({"phase_xy": [dx, dy], "SE_DN": se,
                               "SE_percent": 100 * se / p[0]})
        diagnostics.append({"block_width_pixels": width, "phases": values})
    # A nominal score at an optimum is close to zero. This scalar is a useful
    # stationarity diagnostic in the peak-amplitude direction, not a correction.
    return {"amplitude_direction_total_score_DN": float(influences.sum()),
            "diagnostics": diagnostics}


def calibration_summary(amplitudes):
    k = float(np.mean(amplitudes) / np.mean(FILM_GY))
    residual = 100 * (np.array(amplitudes) / k / FILM_GY - 1)
    return {"DN_per_Gy_refit_same_four_pairs": k,
            "camera_minus_film_percent": residual.tolist(),
            "in_sample_residual_sample_SD_percent": float(np.std(residual, ddof=1)),
            "in_sample_residual_RMS_percent": float(np.sqrt(np.mean(residual ** 2)))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--thresholds", nargs="+", type=float,
                        default=[20, 30, 40, 50, 60])
    parser.add_argument("--skip-blocks", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    spec = importlib.util.spec_from_file_location("beam_fit_audited", ROOT / "dose_cam/beam_fit.py")
    beam = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(beam)
    rows = [r for r in csv.DictReader(SOURCE.open(encoding="utf-8"))
            if r["background"] == "baseline"]
    frames = read_frames(args.captures / CAPTURE)
    assert len(rows) == len(frames) == len(FILM_GY) == 4
    result = {"source": str(SOURCE.relative_to(ROOT)), "capture": CAPTURE,
              "software": {"numpy": np.__version__, "scipy": scipy.__version__},
              "sha256": {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name:
                         hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in [SOURCE, ROOT / "dose_cam/beam_fit.py", args.captures / CAPTURE]},
              "film_Gy_B1_A1_A2_A3": FILM_GY.tolist(),
              "procedure": "Current beam_fit.despike/full image, archived fixed ROI, quadratic border baseline, current fit_gaussian soft_l1 f_scale=5.",
              "caveat": "Recalibration and residuals use the same four pairs, not independent validation. Block-score residuals mix random and fixed structure; no validated statistical interval or quadrature increment is implied.",
              "variants": []}
    for threshold in args.thresholds:
        fits = []
        for index, (frame, row) in enumerate(zip(frames, rows)):
            nx, ny, x, y = map(int, re.fullmatch(r"(\d+)x(\d+)@\((\d+),(\d+)\)", row["roi"]).groups())
            clean, n_replaced = beam.despike(frame, threshold_dn=threshold)
            sub = clean[y:y + ny, x:x + nx].copy()
            sub -= beam.poly_baseline(sub, order=2, exclude_frac=0.45)
            fit = beam.fit_gaussian(sub, x, y)
            details = {"frame": index + 1, "well": row["expected_position"].split()[0],
                       "despiked_px_full_image": n_replaced,
                       "A_DN": fit["amplitude_dn"],
                       "nominal_independent_pixel_SE_DN": fit["amplitude_err_dn"],
                       "residual_RMS_DN": fit["rms_residual_dn"],
                       "converged": fit["converged"], "n_eval": fit["n_eval"],
                       "archive_A_difference_DN": fit["amplitude_dn"] - float(row["amplitude_dn"]),
                       "archive_RMS_difference_DN": fit["rms_residual_dn"] - float(row["rms_residual_dn"])}
            if threshold == 40 and not args.skip_blocks:
                details["approximate_soft_l1_spatial_sandwich"] = block_scores(beam, sub, fit, x, y)
            fits.append(details)
        result["variants"].append({"threshold_DN": threshold,
                                    "fits": fits,
                                    **calibration_summary([f["A_DN"] for f in fits])})
    reference = next((v for v in result["variants"] if v["threshold_DN"] == 40), None)
    if reference:
        for variant in result["variants"]:
            variant["common_scale_difference_from_40_percent"] = 100 * (
                variant["DN_per_Gy_refit_same_four_pairs"] / reference["DN_per_Gy_refit_same_four_pairs"] - 1)
            variant["residual_change_from_40_percentage_points"] = (
                np.array(variant["camera_minus_film_percent"])
                - reference["camera_minus_film_percent"]).tolist()
            variant["raw_amplitude_change_from_40_percent"] = (
                100 * (np.array([f["A_DN"] for f in variant["fits"]])
                       / [f["A_DN"] for f in reference["fits"]] - 1)).tolist()
        result["max_absolute_residual_change_from_40_percentage_points"] = max(
            abs(change) for v in result["variants"]
            for change in v["residual_change_from_40_percentage_points"])
    result["elapsed_seconds"] = time.monotonic() - started
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
