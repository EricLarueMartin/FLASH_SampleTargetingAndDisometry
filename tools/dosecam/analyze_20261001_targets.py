"""Spot-shape analysis of the 1 October 2026 Al_PC and scintillator target runs.

Runs on the Pi against the raw captures (memory-mapped, read-only) and writes
small outputs to OUT. Decode: R16 unpacked, 2944-byte stride (1472 px) of which
1456 are image; left-aligned 10-bit values shifted down six bits; rotated 180
degrees to match the web UI.

usage: python3 analyze_20261001_targets.py survey|full CAPTURES OUT
"""
import json
import sys
from pathlib import Path

import numpy as np

H, W, STRIDE_PX = 1088, 1456, 1472
FULL_SCALE = 1023

RUNS = {
    "PC_200_100": "Al_PC/run_20261001_194433_457037_000001",
    "Scint_200_100": "Scint/run_20261001_194704_633291_000002",
    "PC_220_100": "Al_PC/run_20261001_195317_467474_000005",
    "Scint_200_50": "scint/run_20261001_195109_910461_000003",
    "Scint_220_50": "scint/run_20261001_195132_973084_000004",
}


def open_run(captures, stem):
    meta = json.loads((captures / (stem + ".json")).read_text())
    n = meta["frames_written"]
    raw = np.memmap(captures / (stem + ".raw"), dtype="<u2", mode="r", shape=(n, H, STRIDE_PX))
    return meta, raw


def frame(raw, i):
    img = raw[i, :, :W]
    if img.max() > FULL_SCALE:
        img = img >> 6
    return np.ascontiguousarray(img[::-1, ::-1]).astype(np.float32)


