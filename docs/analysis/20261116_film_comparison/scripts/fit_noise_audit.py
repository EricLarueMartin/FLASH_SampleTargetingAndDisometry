"""Audit the archived peak errors without refitting or changing camera code.

Uses the recorded baseline fits and the same finite-difference model Jacobian
as dose_cam.beam_fit._param_errors. Optional background captures provide a
temporal/background projection, including spatial correlations and the same
quadratic baseline subtraction. Photon estimates require an assumed gain.

Run with NumPy installed:
  python fit_noise_audit.py --captures PATH_TO_20261013_BACKUP
Outputs fit_noise_audit.json and peak_fit_uncertainty.csv beside this script.
"""
import argparse
import csv
import importlib.util
import json
import math
import os
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "docs/analysis/20261014/crosscal_fits_PolyAlDosCal_000006.csv"
BACKGROUND = "Alanine_20261013_145026_730724_000002.raw"


def capture_roi(path, x, y, nx, ny):
    raw = np.memmap(path, dtype="<u2", mode="r")
    n = raw.size // (1088 * 1472)
    raw = raw[:n * 1088 * 1472].reshape(n, 1088, 1472)[:, :, :1456]
    return (raw[:, ::-1, ::-1][:, y:y + ny, x:x + nx] >> 6).astype(float)


