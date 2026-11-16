import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from scipy.ndimage import map_coordinates

BLUE, ORANGE, INK, MUTED = '#2a78d6', '#eb6834', '#1f1f1e', '#6b6a63'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': '#b9b8b0', 'axes.labelcolor': INK,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.titlesize': 10, 'axes.titleweight': 'bold'})

full = json.load(open('full.json')); pcb = json.load(open('pc_blocks.json')); ss = json.load(open('singleshot.json'))
C = np.load('scint_crops.npz'); rows = np.load('scint_perframe.npy')
amp = np.load('scint_mf_amp.npy'); st = np.load('Scint_200_100_strength.npy')
oy, ox = full['Scint_200_100']['crop_origin_full_yx']
on_idx = rows[:, 0].astype(int)
well = amp[on_idx] > 100
mean_well = C['frames'][well].mean(0)  # bin2, 128x128, origin (oy,ox)
ext = [ox, ox + 256, oy + 256, oy]

# per-frame robust shape (bin2 -> full px)
sel = rows[(rows[:, 1] == 1) & (amp[on_idx] > 100)]
med = lambda k: float(np.median(sel[:, k]))
mad = lambda k: float(1.4826 * np.median(np.abs(sel[:, k] - np.median(sel[:, k]))))
x0 = ox + 2 * med(3) + 0.5; y0 = oy + 2 * med(4) + 0.5
sa, sb, th = 2 * med(5), 2 * med(6), med(7)

fig = plt.figure(figsize=(12, 7.6), dpi=130)
gs = fig.add_gridspec(2, 3, hspace=0.42, wspace=0.45)

def ellipses(ax, x, y, a, b, t, col):
    for k, ls in [(1, '-'), (2, '--')]:
        ax.add_patch(Ellipse((x, y), 2 * k * a, 2 * k * b, angle=np.degrees(t), fill=False, ec=col, lw=1.2, ls=ls))

# (a) full-frame scint on-off
ax = fig.add_subplot(gs[0, 0])
d = C['diff_full_binned']
ax.imshow(d, cmap='gray', vmin=0, vmax=40, extent=[0, 1456, 1088, 0])
ax.add_patch(plt.Rectangle((ox, oy), 256, 256, fill=False, ec=BLUE, lw=1.2))
ax.annotate('edge glow', xy=(505, 540), xytext=(150, 900), color='white', fontsize=8,
            arrowprops=dict(arrowstyle='-', color='white', lw=0.8))
ax.set_title('a  Scintillator, beam on − off (mean)')
ax.set_xlabel('x (px)'); ax.set_ylabel('y (px)')

