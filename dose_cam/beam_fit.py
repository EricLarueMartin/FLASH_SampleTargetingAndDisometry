"""Background subtraction and 2D Gaussian beam-profile fitting for DoseCam frames.

Added 2026-10-14. Results are in DN; with a DN->Gy calibration every DN result
gains a matching *_gy field. A built-in default calibration (DEFAULT_CALIBRATION,
film cross-calibration of 2026-10-13) applies unless the operator saves a
custom one from the Options tab, which is stored in
~/.config/dosecam/dn_calibration.json.

Fit-parameter uncertainties (2026-10-26) are 1-sigma statistical, from the
Gauss-Newton covariance scaled by the residual variance. The calibration
uncertainty can optionally be added in quadrature to the Gy values.

Roll back with /home/codex/backups/restore_dose_cam.sh
"""

import json
import math
import os

# Kept outside the (read-only) code directory so it is writable by the service
# and survives a code rollback.
CAL_PATH = os.environ.get(
    "DOSECAM_CAL_PATH",
    os.path.join(os.path.expanduser("~"), ".config", "dosecam", "dn_calibration.json"))


# Default DN->Gy calibration (2026-10-26).
# Source: DoseCam frames PolyAlDosCal_20261013_161112_732305_000006 (4 pulses,
# recorded order B1, A1, A2, A3; 200 us delay, 100 us gate, local-baseline fit)
# against EBT-XD film well_041 (J. Sherman, lot 06092501, 24 h curve, peak dose
# = max over 10 px window): A1 39.61, A2 39.75, A3 39.70, B1 40.94 Gy.
#   k = mean(fitted peak DN) / mean(film peak dose) = 42.251 / 39.9997 = 1.0563 DN/Gy
#   statistical: sqrt(a^2/4 + b^2/4) with a = 1.50 % (camera per-shot sd),
#                b = 1.57 % (film per-well sd)                      -> 1.09 %
#   systematic:  film absolute accuracy (readout calibration, film variation)
#                PROVISIONAL 3.0 % - typical EBT-XD value, not yet stated by the
#                film group; replace when they provide it.
#   total (quadrature): 3.19 %
# Single dose level (~40 Gy) with zero intercept; linearity not yet tested.
DEFAULT_CALIBRATION = {
    "dn_per_gy": 1.0563,
    "dn_per_gy_err_pct": 3.19,
    "err_stat_pct": 1.09,
    "err_sys_pct": 3.0,
    "note": ("Film cross-cal 2026-10-13, 4 pulses at ~40 Gy (EBT-XD well_041). "
             "Uncertainty 3.19% = 1.09% statistical (mean of 4 camera + 4 film) "
             "(+) 3.0% systematic film accuracy (provisional)."),
    "date": "2026-10-26",
}

_CAL_KEYS = ("dn_per_gy", "dn_per_gy_err_pct", "note")


def _pos_float(raw, allow_zero=False):
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v != v or v < 0 or (v == 0 and not allow_zero):
        return None
    return v


