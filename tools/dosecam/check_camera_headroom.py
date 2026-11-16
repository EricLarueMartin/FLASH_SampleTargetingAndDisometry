"""Full-resolution DN headroom for the matched filament runs."""
import json
from pathlib import Path
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/analysis/20260918'
records = json.loads((OUT / 'comparison.json').read_text())
archive_path = ROOT / 'dose_cam/captures/downloads/laser_input_test_prepared_20260918.zip'
yy, xx = np.mgrid[:1088, :1456]
roi = ((xx-800)/72)**2 + ((yy-500)/108)**2 <= 1
results = []
with zipfile.ZipFile(archive_path) as archive:
    for record in records:
        name = 'laser_input_test/' + record['run'] + '.raw'
        roi_frames = []
        frame_max = []
        target_max = []
        full_saturated = target_saturated = 0
        with archive.open(name) as stream:
            for i in range(record['frames']):
                data = stream.read(3203072)
                raw = np.frombuffer(data, '<u2').reshape(1088,1472)[:,:1456]
                assert np.all(raw % 64 == 0), 'Unexpected raw alignment'
                dn = (raw >> 6)[::-1,::-1]
                target = dn[roi]
                roi_frames.append(target)
                frame_max.append(int(dn.max()))
                target_max.append(int(target.max()))
                full_saturated += int(np.count_nonzero(dn == 1023))
                target_saturated += int(np.count_nonzero(target == 1023))
        stack = np.stack(roi_frames)
        median_image_peak = float(np.median(stack,axis=0).max())
        result = dict(position=record['position'], frames=record['frames'],
            stable_target_peak_dn=median_image_peak,
            stable_target_percent_full_scale=100*median_image_peak/1023,
            target_single_pixel_max_dn=max(target_max),
            whole_frame_single_pixel_max_dn=max(frame_max),
            median_frame_max_dn=float(np.median(frame_max)),
            median_target_frame_max_dn=float(np.median(target_max)),
            full_saturated_pixels=full_saturated, target_saturated_pixels=target_saturated,
            target_frame_max_dn=target_max, whole_frame_max_dn=frame_max)
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if not isinstance(v,list)}),flush=True)
(OUT/'camera_headroom.json').write_text(json.dumps(results,indent=2))
