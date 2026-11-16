import json, os, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Ellipse
OUT = 'pc_out'; os.makedirs(f'{OUT}/pulses', exist_ok=True)
INK, MUTED, GRID, SURF = '#1f1f1e', '#6b6a63', '#e4e3dc', '#fcfcfb'
S1, S2, S3 = '#2a78d6', '#eb6834', '#1baf7a'
SEQ = LinearSegmentedColormap.from_list('seq_blue', [SURF, '#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'])
DIV = LinearSegmentedColormap.from_list('div_br', ['#184f95', '#3987e5', '#9ec5f4', '#f0efec', '#f4b3b2', '#e34948', '#a32a2a'])
GRY = LinearSegmentedColormap.from_list('gry', ['#1a1a19', '#6b6a63', '#c9c8c0', '#fcfcfb'])
for c in (SEQ, DIV): c.set_bad('#ffffff')
plt.rcParams.update({'font.size': 8, 'axes.edgecolor': '#c9c8c0', 'axes.labelcolor': INK, 'text.color': INK,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.titlesize': 9, 'figure.facecolor': 'white'})
Z = np.load('pc_pulse_crops_med.npz'); F = json.load(open('pc_fits.json')); S = json.load(open('pc_pulse_stats_med.json'))
X = Z['ds']; y0c, x0c = [int(v) for v in Z['crop_origin']]
ext = [x0c, x0c + 256, y0c + 256, y0c]
P = F['pulses']; byk = {p['k']: p for p in P}
yy, xx = np.mgrid[:64, :64].astype(float)
def g(p):
    A, x0, y0, sa, sb, th, c = p; ct, st = np.cos(th), np.sin(th)
    u = (xx - x0) * ct + (yy - y0) * st; v = -(xx - x0) * st + (yy - y0) * ct
    return A * np.exp(-0.5 * ((u / sa) ** 2 + (v / sb) ** 2)) + c
def ell(ax, p, col, ks=(1,), lw=0.7):
    A, x0, y0, sa, sb, th, c = p
    for k in ks:
        ax.add_patch(Ellipse((x0c + 4 * x0 + 2, y0c + 4 * y0 + 2), 8 * k * sa, 8 * k * sb, angle=np.degrees(th), fill=False, ec=col, lw=lw, ls='-' if k == 1 else '--'))
def zmap(k):
    p = byk[k]; img = X[k]; model = g(p['params'])
    var = p['bg_sd'] ** 2 + F['k1_4x4'] * np.clip(model - p['params'][6], 0, None)
    return (img - model) / np.sqrt(var), model
VMAX = 2.0
# ---------- contact sheets ----------
def sheet(ks, kind, fname, title, foot):
    ncol = 10; nrow = int(np.ceil(len(ks) / ncol))
    fig, axs = plt.subplots(nrow, ncol, figsize=(ncol * 1.55, nrow * 1.72 + 0.9), dpi=150)
    for ax in np.ravel(axs): ax.axis('off')
    for j, k in enumerate(ks):
        ax = np.ravel(axs)[j]; p = byk[k]
        if kind == 'data':
            im = ax.imshow(X[k], cmap=SEQ, vmin=-0.2, vmax=VMAX, extent=ext, interpolation='nearest'); ell(ax, p['params'], S2)
        else:
            z, _ = zmap(k); im = ax.imshow(z, cmap=DIV, vmin=-4, vmax=4, extent=ext, interpolation='nearest')
        lab = f"#{p['frame']}  χ²ᵥ {p['chi2_red']:.2f}" if p['group'] != 'null' else f"#{p['frame']}  A {p['A_fixed']:+.2f}"
        ax.set_title(lab, fontsize=7, pad=2)
    fig.suptitle(title, x=0.01, ha='left', fontsize=11, fontweight='bold')
    cax = fig.add_axes([0.35, 0.058, 0.3, 0.011]); cb = fig.colorbar(im, cax=cax, orientation='horizontal')
    cb.set_label('net DN (4×4-binned, destriped)' if kind == 'data' else 'residual / σ')
    fig.text(0.01, 0.006, foot, fontsize=7, color=MUTED)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95 if nrow > 4 else 0.9, bottom=0.1 if nrow > 4 else 0.16, wspace=0.05, hspace=0.25)
    fig.savefig(f'{OUT}/{fname}', facecolor='white'); plt.close(fig)
s200, s220, null = F['sel200'], F['sel220'], F['null']
foot = 'Each tile 256 × 256 camera px centred on the spot; 4×4 binning; reference = per-pixel median of the 47 target-out frames; rows/columns destriped. χ²ᵥ with sensor hits masked; background-only χ²ᵥ ≈ %.2f.' % np.median([byk[k]['chi2_far'] for k in s200])
sheet(s200, 'data', 'pc_heatmaps_200us_20261001.png', f'Polycarbonate + Al, {len(s200)} fully-on pulses (delay 200 µs) — net light per pulse, 1σ fit ellipse', foot)
sheet(s200, 'z', 'pc_residuals_200us_20261001.png', f'Polycarbonate + Al, {len(s200)} fully-on pulses (delay 200 µs) — Gaussian fit residuals / expected noise', foot)
sheet(s220, 'data', 'pc_heatmaps_220us_20261001.png', f'Polycarbonate + Al, {len(s220)} pulses (delay 220 µs) — net light per pulse, 1σ fit ellipse', foot)
sheet(null, 'data', 'pc_null_frames_20261001.png', f'Null test: {len(null)} target-out frames, leave-one-out reference — same pipeline, no spot expected',
      'Tile title gives the fixed-shape amplitude fitted at the spot position (DN). Same colour scale as the pulse heatmaps.')
# ---------- GoF vs frame ----------
fig, axs = plt.subplots(4, 1, figsize=(9, 9), dpi=150, sharex=False)
groups = [(s200, S1, 'o', 'PC 200 µs plateau'), (s220, S2, 's', 'PC 220 µs (frame + 140)'), (null, '#9a998f', '^', 'null (target out)')]
def xs(ks, off): return np.array([byk[k]['frame'] for k in ks]) + off
offs = [0, 140, 0]
ax = axs[0]
for (ks, col, mk, lab), o in zip(groups, offs):
    ax.plot(xs(ks, o), [byk[k]['A_fixed'] for k in ks], mk, ms=3.5, color=col, label=lab)
ax.axhline(0, color=MUTED, lw=0.7); ax.set_ylabel('peak (DN)'); ax.set_title('Fixed-shape amplitude per pulse', loc='left', fontweight='bold')
ax.legend(frameon=False, ncol=3, fontsize=7.5, loc='center right')
ax = axs[1]
for (ks, col, mk, lab), o in zip(groups[:2], offs):
    ax.plot(xs(ks, o), [byk[k]['chi2_red'] for k in ks], mk, ms=3.5, color=col)
    ax.plot(xs(ks, o), [byk[k]['chi2_far'] for k in ks], mk, ms=3, color=col, alpha=0.35, mfc='none')
ax.axhline(1, color=MUTED, lw=0.7, ls=':'); ax.set_ylabel('reduced χ²')
ax.set_title('Reduced χ², whole tile (filled) vs background-only region (open)', loc='left', fontweight='bold')
ax = axs[2]
for (ks, col, mk, lab), o in zip(groups[:2], offs):
    ax.plot(xs(ks, o), [byk[k]['chi2_red_core2sig'] for k in ks], mk, ms=3.5, color=col)
ax.axhline(1, color=MUTED, lw=0.7, ls=':'); ax.set_ylabel('reduced χ²'); ax.set_title('Reduced χ², core (≤ 2σ)', loc='left', fontweight='bold')
ax = axs[3]
for (ks, col, mk, lab), o in zip(groups[:2], offs):
    ax.errorbar(xs(ks, o), [byk[k]['sigma_major_px'] for k in ks], yerr=[byk[k]['sigma_major_err_px'] for k in ks], fmt=mk, ms=3, color=col, lw=0.6)
    ax.errorbar(xs(ks, o), [byk[k]['sigma_minor_px'] for k in ks], yerr=[byk[k]['sigma_minor_err_px'] for k in ks], fmt=mk, ms=3, color=col, lw=0.6, mfc='white')
ax.set_ylabel('σ (camera px)'); ax.set_xlabel('frame (220 µs run offset by +140)')
ax.set_title('Fitted σ major (filled) and minor (open), ±1 fit error', loc='left', fontweight='bold')
for ax in axs: ax.grid(axis='y', color=GRID, lw=0.6); ax.spines[['top', 'right']].set_visible(False)
fig.tight_layout(); fig.savefig(f'{OUT}/pc_goodness_of_fit_20261001.png', facecolor='white'); plt.close(fig)
# ---------- example triptych + per-pulse files ----------
def trip(k, path, dpi=110):
    p = byk[k]; z, model = zmap(k)
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.6), dpi=dpi)
    im0 = axs[0].imshow(X[k], cmap=SEQ, vmin=-0.2, vmax=VMAX, extent=ext, interpolation='nearest'); ell(axs[0], p['params'], S2, (1, 2))
    axs[0].set_title('data (net DN, 4×4 bin)', loc='left', fontweight='bold'); fig.colorbar(im0, ax=axs[0], fraction=0.046)
    im1 = axs[1].imshow(model - p['offset'], cmap=SEQ, vmin=-0.2, vmax=VMAX, extent=ext, interpolation='nearest')
    axs[1].set_title('Gaussian fit', loc='left', fontweight='bold'); fig.colorbar(im1, ax=axs[1], fraction=0.046)
    im2 = axs[2].imshow(z, cmap=DIV, vmin=-4, vmax=4, extent=ext, interpolation='nearest')
    axs[2].set_title('residual / σ', loc='left', fontweight='bold'); fig.colorbar(im2, ax=axs[2], fraction=0.046)
    for ax in axs: ax.set_xlabel('x (px)')
    axs[0].set_ylabel('y (px)')
    fig.suptitle(f"PC pulse {p['run'].replace('PC_','').replace('_100',' µs')} frame {p['frame']}   ·   peak {p['A']:.2f} ± {p['A_err']:.2f} DN   ·   σ {p['sigma_major_px']:.1f} ± {p['sigma_major_err_px']:.1f} × {p['sigma_minor_px']:.1f} ± {p['sigma_minor_err_px']:.1f} px at {p['theta_deg']:.1f}°\n"
                 f"χ²ᵥ {p['chi2_red']:.2f} (core {p['chi2_red_core2sig']:.2f}, background ref {p['chi2_far']:.2f})   ·   Δχ² vs no spot {p['delta_chi2_null_minus_free']:.0f}   ·   "
                 f"fixed-shape S/N {p['snr_fixed']:.0f}   ·   {p['hits_masked']} bins masked", x=0.01, ha='left', fontsize=8.5)
    fig.tight_layout(rect=[0, 0, 1, 0.88]); fig.savefig(path, facecolor='white'); plt.close(fig)
for k in s200 + s220:
    p = byk[k]; trip(k, f"{OUT}/pulses/pc_{p['run'][3:6]}us_frame_{p['frame']:03d}.png")
keys = ['run', 'frame', 'group', 'A_fixed', 'A_fixed_err', 'snr_fixed', 'A', 'A_err', 'x_full', 'y_full', 'x_err_px', 'y_err_px', 'sigma_major_px', 'sigma_major_err_px',
        'sigma_minor_px', 'sigma_minor_err_px', 'theta_deg', 'offset', 'chi2_red', 'chi2_red_core2sig', 'chi2_far', 'chi2_red_null', 'delta_chi2_null_minus_free',
        'delta_chi2_fixed_minus_free', 'dof', 'r2_3sig', 'bg_sd', 'hits_masked']
with open(f'{OUT}/pc_fits_20261001.csv', 'w') as f:
    f.write(','.join(keys) + '\n')
    for p in P: f.write(','.join(f'{p[k]:.4g}' if isinstance(p[k], float) else str(p[k]) for k in keys) + '\n')
print('ok')