def _read_cal_file():
    try:
        with open(CAL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_calibration():
    """Effective calibration: built-in default, overridden by a saved custom one.

    Returns dn_per_gy, dn_per_gy_err_pct (1-sigma, %, None if unknown),
    err_stat_pct / err_sys_pct (default only), note, source ('default' or
    'custom'), display_units ('DN'|'Gy'), include_cal_err (bool), the default
    record itself, and updated_utc.
    """
    d = DEFAULT_CALIBRATION
    data = _read_cal_file()
    custom_val = _pos_float(data.get("dn_per_gy"))
    custom_err = _pos_float(data.get("dn_per_gy_err_pct"), allow_zero=True) \
        if data.get("dn_per_gy_err_pct") not in (None, "") else None

    if custom_val is not None:
        value, source = custom_val, "custom"
        err = custom_err                      # unknown unless the operator gave one
        stat = sys_ = None
        note = str(data.get("note") or "")
    else:
        value, source = d["dn_per_gy"], "default"
        err = custom_err if custom_err is not None else d["dn_per_gy_err_pct"]
        stat, sys_ = (None, None) if custom_err is not None else (d["err_stat_pct"], d["err_sys_pct"])
        note = d["note"]

    units = "Gy" if str(data.get("display_units", "DN")) == "Gy" else "DN"
    include = data.get("include_cal_err", True)
    return {
        "dn_per_gy": value,
        "dn_per_gy_err_pct": err,
        "err_stat_pct": stat,
        "err_sys_pct": sys_,
        "note": note,
        "source": source,
        "display_units": units,
        "include_cal_err": bool(include),
        "default": dict(d),
        "updated_utc": data.get("updated_utc"),
    }


def save_calibration(dn_per_gy=..., dn_per_gy_err_pct=..., note=None,
                     display_units=None, include_cal_err=None, reset=False):
    """Merge-update the calibration file. Unset arguments keep their value.

    dn_per_gy=None or dn_per_gy_err_pct=None removes that custom value (the
    default applies again); reset=True removes the custom value, error and note.
    """
    data = _read_cal_file()
    if reset:
        for k in _CAL_KEYS:
            data.pop(k, None)
    if dn_per_gy is not ...:
        if dn_per_gy is None:
            data.pop("dn_per_gy", None)
            data.pop("note", None)
        else:
            data["dn_per_gy"] = float(dn_per_gy)
    if dn_per_gy_err_pct is not ...:
        if dn_per_gy_err_pct is None:
            data.pop("dn_per_gy_err_pct", None)
        else:
            data["dn_per_gy_err_pct"] = float(dn_per_gy_err_pct)
    if note is not None:
        data["note"] = str(note)
    if display_units is not None:
        data["display_units"] = "Gy" if display_units == "Gy" else "DN"
    if include_cal_err is not None:
        data["include_cal_err"] = bool(include_cal_err)
    import datetime as _dt
    data["updated_utc"] = _dt.datetime.utcnow().isoformat() + "Z"
    os.makedirs(os.path.dirname(CAL_PATH), exist_ok=True)
    tmp = CAL_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CAL_PATH)
    return load_calibration()


def _to_gy(value, dn_per_gy):
    if dn_per_gy in (None, 0):
        return None
    return float(value) / float(dn_per_gy)


def rotate(arr, degrees):
    """Rotate a decoded frame into display orientation (UI shows 180)."""
    import numpy as np
    rot = int(degrees) % 360
    if rot == 180:
        return arr[::-1, ::-1].copy()
    if rot == 90:
        return np.rot90(arr, 1).copy()
    if rot == 270:
        return np.rot90(arr, 3).copy()
    return arr


# --------------------------------------------------------------------------
# frame access
# --------------------------------------------------------------------------

def decode_saved_frame(cam, rel_path, frame_index):
    """Decode one frame of a saved .raw file into a float32 DN array."""
    import numpy as np
    import camera_core as cc

    path = cam._path_for_relative(rel_path)
    if not os.path.isfile(path):
        raise ValueError("Path is not a file")
    if not path.lower().endswith(".raw"):
        raise ValueError("Beam fitting is only available for .raw files")

    size = os.path.getsize(path)
    frames = size // cc.RAW_FRAME_BYTES
    if frames < 1:
        raise ValueError("Raw file does not contain a complete frame")

    index = int(frame_index)
    if index < 0:
        index = frames - 1
    if index >= frames:
        raise ValueError("Frame index must be between 0 and %d" % (frames - 1))

    with open(path, "rb") as f:
        f.seek(index * cc.RAW_FRAME_BYTES)
        blob = f.read(cc.RAW_FRAME_BYTES)
    if len(blob) != cc.RAW_FRAME_BYTES:
        raise ValueError("Raw frame is incomplete")

    dn = cam._decode_raw_stream_frame(blob)
    return np.asarray(dn, dtype=np.float32), index, frames


def average_frames(cam, rel_path, max_frames=0):
    """Mean of up to max_frames frames (0 = all) of a saved .raw, as float32 DN."""
    import numpy as np
    import camera_core as cc

    path = cam._path_for_relative(rel_path)
    if not os.path.isfile(path) or not path.lower().endswith(".raw"):
        raise ValueError("Background reference must be a .raw file")
    total = os.path.getsize(path) // cc.RAW_FRAME_BYTES
    if total < 1:
        raise ValueError("Background file contains no complete frame")
    n = total if max_frames in (0, None) else min(int(max_frames), total)

    acc = None
    with open(path, "rb") as f:
        for i in range(n):
            f.seek(i * cc.RAW_FRAME_BYTES)
            blob = f.read(cc.RAW_FRAME_BYTES)
            if len(blob) != cc.RAW_FRAME_BYTES:
                break
            arr = np.asarray(cam._decode_raw_stream_frame(blob), dtype=np.float32)
            acc = arr if acc is None else acc + arr
    if acc is None:
        raise ValueError("Background file could not be decoded")
    return acc / float(n), n


