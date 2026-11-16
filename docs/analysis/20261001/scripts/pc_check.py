import json, numpy as np, sys
sys.path.insert(0, '.')
from analyze_20261001_targets import open_run, frame, bin4, RUNS
from pathlib import Path
cap = Path('/home/codex/SynchronizedCameraDosimeter/dose_cam/captures')
m = np.load('out/pc_maps.npz'); core, ann = m['core'], m['ann']
out = {}
for name in ['PC_200_100', 'PC_220_100', 'Scint_200_100']:
    meta, raw = open_run(cap, RUNS[name])
    v = []
    for i in range(raw.shape[0]):
        b = bin4(frame(raw, i))
        v.append(b[core].mean() - b[ann].mean())
    v = np.array(v)
    np.save(f'out/{name}_rawcontrast.npy', v.astype(np.float32))
    h, e = np.histogram(v, 20)
    out[name] = {'pct_0_10_25_50_75_90_100': [round(float(x), 3) for x in np.percentile(v, [0,10,25,50,75,90,100])],
                 'hist': h.tolist(), 'edges': [round(float(x), 3) for x in e]}
    print(name, json.dumps(out[name]))
