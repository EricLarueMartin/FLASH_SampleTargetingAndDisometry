import json, numpy as np, sys
sys.path.insert(0, '.')
from analyze_20261001_targets import open_run, frame, bin4, RUNS, gauss2d
from pathlib import Path
cap = Path('/home/codex/SynchronizedCameraDosimeter/dose_cam/captures')
sc = json.load(open('out/full.json'))['Scint_200_100']
pcb = json.load(open('out/pc_blocks.json'))
yy, xx = np.mgrid[:272, :364].astype(float)
def template(x0, y0, sa, sb, th):
    # in 4x4-binned coords
    return gauss2d((xx, yy), 1.0, (x0-2)/4, (y0-2)/4, sa/4, sb/4, np.radians(th), 0.0).reshape(272, 364)
def win(t):
    return t > np.exp(-0.5*16)  # 4-sigma footprint
def mf(frames_b, t, ref):
    yc, xc = np.argwhere(t == t.max())[0]
    box = (slice(max(0,yc-30), yc+30), slice(max(0,xc-30), xc+30))
    T = t[box].ravel(); A = np.stack([T, np.ones_like(T)], 1)
    out = []
    for f in frames_b:
        d = (f - ref)[box].ravel()
        co, *_ = np.linalg.lstsq(A, d, rcond=None)
        out.append(co[0])
    return np.array(out)
res = {}
# scint
meta, raw = open_run(cap, RUNS['Scint_200_100'])
st = np.load('out/Scint_200_100_strength.npy')
fb = np.stack([bin4(frame(raw, i)) for i in range(raw.shape[0])])
off = st < 10; on = st > 15
ref = fb[off].mean(0)
t = template(*sc['centroid_full_xy'], sc['sigma_major_px'], sc['sigma_minor_px'], sc['theta_deg'])
a = mf(fb, t, ref)
res['Scint_200_100'] = {'on_amp_mean': round(float(a[on].mean()),2), 'on_amp_sd': round(float(a[on].std()),2),
    'off_amp_mean': round(float(a[off].mean()),3), 'off_amp_sd': round(float(a[off].std()),3),
    'single_shot_snr': round(float(a[on].mean()/a[off].std()),0), 'on_amp_pct_10_50_90': [round(float(x),1) for x in np.percentile(a[on],[10,50,90])]}
np.save('out/scint_mf_amp.npy', a.astype(np.float32))
# PC 200 M block and PC 220, reference = PC200 L block
v = np.load('out/PC_200_100_rawcontrast.npy'); cl = np.digitize(v, [0.3, 0.75])
meta, raw = open_run(cap, RUNS['PC_200_100'])
fb = np.stack([bin4(frame(raw, i)) for i in range(raw.shape[0])])
L = fb[cl == 0]; ref = L.mean(0)
p = pcb['M_minus_L']
t = template(p['x0_full'], p['y0_full'], p['sigma_major_full_px'], p['sigma_minor_full_px'], p['theta_deg'])
a = mf(fb, t, ref)
# leave-one-out for L frames so the off-sd is honest
aL = []
Lidx = np.where(cl == 0)[0]
for j, i in enumerate(Lidx):
    r = (L.sum(0) - fb[i]) / (len(L) - 1)
    aL.append(mf(fb[i:i+1], t, r)[0])
aL = np.array(aL)
res['PC_200_100'] = {'M_amp_mean': round(float(a[cl==1].mean()),3), 'M_amp_sd': round(float(a[cl==1].std()),3),
    'L_amp_mean_loo': round(float(aL.mean()),3), 'L_amp_sd_loo': round(float(aL.std()),3),
    'H_amp_mean_at_M_position': round(float(a[cl==2].mean()),3),
    'single_shot_snr_M': round(float(a[cl==1].mean()/aL.std()),1)}
np.save('out/pc200_mf_amp.npy', a.astype(np.float32))
meta, raw = open_run(cap, RUNS['PC_220_100'])
fb2 = np.stack([bin4(frame(raw, i)) for i in range(raw.shape[0])])
a2 = mf(fb2, t, ref)
res['PC_220_100'] = {'amp_mean': round(float(a2.mean()),3), 'amp_sd': round(float(a2.std()),3), 'frames_below_half_mean': int((a2 < 0.5*a2.mean()).sum())}
np.save('out/pc220_mf_amp.npy', a2.astype(np.float32))
print(json.dumps(res, indent=1)); json.dump(res, open('out/singleshot.json','w'), indent=2)
