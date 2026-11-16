import json, numpy as np
from scipy.optimize import least_squares

C = np.load('scint_crops.npz'); rows = np.load('scint_perframe.npy'); amp = np.load('scint_mf_amp.npy')
F = C['frames'].astype(np.float64)            # (107,128,128) bin2, net of target-out mean
fidx = rows[:, 0].astype(int)                 # frame number of each crop
full = json.load(open('full.json'))['Scint_200_100']
oy, ox = full['crop_origin_full_yx']

# ---- select fully-on pulses: amplitude plateau
core = np.r_[30:51, 125:161]
pm, ps = np.median(amp[core]), np.std(amp[core])
thr = pm - 2.5 * ps
sel = np.where(amp[fidx] >= thr)[0]
excluded_edge = [int(f) for f in fidx if thr - 25 < amp[f] < thr]
print(f'plateau median {pm:.1f} sd {ps:.2f} thr {thr:.1f}; selected {len(sel)}; borderline excluded {excluded_edge}')

yy, xx = np.mgrid[:128, :128].astype(float)
def g(p):
    A, x0, y0, sa, sb, th, c = p
    ct, st = np.cos(th), np.sin(th)
    u = (xx - x0) * ct + (yy - y0) * st; v = -(xx - x0) * st + (yy - y0) * ct
    return A * np.exp(-0.5 * ((u / sa) ** 2 + (v / sb) ** 2)) + c

def fit(img, p0, w=None, mask=None):
    m = np.ones_like(img, bool) if mask is None else mask
    W = np.ones_like(img) if w is None else w
    f = lambda p: ((g(p) - img) * W)[m]
    r = least_squares(f, p0, x_scale='jac')
    return r.x

def ell_r2(p):
    A, x0, y0, sa, sb, th, c = p
    ct, st = np.cos(th), np.sin(th)
    u = (xx - x0) * ct + (yy - y0) * st; v = -(xx - x0) * st + (yy - y0) * ct
    return (u / sa) ** 2 + (v / sb) ** 2

# ---- pass 1: unweighted fits, background noise from far region
p0 = [130, 64, 64, 17, 9.5, 1.27, 0]
P1, bgsd = [], []
for k in sel:
    p = fit(F[k], p0); P1.append(p)
    far = ell_r2(p) > 36  # beyond 6 sigma
    r = F[k] - g(p)
    bgsd.append(1.4826 * np.median(np.abs(r[far] - np.median(r[far]))))
P1 = np.array(P1); bgsd = np.array(bgsd)

# ---- photon transfer from temporal variance of amplitude-normalised frames near the peak
Aref = np.median(P1[:, 0])
N = np.stack([(F[k] - P1[j, 6]) * Aref / P1[j, 0] for j, k in enumerate(sel)])
Mmean = N.mean(0); Mvar = N.var(0, ddof=1)
peak_region = ell_r2(np.median(P1, 0)) < 0.25        # inside 0.5 sigma: small gradient
mid_region = (ell_r2(np.median(P1, 0)) > 1) & (ell_r2(np.median(P1, 0)) < 2.25)
bg_var = np.median(bgsd) ** 2
# shot variance scales with signal; fit var = bg + k*mean over r<1.5 sigma pixels binned by mean
reg = ell_r2(np.median(P1, 0)) < 2.25
mm, vv = Mmean[reg], Mvar[reg]
bins = np.linspace(mm.min(), mm.max(), 12)
bc, bv = [], []
for a, b in zip(bins[:-1], bins[1:]):
    s = (mm >= a) & (mm < b)
    if s.sum() > 20:
        bc.append(np.median(mm[s])); bv.append(np.median(vv[s]))
bc, bv = np.array(bc), np.array(bv)
nm = json.load(open('noise_model.json')); var0, kshot, kq = nm['quad']
print(f'background sd per bin2 px: median {np.median(bgsd):.3f} DN; noise model var = bg^2 + {kshot:.4f} s + {kq:.2e} s^2')
# (temporal variance also includes real pulse-to-pulse shape change, so kshot is an upper bound on shot noise)

