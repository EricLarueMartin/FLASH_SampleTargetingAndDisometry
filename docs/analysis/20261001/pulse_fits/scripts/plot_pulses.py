import json, os, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Ellipse

OUT = 'pulse_out'; os.makedirs(f'{OUT}/pulses', exist_ok=True)
INK, MUTED, GRID, SURF = '#1f1f1e', '#6b6a63', '#e4e3dc', '#fcfcfb'
S1, S2, S3 = '#2a78d6', '#eb6834', '#1baf7a'
SEQ = LinearSegmentedColormap.from_list('seq_blue', [SURF, '#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'])
DIV = LinearSegmentedColormap.from_list('div_br', ['#184f95', '#3987e5', '#9ec5f4', '#f0efec', '#f4b3b2', '#e34948', '#a32a2a'])
DIV.set_bad('#ffffff'); SEQ.set_bad('#ffffff')
plt.rcParams.update({'font.size': 8, 'axes.edgecolor': '#c9c8c0', 'axes.labelcolor': INK, 'text.color': INK,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.titlesize': 9, 'figure.facecolor': 'white'})

D = json.load(open('pulse_fits.json')); P = D['pulses']
C = np.load('scint_crops.npz')['frames']; M = np.load('pulse_models.npz')
full = json.load(open('full.json'))['Scint_200_100']; oy, ox = full['crop_origin_full_yx']
ext = [ox, ox + 256, oy + 256, oy]
VMAX = 160
def ell(ax, q, col, lw=0.8, k=(1, 2)):
    A, x0, y0, sa, sb, th, c = q['params']
    for kk in k:
        ax.add_patch(Ellipse((ox + 2 * x0 + .5, oy + 2 * y0 + .5), 4 * kk * sa, 4 * kk * sb, angle=np.degrees(th),
                             fill=False, ec=col, lw=lw, ls='-' if kk == 1 else '--'))

# ---------- A/B: contact sheets ----------
def sheet(kind, fname, title):
    ncol = 10; nrow = int(np.ceil(len(P) / ncol))
    fig, axs = plt.subplots(nrow, ncol, figsize=(ncol * 1.55, nrow * 1.72 + 0.9), dpi=150)
    for ax in axs.ravel(): ax.axis('off')
    for j, q in enumerate(P):
        ax = axs.ravel()[j]
        if kind == 'data':
            im = ax.imshow(C[q['crop']], cmap=SEQ, vmin=0, vmax=VMAX, extent=ext, interpolation='nearest')
            ell(ax, q, S2, 0.6, k=(1,))
        else:
            im = ax.imshow(M['z'][j], cmap=DIV, vmin=-5, vmax=5, extent=ext, interpolation='nearest')
        ax.set_title(f"#{q['frame']}  χ²ᵥ {q['chi2_red']:.2f}", fontsize=7, pad=2,
                     color=INK if q['frame'] > 37 else MUTED)
    fig.suptitle(title, x=0.01, ha='left', fontsize=11, fontweight='bold')
    cax = fig.add_axes([0.35, 0.058, 0.3, 0.011])
    cb = fig.colorbar(im, cax=cax, orientation='horizontal')
    cb.set_label('net DN (2×2-binned)' if kind == 'data' else 'residual / σ  (white = masked sensor hit)')
    fig.text(0.01, 0.006, 'Each tile 256 × 256 camera px centred on the spot. Grey titles: frames 26–37, glowing scintillator edge inside the tile (inflates whole-tile χ²ᵥ). '
             'χ²ᵥ over the whole tile with sensor hits masked; clear frames give background-only χ²ᵥ ≈ 1.38.', fontsize=7, color=MUTED)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.1, wspace=0.05, hspace=0.25)
    fig.savefig(f'{OUT}/{fname}', facecolor='white'); plt.close(fig)
sheet('data', 'pulse_heatmaps_20261001.png', f'Scintillator, {len(P)} fully-on pulses — net light per pulse, 1σ fit ellipse')
sheet('z', 'pulse_residuals_20261001.png', f'Scintillator, {len(P)} fully-on pulses — Gaussian fit residuals in units of expected noise')

# ---------- C: goodness of fit vs frame ----------
fr = np.array([q['frame'] for q in P])
def col(k): return np.array([q[k] for q in P])
fig, axs = plt.subplots(3, 1, figsize=(9, 7.2), dpi=150, sharex=True)
for ax in axs:
    ax.axvspan(25.5, 37.5, color='#f0efec', lw=0); ax.grid(axis='y', color=GRID, lw=0.6); ax.spines[['top', 'right']].set_visible(False)
ax = axs[0]
ax.plot(fr, col('chi2_red_core2sig'), 'o', ms=4, color=S2, label='core (≤ 2σ)')
ax.plot(fr, col('chi2_red'), 's', ms=3.5, color=S1, label='whole 256 px tile')
ax.plot(fr, col('chi2_far'), '^', ms=3.5, color=S3, label='background only (> 6σ), reference')
ax.set_yscale('log')
ax.axhline(1, color=MUTED, lw=0.8, ls=':')
ax.set_ylabel('reduced χ²'); ax.set_title('Reduced χ² of a rotated 2D Gaussian + constant, per pulse', loc='left', fontweight='bold')
ax.legend(frameon=False, ncol=3, loc='upper right', fontsize=7.5)
ax.text(31.5, 30, 'scintillator edge\nin window', ha='center', va='top', fontsize=7, color=MUTED)
ax = axs[1]
ax.plot(fr, col('systematic_misfit_core_pct'), 'o', ms=4, color=S1)
ax.set_ylabel('% of peak'); ax.set_ylim(0, None)
ax.set_title('Systematic misfit in the core (residual rms with expected noise removed)', loc='left', fontweight='bold')
ax = axs[2]
ax.plot(fr, col('r2_3sig'), 'o', ms=4, color=S1)
ax.set_ylabel('R²'); ax.set_xlabel('frame number (run Scint/…000002)')
ax.set_title('Fraction of variance explained inside the 3σ ellipse', loc='left', fontweight='bold')
fig.tight_layout(); fig.savefig(f'{OUT}/pulse_goodness_of_fit_20261001.png', facecolor='white'); plt.close(fig)

# ---------- D: mean normalised residual ----------
R = np.load('mean_norm_resid.npy')
pm = np.median([q['params'] for q in P], 0)
yy, xx = np.mgrid[:128, :128].astype(float)
A, x0, y0, sa, sb, th, c = pm; ct, st = np.cos(th), np.sin(th)
u = (xx - x0) * ct + (yy - y0) * st; v = -(xx - x0) * st + (yy - y0) * ct; e = np.sqrt((u / sa) ** 2 + (v / sb) ** 2)
fig, axs = plt.subplots(1, 2, figsize=(10, 4), dpi=150, gridspec_kw=dict(width_ratios=[1, 1.3]))
ax = axs[0]
im = ax.imshow(R * 100, cmap=DIV, vmin=-4, vmax=4, extent=ext, interpolation='nearest')
for kk in (1, 2, 3):
    ax.add_patch(Ellipse((ox + 2 * x0 + .5, oy + 2 * y0 + .5), 4 * kk * sa, 4 * kk * sb, angle=np.degrees(th), fill=False, ec=MUTED, lw=0.7, ls=':'))
fig.colorbar(im, ax=ax, fraction=0.046, label='mean residual, % of peak')
ax.set_title('Mean residual: skew across the minor axis', loc='left', fontweight='bold')
ax.text(0.0, -0.2, 'Straight diagonal and horizontal lines are background-reference artifacts:\nthe target-out frames contain glowing scintillator edges at other positions.', transform=ax.transAxes, fontsize=7, color=MUTED, va='top'); ax.set_xlabel('x (px)'); ax.set_ylabel('y (px)')
ax = axs[1]
edges = np.arange(0, 5.01, 0.25); mids = (edges[1:] + edges[:-1]) / 2
prof = [np.nanmean(R[(e >= a) & (e < b)]) * 100 for a, b in zip(edges[:-1], edges[1:])]
ax.axhline(0, color=MUTED, lw=0.8)
ax.plot(mids, prof, '-o', color=S1, ms=4, lw=2)
ax.set_xlabel('elliptical radius (σ of the fit)'); ax.set_ylabel('mean residual, % of peak')
ax.set_title('Ring-averaged: sharper core, heavier tails', loc='left', fontweight='bold')
ax.text(0.98, 0.95, 'Ring averaging cancels the skew dipole;\nwhat remains is the radial shape mismatch.', transform=ax.transAxes, ha='right', va='top', fontsize=7, color=MUTED)
ax.grid(axis='y', color=GRID, lw=0.6); ax.spines[['top', 'right']].set_visible(False)
fig.tight_layout(rect=[0, 0.06, 1, 1]); fig.savefig(f'{OUT}/pulse_mean_residual_20261001.png', facecolor='white'); plt.close(fig)

# ---------- E: one triptych per pulse ----------
for j, q in enumerate(P):
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.6), dpi=110)
    im0 = axs[0].imshow(C[q['crop']], cmap=SEQ, vmin=0, vmax=VMAX, extent=ext, interpolation='nearest'); ell(axs[0], q, S2)
    axs[0].set_title('data (net DN)', loc='left', fontweight='bold'); fig.colorbar(im0, ax=axs[0], fraction=0.046)
    im1 = axs[1].imshow(M['model'][j] - q['offset'], cmap=SEQ, vmin=0, vmax=VMAX, extent=ext, interpolation='nearest')
    axs[1].set_title('Gaussian fit', loc='left', fontweight='bold'); fig.colorbar(im1, ax=axs[1], fraction=0.046)
    im2 = axs[2].imshow(M['z'][j], cmap=DIV, vmin=-5, vmax=5, extent=ext, interpolation='nearest')
    axs[2].set_title('residual / σ', loc='left', fontweight='bold'); fig.colorbar(im2, ax=axs[2], fraction=0.046)
    for ax in axs: ax.set_xlabel('x (px)')
    axs[0].set_ylabel('y (px)')
    fig.suptitle(f"Pulse frame {q['frame']}   ·   peak {q['A']:.1f} DN   ·   σ {q['sigma_major_px']:.1f} × {q['sigma_minor_px']:.1f} px at {q['theta_deg']:.1f}°   ·   "
                 f"centroid ({q['x_full']:.1f}, {q['y_full']:.1f})\n"
                 f"χ²ᵥ {q['chi2_red']:.2f} (core {q['chi2_red_core2sig']:.2f}, background ref {q['chi2_far']:.2f})   ·   "
                 f"R² {q['r2_3sig']:.4f}   ·   systematic misfit {q['systematic_misfit_core_pct']:.2f}% of peak   ·   {q['hits_masked']} px masked"
                 + ("   ·   scintillator edge in window" if q['frame'] <= 37 else ""),
                 x=0.01, ha='left', fontsize=8.5)
    fig.tight_layout(rect=[0, 0, 1, 0.88]); fig.savefig(f"{OUT}/pulses/pulse_{q['frame']:03d}.png", facecolor='white'); plt.close(fig)

# ---------- CSV ----------
keys = ['frame', 'A', 'x_full', 'y_full', 'sigma_major_px', 'sigma_minor_px', 'theta_deg', 'offset', 'chi2_red', 'chi2_red_core2sig',
        'chi2_far', 'dof', 'r2_3sig', 'systematic_misfit_core_pct', 'resid_rms_core_pct', 'resid_max_3sig_pct', 'hits_masked', 'bg_sd']
with open(f'{OUT}/pulse_fits_20261001.csv', 'w') as f:
    f.write(','.join(keys) + '\n')
    for q in P: f.write(','.join(f'{q[k]:.4g}' if isinstance(q[k], float) else str(q[k]) for k in keys) + '\n')
print('done', len(os.listdir(f'{OUT}/pulses')))
