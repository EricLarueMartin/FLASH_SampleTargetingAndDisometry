import json, sys, numpy as np
from scipy.optimize import least_squares
from scipy.ndimage import median_filter, binary_dilation
SRC = sys.argv[1] if len(sys.argv) > 1 else 'pc_pulse_crops_med.npz'
Z = np.load(SRC); X = Z['ds'].astype(np.float64); RAW = Z['raw'].astype(np.float64)
run = Z['run']; idx = Z['idx']; y0c, x0c = [int(v) for v in Z['crop_origin']]
v = np.load('/home/claude/a1001/PC_200_100_rawcontrast.npy'); cl = np.digitize(v, [0.3, 0.75])
is200 = run == 'PC_200_100'
sel200 = np.where(is200 & (idx >= 82) & (cl[np.clip(idx, 0, 137)] == 1))[0]
sel220 = np.where(run == 'PC_220_100')[0]
null = np.where(is200 & (idx < 43) & (cl[np.clip(idx, 0, 137)] == 0))[0]
K1_4 = 0.0208 / 4                      # shot-noise slope at 4x4 binning (from scintillator photon transfer)
yy, xx = np.mgrid[:64, :64].astype(float)
def g(p):
    A, x0, y0, sa, sb, th, c = p; ct, st = np.cos(th), np.sin(th)
    u = (xx - x0) * ct + (yy - y0) * st; vv = -(xx - x0) * st + (yy - y0) * ct
    return A * np.exp(-0.5 * ((u / sa) ** 2 + (vv / sb) ** 2)) + c
def e2(p):
    A, x0, y0, sa, sb, th, c = p; ct, st = np.cos(th), np.sin(th)
    u = (xx - x0) * ct + (yy - y0) * st; vv = -(xx - x0) * st + (yy - y0) * ct
    return (u / sa) ** 2 + (vv / sb) ** 2
LO = [-5, 16, 16, 2, 1.5, -np.pi, -5]; HI = [20, 48, 48, 25, 25, np.pi, 5]
def fit(img, p0, w, m, lo=LO, hi=HI):
    r = least_squares(lambda p: ((g(p) - img) * w)[m], p0, bounds=(lo, hi), x_scale='jac')
    J = r.jac; cov = None
    try:
        cov = np.linalg.inv(J.T @ J)
    except np.linalg.LinAlgError:
        pass
    return r.x, (np.sqrt(np.diag(cov)) if cov is not None else np.full(7, np.nan))
# template from the stacked mean of the 200 us plateau
T = {}
for name, s in [('PC_200_100', sel200), ('PC_220_100', sel220)]:
    mimg = X[s].mean(0)
    p, pe = fit(mimg, [1.4, 32, 32, 8.5, 5, 1.3, 0], np.ones_like(mimg), np.ones_like(mimg, bool))
    if p[3] < p[4]: p[3], p[4], p[5] = p[4], p[3], p[5] + np.pi / 2
    p[5] = (p[5] + np.pi / 2) % np.pi - np.pi / 2
    T[name] = dict(params=p.tolist(), err=pe.tolist(), x_full=x0c + 4 * p[1] + 2, y_full=y0c + 4 * p[2] + 2,
                   sigma_major_px=4 * p[3], sigma_minor_px=4 * p[4], theta_deg=float(np.degrees(p[5])), n=int(len(s)))
    print(name, 'mean-image fit: A %.3f±%.3f  sigma %.1f x %.1f px  theta %.1f  c %.3f' % (p[0], pe[0], 4*p[3], 4*p[4], np.degrees(p[5]), p[6]))