# ---- pass 2: weighted fits, mask sensor hits, chi2
import os
GLOBAL_FLOOR = float(os.environ['FLOOR']) if os.environ.get('FLOOR') else None
res = []; store_model = []; store_z = []
for j, k in enumerate(sel):
    img = F[k]; p = P1[j]
    sp = np.clip(g(p) - p[6], 0, None); var = bgsd[j] ** 2 + kshot * sp + kq * sp ** 2
    # model-independent sensor-hit detector: compact positive spikes above the local 5x5 median
    from scipy.ndimage import median_filter, binary_dilation
    hp = img - median_filter(img, 5)
    hit = hp / np.sqrt(var) > 5
    hit = binary_dilation(hit, iterations=1)
    # noise floor from this frame's own empty region (>6 sigma), plain variance so row banding counts
    farm = (ell_r2(p) > 36) & ~hit
    rf = (img - g(p))[farm]
    for _ in range(5):  # sigma-clip: drops hit halos, keeps Gaussian-like banding
        sd = rf.std(); rf = rf[np.abs(rf - rf.mean()) < 4 * sd]
    bgsd[j] = float(rf.std()) if GLOBAL_FLOOR is None else GLOBAL_FLOOR
    sp = np.clip(g(p) - p[6], 0, None); var = bgsd[j] ** 2 + kshot * sp + kq * sp ** 2
    p = fit(img, p, w=1 / np.sqrt(var), mask=~hit)
    sp = np.clip(g(p) - p[6], 0, None); var = bgsd[j] ** 2 + kshot * sp + kq * sp ** 2
    model = g(p); resid = img - model
    z = resid / np.sqrt(var)
    good = ~hit
    dof = good.sum() - 7
    chi2 = float((z[good] ** 2).sum()); chi2n = chi2 / dof
    e2 = ell_r2(p)
    in2 = (e2 <= 4) & good; in3 = (e2 <= 9) & good
    sig = img - p[6]
    r2_3 = 1 - (resid[in3] ** 2).sum() / ((sig[in3] - sig[in3].mean()) ** 2).sum()
    chi2n_core = float((z[in2] ** 2).mean())
    chi2_far = float((z[(e2 > 36) & good] ** 2).mean())
    sys_var = max(0.0, float((resid[in2] ** 2).mean() - var[in2].mean()))
    sys_pct = float(np.sqrt(sys_var) / p[0] * 100)
    rms2 = float(np.sqrt((resid[in2] ** 2).mean()) / p[0] * 100)
    maxr = float(np.abs(resid[in3]).max() / p[0] * 100)
    # background-only chi2 in the core, to show how much signal-dependent noise matters
    store_model.append(model.astype(np.float32)); store_z.append(np.where(good, z, np.nan).astype(np.float32))
    res.append(dict(frame=int(fidx[k]), crop=int(k), A=p[0], x_full=ox + 2 * p[1] + 0.5, y_full=oy + 2 * p[2] + 0.5,
                    sigma_major_px=2 * max(p[3], p[4]), sigma_minor_px=2 * min(p[3], p[4]),
                    theta_deg=float(np.degrees(((p[5] if p[3] >= p[4] else p[5] + np.pi / 2) + np.pi / 2) % np.pi - np.pi / 2)),
                    offset=p[6], chi2_red=chi2n, chi2_red_core2sig=chi2n_core, chi2_far=chi2_far, systematic_misfit_core_pct=sys_pct, dof=int(dof), r2_3sig=float(r2_3),
                    resid_rms_core_pct=rms2, resid_max_3sig_pct=maxr, hits_masked=int(hit.sum()), bg_sd=float(bgsd[j]),
                    params=[float(x) for x in p]))
json.dump(dict(plateau_median=float(pm), plateau_sd=float(ps), threshold=float(thr), borderline_excluded=excluded_edge,
               noise=dict(bg_sd_median=float(np.median(bgsd)), model='var = bg_sd^2 + k1*s + k2*s^2 (bin2 DN)', k1=float(kshot), k2=float(kq), hp_var0=float(var0)),
               pulses=res), open('pulse_fits.json', 'w'), indent=1)
np.savez_compressed('pulse_models.npz', model=np.stack(store_model), z=np.stack(store_z), sel=sel)
np.savez_compressed('pulse_ptc.npz', bc=bc, bv=bv, Mmean=Mmean.astype(np.float32), Mvar=Mvar.astype(np.float32))
t = np.array([[d['chi2_red'], d['chi2_red_core2sig'], d['r2_3sig'], d['resid_rms_core_pct'], d['resid_max_3sig_pct'], d['hits_masked']] for d in res])
for name, col in zip(['chi2_red', 'chi2_core', 'R2_3sig', 'rms_core_%', 'max_3sig_%', 'hits'], t.T):
    print(f'{name:11s} median {np.median(col):8.3f}  min {col.min():8.3f}  max {col.max():8.3f}')