def latest_live_frame(cam):
    """(array, rel_path, frame_index) for the frame behind the main-page image."""
    meta = (cam.store.get("meta") or {})
    raw_path = meta.get("raw_path")
    if not raw_path:
        raise ValueError("No raw frame is loaded on the main page yet")
    index = int(meta.get("frame_index", -1))
    arr, index, _frames = decode_saved_frame(cam, raw_path, index)
    return arr, raw_path, index


# --------------------------------------------------------------------------
# conditioning
# --------------------------------------------------------------------------

def despike(arr, threshold_dn=40.0):
    """Replace single-pixel radiation hits with the local median.

    At 30 Gy/pulse a large number of pixels take direct ionisation hits; those
    are not scintillation light and would otherwise dominate a least-squares
    fit. Returns (cleaned, n_replaced).
    """
    import numpy as np
    from scipy.ndimage import median_filter

    med = median_filter(arr, size=3)
    bad = (arr - med) > float(threshold_dn)
    out = arr.copy()
    out[bad] = med[bad]
    return out, int(bad.sum())


def auto_roi(img, half=260):
    """Window around the brightest smoothed blob -> (x1, x2, y1, y2)."""
    import numpy as np
    from scipy.ndimage import uniform_filter

    sm = uniform_filter(img, 25)
    y0, x0 = np.unravel_index(int(np.argmax(sm)), sm.shape)
    y0, x0 = int(y0), int(x0)
    h, w = img.shape
    half = int(half)
    return (int(max(0, x0 - half)), int(min(w, x0 + half)),
            int(max(0, y0 - half)), int(min(h, y0 + half)))


def clamp_roi(roi, shape):
    h, w = shape
    x1, x2, y1, y2 = [int(v) for v in roi]
    x1 = max(0, min(x1, w - 2)); x2 = max(x1 + 2, min(x2, w))
    y1 = max(0, min(y1, h - 2)); y2 = max(y1 + 2, min(y2, h))
    return int(x1), int(x2), int(y1), int(y2)


def poly_baseline(sub, order=2, exclude_frac=0.45):
    """Fit a smooth 2D polynomial to the ROI border and return that surface.

    The central exclude_frac of the window is masked out so the beam spot does
    not pull the baseline up.
    """
    import numpy as np

    ny, nx = sub.shape
    yy, xx = np.mgrid[0:ny, 0:nx].astype(np.float64)
    cx, cy = (nx - 1) / 2.0, (ny - 1) / 2.0
    rx, ry = nx * exclude_frac / 2.0, ny * exclude_frac / 2.0
    mask = (((xx - cx) / max(rx, 1)) ** 2 + ((yy - cy) / max(ry, 1)) ** 2) > 1.0
    if mask.sum() < 50:
        return np.full_like(sub, float(np.median(sub)))

    xn = (xx - cx) / max(nx, 1); yn = (yy - cy) / max(ny, 1)
    terms = [np.ones_like(xn), xn, yn]
    if int(order) >= 2:
        terms += [xn * xn, yn * yn, xn * yn]
    A = np.stack([t[mask] for t in terms], axis=1)
    coef, *_ = np.linalg.lstsq(A, sub[mask].astype(np.float64), rcond=None)
    surface = sum(c * t for c, t in zip(coef, terms))
    return surface.astype(np.float32)


# --------------------------------------------------------------------------
# the fit
# --------------------------------------------------------------------------

def _gauss2d(p, X, Y):
    import numpy as np
    A, x0, y0, sx, sy, th, off = p
    c, s = math.cos(th), math.sin(th)
    xr = (X - x0) * c + (Y - y0) * s
    yr = -(X - x0) * s + (Y - y0) * c
    return off + A * np.exp(-0.5 * ((xr / sx) ** 2 + (yr / sy) ** 2))


