import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import map_coordinates, shift as ndshift
INK, MUTED, GRID = '#1f1f1e', '#6b6a63', '#e4e3dc'
S1, S2, S3 = '#2a78d6', '#eb6834', '#1baf7a'
DIV = LinearSegmentedColormap.from_list('div_br', ['#184f95', '#3987e5', '#9ec5f4', '#f0efec', '#f4b3b2', '#e34948', '#a32a2a'])
plt.rcParams.update({'font.size': 8, 'axes.edgecolor': '#c9c8c0', 'axes.labelcolor': INK, 'text.color': INK, 'xtick.color': MUTED, 'ytick.color': MUTED, 'figure.facecolor': 'white'})
R = json.load(open('compare.json'))
D = {n: (np.load(f'{n}_net.npy'), np.load(f'{n}_p.npy')) for n in ['scint', 'pc200', 'pc220']}
style = {'scint': (S1, '-', 'Scintillator (19:47)'), 'pc200': (S2, '--', 'PC + Al, 200 µs (19:44)'), 'pc220': (S3, ':', 'PC + Al, 220 µs (19:53)')}
t = np.linspace(-30, 30, 241)
def prof(net, p, ang_off, band=1.5):
    acc = 0; ws = np.linspace(-band, band, 7); ang = p[5] + ang_off
    for w in ws:
        xs = p[1] + t * np.cos(ang) - w * np.sin(ang); ys = p[2] + t * np.sin(ang) + w * np.cos(ang)
        acc = acc + map_coordinates(net, [ys, xs], order=1)
    return acc / len(ws)
fig = plt.figure(figsize=(12, 8.0), dpi=150); gs = fig.add_gridspec(2, 3, hspace=0.62, wspace=0.35)
for j, (off, nm) in enumerate([(0, 'major'), (np.pi / 2, 'minor')]):
    ax = fig.add_subplot(gs[0, j])
    for n in ['scint', 'pc200', 'pc220']:
        net, p = D[n]; pr = prof(net, p, off); col, ls, lab = style[n]
        ax.plot(4 * t, pr / pr.max(), color=col, ls=ls, lw=2 if n == 'scint' else 1.6, label=lab)
    ax.axhline(0, color=MUTED, lw=0.6); ax.set_xlim(-110, 110)
    ax.set_xlabel(f'distance along {nm} axis (camera px)'); ax.set_ylabel('normalized net signal')
    ax.set_title(f'{"ab"[j]}  Mean profile, {nm} axis', loc='left', fontweight='bold')
    ax.grid(axis='y', color=GRID, lw=0.6); ax.spines[['top', 'right']].set_visible(False)
    if j == 0: ax.legend(frameon=False, fontsize=7, loc='upper left', bbox_to_anchor=(0, -0.22), ncol=1)
# difference map: normalised PC200 - normalised scint, aligned on fitted centroids
ax = fig.add_subplot(gs[0, 2])
sn, sp = D['scint']; pn, pp = D['pc200']
pa = ndshift(pn / pp[0], (sp[2] - pp[2], sp[1] - pp[1]), order=1)
diff = pa - sn / sp[0]
im = ax.imshow(diff * 100, cmap=DIV, vmin=-15, vmax=15, extent=[-128, 128, 128, -128], interpolation='nearest')
fig.colorbar(im, ax=ax, fraction=0.046, label='PC − scint, % of peak')
ax.set_title('c  Normalised difference (PC 200 µs − scint)', loc='left', fontweight='bold')
ax.annotate('extra PC light', xy=(62, 62), xytext=(-110, 112), fontsize=7, color=INK, arrowprops=dict(arrowstyle='-', color=INK, lw=0.6))
ax.annotate('scint reference artifact', xy=(100, -20), xytext=(-110, -112), fontsize=7, color=INK, arrowprops=dict(arrowstyle='-', color=INK, lw=0.6)); ax.set_xlabel('Δx (px)'); ax.set_ylabel('Δy (px)')
# parameter comparison
keys = [('s_major', 'σ major'), ('s_minor', 'σ minor'), ('rms_major', 'rms major (model-free)'), ('rms_minor', 'rms minor (model-free)'), ('fwhm_major', 'FWHM major'), ('fwhm_minor', 'FWHM minor')]
ax = fig.add_subplot(gs[1, :2])
x = np.arange(len(keys)); wbar = 0.26
wbar = 0.36
for i, n in enumerate(['pc200', 'pc220']):
    col, ls, lab = style[n]
    v = np.array([R[n][k][0] for k, _ in keys]); e = np.array([R[n][k][1] for k, _ in keys])
    ref = np.array([R['scint'][k][0] for k, _ in keys])
    ax.bar(x + (i - 0.5) * wbar, 100 * (v / ref - 1), wbar * 0.92, yerr=100 * e / ref, color=col, label=lab, error_kw=dict(lw=0.8, ecolor=INK))
ax.axhline(0, color=MUTED, lw=0.8); ax.set_xticks(x); ax.set_xticklabels([l.replace(' (', '\n(') for _, l in keys], fontsize=7.5)
ax.set_ylabel('% difference from scintillator'); ax.legend(frameon=False, fontsize=7.5, ncol=2, loc='lower left')
ax.set_title('d  PC shape parameters relative to the scintillator spot (±1σ bootstrap)', loc='left', fontweight='bold')
ax.grid(axis='y', color=GRID, lw=0.6); ax.spines[['top', 'right']].set_visible(False)
ax = fig.add_subplot(gs[1, 2]); ax.axis('off')
rows = [['', 'Scint', 'PC 200', 'PC 220']]
for k, l in [('s_major', 'σ maj (px)'), ('s_minor', 'σ min (px)'), ('theta', 'angle (°)'), ('fwhm_major', 'FWHM maj'), ('fwhm_minor', 'FWHM min'), ('x', 'centroid x'), ('y', 'centroid y')]:
    rows.append([l] + [f"{R[n][k][0]:.1f}±{R[n][k][1]:.1f}" for n in ['scint', 'pc200', 'pc220']])
rows.append(['pulses'] + [str(R[n]['n']) for n in ['scint', 'pc200', 'pc220']])
tb = ax.table(cellText=rows, loc='center', cellLoc='center'); tb.auto_set_font_size(False); tb.set_fontsize(7.5); tb.scale(1, 1.35)
for (r, c), cell in tb.get_celld().items():
    cell.set_edgecolor('#e4e3dc')
    if r == 0 or c == 0: cell.set_text_props(fontweight='bold')
ax.set_title('e  Mean-spot parameters (identical processing)', loc='left', fontweight='bold', fontsize=9)
fig.text(0.01, 0.005, 'All three: mean of fully-on pulses, 4×4 binning, rows destriped against pixels beyond 4σ, Gaussian + tilted-plane fit. Model-free rms is the second moment inside 3σ, corrected for truncation.', fontsize=7, color=MUTED)
fig.savefig('profile_comparison_20261001.png', facecolor='white', bbox_inches='tight'); print('ok')
