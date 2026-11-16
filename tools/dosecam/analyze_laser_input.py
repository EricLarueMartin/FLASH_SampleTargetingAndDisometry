"""Exploratory analysis of the September 18 filament camera data."""
import json
from pathlib import Path
import zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'analysis' / '20260918'
CACHE = ROOT / 'dose_cam' / 'captures' / 'analysis'
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
SOURCE = Path('E:/Downloads/laser_input_test_directory.zip')
if not SOURCE.exists():
    SOURCE = ROOT / 'dose_cam' / 'captures' / 'downloads' / 'laser_input_test_prepared_20260918.zip'


def load():
    cache = CACHE / 'binned_frames.npz'
    meta_path = CACHE / 'metadata.json'
    if cache.exists():
        return dict(np.load(cache)), json.loads(meta_path.read_text())
    frames, metadata = {}, {}
    with zipfile.ZipFile(SOURCE) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith('.json'):
                continue
            meta = json.loads(archive.read(name))
            key = Path(name).stem
            metadata[key] = meta
            run = []
            with archive.open(name[:-5] + '.raw') as stream:
                for _ in range(meta['frames_written']):
                    raw = stream.read(meta['raw_frame_bytes'])
                    image = np.frombuffer(raw, '<u2').reshape(1088, 1472)[:, :1456]
                    if image.max() > 1023:
                        image = image >> 6
                    # Match web display orientation; 4x4 averaging retains linear DN.
                    image = image[::-1, ::-1].reshape(272, 4, 364, 4).mean((1, 3)).astype(np.float32)
                    run.append(image)
            frames[key] = np.stack(run)
            print(key, len(run), 'mean range', frames[key].mean((1, 2)).min(), frames[key].mean((1, 2)).max(), flush=True)
    np.savez_compressed(cache, **frames)
    meta_path.write_text(json.dumps(metadata, indent=2))
    return frames, metadata


