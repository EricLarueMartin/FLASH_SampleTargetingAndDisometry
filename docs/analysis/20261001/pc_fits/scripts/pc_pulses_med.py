import json, numpy as np, sys
sys.path.insert(0, '.')
from analyze_20261001_targets import open_run, frame, RUNS
from pathlib import Path
from scipy.ndimage import median_filter
cap = Path('/home/codex/SynchronizedCameraDosimeter/dose_cam/captures')
H, W = 1088, 1456
CY, CX = 444, 849                      # PC spot centre (full res) from the averaged fit
Y0, X0 = CY - 128, CX - 128            # 256x256 crop
SPOT_COLS = (600, 1100)                # excluded from row-offset estimate
SPOT_ROWS = (250, 650)                 # excluded from column-offset estimate
OUTSIDE = np.ones((H, W), bool); OUTSIDE[250:650, 600:1100] = False
FAR = [(slice(720, 976), slice(80, 336)), (slice(60, 316), slice(1150, 1406))]
def b4(a): return a.reshape(a.shape[0] // 4, 4, a.shape[1] // 4, 4).mean((1, 3))
v = np.load('out/PC_200_100_rawcontrast.npy'); cl = np.digitize(v, [0.3, 0.75])
meta, raw = open_run(cap, RUNS['PC_200_100'])
Lidx = np.where(cl == 0)[0]
Lstack = np.stack([frame(raw, i) for i in Lidx]).astype(np.float32)
Lmed = np.median(Lstack, 0)
KEEP = Lstack <= Lmed[None] + 3.0          # reject radiation hits: > 3 DN (~10 sigma read noise) above the pixel median
Ssum = np.where(KEEP, Lstack, 0).sum(0); Nk = KEEP.sum(0)
Lmean = Ssum / Nk                          # hit-clipped mean reference
Lavg = Lstack.mean(0)
pos = {int(i): k for k, i in enumerate(Lidx)}
clip_frac = 1 - KEEP.mean()
colmask = np.ones(W, bool); colmask[SPOT_COLS[0]:SPOT_COLS[1]] = False
rowmask = np.ones(H, bool); rowmask[SPOT_ROWS[0]:SPOT_ROWS[1]] = False
def process(r):
    stats = {}
    rowoff = np.median(r[:, colmask], 1)
    r1 = r - rowoff[:, None]
    coloff = np.median(r1[rowmask, :], 0)
    r2 = r1 - coloff[None, :]
    glob = float(np.median(r[:, colmask]))
    stats['global_offset'] = glob
    stats['row_band_rms'] = float(np.std(rowoff - glob))
    stats['col_band_rms'] = float(np.std(coloff))
    for tag, img in [('raw', r), ('destriped', r2)]:
        vals = []
        for sl in FAR:
            bb = b4(img[sl]); vals.append(np.std(bb - np.median(bb)))
        stats[f'far_sd_b4_{tag}'] = float(np.mean(vals))
    # white noise via high-pass at 4x4 binning on destriped far boxes
    hp = []
    for sl in FAR:
        bb = b4(r2[sl]); hp.append(np.std(bb[1:-1, 1:-1] - 0.25 * (bb[:-2, 1:-1] + bb[2:, 1:-1] + bb[1:-1, :-2] + bb[1:-1, 2:])) / np.sqrt(1.25))
    stats['white_sd_b4'] = float(np.mean(hp))
    # full-res white noise and sensor hits (spikes > 8 sigma above local 3x3 median), whole frame
    sp = r2 - median_filter(r2, 3)
    sd = 1.4826 * np.median(np.abs(sp[::4, ::4]))
    stats['white_sd_full'] = float(sd)
    stats['hits'] = int((sp[OUTSIDE] > 3.0).sum())
    crop = r[Y0:Y0 + 256, X0:X0 + 256]; crop2 = r2[Y0:Y0 + 256, X0:X0 + 256]
    return stats, b4(crop).astype(np.float32), b4(crop2).astype(np.float32), crop2
out = {'PC_200_100': [], 'PC_220_100': []}
crops_raw, crops_ds, crop_full_sum, ids = [], [], {}, []
ex = {}
for run in ['PC_200_100', 'PC_220_100']:
    meta, raw = open_run(cap, RUNS[run])
    acc = np.zeros((H // 4, W // 4)); nacc = 0
    for i in range(raw.shape[0]):
        f = frame(raw, i)
        if run == 'PC_200_100' and cl[i] == 0:
            kk = pos[i]; ref = (Ssum - np.where(KEEP[kk], Lstack[kk], 0)) / np.maximum(Nk - KEEP[kk], 1)   # leave-one-out clipped mean
        else:
            ref = Lmean
        r = f - ref
        st, c4, c4d, c2 = process(r)
        st['frame'] = int(i); st['block'] = ('LMH'[cl[i]] if run == 'PC_200_100' else 'P')
        st['frame_mean_raw'] = float(f.mean())
        out[run].append(st); crops_raw.append(c4); crops_ds.append(c4d); ids.append((run, i))
        if st['block'] in ('M', 'P') and (run != 'PC_200_100' or i > 76):
            acc += b4(r - np.median(r[:, colmask], 1)[:, None]); nacc += 1
        if run == 'PC_200_100' and i == 110:
            ex['example_raw'] = b4(r).astype(np.float32); ex['example_destriped'] = b4(r - np.median(r[:, colmask], 1)[:, None]).astype(np.float32)
    ex[f'{run}_plateau_mean_destriped'] = (acc / nacc).astype(np.float32)
    print(run, 'done', len(out[run]), 'plateau frames', nacc, flush=True)
np.savez_compressed('out/pc_pulse_crops_med.npz', raw=np.stack(crops_raw), ds=np.stack(crops_ds),
                    run=np.array([r for r, _ in ids]), idx=np.array([i for _, i in ids]),
                    Lmean_b4=b4(Lmean).astype(np.float32), Lavg_minus_clip_b4=b4(Lavg - Lmean).astype(np.float32), Lmed_b4=b4(Lmed).astype(np.float32), crop_origin=np.array([Y0, X0]), **ex)
json.dump(out, open('out/pc_pulse_stats_med.json', 'w'))
for run in out:
    for k in ['global_offset', 'row_band_rms', 'col_band_rms', 'far_sd_b4_raw', 'far_sd_b4_destriped', 'white_sd_b4', 'white_sd_full', 'hits']:
        vals = np.array([s[k] for s in out[run]])
        print(run, f'{k:20s} median {np.median(vals):8.3f}  sd {vals.std():7.3f}  min {vals.min():8.3f} max {vals.max():8.3f}')
print('hit-clip fraction of reference samples: %.4f' % clip_frac)
print('Lmean raw: median %.2f  p1 %.2f p99 %.2f at-spot(4x4 mean) %.2f' % (np.median(Lmean), np.percentile(Lmean,1), np.percentile(Lmean,99), Lmean[CY-40:CY+40, CX-40:CX+40].mean()))

st = np.load('out/Scint_200_100_strength.npy')
meta, raw = open_run(cap, RUNS['Scint_200_100'])
hs = []
for i in range(raw.shape[0]):
    f = frame(raw, i); sp = f - median_filter(f, 3); hs.append(int((sp[OUTSIDE] > 3.0).sum()))
hs = np.array(hs); np.save('out/scint_hits.npy', hs)
print('scint hits outside spot region: target out (strength<10) median %d   target in (>15) median %d' % (np.median(hs[st < 10]), np.median(hs[st > 15])))
