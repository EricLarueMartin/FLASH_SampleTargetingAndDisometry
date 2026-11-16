import json, numpy as np
from scipy.optimize import least_squares
from scipy.ndimage import map_coordinates
rng = np.random.default_rng(1)
# ---------- load ----------
SC = np.load('/home/claude/a1001/scint_crops.npz'); SF = json.load(open('/home/claude/a1001/pulse_fits.json'))
sfull = json.load(open('/home/claude/a1001/full.json'))['Scint_200_100']; soy, sox = sfull['crop_origin_full_yx']
PCZ = np.load('/home/claude/pc/pc_pulse_crops_med.npz'); PF = json.load(open('/home/claude/pc/pc_fits.json'))
poy, pox = [int(v) for v in PCZ['crop_origin']]
def b2to4(a): return a.reshape(a.shape[0], 64, 2, 64, 2).mean((2, 4))
sc_k = [p['crop'] for p in SF['pulses'] if p['frame'] > 37]          # clear fully-on frames (no edge glow in tile)
sc_k_all = [p['crop'] for p in SF['pulses']]
S4 = b2to4(SC['frames'][sc_k].astype(float))                          # (n,64,64) 4x4 bins, origin (soy,sox)
P2 = PCZ['ds'][PF['sel200']].astype(float); P2b = PCZ['ds'][PF['sel220']].astype(float)
yy, xx = np.mgrid[:64, :64].astype(float)
def g(p):
    A, x0, y0, sa, sb, th, c, gx, gy = p; ct, st = np.cos(th), np.sin(th)
    u = (xx - x0) * ct + (yy - y0) * st; v = -(xx - x0) * st + (yy - y0) * ct
    return A * np.exp(-0.5 * ((u / sa) ** 2 + (v / sb) ** 2)) + c + gx * (xx - 32) + gy * (yy - 32)
def e2(p):
    A, x0, y0, sa, sb, th = p[:6]; ct, st = np.cos(th), np.sin(th)
    u = (xx - x0) * ct + (yy - y0) * st; v = -(xx - x0) * st + (yy - y0) * ct
    return (u / sa) ** 2 + (v / sb) ** 2
def prep(img, p0):
    """best-effort background: destripe rows on pixels outside 4 sigma, then fit Gaussian + tilted plane"""
    img = img.copy()
    for _ in range(2):
        r = least_squares(lambda p: (g(p) - img).ravel(), p0, x_scale='jac'); p0 = r.x
        far = e2(p0) > 16
        bgfit = g(np.r_[0, p0[1:]])   # plane only
        rowoff = np.array([np.median((img - bgfit)[i][far[i]]) if far[i].sum() > 8 else 0 for i in range(64)])
        img = img - rowoff[:, None]
    r = least_squares(lambda p: (g(p) - img).ravel(), p0, x_scale='jac'); p = r.x
    if p[3] < p[4]: p[3], p[4], p[5] = p[4], p[3], p[5] + np.pi / 2
    p[5] = (p[5] + np.pi / 2) % np.pi - np.pi / 2
    net = img - (g(np.r_[0, p[1:]]))           # remove plane + offset
    return p, net
def moments(net, p, R=3.0):
    """model-independent rms widths along the fitted axes inside an R-sigma ellipse"""
    m = e2(p) <= R * R; w = np.clip(net, 0, None) * m
    x0 = (w * xx).sum() / w.sum(); y0 = (w * yy).sum() / w.sum()
    ct, st = np.cos(p[5]), np.sin(p[5]); u = (xx - x0) * ct + (yy - y0) * st; v = -(xx - x0) * st + (yy - y0) * ct
    su = np.sqrt((w * u * u).sum() / w.sum()); sv = np.sqrt((w * v * v).sum() / w.sum())
    trunc = np.sqrt(1 - R * R * np.exp(-R * R / 2) / (1 - np.exp(-R * R / 2)) / 2)  # rms of a Gaussian truncated at R sigma (2D, per axis approx)
    return x0, y0, su / trunc, sv / trunc
def fwhm(net, p, axis):
    t = np.linspace(-30, 30, 601); ang = p[5] + (0 if axis == 0 else np.pi / 2)
    acc = 0
    for wofs in np.linspace(-1, 1, 5):
        xs = p[1] + t * np.cos(ang) - wofs * np.sin(ang); ys = p[2] + t * np.sin(ang) + wofs * np.cos(ang)
        acc = acc + map_coordinates(net, [ys, xs], order=1)
    prof = acc / 5; half = prof.max() / 2; above = np.where(prof >= half)[0]
    def cross(i0, i1):
        return t[i0] + (half - prof[i0]) * (t[i1] - t[i0]) / (prof[i1] - prof[i0])
    lo = cross(above[0] - 1, above[0]); hi = cross(above[-1], above[-1] + 1)
    return hi - lo
def measure(stack, origin):
    img = stack.mean(0); p0 = [img.max(), 32, 32, 8.5, 5, 1.27, 0, 0, 0]
    p, net = prep(img, p0); mx, my, su, sv = moments(net, p)
    return dict(A=p[0], x=origin[1] + 4 * p[1] + 2, y=origin[0] + 4 * p[2] + 2, s_major=4 * p[3], s_minor=4 * p[4], theta=np.degrees(p[5]),
                rms_major=4 * su, rms_minor=4 * sv, fwhm_major=4 * fwhm(net, p, 0), fwhm_minor=4 * fwhm(net, p, 1)), p, net
def boot(stack, origin, n=200):
    out = []
    for _ in range(n):
        s = stack[rng.integers(0, len(stack), len(stack))]
        out.append(measure(s, origin)[0])
    return {k: float(np.std([o[k] for o in out])) for k in out[0]}
res = {}
for name, stack, org in [('scint', S4, (soy, sox)), ('pc200', P2, (poy, pox)), ('pc220', P2b, (poy, pox))]:
    m, p, net = measure(stack, org); e = boot(stack, org)
    res[name] = {k: (round(float(m[k]), 3), round(e[k], 3)) for k in m}; res[name]['n'] = len(stack)
    np.save(f'{name}_net.npy', net.astype(np.float32)); np.save(f'{name}_p.npy', p)
    print(name, len(stack), {k: f'{v[0]:.2f}±{v[1]:.2f}' for k, v in res[name].items() if k != 'n'})
# scint with near-edge frames included, and split by time block, for drift
for name, ks in [('scint_all', sc_k_all), ('scint_blockA', [p['crop'] for p in SF['pulses'] if 37 < p['frame'] < 60]), ('scint_blockB', [p['crop'] for p in SF['pulses'] if p['frame'] > 100])]:
    m, p, net = measure(b2to4(SC['frames'][ks].astype(float)), (soy, sox)); res[name] = {k: round(float(v), 3) for k, v in m.items()}; res[name]['n'] = len(ks)
    print(name, len(ks), {k: round(v, 2) for k, v in res[name].items()})
json.dump(res, open('compare.json', 'w'), indent=1)
