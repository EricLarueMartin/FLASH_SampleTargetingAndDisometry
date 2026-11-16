import json, numpy as np
from scipy.ndimage import convolve
C = np.load('scint_crops.npz'); F = C['frames'].astype(np.float64)
d = json.load(open('pulse_fits.json'))
yy, xx = np.mgrid[:128, :128].astype(float)
def g(p):
    A, x0, y0, sa, sb, th, c = p
    ct, st = np.cos(th), np.sin(th)
    u = (xx - x0) * ct + (yy - y0) * st; v = -(xx - x0) * st + (yy - y0) * ct
    return A * np.exp(-0.5 * ((u / sa) ** 2 + (v / sb) ** 2)) + c
# high-pass: pixel minus mean of its 4 neighbours; for white noise var(hp) = 1.25 var
K = np.array([[0, -.25, 0], [-.25, 1, -.25], [0, -.25, 0]])
S, V = [], []
for q in d['pulses']:
    p = q['params']; m = g(p) - p[6]
    hp = convolve(F[q['crop']] - g(p), K, mode='reflect')
    S.append(m[1:-1, 1:-1].ravel()); V.append(hp[1:-1, 1:-1].ravel() ** 2 / 1.25)
S = np.concatenate(S); V = np.concatenate(V)
edges = np.r_[np.linspace(-0.5, 5, 6), np.linspace(10, 140, 14)]
bc, bv, bn = [], [], []
for a, b in zip(edges[:-1], edges[1:]):
    s = (S >= a) & (S < b)
    if s.sum() > 200:
        # robust variance: MAD^2 of hp residual, insensitive to sensor hits
        hp = np.sqrt(V[s] * 1.25)  # |hp|
        bc.append(np.median(S[s])); bn.append(int(s.sum()))
        bv.append(np.median(V[s]) / 0.4549)  # median of chi2_1 = 0.4549 -> variance
bc, bv = np.array(bc), np.array(bv)
c2, c1, c0 = np.polyfit(bc, bv, 2)
l1, l0 = np.polyfit(bc, bv, 1)
print('bins', np.round(bc, 1)); print('var', np.round(bv, 3))
print(f'quadratic: var = {c0:.3f} + {c1:.4f} s + {c2:.6f} s^2 ; linear: var = {l0:.3f} + {l1:.4f} s')
json.dump(dict(bc=bc.tolist(), bv=bv.tolist(), n=bn, quad=[c0, c1, c2], lin=[l0, l1]), open('noise_model.json', 'w'), indent=1)