def clipped_variance(values):
    values = values.ravel().copy()
    for _ in range(4):
        sigma = values.std()
        values = values[np.abs(values - values.mean()) < 3.5 * sigma]
    return float(values.var())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path,
                        default=os.environ.get("DOSECAM_CAPTURES"))
    parser.add_argument("--gain", type=float, default=10.7,
                        help="Manufacturer-camera proxy, electrons/DN")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("beam_covariance", ROOT / "dose_cam/beam_fit.py")
    beam = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(beam)
    rows = [r for r in csv.DictReader(SOURCE.open(encoding="utf-8"))
            if r["background"] == "baseline"]

    dark_rms = None
    if args.captures:
        dark = capture_roi(args.captures / BACKGROUND, 600, 175, 520, 520)
        variances = [clipped_variance(dark[i] - dark[i + 1]) / 2
                     for i in range(0, len(dark) - 1, 2)]
        dark_rms = math.sqrt(float(np.median(variances)))
        del dark

    output = {
        "source_fit_csv": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "method": "Archived parameters; no refit. C = residual_variance * inv(J.T @ J).",
        "fit_objective": "Unweighted DN residuals with soft_l1 loss; reported covariance uses plain model Jacobian.",
        "gain_e_per_DN_proxy": args.gain,
        "gain_sensitivity_e_per_DN": [8, 12],
        "background_capture": BACKGROUND if args.captures else None,
        "background_pixel_rms_DN": dark_rms,
        "background_pixel_method": "Median consecutive-pair clipped variance / 2, 520x520 ROI at (600,175).",
        "accounting": "Residual-covariance SE is combined; do not add photon/background component checks to it.",
        "limitations": [
            "Nominal covariance assumes independent pixels and does not use a Poisson/read variance weight map.",
            "Plain-Jacobian covariance is not an exact robust-estimator or spatially correlated covariance.",
            "Gain is a proxy from another IMX296 camera, not a measured conversion gain for this module.",
            "Background projection is linearized and based on 34 no-beam frames; it includes drift/artifacts, not pure electronic read noise.",
            "Masking-method sensitivity is separate; no independence or quadrature total is asserted.",
        ],
        "fits": [],
    }
    for row in rows:
        nx, ny, x, y = map(int, re.fullmatch(r"(\d+)x(\d+)@\((\d+),(\d+)\)", row["roi"]).groups())
        Y, X = np.mgrid[y:y + ny, x:x + nx].astype(float)
        p = np.array([float(row[k]) for k in
                      ["amplitude_dn", "center_x", "center_y", "sigma_x", "sigma_y"]]
                     + [math.radians(float(row["theta_deg"])), float(row["offset_dn"])])
        columns = []
        for k in range(7):
            step = 1e-4 * max(1.0, abs(p[k]))
            delta = np.zeros(7)
            delta[k] = step
            columns.append(((beam._gauss2d(p + delta, X, Y)
                             - beam._gauss2d(p - delta, X, Y)) / (2 * step)).ravel())
        J = np.stack(columns, axis=1)
        gram = J.T @ J
        unit = np.eye(7)[0]
        h = J @ np.linalg.solve(gram, unit)
        n = nx * ny
        residual_var = float(row["rms_residual_dn"]) ** 2 * n / (n - 7)
        peak_se = math.sqrt(residual_var * float(np.linalg.solve(gram, unit)[0]))
        expected = beam._param_errors(p, X, Y, residual_var)["amplitude_err_dn"]
        assert math.isclose(peak_se, expected, rel_tol=1e-10)
        signal = np.maximum(beam._gauss2d(p, X, Y) - p[6], 0).ravel()
        photon_se = math.sqrt(float(np.sum(h * h * signal / args.gain)))

        result = {
            "frame": int(row["frame"]),
            "well": row["expected_position"].split()[0],
            "amplitude_DN": float(p[0]),
            "nominal_peak_SE_DN": peak_se,
            "nominal_peak_SE_percent": 100 * peak_se / p[0],
            "recorded_reduced_chi_squared": float(row["chi2_reduced"]),
            "recorded_residual_rms_DN": float(row["rms_residual_dn"]),
            "equivalent_gaussian_area_pixels": float(2 * math.pi * p[3] * p[4]),
            "total_signal_electrons_proxy": float(2 * math.pi * p[0] * p[3] * p[4] * args.gain),
            "peak_signal_electrons_per_pixel_proxy": float(p[0] * args.gain),
            "photon_plain_LS_peak_SE_percent_proxy": float(100 * photon_se / p[0]),
        }
        if args.captures:
            white_se = dark_rms * float(np.linalg.norm(h))
            # Full-image context for each ROI's median, not reflection at ROI edges.
            dark = capture_roi(args.captures / BACKGROUND, x - 1, y - 1, nx + 2, ny + 2)
            projections, conditioned = [], []
            for expanded in dark:
                frame = expanded[1:-1, 1:-1]
                corrected = frame - beam.poly_baseline(frame, order=2, exclude_frac=0.45)
                projections.append(float(h @ corrected.ravel()))
                neighborhoods = np.lib.stride_tricks.sliding_window_view(expanded, (3, 3))
                median = np.median(neighborhoods, axis=(-2, -1))
                cleaned = np.where(frame > median + 40.0, median, frame)
                corrected = cleaned - beam.poly_baseline(cleaned, order=2, exclude_frac=0.45)
                conditioned.append(float(h @ corrected.ravel()))
            projected_se = float(np.std(projections, ddof=1))
            conditioned_se = float(np.std(conditioned, ddof=1))
            result.update({
                "background_frames": len(dark),
                "background_white_pixel_peak_SE_percent_proxy": float(100 * white_se / p[0]),
                "raw_background_temporal_projection_peak_SE_DN": projected_se,
                "raw_background_temporal_projection_peak_SE_percent": float(100 * projected_se / p[0]),
                "conditioned_background_temporal_projection_peak_SE_DN": conditioned_se,
                "conditioned_background_temporal_projection_peak_SE_percent": float(100 * conditioned_se / p[0]),
                "conditioned_background_method": "Positive 3x3-median outliers >40 DN replaced, then quadratic border baseline; sample SD of peak projections across 34 frames.",
                "photon_plus_conditioned_background_percent_crosscheck": float(100 * math.hypot(photon_se, conditioned_se) / p[0]),
            })
            del dark
        output["fits"].append(result)

    outdir = Path(__file__).resolve().parent
    (outdir / "fit_noise_audit.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    fields = ["frame", "well", "amplitude_DN", "nominal_peak_SE_DN",
              "nominal_peak_SE_percent", "recorded_reduced_chi_squared"]
    with (outdir / "peak_fit_uncertainty.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in output["fits"])
    print(json.dumps({"background_pixel_rms_DN": dark_rms,
                      "fits": [{k: r[k] for k in fields} for r in output["fits"]]}))


if __name__ == "__main__":
    main()