# (b) scint single frame
ax = fig.add_subplot(gs[0, 1])
k = np.where(well)[0]; pick = k[np.argsort(amp[on_idx][k])[len(k) // 2]]
fr = C['frames'][pick]
im = ax.imshow(fr, cmap='gray', vmin=-5, vmax=150, extent=ext)
r = rows[pick]
ellipses(ax, ox + 2 * r[3] + .5, oy + 2 * r[4] + .5, 2 * r[5], 2 * r[6], r[7], BLUE)
ax.set_title(f'b  Scintillator, one pulse (frame {int(r[0])})')
ax.set_xlabel('x (px)'); fig.colorbar(im, ax=ax, fraction=0.046, label='net DN (2×2 bin)')
ax.text(0.03, 0.04, f'peak {r[2]:.0f} DN · σ {2*r[5]:.1f} × {2*r[6]:.1f} px', transform=ax.transAxes, color='white', fontsize=8)

# (c) PC average
ax = fig.add_subplot(gs[0, 2])
B = np.load('pc_blocks.npz')['dM']
by0, bx0 = oy / 4, ox / 4
cpc = B[int(by0):int(by0) + 64, int(bx0):int(bx0) + 64]
im = ax.imshow(cpc, cmap='gray', vmin=-0.3, vmax=1.6, extent=[int(bx0) * 4, int(bx0) * 4 + 256, int(by0) * 4 + 256, int(by0) * 4])
p = pcb['M_minus_L']
ellipses(ax, p['x0_full'], p['y0_full'], p['sigma_major_full_px'], p['sigma_minor_full_px'], np.radians(p['theta_deg']), ORANGE)
ax.set_title('c  0.5 mm PC + Al, mean of 67 pulses')
ax.set_xlabel('x (px)'); fig.colorbar(im, ax=ax, fraction=0.046, label='net DN (4×4 bin)')
ax.text(0.03, 0.04, f'peak {p["amp_dn"]:.2f} DN · σ {p["sigma_major_full_px"]:.0f} × {p["sigma_minor_full_px"]:.0f} px', transform=ax.transAxes, color='white', fontsize=8)

# (d) normalized profiles along major/minor axes
ax = fig.add_subplot(gs[1, 0])
t = np.linspace(-120, 120, 241)
def prof(img, scale, oxy, x, y, ang, band=8):
    acc = 0
    offs = np.arange(-band, band + 1, 2)
    for w in offs:  # average a band perpendicular to the cut
        xs = x + t * np.cos(ang) - w * np.sin(ang); ys = y + t * np.sin(ang) + w * np.cos(ang)
        acc = acc + map_coordinates(img, [(ys - oxy[0]) / scale - 0.5, (xs - oxy[1]) / scale - 0.5], order=1)
    return acc / len(offs)
for ang_off, ls_lab in [(0, 'major'), (np.pi / 2, 'minor')]:
    s = prof(mean_well, 2, (oy, ox), x0, y0, th + ang_off)
    q = prof(B, 4, (0, 0), p['x0_full'], p['y0_full'], np.radians(p['theta_deg']) + ang_off)
    lw = 2 if ls_lab == 'major' else 1.2
    ax.plot(t, s / s.max(), color=BLUE, lw=lw, ls='-' if ls_lab == 'major' else ':', label=f'Scint · {ls_lab}')
    ax.plot(t, q / np.max(q), color=ORANGE, lw=lw, ls='--' if ls_lab == 'major' else '-.', label=f'PC · {ls_lab}')
ax.axhline(0, color='#d8d7cf', lw=0.8)
ax.set_xlabel('distance from centroid (px)'); ax.set_ylabel('normalized net signal')
ax.set_title('d  Spot profiles (±8 px band)'); ax.legend(frameon=False, fontsize=7.5, loc='upper right')
ax.spines[['top', 'right']].set_visible(False)

# (e) scint per-pulse amplitude sequence
ax = fig.add_subplot(gs[1, 1])
n = len(amp); col = np.where(amp > 100, BLUE, np.where(amp > 20, '#86b6ef', '#c9c8c0'))
ax.scatter(np.arange(n), amp, s=10, c=col, lw=0)
ax.set_xlabel('frame'); ax.set_ylabel('fitted peak (net DN, 4×4 bin)')
ax.set_title('e  Scintillator per pulse (target moved)')
ax.text(0.02, 0.95, f'{int((amp>100).sum())} well hit · {int(((amp>20)&(amp<=100)).sum())} partial · {int((amp<=20).sum())} no spot',
        transform=ax.transAxes, fontsize=8, color=INK, va='top')
ax.spines[['top', 'right']].set_visible(False)

# (f) PC per pulse
ax = fig.add_subplot(gs[1, 2])
a200 = np.load('pc200_mf_amp.npy'); a220 = np.load('pc220_mf_amp.npy')
ax.scatter(np.arange(len(a200)), a200, s=10, c=ORANGE, lw=0, label='delay 200 µs')
ax.scatter(len(a200) + 5 + np.arange(len(a220)), a220, s=10, c=ORANGE, marker='^', lw=0, alpha=0.75, label='delay 220 µs')
ax.axhline(0, color='#d8d7cf', lw=0.8)
ax.set_xlabel('frame (two runs, in order)'); ax.set_ylabel('fitted peak (net DN, 4×4 bin)')
ax.set_title('f  Polycarbonate per pulse'); ax.legend(frameon=False, fontsize=7.5, loc='lower right')
ax.text(0.02, 0.95, f'single-shot S/N ≈ {ss["PC_200_100"]["single_shot_snr_M"]:.0f}', transform=ax.transAxes, fontsize=8, va='top')
ax.spines[['top', 'right']].set_visible(False)

fig.suptitle('DoseCam target test, 1 Oct 2026 — 100 µs gate', x=0.01, ha='left', fontsize=12, fontweight='bold', color=INK)
fig.savefig('spot_shape_20261001.png', bbox_inches='tight', facecolor='white')

print(json.dumps({'well_hit': int(well.sum()), 'x0': round(x0,1), 'y0': round(y0,1), 'sigma_major_px': round(sa,2), 'sigma_minor_px': round(sb,2),
  'theta_deg': round(np.degrees(th),1), 'mad_x0_px': round(2*mad(3),2), 'mad_y0_px': round(2*mad(4),2),
  'mad_sa_px': round(2*mad(5),2), 'mad_sb_px': round(2*mad(6),2), 'mad_theta_deg': round(np.degrees(mad(7)),2),
  'peak3_raw_median': med(9), 'peak3_raw_max': float(sel[:,9].max()), 'integ_median': med(11), 'integ_mad_frac': round(mad(11)/med(11),3)}, indent=1))