def bin4(img):
    return img.reshape(H // 4, 4, W // 4, 4).mean((1, 3))


def survey(captures, out):
    report = {}
    for name, stem in RUNS.items():
        meta, raw = open_run(captures, stem)
        n = raw.shape[0]
        stats, binned = [], []
        for i in range(n):
            f = frame(raw, i)
            b = bin4(f)
            binned.append(b)
            stats.append((float(f.mean()), float(np.percentile(f, 99.9)), float(f.max()),
                          int((f >= FULL_SCALE).sum())))
        cube = np.stack(binned)
        med = np.median(cube, 0)
        bg = np.median(med)
        peak = np.unravel_index(np.argmax(med - bg), med.shape)
        # per-frame light in a 40x40 binned box round the median peak
        y0, x0 = peak
        box = cube[:, max(0, y0 - 20):y0 + 20, max(0, x0 - 20):x0 + 20]
        far = cube[:, 5:45, 5:45]
        net = (box.mean((1, 2)) - far.mean((1, 2)))
        s = np.array(stats)
        report[name] = {
            "frames": n, "delay": meta["esp_delay_us"], "gate": meta["esp_width_us"],
            "median_image_bg_dn": round(float(bg), 2),
            "median_image_peak_dn": round(float(med.max()), 1),
            "peak_binned_yx": [int(peak[0]), int(peak[1])],
            "peak_full_res_yx": [int(peak[0] * 4 + 2), int(peak[1] * 4 + 2)],
            "frame_mean_dn_min_med_max": [round(float(v), 2) for v in (s[:, 0].min(), np.median(s[:, 0]), s[:, 0].max())],
            "frame_max_dn_median": float(np.median(s[:, 2])),
            "frames_with_any_saturated": int((s[:, 3] > 0).sum()),
            "box_net_dn_percentiles_0_10_50_90_100": [round(float(v), 2) for v in np.percentile(net, [0, 10, 50, 90, 100])],
            "frames_box_net_below_10pct_of_median": int((net < 0.1 * np.median(net)).sum()),
        }
        np.save(out / f"{name}_binned_median.npy", med.astype(np.float32))
        np.save(out / f"{name}_box_net.npy", net.astype(np.float32))
        print(name, json.dumps(report[name]), flush=True)
    (out / "survey.json").write_text(json.dumps(report, indent=2))


def strength(b):
    """Generic per-frame spot strength: 99.5th pct of 8x8-binned frame above its median."""
    c = b.reshape(b.shape[0] // 2, 2, b.shape[1] // 2, 2).mean((1, 3))
    return float(np.percentile(c, 99.5) - np.median(c))


def look(captures, out):
    from PIL import Image, ImageDraw
    tiles, info = [], {}
    for name, stem in RUNS.items():
        meta, raw = open_run(captures, stem)
        n = raw.shape[0]
        st = np.array([strength(bin4(frame(raw, i))) for i in range(n)])
        order = np.argsort(st)
        off = order[: max(3, n // 5)]
        on = order[n // 2:]
        acc_on = np.zeros((H, W), np.float64)
        acc_off = np.zeros((H, W), np.float64)
        on_stack = []
        for i in on:
            f = frame(raw, i)
            acc_on += f
            on_stack.append(bin4(f))
        for i in off:
            acc_off += frame(raw, i)
        diff = acc_on / len(on) - acc_off / len(off)
        med_on = np.median(np.stack(on_stack), 0)
        np.save(out / f"{name}_diff_full.npy", diff.astype(np.float32))
        np.save(out / f"{name}_on_median_binned.npy", med_on.astype(np.float32))
        np.save(out / f"{name}_strength.npy", st.astype(np.float32))
        db = bin4(diff)
        lo, hi = np.percentile(db, 1), max(np.percentile(db, 99.97), np.percentile(db, 1) + 1)
        img = Image.fromarray(np.uint8(np.clip((db - lo) / (hi - lo) * 255, 0, 255))).convert("RGB")
        d = ImageDraw.Draw(img)
        d.text((4, 4), f"{name}  on-off  0..{hi:.1f} DN", fill=(255, 255, 0))
        tiles.append(img)
        info[name] = {"n": n, "strength_pct_0_20_50_80_100": [round(float(v), 2) for v in np.percentile(st, [0, 20, 50, 80, 100])],
                      "diff_binned_max": round(float(db.max()), 2), "diff_binned_argmax_yx": [int(v) for v in np.unravel_index(db.argmax(), db.shape)],
                      "diff_full_p9999": round(float(np.percentile(diff, 99.99)), 1),
                      "on_mean_full_p9999": round(float(np.percentile(acc_on / len(on), 99.99)), 1)}
        print(name, json.dumps(info[name]), flush=True)
    sheet = Image.new("RGB", (364 * 3, 272 * 2), "black")
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % 3) * 364, (k // 3) * 272))
    sheet.save(out / "look_on_minus_off.png")
    (out / "look.json").write_text(json.dumps(info, indent=2))


def gauss2d(coords, amp, x0, y0, sa, sb, theta, c):
    x, y = coords
    ct, st = np.cos(theta), np.sin(theta)
    u = (x - x0) * ct + (y - y0) * st
    v = -(x - x0) * st + (y - y0) * ct
    return (amp * np.exp(-0.5 * ((u / sa) ** 2 + (v / sb) ** 2)) + c).ravel()


def fit_gauss(img, guess):
    from scipy.optimize import curve_fit
    yy, xx = np.mgrid[: img.shape[0], : img.shape[1]].astype(float)
    p, cov = curve_fit(gauss2d, (xx, yy), img.ravel().astype(float), p0=guess, maxfev=20000)
    if p[3] < p[4]:  # make sa the major axis
        p[3], p[4], p[5] = p[4], p[3], p[5] + np.pi / 2
    p[5] = (p[5] + np.pi / 2) % np.pi - np.pi / 2
    model = gauss2d((xx, yy), *p).reshape(img.shape)
    return p, np.sqrt(np.diag(cov)), model


CROP = 256  # full-res crop side
HALF = CROP // 2


def crop(img, cy, cx):
    return img[cy - HALF: cy + HALF, cx - HALF: cx + HALF]


def bin2(img):
    return img.reshape(img.shape[0] // 2, 2, img.shape[1] // 2, 2).mean((1, 3))


def full(captures, out):
    from scipy.ndimage import median_filter
    res = {}

    # ---------------- scintillator, 200/100 ----------------
    meta, raw = open_run(captures, RUNS["Scint_200_100"])
    n = raw.shape[0]
    st = np.load(out / "Scint_200_100_strength.npy")
    on = np.where(st > 15)[0]
    off = np.where(st < 10)[0]
    off_mean = np.mean([frame(raw, i) for i in off], 0)
    on_mean = np.mean([frame(raw, i) for i in on], 0)
    diff = on_mean - off_mean
    sm = median_filter(bin4(diff), 3)
    by, bx = np.unravel_index(sm.argmax(), sm.shape)
    cy, cx = int(by * 4 + 2), int(bx * 4 + 2)
    cy = min(max(cy, HALF), H - HALF); cx = min(max(cx, HALF), W - HALF)
    c_mean = bin2(crop(diff, cy, cx))  # 128x128, 2 px per bin
    g0 = [float(c_mean.max()), 64, 64, 12, 6, 0.8, 0.0]
    p, perr, model = fit_gauss(c_mean, g0)
    resid = c_mean - model
    s_fit = {
        "frames_on": int(len(on)), "frames_off": int(len(off)), "frames_between": int(n - len(on) - len(off)),
        "crop_origin_full_yx": [cy - HALF, cx - HALF],
        "centroid_full_xy": [round(cx - HALF + 2 * p[1] + 0.5, 1), round(cy - HALF + 2 * p[2] + 0.5, 1)],
        "amp_dn": round(p[0], 2), "sigma_major_px": round(2 * p[3], 2), "sigma_minor_px": round(2 * p[4], 2),
        "fwhm_major_px": round(2.3548 * 2 * p[3], 1), "fwhm_minor_px": round(2.3548 * 2 * p[4], 1),
        "theta_deg": round(np.degrees(p[5]), 1), "offset_dn": round(p[6], 3),
        "fit_err": [round(float(v), 4) for v in perr],
        "residual_rms_dn": round(float(resid.std()), 3),
        "residual_max_abs_dn": round(float(np.abs(resid).max()), 2),
        "integrated_net_dn_px_in_crop": round(float(crop(diff, cy, cx).sum()), 0),
        "gauss_integral_dn_px": round(float(2 * np.pi * p[0] * (2 * p[3]) * (2 * p[4])), 0),
    }
    # per frame
    rows = []
    stack = []
    guess = list(p)
    for i in on:
        f = frame(raw, i)
        c_raw = crop(f, cy, cx)
        c = bin2(c_raw - crop(off_mean, cy, cx))
        stack.append(c.astype(np.float32))
        try:
            q, qe, _ = fit_gauss(c, guess)
            ok = True
        except Exception:
            q, ok = [np.nan] * 7, False
        peak3 = float(median_filter(c_raw, 3).max())
        rows.append([int(i), ok, *[float(v) for v in q], peak3, int((c_raw >= FULL_SCALE).sum()),
                     float(c_raw.sum() - crop(off_mean, cy, cx).sum())])
    rows = np.array(rows, dtype=float)
    np.save(out / "scint_perframe.npy", rows)
    np.savez_compressed(out / "scint_crops.npz", mean=c_mean.astype(np.float32), model=model.astype(np.float32),
                        frames=np.stack(stack), off_full_binned=bin4(off_mean).astype(np.float32),
                        diff_full_binned=bin4(diff).astype(np.float32))
    good = rows[rows[:, 1] == 1]
    def spread(col):
        v = good[:, col]
        return [round(float(np.mean(v)), 3), round(float(np.std(v)), 3)]
    s_fit["per_frame_fits_ok"] = int(len(good))
    s_fit["per_frame_amp_dn_mean_std"] = spread(2)
    s_fit["per_frame_x0_bin2_mean_std"] = spread(3)
    s_fit["per_frame_y0_bin2_mean_std"] = spread(4)
    s_fit["per_frame_sigma_major_bin2_mean_std"] = spread(5)
    s_fit["per_frame_sigma_minor_bin2_mean_std"] = spread(6)
    s_fit["per_frame_theta_rad_mean_std"] = spread(7)
    s_fit["per_frame_peak3x3_dn_pct_0_50_90_100"] = [round(float(v), 1) for v in np.percentile(rows[:, 9], [0, 50, 90, 100])]
    s_fit["per_frame_saturated_px_in_crop_max"] = int(rows[:, 10].max())
    s_fit["per_frame_integrated_net_pct_10_50_90"] = [round(float(v), 0) for v in np.percentile(rows[:, 11], [10, 50, 90])]
    s_fit["black_level_dn"] = round(float(np.median(off_mean)), 2)
    res["Scint_200_100"] = s_fit
    print("Scint", json.dumps(s_fit), flush=True)

    # ---------------- polycarbonate, 200/100 ----------------
    meta, raw = open_run(captures, RUNS["PC_200_100"])
    n = raw.shape[0]
    frames_b = np.stack([bin4(frame(raw, i)) for i in range(n)]).astype(np.float64)  # (n,272,364)
    M = np.median(frames_b, 0)
    # flicker model fit outside a generous box round the expected spot
    sy, sx = cy // 4, cx // 4
    mask = np.ones(M.shape, bool)
    mask[max(0, sy - 40): sy + 40, max(0, sx - 40): sx + 40] = False
    A = np.stack([np.ones(mask.sum()), M[mask]], 1)
    R = np.empty_like(frames_b)
    coefs = []
    for i in range(n):
        co, *_ = np.linalg.lstsq(A, frames_b[i][mask], rcond=None)
        coefs.append(co)
        R[i] = frames_b[i] - (co[0] + co[1] * M)
    coefs = np.array(coefs)
    # spot ellipse from the scint fit, in 4x4-binned units
    yy, xx = np.mgrid[: M.shape[0], : M.shape[1]].astype(float)
    x0 = (cx - HALF + 2 * p[1] + 0.5) / 4; y0 = (cy - HALF + 2 * p[2] + 0.5) / 4
    ct, s_ = np.cos(p[5]), np.sin(p[5])
    u = (xx - x0) * ct + (yy - y0) * s_; v = -(xx - x0) * s_ + (yy - y0) * ct
    r2 = (u / (2 * p[3] / 4)) ** 2 + (v / (2 * p[4] / 4)) ** 2
    core = r2 <= 4  # 2-sigma ellipse
    ann = (r2 > 9) & (r2 <= 25)
    net = R[:, core].mean(1) - R[:, ann].mean(1)
    np.save(out / "pc_net.npy", net.astype(np.float32))
    np.save(out / "pc_flicker_coefs.npy", coefs.astype(np.float32))
    order = np.argsort(net)
    k = max(10, n // 4)
    pc_on, pc_off = order[-k:], order[:k]
    d_on = R[pc_on].mean(0) - R[pc_off].mean(0)
    d_all = R.mean(0)
    np.savez_compressed(out / "pc_maps.npz", d_top_minus_bottom=d_on.astype(np.float32), d_all=d_all.astype(np.float32),
                        median_scene=M.astype(np.float32), core=core, ann=ann)
    # does the scintillator geometry predict where the PC light is? check the all-frames residual too
    res["PC_200_100"] = {
        "frames": n,
        "flicker_gain_pct_spread": round(float(100 * coefs[:, 1].std()), 3),
        "flicker_offset_dn_spread": round(float(coefs[:, 0].std()), 3),
        "net_core_minus_annulus_dn_pct_0_10_25_50_75_90_100": [round(float(v), 3) for v in np.percentile(net, [0, 10, 25, 50, 75, 90, 100])],
        "net_mean_dn": round(float(net.mean()), 4), "net_sem_dn": round(float(net.std() / np.sqrt(n)), 4),
        "all_frames_residual_core_minus_ann_dn": round(float(d_all[core].mean() - d_all[ann].mean()), 4),
        "spot_ellipse_center_binned_xy": [round(x0, 1), round(y0, 1)],
    }
    print("PC", json.dumps(res["PC_200_100"]), flush=True)
    (out / "full.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    stage, captures, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    {"survey": survey, "look": look, "full": full}[stage](captures, out)
