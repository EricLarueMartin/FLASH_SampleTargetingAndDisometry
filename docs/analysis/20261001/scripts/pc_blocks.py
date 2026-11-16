import json, numpy as np, sys
sys.path.insert(0, '.')
from analyze_20261001_targets import open_run, frame, bin4, RUNS, fit_gauss
from pathlib import Path
cap = Path('/home/codex/SynchronizedCameraDosimeter/dose_cam/captures')
v = np.load('out/PC_200_100_rawcontrast.npy')
cl = np.digitize(v, [0.3, 0.75])
meta, raw = open_run(cap, RUNS['PC_200_100'])
acc = {0: [], 1: [], 2: []}
for i in range(raw.shape[0]):
    acc[int(cl[i])].append(bin4(frame(raw, i)))
mean = {k: np.mean(a, 0) for k, a in acc.items()}
dH = mean[2] - mean[0]; dM = mean[1] - mean[0]
np.savez_compressed('out/pc_blocks.npz', dH=dH.astype(np.float32), dM=dM.astype(np.float32), L=mean[0].astype(np.float32))
# PC_220: compare with PC_200 L block
meta2, raw2 = open_run(cap, RUNS['PC_220_100'])
m220 = np.mean([bin4(frame(raw2, i)) for i in range(raw2.shape[0])], 0)
d220 = m220 - mean[0]
np.save('out/pc220_minus_pc200L.npy', d220.astype(np.float32))
sc = json.load(open('out/full.json'))['Scint_200_100']
cx, cy = sc['centroid_full_xy']; bx, by = int(round(cx/4)), int(round(cy/4))
res = {}
for name, d in [('H_minus_L', dH), ('M_minus_L', dM), ('PC220_minus_L', d220)]:
    c = d[by-32:by+32, bx-32:bx+32]
    g = [float(c.max()), 32, 32, 10/4*4, 5, 1.28, 0.0]
    try:
        p, pe, model = fit_gauss(c, [float(np.percentile(c, 99.5)), 32, 32, 10, 5, 1.28, 0.0])
        r = {'amp_dn': round(p[0],3), 'amp_err': round(pe[0],3), 'x0_full': round((bx-32+p[1])*4+2,1), 'y0_full': round((by-32+p[2])*4+2,1),
             'sigma_major_full_px': round(4*p[3],1), 'sigma_minor_full_px': round(4*p[4],1), 'theta_deg': round(np.degrees(p[5]),1),
             'offset': round(p[6],3), 'resid_rms': round(float((c-model).std()),3)}
    except Exception as e:
        r = {'fit_error': str(e)}
    r['crop_max'] = round(float(c.max()),3); r['crop_p50'] = round(float(np.median(c)),3)
    r['global_argmax_binned_yx'] = [int(x) for x in np.unravel_index(np.argmax(d), d.shape)]
    res[name] = r
    print(name, json.dumps(r))
json.dump(res, open('out/pc_blocks.json','w'), indent=2)