def fit_gaussian(sub, x1, y1, robust=True):
    """Rotated elliptical Gaussian + constant offset, fitted on a ROI."""
    import numpy as np
    from scipy.ndimage import uniform_filter
    from scipy.optimize import least_squares

    ny, nx = sub.shape
    sm = uniform_filter(sub, 25)
    iy, ix = np.unravel_index(int(np.argmax(sm)), sm.shape)
    base = float(np.median(sub))
    amp0 = max(float(sm[iy, ix]) - base, 1e-3)

    p0 = [amp0, float(x1 + ix), float(y1 + iy), 30.0, 30.0, 0.0, base]
    lo = [0.0, float(x1), float(y1), 1.0, 1.0, -math.pi / 2, base - 500.0]
    hi = [max(amp0 * 20, 10.0), float(x1 + nx), float(y1 + ny),
          float(max(nx, ny)), float(max(nx, ny)), math.pi / 2, base + 500.0]

    Y, X = np.mgrid[y1:y1 + ny, x1:x1 + nx].astype(np.float64)
    kw = dict(loss="soft_l1", f_scale=5.0) if robust else {}
    res = least_squares(lambda p: (_gauss2d(p, X, Y) - sub).ravel(),
                        p0, bounds=(lo, hi), max_nfev=600, **kw)
    p = res.x
    model = _gauss2d(p, X, Y)
    resid = sub - model

    # goodness of fit
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((sub - sub.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    # noise from the quiet border of the ROI, away from the spot
    edge = np.concatenate([resid[:12, :].ravel(), resid[-12:, :].ravel(),
                           resid[:, :12].ravel(), resid[:, -12:].ravel()])
    sigma = float(np.std(edge)) or 1.0
    dof = max(sub.size - 7, 1)
    chi2_red = ss_res / (sigma ** 2 * dof)

    A, x0, y0, sx, sy, th, off = [float(v) for v in p]
    sx, sy = abs(sx), abs(sy)
    integ_fit = 2.0 * math.pi * A * sx * sy          # analytic volume
    integ_sum = float(np.sum(sub - off))             # numeric, offset removed

    errs = _param_errors(p, X, Y, ss_res / dof)

    return {
        "amplitude_dn": A,
        "center_x": x0,
        "center_y": y0,
        "sigma_x": sx,
        "sigma_y": sy,
        "fwhm_x": 2.3548200450309493 * sx,
        "fwhm_y": 2.3548200450309493 * sy,
        "theta_deg": math.degrees(th),
        "offset_dn": off,
        "integrated_dn_fit": integ_fit,
        "integrated_dn_sum": integ_sum,
        "r_squared": r2,
        "chi2_reduced": chi2_red,
        "rms_residual_dn": float(math.sqrt(ss_res / sub.size)),
        "noise_sigma_dn": sigma,
        "dof": int(dof),
        "converged": bool(res.success),
        "n_eval": int(res.nfev),
        **errs,
    }


def _param_errors(p, X, Y, resid_var):
    """1-sigma statistical errors from the Gauss-Newton covariance.

    cov = s^2 (J^T J)^-1 with J the plain model Jacobian at the solution and
    s^2 the residual variance (so chi2_red > 1 inflates the errors). Assumes
    independent pixels; correlated noise (hit streaks, row banding) makes the
    true error somewhat larger.
    """
    import numpy as np
    p = np.asarray(p, dtype=np.float64)
    cols = []
    for k in range(p.size):
        h = 1e-4 * max(1.0, abs(p[k]))
        d = np.zeros_like(p); d[k] = h
        cols.append(((_gauss2d(p + d, X, Y) - _gauss2d(p - d, X, Y)) / (2 * h)).ravel())
    J = np.stack(cols, axis=1)
    try:
        cov = float(resid_var) * np.linalg.inv(J.T @ J)
    except np.linalg.LinAlgError:
        return {"errors_available": False}
    var = np.diag(cov)
    if not np.all(np.isfinite(var)) or np.any(var < 0):
        return {"errors_available": False}
    e = np.sqrt(var)
    A, sx, sy = float(p[0]), abs(float(p[3])), abs(float(p[4]))
    g = np.array([2 * math.pi * sx * sy, 0, 0, 2 * math.pi * A * sy, 2 * math.pi * A * sx, 0, 0])
    k = 2.3548200450309493
    return {
        "errors_available": True,
        "amplitude_err_dn": float(e[0]),
        "center_x_err": float(e[1]),
        "center_y_err": float(e[2]),
        "sigma_x_err": float(e[3]),
        "sigma_y_err": float(e[4]),
        "fwhm_x_err": k * float(e[3]),
        "fwhm_y_err": k * float(e[4]),
        "theta_err_deg": math.degrees(float(e[5])),
        "offset_err_dn": float(e[6]),
        "integrated_dn_fit_err": float(math.sqrt(max(g @ cov @ g, 0.0))),
    }


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def render_png(img, rotation_degrees=0, lo_pct=0.5, hi_pct=99.8, suppress=None,
               overlay=None, roi_box=None):
    """8-bit PNG of a float DN image, percentile-stretched.

    suppress: optional (x0, y0, sx, sy, theta_deg, n) -> blank the fitted spot
    out to n sigma so the faint background structure can be stretched hard.
    """
    import io
    import numpy as np
    from PIL import Image

    a = np.asarray(img, dtype=np.float32).copy()
    if suppress:
        x0, y0, sx, sy, th_deg, nsig = suppress
        ny, nx = a.shape
        Y, X = np.mgrid[0:ny, 0:nx].astype(np.float32)
        th = math.radians(th_deg)
        c, s = math.cos(th), math.sin(th)
        xr = (X - x0) * c + (Y - y0) * s
        yr = -(X - x0) * s + (Y - y0) * c
        inside = ((xr / max(sx, 1e-3)) ** 2 + (yr / max(sy, 1e-3)) ** 2) <= float(nsig) ** 2
        if inside.any() and (~inside).any():
            a[inside] = float(np.median(a[~inside]))

    lo = float(np.percentile(a, lo_pct))
    hi = float(np.percentile(a, hi_pct))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((a - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)

    rot = int(rotation_degrees) % 360
    if rot == 180:
        scaled = scaled[::-1, ::-1]
    elif rot == 90:
        scaled = np.rot90(scaled, 1)
    elif rot == 270:
        scaled = np.rot90(scaled, 3)

    image = Image.fromarray(scaled, mode="L").convert("RGB")

    if overlay or roi_box:
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        if roi_box:
            rx, ry, rw, rh = roi_box
            draw.rectangle([rx, ry, rx + rw - 1, ry + rh - 1],
                           outline=(255, 190, 40), width=2)
        if overlay:
            x0, y0, sx, sy, th_deg = overlay
            th = math.radians(th_deg)
            c, s_ = math.cos(th), math.sin(th)
            for nsig, colour in ((1.0, (0, 230, 255)), (2.0, (0, 140, 255))):
                pts = []
                for k in range(145):
                    t = 2.0 * math.pi * k / 144.0
                    ex, ey = nsig * sx * math.cos(t), nsig * sy * math.sin(t)
                    pts.append((x0 + ex * c - ey * s_, y0 + ex * s_ + ey * c))
                draw.line(pts, fill=colour, width=2)
            draw.line([(x0 - 9, y0), (x0 + 9, y0)], fill=(0, 230, 255), width=2)
            draw.line([(x0, y0 - 9), (x0, y0 + 9)], fill=(0, 230, 255), width=2)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue(), lo, hi


# --------------------------------------------------------------------------
# top level
# --------------------------------------------------------------------------

def analyze(cam, source="file", path="", frame=-1,
            background="none", bg_path="", bg_frames=0,
            baseline_order=2, roi=None, despike_dn=40.0,
            rotation_degrees=180, want_png=False, png_mode="subtracted",
            suppress_sigma=0.0):
    """Background-subtract a frame and fit the beam profile. Returns a dict."""
    import numpy as np

    if source == "live":
        raw, used_path, used_frame = latest_live_frame(cam)
        total_frames = None
    else:
        raw, used_frame, total_frames = decode_saved_frame(cam, path, frame)
        used_path = path

    # Work in DISPLAY orientation throughout, so the ROI the operator drags and
    # the ellipse drawn back on the image share one coordinate system.
    raw = rotate(raw, rotation_degrees)

    saturated = int(np.count_nonzero(raw >= 1023))
    used_frame = int(used_frame)
    clean, n_spikes = despike(raw, despike_dn) if despike_dn else (raw, 0)

    # ---- background ----
    bg_info = {"mode": background}
    img = clean
    if background == "file":
        if not bg_path:
            raise ValueError("A background .raw file must be selected")
        bg, n_used = average_frames(cam, bg_path, bg_frames)
        bg = rotate(bg, rotation_degrees)
        if bg.shape != clean.shape:
            raise ValueError("Background frame size does not match")
        img = clean - bg
        bg_info.update(path=bg_path, frames_averaged=n_used,
                       mean_dn=float(bg.mean()))
    elif background == "baseline":
        bg_info.update(order=int(baseline_order))
    elif background != "none":
        raise ValueError("Unknown background mode: %s" % background)

    # ---- ROI ----
    if roi:
        x1, x2, y1, y2 = clamp_roi(roi, img.shape)
        roi_source = "manual"
    else:
        x1, x2, y1, y2 = auto_roi(img)
        roi_source = "auto"
    sub = img[y1:y2, x1:x2].astype(np.float32)

    if background == "baseline":
        surface = poly_baseline(sub, baseline_order)
        sub = sub - surface
        bg_info["baseline_mean_dn"] = float(np.mean(surface))
        # For display, put the whole frame on the same zero as the ROI, so the
        # stretch is not split between a pedestal outside and ~0 inside.
        img = img - float(np.median(img))
        img[y1:y2, x1:x2] = sub

    fit = fit_gaussian(sub, x1, y1)

    cal = load_calibration()
    dpg = cal["dn_per_gy"]
    cal_rel = 0.0
    if cal["include_cal_err"] and cal["dn_per_gy_err_pct"]:
        cal_rel = float(cal["dn_per_gy_err_pct"]) / 100.0
    gy = {}
    if dpg:
        def conv(val_dn, err_dn):
            v = float(val_dn) / dpg
            parts = []
            if err_dn is not None:
                parts.append(float(err_dn) / dpg)
            if cal_rel:
                parts.append(abs(v) * cal_rel)
            return v, (math.sqrt(sum(x * x for x in parts)) if parts else None)
        # per-pixel quantities convert to dose directly
        for key in ("amplitude", "offset"):
            v, e = conv(fit[key + "_dn"], fit.get(key + "_err_dn"))
            gy[key + "_gy"], gy[key + "_gy_err"] = v, e
        for key in ("rms_residual", "noise_sigma"):
            gy[key + "_gy"] = float(fit[key + "_dn"]) / dpg
        # integrals are dose-area products in pixel units: Gy * px^2
        gy["integrated_gypx2_fit"], gy["integrated_gypx2_fit_err"] = conv(
            fit["integrated_dn_fit"], fit.get("integrated_dn_fit_err"))
        gy["integrated_gypx2_sum"], gy["integrated_gypx2_sum_err"] = conv(
            fit["integrated_dn_sum"], None)
    error_model = {
        "fit": "1-sigma statistical, fit covariance scaled by residual variance",
        "calibration_pct": cal["dn_per_gy_err_pct"],
        "calibration_included": bool(cal_rel),
    }

    out = {
        "source": source,
        "path": used_path,
        "frame_index": used_frame,
        "frames_available": None if total_frames is None else int(total_frames),
        "roi": {"x": int(x1), "y": int(y1), "w": int(x2 - x1),
                "h": int(y2 - y1), "source": roi_source},
        "background": bg_info,
        "despike": {"threshold_dn": float(despike_dn), "pixels_replaced": n_spikes},
        "saturated_pixels": saturated,
        "fit": fit,
        "calibration": cal,
        "gy": gy,
        "error_model": error_model,
        "units": cal["display_units"],
        "coordinate_space": "display (frame rotated %d deg)" % (int(rotation_degrees) % 360),
    }

    if want_png:
        f = fit
        sup = None
        if suppress_sigma and suppress_sigma > 0:
            sup = (f["center_x"], f["center_y"], f["sigma_x"], f["sigma_y"],
                   f["theta_deg"], float(suppress_sigma))
        target = img if png_mode == "subtracted" else clean
        png, lo, hi = render_png(
            target, 0, suppress=sup,
            overlay=(f["center_x"], f["center_y"], f["sigma_x"], f["sigma_y"], f["theta_deg"]),
            roi_box=(x1, y1, x2 - x1, y2 - y1))
        out["png"] = png
        out["png_scale"] = {"lo_dn": lo, "hi_dn": hi, "mode": png_mode,
                            "suppress_sigma": float(suppress_sigma or 0)}
    return out
