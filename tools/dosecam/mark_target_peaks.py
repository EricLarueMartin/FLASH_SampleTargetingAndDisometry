"""Annotate measured peaks on full-resolution temporal-median RAW images."""
import json
from pathlib import Path
import zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/analysis/20260918'
records = json.loads((OUT / 'comparison.json').read_text())
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 24)
small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
yy, xx = np.mgrid[:1088,:1456]
mask = ((xx-800)/72)**2 + ((yy-500)/108)**2 <= 1
overview = Image.new('RGB',(1456,3*620+80),'white')
zoom_sheet = Image.new('RGB',(3*480,2*490+90),'white')
ImageDraw.Draw(overview).text((15,10),'Cyan: measurement region. Yellow circle: peak in temporal-median image. Display rotated 180 degrees.',font=small,fill='black')
ImageDraw.Draw(zoom_sheet).text((15,10),'Yellow circle: measured target peak. Cyan ellipse: integration region. Same 58–90 DN display scale for all.',font=small,fill='black')
positions = []
with zipfile.ZipFile(ROOT/'dose_cam/captures/downloads/laser_input_test_prepared_20260918.zip') as archive:
    for i,r in enumerate(records):
        cube=[]
        with archive.open('laser_input_test/'+r['run']+'.raw') as stream:
            for _ in range(r['frames']):
                raw=np.frombuffer(stream.read(3203072),'<u2').reshape(1088,1472)[:,:1456]
                cube.append((raw>>6)[::-1,::-1].copy())
        median=np.median(np.stack(cube),axis=0)
        peak=float(median[mask].max())
        candidates=np.argwhere(mask & (median==peak))
        # Ties: choose the maximum nearest the measurement center.
        y,x=map(int,min(candidates,key=lambda p:(p[1]-800)**2+(p[0]-500)**2))
        positions.append(dict(position=r['position'],x=x,y=y,peak_dn=peak,tied_maxima=len(candidates)))
        image=Image.fromarray(np.uint8(np.clip((median-58)/32*255,0,255))).convert('RGB')
        draw=ImageDraw.Draw(image)
        draw.ellipse((728,392,872,608),outline='cyan',width=3)
        draw.ellipse((x-23,y-23,x+23,y+23),outline='yellow',width=4)
        closeup=image.copy()
        draw.line((x+24,y,x+100,y-65),fill='yellow',width=3)
        draw.text((x+102,y-85),f'{peak:g} DN',font=font,fill='yellow')
        image.save(OUT/f'{r["position"]}_target_peak.png')
        ox,oy=(i%2)*728,80+(i//2)*620
        overview.paste(image.resize((728,544)),(ox,oy+40))
        ImageDraw.Draw(overview).text((ox+12,oy+7),f'{r["position"]} — {r["frames"]} frames; peak {peak:g} DN',font=font,fill='black')
        # Enlarged crop; coordinates refer to the displayed full-resolution image.
        crop=closeup.crop((640,330,960,630)).resize((480,450))
        zx,zy=(i%3)*480,80+(i//3)*490
        zoom_sheet.paste(crop,(zx,zy+35))
        ImageDraw.Draw(zoom_sheet).text((zx+10,zy+4),f'{r["position"]}: {peak:g} DN at ({x}, {y})',font=small,fill='black')
overview.save(OUT/'target_peaks_full_view.png')
zoom_sheet.save(OUT/'target_peaks_closeup.png')
(OUT/'target_peak_coordinates.json').write_text(json.dumps(positions,indent=2))
print(json.dumps(positions,indent=2))