def overview(frames, meta):
    keys = [k for k in sorted(frames) if meta[k]['esp_delay_us'] == 200 and meta[k]['esp_width_us'] == 100]
    sheet = Image.new('RGB', (1092, len(keys)*305), 'white')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    for row, key in enumerate(keys):
        cube = frames[key]
        means = cube.mean((1, 2))
        for col, index in enumerate([int(means.argmin()), int(np.argsort(means)[len(means)//2]), int(means.argmax())]):
            image = Image.fromarray(np.uint8(np.clip((cube[index]-58)/32*255, 0, 255)))
            sheet.paste(image, (col*364, row*305+30))
            draw.text((col*364+4, row*305+5), f'{key.split("_")[0]} frame {index+1}/{len(cube)}; mean {means[index]:.1f} DN', fill='black', font=font)
    sheet.save(OUT / 'frame_overview.png')


def background(image, rx=18, ry=27):
    yy, xx = np.mgrid[:272, :364]
    x, y = xx-200, yy-125
    roi = (x/rx)**2 + (y/ry)**2 <= 1
    ring = ((x/43)**2 + (y/48)**2 <= 1) & ((x/25)**2 + (y/35)**2 > 1)
    design = np.stack([np.ones_like(x), x, y], axis=-1).astype(float)
    keep = ring.copy()
    for _ in range(4):
        coeff = np.linalg.lstsq(design[keep], image[keep], rcond=None)[0]
        residual = image - design @ coeff
        mad = max(.2, 1.4826*np.median(np.abs(residual[keep]-np.median(residual[keep]))))
        keep = ring & (np.abs(residual) < 3*mad)
    return residual, roi


def compare(frames, meta):
    keys = [k for k in sorted(frames) if meta[k]['esp_delay_us'] == 200 and meta[k]['esp_width_us'] == 100]
    results = []
    # Same-width off-time exposures; target is absent in both. Avoid subtracting
    # adjacent on-time frames, which contain the desired light themselves.
    dark_keys = [k for k in frames if k.startswith('B2') and meta[k]['esp_width_us']==100 and meta[k]['esp_delay_us'] in (1,100)]
    dark = np.median(np.concatenate([frames[k] for k in dark_keys]), axis=0)
    sheet = Image.new('RGB', (1080, 650), 'white')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
    for index, key in enumerate(keys):
        cube = frames[key]
        median = np.median(cube, axis=0)
        residual, roi = background(median)
        dark_residual, _ = background(median-dark)
        values = [float(background(im)[0][roi].sum()*16) for im in cube]
        result = dict(position=key[:2], run=key, frames=len(cube),
                      median_image_net_dn=float(residual[roi].sum()*16),
                      off_time_subtracted_dn=float(dark_residual[roi].sum()*16),
                      frame_net_dn_median=float(np.median(values)),
                      frame_net_dn_q25=float(np.percentile(values,25)),
                      frame_net_dn_q75=float(np.percentile(values,75)),
                      peak_binned_net_dn=float(residual[roi].max()),
                      net_by_frame=values,
                      aperture_sensitivity={str(r):float(background(median,r,r*1.5)[0][background(median,r,r*1.5)[1]].sum()*16) for r in (12,18,24)})
        results.append(result)
        crop = residual[80:175,150:250]
        norm = np.clip(crop/20,0,1)
        rgb = np.stack([norm, np.sqrt(norm)*.8, norm*.15],axis=-1)
        tile = Image.fromarray(np.uint8(rgb*255)).resize((300,285))
        x,y = (index%3)*360,(index//3)*325
        sheet.paste(tile,(x+25,y+30))
        draw.text((x+25,y+5),f'{key[:2]}   net {result["median_image_net_dn"]:.0f} DN-pixels',font=font,fill='black')
    sheet.save(OUT/'background_subtracted.png')
    (OUT/'comparison.json').write_text(json.dumps(results,indent=2))
    print(json.dumps([{k:v for k,v in r.items() if k!='net_by_frame'} for r in results],indent=2))
    # Timing medians on a common linear scale for visual comparison.
    keys = [k for k in sorted(frames) if k.startswith('B2')]
    sheet = Image.new('RGB',(4*300,((len(keys)+3)//4)*245),'white')
    draw=ImageDraw.Draw(sheet)
    timing=[]
    for i,key in enumerate(keys):
        im=np.median(frames[key],axis=0)
        residual,roi=background(im)
        crop=residual[80:175,150:250]
        tile=Image.fromarray(np.uint8(np.clip(crop/20,0,1)*255)).resize((220,209))
        x,y=i%4*300,i//4*245
        sheet.paste(tile,(x,y+30))
        draw.text((x,y+4),f'{meta[key]["esp_delay_us"]} us / {meta[key]["esp_width_us"]} us; n={len(frames[key])}',font=font,fill='black')
        timing.append(dict(run=key,delay=meta[key]['esp_delay_us'],gate=meta[key]['esp_width_us'],signal=float(residual[roi].sum()*16)))
    sheet.save(OUT/'timing_medians.png')
    (OUT/'timing.json').write_text(json.dumps(timing,indent=2))
    # Reader-facing report, preserving analysis assumptions and limitations.
    materials = {'A1':'SUNLU transparent PETG','A2':'Bambu transparent brown PETG','A3':'SUNLU transparent orange PETG',
                 'B1':'IEMAI transparent ocean blue PLA','B2':'Bambu transparent pink PETG','B3':'Bambu transparent teal PETG'}
    ref=results[0]['median_image_net_dn']
    lines=['# Filament comparison — 18 September 2026','',
      'Exploratory relative collected-light comparison; no independent dose normalization.', '',
      '## Method','',
      'All six comparison runs use 200 us delay and 100 us gate. Decode R16 by shifting the left-aligned 10-bit values six bits; exclude row padding; rotate 180 degrees to match the UI. Average 4x4 pixels, form a temporal median per run to suppress sparse radiation-hit specks/tracks, and fit a robust local background plane around the target.', '',
      'Use the same elliptical aperture centered at binned (200,125), radii (18,27), equivalent to full-resolution (800,500) and radii (72,108). Background uses an outer ellipse of radii (43,48), excluding an inner ellipse of (25,35), with iterative 3-MAD outlier rejection. Sum signed residuals, multiplying by 16 to recover original-pixel integrated DN units. Do not clip negative residuals.', '',
      'As a cross-check, subtract a median of ten off-time B2 frames at 1/100 and 100/100 us before fitting the local residual background. These are not beam-off references for each individual material. Nearby on-time frames all contain target light, so using those as dark frames would remove the signal.', '',
      '| Position | Material | Frames | Net integrated DN | Relative to A1 | Off-time-subtracted DN |',
      '|---|---|---:|---:|---:|---:|']
    for r in results:
        lines.append(f'| {r["position"]} | {materials[r["position"]]} | {r["frames"]} | {r["median_image_net_dn"]:.0f} | {r["median_image_net_dn"]/ref:.2f} | {r["off_time_subtracted_dn"]:.0f} |')
    lines += ['', 'Ranking remains A3 > B2 > B1 > A1 > A2 > B3 for smaller/larger apertures (radii 12/18, 18/27, 24/36). Frame-to-frame scatter is reported in comparison.json, but is not an uncertainty on intrinsic material yield: beam dose, optical alignment, thickness, dye absorption, and collection efficiency are unnormalized.', '',
      '## Timing and interpretation', '',
      'At 300 us gate, B2 net integrated DN is about 50,789 at delay 220 us, 1,389 at 230 us, and 618 at 250 us. At 200 us delay, gates 100/150/200/300 us give about 49,067/50,257/50,762/52,084 DN-pixels. Most collected light therefore falls within the 100 us gate; nominal optical shutoff bracket is between the 220 and 230 us start settings, subject to latency/jitter and changing beam conditions. This is not a nanosecond lifetime measurement.', '',
      'The prompt signal is compatible with Cherenkov light and fast fluorescence/scintillation. Brightness rankings alone do not determine the Cherenkov fraction. Colored filament may change absorption, wavelength shifting, scattering and light extraction. A known-clear undyed reference with matched geometry, angular/spectral measurements, and independent pulse-charge or dose normalization would distinguish the mechanisms better.', '',
      'The comparison image uses the same false-color scale for all six panels (0–20 net DN per 4x4-averaged pixel). It is not a spectral/color measurement. Temporal medians remove many transient sensor-hit artifacts; single-pixel maxima should not be used as the light-yield estimator.', '',
      'Outputs: background_subtracted.png, frame_overview.png (58–90 DN display), timing_medians.png (0–20 net DN), comparison.json, timing.json. Reproduce with tools/analyze_laser_input.py and NumPy/Pillow.']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__ == '__main__':
    frames, meta = load()
    overview(frames, meta)
    compare(frames, meta)
