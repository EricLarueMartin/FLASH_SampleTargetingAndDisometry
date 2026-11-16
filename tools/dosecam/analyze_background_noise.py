"""Exposure-dependent RAW background; full-resolution temporal noise, not binned noise."""
import json
import zipfile
import numpy as np
from analyze_laser_input import load, SOURCE, OUT

# Display coordinates, away from filament; upper-left and lower-right controls.
PATCHES = {'near_target': (560, 380, 680, 620),
           'upper_left': (160, 160, 400, 400),
           'lower_right': (1040, 720, 1280, 960)}

def clipped(values):
    med = np.median(values)
    scale = max(float(np.std(values[np.abs(values-med)<5])), .5)
    return values[np.abs(values-med) < 5*scale]

def main():
    _, meta = load()
    records = []
    with zipfile.ZipFile(SOURCE) as archive:
        for key in sorted(meta):
            if not key.startswith('B2'):
                continue
            m = meta[key]
            patches = {name: [] for name in PATCHES}
            with archive.open('laser_input_test/'+key+'.raw') as stream:
                for _ in range(m['frames_written']):
                    raw = np.frombuffer(stream.read(m['raw_frame_bytes']), '<u2').reshape(1088,1472)[:,:1456]
                    assert np.all(raw % 64 == 0)
                    dn = (raw >> 6)[::-1,::-1]
                    for name,(x0,y0,x1,y1) in PATCHES.items():
                        patches[name].append(dn[y0:y1,x0:x1].astype(np.float32))
            record = dict(run=key, gate_us=m['esp_width_us'], delay_us=m['esp_delay_us'],
                          exposure_us=m['esp_width_us']+14.26, frames=m['frames_written'], patches={})
            for name, images in patches.items():
                means = [float(clipped(im.ravel()).mean()) for im in images]
                variances = []
                # Disjoint temporal pairs remove fixed pattern. Remove local 16x16
                # common-mode changes before measuring random pixel fluctuations.
                for i in range(0,len(images)-1,2):
                    d = images[i+1]-images[i]
                    h,w=d.shape
                    d=d[:h//16*16,:w//16*16].reshape(h//16,16,w//16,16).transpose(0,2,1,3).reshape(-1,256)
                    d=d-np.median(d,axis=1,keepdims=True)
                    good=clipped(d.ravel())
                    variances.append(float(np.var(good)/2))
                record['patches'][name] = dict(mean_dn=float(np.mean(means)),
                    frame_sd_dn=float(np.std(means,ddof=1)), means=means,
                    noise_rms_dn=float(np.sqrt(np.mean(variances))), pair_variances=variances)
            records.append(record)
            print(key, record['gate_us'], [(n,round(p['mean_dn'],3),round(p['noise_rms_dn'],3)) for n,p in record['patches'].items()],flush=True)
    result = dict(patches=PATCHES,runs=records,groups=[])
    for width in sorted({r['gate_us'] for r in records}):
        selected=[r for r in records if r['gate_us']==width]
        group=dict(gate_us=width, exposure_us=width+14.26,frames=sum(r['frames'] for r in selected),patches={})
        for name in PATCHES:
            means=np.concatenate([r['patches'][name]['means'] for r in selected])
            variances=np.concatenate([r['patches'][name]['pair_variances'] for r in selected])
            group['patches'][name]=dict(mean_dn=float(means.mean()),frame_sd_dn=float(means.std(ddof=1)),noise_rms_dn=float(np.sqrt(variances.mean())))
        result['groups'].append(group)
    for scope,rs in [('all_groups',result['groups']),('delay_200',[r for r in records if r['delay_us']==200])]:
        result[scope+'_fits']={}
        for name in PATCHES:
            t=np.array([r['exposure_us']/1000 for r in rs])
            means=np.array([r['patches'][name]['mean_dn'] for r in rs])
            variance=np.array([r['patches'][name]['noise_rms_dn']**2 for r in rs])
            result[scope+'_fits'][name]=dict(mean_slope_dn_per_ms=float(np.polyfit(t,means,1)[0]),
                mean_intercept_dn=float(np.polyfit(t,means,1)[1]),variance_slope_dn2_per_ms=float(np.polyfit(t,variance,1)[0]),
                variance_intercept_dn2=float(np.polyfit(t,variance,1)[1]))
    (OUT/'background_noise.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='runs'},indent=2))

if __name__=='__main__':
    main()