tp = np.array(T['PC_200_100']['params'])
shape = g([1, *tp[1:6], 0])
far = e2(tp) > 16    # beyond 4 sigma of the mean spot
core = e2(tp) <= 4; in3 = e2(tp) <= 9
res = []
for k in range(len(X)):
    img = X[k]
    # robust local background noise: sigma-clipped sd outside 4 sigma
    rf = img[far] - np.median(img[far])
    for _ in range(5):
        sd = rf.std(); rf = rf[np.abs(rf) < 4 * sd]
    bg = float(rf.std())
    hp = img - median_filter(img, 3)
    hit = binary_dilation(hp > 5 * bg, iterations=1)
    var = bg ** 2 + K1_4 * np.clip(shape * 1.4, 0, None)
    w = 1 / np.sqrt(var); m = ~hit
    # null model: constant only
    c0 = np.sum((img * w * w)[m]) / np.sum((w * w)[m]); chi0 = float((((img - c0) * w)[m] ** 2).sum())
    # fixed shape: A*shape + c (linear)
    Aa = np.stack([shape[m], np.ones(m.sum())], 1) * w[m][:, None]
    sol, *_ = np.linalg.lstsq(Aa, img[m] * w[m], rcond=None)
    covf = np.linalg.inv(Aa.T @ Aa); Afix, Afix_err = float(sol[0]), float(np.sqrt(covf[0, 0]))
    chifix = float((((img - (sol[0] * shape + sol[1])) * w)[m] ** 2).sum())
    # free Gaussian
    p, pe = fit(img, [max(Afix, 0.3), *tp[1:6], sol[1]], w, m)
    model = g(p); z = (img - model) * w
    dof = int(m.sum() - 7); chif = float((z[m] ** 2).sum())
    sa, sb, th = p[3], p[4], p[5]
    if sa < sb: sa, sb, th = sb, sa, th + np.pi / 2
    th = (th + np.pi / 2) % np.pi - np.pi / 2
    sig = img - p[6]; mm = in3 & m
    r2 = 1 - ((img - model)[mm] ** 2).sum() / ((sig[mm] - sig[mm].mean()) ** 2).sum()
    res.append(dict(k=k, run=str(run[k]), frame=int(idx[k]), group=('plateau' if k in set(sel200) | set(sel220) else ('null' if k in set(null) else 'other')),
                    bg_sd=bg, hits_masked=int(hit.sum()), A_fixed=Afix, A_fixed_err=Afix_err, snr_fixed=Afix / Afix_err,
                    A=float(p[0]), A_err=float(pe[0]), x_full=x0c + 4 * p[1] + 2, y_full=y0c + 4 * p[2] + 2,
                    x_err_px=float(4 * pe[1]), y_err_px=float(4 * pe[2]),
                    sigma_major_px=float(4 * sa), sigma_minor_px=float(4 * sb), sigma_major_err_px=float(4 * (pe[3] if p[3] >= p[4] else pe[4])),
                    sigma_minor_err_px=float(4 * (pe[4] if p[3] >= p[4] else pe[3])), theta_deg=float(np.degrees(th)), offset=float(p[6]),
                    chi2_red=chif / dof, chi2_red_core2sig=float((z[core & m] ** 2).mean()), chi2_far=float((z[far & m] ** 2).mean()),
                    chi2_red_null=chi0 / (m.sum() - 1), chi2_red_fixed=chifix / (m.sum() - 2),
                    delta_chi2_null_minus_free=chi0 - chif, delta_chi2_fixed_minus_free=chifix - chif, dof=dof, r2_3sig=float(r2),
                    params=[float(x) for x in p]))
json.dump(dict(template=T, k1_4x4=K1_4, sel200=sel200.tolist(), sel220=sel220.tolist(), null=null.tolist(), pulses=res), open('pc_fits.json', 'w'), indent=1)
def summ(group, runname=None):
    L = [r for r in res if r['group'] == group and (runname is None or r['run'] == runname)]
    out = {}
    for kk in ['bg_sd', 'hits_masked', 'A_fixed', 'A_fixed_err', 'snr_fixed', 'A', 'A_err', 'sigma_major_px', 'sigma_major_err_px', 'sigma_minor_px', 'sigma_minor_err_px', 'x_err_px', 'y_err_px',
               'chi2_red', 'chi2_red_core2sig', 'chi2_far', 'chi2_red_null', 'delta_chi2_null_minus_free', 'delta_chi2_fixed_minus_free', 'r2_3sig']:
        vv = np.array([r[kk] for r in L]); out[kk] = (round(float(np.median(vv)), 3), round(float(np.percentile(vv, 10)), 3), round(float(np.percentile(vv, 90)), 3))
    return len(L), out
for gname, rn in [('plateau', 'PC_200_100'), ('plateau', 'PC_220_100'), ('null', None)]:
    n, o = summ(gname, rn); print('\n==', gname, rn, n)
    for kk, vv in o.items(): print(f'  {kk:28s} {vv}')
