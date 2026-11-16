import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
INK, MUTED, GRID, SURF = '#1f1f1e', '#6b6a63', '#e4e3dc', '#fcfcfb'
S1, S2, S3 = '#2a78d6', '#eb6834', '#1baf7a'
SEQ = LinearSegmentedColormap.from_list('seq_blue', [SURF, '#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'])
DIV = LinearSegmentedColormap.from_list('div_br', ['#184f95', '#3987e5', '#9ec5f4', '#f0efec', '#f4b3b2', '#e34948', '#a32a2a'])
plt.rcParams.update({'font.size': 8, 'axes.edgecolor': '#c9c8c0', 'axes.labelcolor': INK, 'text.color': INK,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.titlesize': 9, 'figure.facecolor': 'white'})
Z = np.load('pc_pulse_crops_med.npz'); S = json.load(open('pc_pulse_stats_med.json')); F = json.load(open('pc_fits.json'))
sc_hits = np.load('scint_hits.npy'); st = np.load('/home/claude/a1001/Scint_200_100_strength.npy')
EXT = [0, 1456, 1088, 0]
# ---------- figure B1: background images ----------
fig, axs = plt.subplots(2, 3, figsize=(12, 6.6), dpi=150)
def show(ax, img, cmap, vmin, vmax, title, cb):
    im = ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax, extent=EXT, interpolation='nearest')
    ax.set_title(title, loc='left', fontweight='bold'); fig.colorbar(im, ax=ax, fraction=0.035, label=cb)
    ax.add_patch(plt.Rectangle((849 - 128, 444 - 128), 256, 256, fill=False, ec=S2, lw=0.9))
show(axs[0, 0], Z['Lmean_b4'] - 60.032, DIV, -0.5, 0.5, 'a  Room-light scene (reference − black)', 'DN above 60.03')
show(axs[0, 1], Z['Lavg_minus_clip_b4'], SEQ, 0, 0.6, 'b  Hit bias of a plain-mean reference', 'DN')
show(axs[0, 2], Z['PC_200_100_plateau_mean_destriped'], SEQ, -0.1, 1.4, 'c  Mean PC pulse − reference (destriped)', 'net DN')
show(axs[1, 0], Z['example_raw'], DIV, -2, 2, 'd  One PC pulse (frame 110), reference only', 'net DN')
show(axs[1, 1], Z['example_destriped'], DIV, -2, 2, 'e  Same pulse, rows destriped', 'net DN')
dd = Z['example_raw'] - Z['example_destriped']
show(axs[1, 2], dd, DIV, -1, 1, 'f  What destriping removed', 'DN')
for ax in axs.ravel(): ax.set_xticks([0, 500, 1000]); ax.set_yticks([0, 500, 1000])
fig.text(0.01, 0.005, 'Orange box: the 256 × 256 px analysis tile. In c, the structures away from the spot are scene changes: the target assembly moved between the reference frames and the pulses. Frame 110 sits in a pedestal burst (+0.72 DN across the whole frame); the destriping step removes it because it is uniform along rows.', fontsize=7, color=MUTED)
fig.tight_layout(rect=[0, 0.025, 1, 1]); fig.savefig('pc_out/pc_background_images_20261001.png', facecolor='white'); plt.close(fig)
# ---------- figure B2: per-frame background terms ----------
fig, axs = plt.subplots(3, 2, figsize=(12, 7.2), dpi=150, gridspec_kw=dict(width_ratios=[2.2, 1]))
run = S['PC_200_100']; fr = np.arange(len(run)); blk = np.array([s['block'] for s in run])
cols = {'L': '#9a998f', 'M': S1, 'H': S3}
names = {'L': 'target out (no spot)', 'M': 'PC in beam', 'H': 'PC in beam, spot offset'}
for ax, key, lab, log in [(axs[0, 0], 'hits', 'radiation hits / frame\n(outside spot region)', True), (axs[1, 0], 'global_offset', 'frame pedestal (DN)', False), (axs[2, 0], 'row_band_rms', 'row-banding rms (DN)', False)]:
    v = np.array([s[key] for s in run])
    for b in 'LHM':
        m = blk == b; ax.plot(fr[m], v[m], 'o', ms=3, color=cols[b], label=names[b])
    ax.set_ylabel(lab); ax.grid(axis='y', color=GRID, lw=0.6); ax.spines[['top', 'right']].set_visible(False)
    if log: ax.set_yscale('log')
axs[0, 0].legend(frameon=False, ncol=3, fontsize=7.5, loc='upper right'); axs[0, 0].set_title('PC run, 200 µs: background terms frame by frame', loc='left', fontweight='bold')
axs[2, 0].set_xlabel('frame')
# hits comparison bar (scint and PC, target in vs out)
ax = axs[0, 1]
vals = [np.median(sc_hits[st < 10]), np.median(sc_hits[st > 15]), np.median([s['hits'] for s in run if s['block'] == 'L']), np.median([s['hits'] for s in run if s['block'] == 'M'])]
labs = ['Scint\ntarget out', 'Scint\ntarget in', 'PC\ntarget out', 'PC\ntarget in']
ax.bar(range(4), vals, color=['#9a998f', S1, '#9a998f', S1], width=0.6)
for i, v in enumerate(vals): ax.text(i, v * 1.02, f'{v:,.0f}', ha='center', va='bottom', fontsize=7.5)
ax.set_xticks(range(4)); ax.set_xticklabels(labs, fontsize=7.5); ax.set_ylabel('median hits / frame')
ax.set_title('Radiation hits at the sensor', loc='left', fontweight='bold'); ax.spines[['top', 'right']].set_visible(False)
# noise budget per 4x4 bin at the spot
axs[1, 1].axis('off'); axs[2, 1].axis('off')
ax2 = fig.add_subplot(3, 2, (4, 6))
plat = [s for s in run if s['block'] == 'M']
pk = np.mean([p['A_fixed'] for p in F['pulses'] if p['k'] in set(F['sel200'])])
budget = [
    ('PC spot peak (signal)', pk, 'signal'),
    ('Pedestal bursts, 9–13% of frames', 0.74, 'removed'),
    ('Hit bias, plain-mean reference', 0.163, 'avoided'),
    ('Measured local background, all corrections', np.median([p['bg_sd'] for p in F['pulses'] if p['k'] in set(F['sel200'])]), 'remains'),
    ('Row banding (per 4×4 bin)', np.median([s['row_band_rms'] for s in plat]) / 2, 'removed'),
    ('Typical pedestal step', 0.09, 'absorbed'),
    ('Shot noise at the peak', np.sqrt(F['k1_4x4'] * pk), 'remains'),
    ('Scene change in tile (target moved), rms', 0.08, 'remains'),
    ('Room light at the spot (static)', 0.067, 'subtracted'),
    ('Sensor read noise (per 4×4 bin)', np.median([s['white_sd_full'] for s in plat]) / 4, 'remains'),
]
cmap = {'signal': '#0d366b', 'remains': S2, 'removed': '#9ec5f4', 'avoided': '#9ec5f4', 'absorbed': '#9ec5f4', 'subtracted': '#9ec5f4'}
y = np.arange(len(budget))[::-1]
budget = sorted(budget, key=lambda b: (b[2] != 'signal', -b[1])); y = np.arange(len(budget))[::-1]
ax2.barh(y, [b[1] for b in budget], color=[cmap[b[2]] for b in budget], height=0.6)
for yi, b in zip(y, budget): ax2.text(b[1] + 0.02, yi, f'{b[1]:.3f} DN · {b[2]}', va='center', fontsize=7)
ax2.set_yticks(y); ax2.set_yticklabels([b[0] for b in budget], fontsize=7.5); ax2.set_xlim(0, 2.0)
ax2.set_xlabel('DN (per 4×4 bin, per pulse)'); ax2.set_title('Background budget vs PC signal', loc='left', fontweight='bold')
ax2.spines[['top', 'right']].set_visible(False); ax2.grid(axis='x', color=GRID, lw=0.6)
fig.tight_layout(); fig.savefig('pc_out/pc_background_terms_20261001.png', facecolor='white'); plt.close(fig)
print('budget', [(b[0], round(b[1], 3)) for b in budget])
