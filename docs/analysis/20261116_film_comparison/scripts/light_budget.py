"""Reproduce the literature-based sensitivity calculation; no hardware access.

Run with Python + NumPy >=2.0. Outputs light_budget.json beside this script's parent.
Curve points are approximate visual readings, NOT manufacturer tabulated data.
Absolute PC yield and stopping power below are scaling assumptions; see RESEARCH.md.
"""
from pathlib import Path
import json
import math
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "light_budget.json"
wl = np.arange(300.0, 1101.0)
# Nakamura et al. (2014), Fig. 4, emission under 310-nm optical excitation.
# This is a proxy for the scintillation spectrum, not a beam-on spectrum.
s_wl = [300, 325, 330, 335, 340, 345, 350, 355, 360, 365, 370,
        380, 390, 400, 410, 420, 430, 450, 1100]
s_y = [0, 0, .35, .6, .67, .82, 1, .97, .85, .80, .75,
       .44, .29, .16, .09, .05, .02, 0, 0]
# Teledyne FLIR FFY-U3-16S2M-DL EMVA spectral response graph, 2022-11-22.
q_wl = [300, 325, 350, 375, 400, 425, 450, 475, 500, 525,
        550, 575, 600, 625, 650, 675, 700, 750, 800, 850, 900, 950, 1000, 1050, 1100]
q_y = [.06, .12, .20, .30, .43, .53, .60, .615, .64, .65,
       .65, .63, .61, .57, .54, .49, .43, .33, .27, .18, .12, .06, .025, .008, 0]
s = np.interp(wl, s_wl, s_y)
q = np.interp(wl, q_wl, q_y)
integrate = np.trapezoid
beta = math.sqrt(1 - (1 / (1 + 30 / .51099895)) ** 2)
n = 1.585
length_mm = .5
# nm/mm conversion: 1 mm = 1e6 nm.
c = (2 * math.pi / 137.035999084 * length_mm * 1e6
     * (1 - 1 / (beta * n) ** 2) / wl ** 2)
pc_yield_proxy = .67 / 7 * 10000  # relative light-output chain, not absolute LY
edep_proxy = 1.2 * .05 * 2.0     # rho * thickness_cm * assumed collision stopping
ns = pc_yield_proxy * edep_proxy
nc = float(integrate(c, wl))
qs = float(integrate(s*q, wl) / integrate(s, wl))
nc_q = float(integrate(c*q, wl))
ns_q = ns * qs
spectral_scenarios = []
for uv_transmission in [1.0, .2, .01]:
    for cherenkov_relative_collection in [.1, 1.0, 4.0]:
        det_s = ns_q * uv_transmission
        det_c = nc_q * cherenkov_relative_collection
        spectral_scenarios.append({
            "scintillation_relative_throughput": uv_transmission,
            "cherenkov_relative_angular_collection": cherenkov_relative_collection,
            "scintillation_fraction": det_s / (det_s + det_c),
        })
gain_rows = []
for gain in [8.0, 10.7, 12.0]:
    total = 180000 * gain
    fitted = 100 * 1.42 / math.sqrt(total)
    gain_rows.append({"e_per_DN": gain, "spot_e": total,
                      "peak_pixel_shot_pct": 100/math.sqrt(42*gain),
                      "window_10x10_shot_pct": 100/math.sqrt(4200*gain),
                      "whole_spot_shot_pct": 100/math.sqrt(total),
                      "fitted_peak_shot_pct": fitted})
result = {
    "warning": "Conditional sensitivity model, not a measured component separation or confidence interval",
    "band_nm": [300, 1100], "pc_yield_proxy_ph_MeV": pc_yield_proxy,
    "edep_proxy_MeV": edep_proxy, "scintillation_photons_proxy": ns,
    "cherenkov_photons": nc,
    "cherenkov_300_700_photons": float(integrate(c[wl <= 700], wl[wl <= 700])),
    "cherenkov_400_700_photons": float(integrate(c[(wl >= 400) & (wl <= 700)], wl[(wl >= 400) & (wl <= 700)])),
    "mean_QE_scintillation": qs, "mean_QE_cherenkov": nc_q/nc,
    "scintillation_QE_weighted": ns_q, "cherenkov_QE_weighted": nc_q,
    "scintillation_production_fraction_proxy": ns/(ns+nc),
    "scintillation_equal_throughput_fraction_proxy": ns_q/(ns_q+nc_q),
    "theta_C_deg": math.degrees(math.acos(1/(beta*n))),
    "critical_angle_deg": math.degrees(math.asin(1/n)),
    "camera_internal_angle_deg": math.degrees(math.asin(math.sin(math.radians(30))/n)),
    "diffuse_reflector_scenarios": [
        {"scintillation_relative_throughput": t, "single_bounce_diffuse_fraction": d,
         "scintillation_fraction": ns_q*t/(ns_q*t+nc_q*(4*.9*math.cos(math.asin(.5/n))/(1+.9))*d)}
        for t in [1.0, .2, .01] for d in [.01, .1]
    ],
    "spectral_scenarios": spectral_scenarios, "gain_rows": gain_rows,
    "conditional_calibration_pct": {str(f): math.hypot(1.09, f) for f in [3.0, 3.1, 5.0]},
    "read_noise_plus_quantization_DN": math.hypot(4.69/10.7, 1/math.sqrt(12)),
    "curve_points": {"emission_nm": s_wl, "emission_relative": s_y,
                     "QE_nm": q_wl, "QE_fraction": q_y},
}
OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k not in ["curve_points", "spectral_scenarios"]}, indent=2))
