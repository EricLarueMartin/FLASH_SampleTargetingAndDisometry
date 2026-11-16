import json, numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
pdfmetrics.registerFont(TTFont('DV', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVB', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
pdfmetrics.registerFont(TTFont('DVI', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'))
from reportlab.lib.fonts import addMapping
addMapping('DV', 0, 0, 'DV'); addMapping('DV', 1, 0, 'DVB'); addMapping('DV', 0, 1, 'DVI'); addMapping('DV', 1, 1, 'DVB')
INK = colors.HexColor('#1f1f1e'); MUTED = colors.HexColor('#6b6a63'); RULE = colors.HexColor('#e4e3dc'); ACC = colors.HexColor('#2a78d6')
ss = getSampleStyleSheet()
B = ParagraphStyle('b', parent=ss['Normal'], fontName='DV', fontSize=9.2, leading=13, textColor=INK, spaceAfter=5)
SM = ParagraphStyle('sm', parent=B, fontSize=7.8, leading=10.5, textColor=MUTED)
CAP = ParagraphStyle('cap', parent=B, fontSize=8, leading=10.8, textColor=MUTED, spaceBefore=3, spaceAfter=10)
H1 = ParagraphStyle('h1', parent=B, fontName='DVB', fontSize=14, leading=18, spaceBefore=10, spaceAfter=6, textColor=INK)
H2 = ParagraphStyle('h2', parent=B, fontName='DVB', fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=4, textColor=INK)
TITLE = ParagraphStyle('t', parent=B, fontName='DVB', fontSize=20, leading=25, spaceAfter=4)
SUB = ParagraphStyle('s', parent=B, fontSize=10.5, leading=14, textColor=MUTED, spaceAfter=2)
BUL = ParagraphStyle('bul', parent=B, leftIndent=12, bulletIndent=2, spaceAfter=3)
TB = ParagraphStyle('tb', parent=B, fontSize=8, leading=10, spaceAfter=0)
TBH = ParagraphStyle('tbh', parent=TB, fontName='DVB')
W = 7.0 * inch
def P(t, s=B): return Paragraph(t, s)
def bullets(items): return [Paragraph(i, BUL, bulletText='•') for i in items]
def fig(path, cap, width=W, maxh=8.2 * inch):
    w, h = PILImage.open(path).size; hh = width * h / w
    if hh > maxh: width, hh = maxh * w / h, maxh
    return KeepTogether([Image(path, width=width, height=hh), P(cap, CAP)])
def table(rows, widths, hdr=True):
    data = [[Paragraph(str(c), TBH if (hdr and r == 0) or c_i == 0 else TB) for c_i, c in enumerate(row)] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, hAlign='LEFT')
    t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, INK), ('LINEBELOW', (0, 1), (-1, -1), 0.3, RULE),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5)]))
    return t
X2 = '<font name="DV">χ</font><super>2</super><sub>ν</sub>'
# ------------- numbers -------------
SF = json.load(open('/home/claude/a1001/pulse_fits.json')); SP = SF['pulses']
PF = json.load(open('/home/claude/pc/pc_fits.json')); byk = {p['k']: p for p in PF['pulses']}
CMP = json.load(open('/home/claude/cmp/compare.json'))
def stat(L, k): v = np.array([q[k] for q in L]); return np.median(v), np.percentile(v, 5), np.percentile(v, 95)
def f3(L, k, fmt='{:.2f}'): m, a, b = stat(L, k); return f"{fmt.format(m)} [{fmt.format(a)}–{fmt.format(b)}]"
clear = [q for q in SP if q['frame'] > 37]; near = [q for q in SP if q['frame'] <= 37]
p200 = [byk[k] for k in PF['sel200']]; p220 = [byk[k] for k in PF['sel220']]; pnull = [byk[k] for k in PF['null']]
nullA = np.array([q['A_fixed'] for q in pnull]); A200 = np.array([q['A_fixed'] for q in p200]); A220 = np.array([q['A_fixed'] for q in p220])
snr_emp = A200.mean() / nullA.std()
sc_peak = np.median([q['A'] for q in SP])
S = '/home/claude/a1001/pulse_out/'; PCD = '/home/claude/pc/pc_out/'
story = []
# ------------- title + summary -------------
story += [P('DoseCam pulse-by-pulse spot analysis', TITLE),
          P('Scintillator and 0.5 mm polycarbonate targets · 30 MeV electrons · 1 October 2026 test runs', SUB),
          P('Prepared 2 October 2026 for Eric Martin, Duke FEL Lab · analysis of raw captures on pi-06-ioc · 100 µs gate', SM), Spacer(1, 6)]
story += [P('Summary', H1)]
story += bullets([
    f"<b>Same beam, same shape.</b> With identical processing, the mean spot measures σ {CMP['scint']['s_major'][0]:.1f} × {CMP['scint']['s_minor'][0]:.1f} px on the scintillator and "
    f"{CMP['pc200']['s_major'][0]:.1f} × {CMP['pc200']['s_minor'][0]:.1f} px on the polycarbonate taken 3 minutes earlier, with long axes at {CMP['scint']['theta'][0]:.1f}° and {CMP['pc200']['theta'][0]:.1f}°. "
    f"That is 2.4% and 1.4% apart. The same PC target 9 minutes later differed by 4% and 10%, so the target-to-target difference is smaller than the beam's own drift.",
    f"<b>Scintillator:</b> all {len(SP)} fully-on pulses are resolved individually. A rotated Gaussian explains 99.5% of the variance inside 3σ, but the core {X2} is about {stat(SP,'chi2_red_core2sig')[0]:.1f}. "
    f"There is a systematic misfit of about {stat(SP,'systematic_misfit_core_pct')[0]:.0f}% of peak: a skew across the short axis plus a sharper core and heavier tails. It repeats in every pulse. "
    f"The peak is {sc_peak:.0f} DN, about 15% of the ADC range.",
    f"<b>Polycarbonate:</b> peak {A200.mean():.2f} DN, about 1.0% of the scintillator. With the background handled carefully, a single pulse gives the amplitude to S/N ≈ {snr_emp:.0f} "
    f"(from the scatter of null frames) and the width to ±{stat(p200,'sigma_major_err_px')[0]:.1f} / ±{stat(p200,'sigma_minor_err_px')[0]:.1f} px. "
    f"A Gaussian fits to the noise level: {X2} {stat(p200,'chi2_red')[0]:.2f} (200 µs) and {stat(p220,'chi2_red')[0]:.2f} (220 µs), against 1.00 in background-only pixels. "
    f"This supersedes the earlier quick estimate of S/N ≈ 9.",
    "<b>Background is the main difficulty for the PC.</b> Frame-wide pedestal jumps of 0.6–1.0 DN appear in 9–13% of frames, half the size of the whole PC signal. "
    "Frames with the target out of the beam carry about 17× more radiation hits than frames with it in. "
    "A plain-mean reference built from those frames would be biased by +0.16 DN. Section 2.2 gives the full budget.",
    "<b>Next:</b> lens-capped dark frames with beam on and off, a target-out reference taken at a fixed position, a flat field, and a printed grid for mm scale and viewing angle."])
story.append(PageBreak())
# ------------- section 1 -------------
story += [P('1  Scintillator', H1), P('1.1  Data, selection and method', H2)]
story += [P(f"Run <i>Scint/run_20261001_194704_633291_000002</i>, 165 frames at 200 µs delay and 100 µs gate. The target was moved through the beam during the run, "
            f"so the per-pulse amplitude ramps up and down (Fig. 3 shows the plateau). A pulse counts as <b>fully on</b> when its matched-filter amplitude is within 2.5σ of the plateau: "
            f"median {SF['plateau_median']:.1f} DN, scatter {SF['plateau_sd']:.1f} DN, threshold {SF['threshold']:.1f} DN. That gives {len(SP)} pulses. "
            f"The ramp frames {', '.join(map(str, SF['borderline_excluded']))} fall just below threshold and are excluded. In frames 26–37 the spot is fully on the target, "
            "but the glowing edge of the scintillator is inside the analysis tile. These frames are kept and flagged.")]
story += [P("Each pulse is cut to a 256 × 256 px tile around the spot and binned 2 × 2. The background reference is the mean of the 50 target-out frames. "
            "The model is a rotated 2D Gaussian plus a constant (7 parameters). Its noise model was measured from the data by photon transfer on pixel-to-pixel fluctuations: "
            "variance = σ<sub>bg</sub><super>2</super> + 0.0208 s + 4.3×10<super>−5</super> s<super>2</super> in 2×2-binned DN. That implies about 0.10 DN per electron, "
            "so the 963 DN range above black is roughly 9,300 e⁻, consistent with this sensor's full well. "
            "σ<sub>bg</sub> = 0.63 DN is taken from frames with no edge in the tile. Sensor hits are masked with a model-independent detector: pixels more than 5σ above their 5 × 5 local median.")]
story += [P(f"Goodness-of-fit measures: {X2} over the whole tile, {X2} in the core (≤ 2σ), {X2} in the background-only region beyond 6σ (the floor a perfect model can reach), "
            "R² inside the 3σ ellipse, and the <b>systematic misfit</b>. The last is the core residual rms with the expected noise removed in quadrature, as a percentage of the peak. "
            "It is the noise-independent measure of how far the spot departs from a Gaussian.")]
rows = [['', 'Clear frames (n = %d)' % len(clear), 'Edge in tile, 26–37 (n = %d)' % len(near)],
        ['Peak (DN, 2×2 bin)', f3(clear, 'A', '{:.0f}'), f3(near, 'A', '{:.0f}')],
        ['σ major / minor (px)', f"{stat(clear,'sigma_major_px')[0]:.1f} / {stat(clear,'sigma_minor_px')[0]:.1f}", f"{stat(near,'sigma_major_px')[0]:.1f} / {stat(near,'sigma_minor_px')[0]:.1f}"],
        ['Angle (°)', f3(clear, 'theta_deg', '{:.1f}'), f3(near, 'theta_deg', '{:.1f}')],
        [f'{X2} whole tile', f3(clear, 'chi2_red'), f3(near, 'chi2_red')],
        [f'{X2} core ≤ 2σ', f3(clear, 'chi2_red_core2sig'), f3(near, 'chi2_red_core2sig')],
        [f'{X2} background only', f3(clear, 'chi2_far'), f3(near, 'chi2_far')],
        ['R² inside 3σ', f3(clear, 'r2_3sig', '{:.4f}'), f3(near, 'r2_3sig', '{:.4f}')],
        ['Systematic misfit (% of peak)', f3(clear, 'systematic_misfit_core_pct'), f3(near, 'systematic_misfit_core_pct')],
        ['Max |residual| in 3σ (% of peak)', f3(clear, 'resid_max_3sig_pct', '{:.1f}'), f3(near, 'resid_max_3sig_pct', '{:.1f}')]]
story += [P('1.2  Results', H2), table(rows, [2.1 * inch, 2.45 * inch, 2.45 * inch]), P('Median and 5th–95th percentile across pulses.', CAP)]
story += bullets([
    "<b>Shape is stable pulse to pulse.</b> σ varies ±0.6 px (2–3%) and the angle ±1°. Peak brightness and spot size are anticorrelated (r = −0.81): when the spot shrinks, the peak rises. "
    "The Gaussian integral is therefore steadier (3.2% rms) than the peak (5.0%), consistent with roughly constant light per pulse and a breathing spot size.",
    "<b>The Gaussian is a good but not perfect description.</b> Away from the spot the background-only {0} is 1.38, but the core gives about 4.4. The ~2% misfit has a fixed pattern (Fig. 4). "
    "Its main part is a skew dipole across the short axis: the upper-right flank is brighter and the lower-left dimmer than a Gaussian. Ring-averaged, it is a sharper core and heavier tails. "
    "It is the same in every pulse (Fig. 2), so it is a property of the beam or the optics, not noise.".format(X2),
    "<b>Edge-in-tile frames</b> have an inflated whole-tile {0} (about 6.9) because the glowing edge isn't in the model. Their core {0} and misfit match the clear frames.".format(X2),
    "<b>Background-reference artifacts.</b> The straight diagonal and horizontal lines in the residual maps come from the target-out reference: those frames contain the glowing scintillator edges at other positions."])
story += [fig(S + 'pulse_heatmaps_20261001.png', f'<b>Figure 1.</b> Net light for each of the {len(SP)} fully-on scintillator pulses, with the 1σ ellipse of each pulse\'s own Gaussian fit. Grey titles mark frames with the scintillator edge inside the tile.')]
story += [fig(S + 'pulse_residuals_20261001.png', '<b>Figure 2.</b> Residuals of each pulse\'s fit, in units of the expected noise. White pixels are masked sensor hits. The core pattern repeats in every pulse.')]
story += [fig(S + 'pulse_goodness_of_fit_20261001.png', '<b>Figure 3.</b> Goodness of fit per pulse. Shading marks frames 26–37 (edge in tile). R² stays above 0.993 throughout.', maxh=6.3 * inch)]
story += [fig(S + 'pulse_mean_residual_20261001.png', '<b>Figure 4.</b> Mean residual of all fully-on pulses (left) and its ring average against elliptical radius (right).')]
story += [fig(S + 'pulses/pulse_143.png', '<b>Figure 5.</b> A typical pulse (frame 143): data, fit and normalised residual. One such image per pulse is in <i>docs/analysis/20261001/pulse_fits/pulses/</i>.')]
story.append(PageBreak())
# ------------- section 2 -------------
story += [P('2  Polycarbonate (0.5 mm, aluminium-tape backing)', H1), P('2.1  Data and selection', H2)]
story += [P(f"Runs <i>Al_PC/…000001</i> (138 frames, 200 µs delay) and <i>Al_PC/…000005</i> (112 frames, 220 µs delay), both with a 100 µs gate. In the 200 µs run, frames 0–47 show no spot (target out). "
            "In frames 48–76 the spot sits about 55 px lower and is rounder while the target is being positioned. In frames 77–81 the target's bright edge crosses the analysis tile. "
            f"<b>Fully on</b> is therefore frames 82–137 in the 200 µs run ({len(p200)} pulses) and all {len(p220)} pulses of the 220 µs run, which was stable throughout. "
            f"Frames 0–42 ({len(pnull)}) serve as <b>null frames</b> for testing the pipeline. Frames 43–47 are left out because the light was already beginning to rise.")]
story += [P('2.2  Background: what it is and how it was handled', H2)]
story += [P("The PC spot peaks at only 1.4 DN on a 60 DN black level, so background terms that are invisible in the scintillator data are comparable to the signal here. "
            "Each one below was measured from the frames themselves. Values are per 4 × 4-binned pixel per pulse unless stated (Fig. 7, right).")]
bg_rows = [['Component', 'Size', 'Nature and evidence', 'Treatment'],
           ['Black level', '60.03 DN', 'Static sensor offset.', 'Subtracted with the reference.'],
           ['Pedestal bursts', '0.6–1.0 DN', 'Uniform frame-wide jumps in runs of consecutive frames, in 9–13% of frames. They do not follow the room-light pattern (scene coefficient −0.16), so they are electronic or black-level shifts, not light.', 'Removed by row destriping; the fit constant absorbs the rest.'],
           ['Small pedestal steps', '0.04–0.13 DN', 'Frame-to-frame alternation, also present in null frames. About 0.08 DN higher on average when the PC is in the beam.', 'Absorbed by the fit constant.'],
           ['Row banding', '0.17–0.24 DN/row (≈0.12 per bin)', 'Horizontal stripes, stronger during pedestal bursts (r = 0.6–0.66).', 'Per-row median from columns away from the spot, subtracted.'],
           ['Radiation hits', '≈500 per frame (PC in); ≈8,500 (PC out)', 'Direct sensor hits. The scintillator shows the same pattern: 2,200 per frame with the target in, 8,600 with it out. Whatever the beam strikes when the target is out irradiates the camera far more.', 'Hit-clipped reference; hits masked in every fit.'],
           ['Hit bias in a plain-mean reference', '+0.16 DN mean, up to 2.5 DN', 'The reference frames are the heavily hit target-out frames.', 'Reference = per-pixel mean after rejecting values > 3 DN above the pixel median (0.7% of samples).'],
           ['Room light', '≤ 0.4 DN (p99); 0.07 at the spot', 'LED room light during the 100 µs gate.', 'Subtracted with the reference.'],
           ['Scene change', '±0.08 DN rms in the tile', 'The target assembly moved between the reference frames and the pulses, so objects in view moved (Fig. 6c).', 'Tilted-plane term in the fit; otherwise remains.'],
           ['Read noise', '0.19 DN per pixel (0.06 per bin)', '≈1.9 e⁻ at 0.10 DN/e⁻.', 'Remains (white).'],
           ['Shot noise at the peak', '0.085 DN', 'Photon statistics of the PC light itself.', 'Remains; included in the noise model.'],
           ['Measured local background', '0.17 DN', 'After all corrections. About 0.10 DN is accounted for above; the remaining ≈0.13 DN is spatially correlated and not yet identified (candidates: sub-threshold hit halos, residual banding).', 'Remains; sets the noise floor of the fits.']]
story += [table(bg_rows, [1.25 * inch, 1.15 * inch, 2.9 * inch, 1.7 * inch]), Spacer(1, 6)]
story += [P(f"<b>Null test.</b> The same pipeline run on the {len(pnull)} null frames, each with a leave-one-out reference, gives a fixed-shape amplitude at the spot position of "
            f"{nullA.mean():+.3f} ± {nullA.std():.3f} DN. That is a bias below 1% of the PC peak, and the scatter is 1.25× the formal error. "
            f"Free-shape fits on null frames run to the edge of their bounds and find no spot (Fig. 11). "
            f"One caution: a free Gaussian on a null frame still improves χ² over a constant by a median of {stat(pnull,'delta_chi2_null_minus_free')[0]:.0f}, because it absorbs structured background. "
            f"The PC pulses improve by ≈6,500. Shape-change tests between pulses should be judged against that null level.")]
story += [fig(PCD + 'pc_background_images_20261001.png', '<b>Figure 6.</b> Background components in full-frame images (4 × 4 binned). (a) Room-light scene in the reference. (b) The hit bias a plain-mean reference would carry. (c) Mean PC pulse minus reference. (d–f) One pulse inside a pedestal burst, before and after row destriping, and what the destriping removed.')]
story += [fig(PCD + 'pc_background_terms_20261001.png', '<b>Figure 7.</b> Left: hits, pedestal and row banding frame by frame through the 200 µs PC run. Upper right: radiation hits with the target in and out, for both targets. Lower right: the background budget against the PC signal.')]
story += [P('2.3  Per-pulse fits', H2)]
story += [P("The per-pulse pipeline matches the scintillator's, with three changes forced by the low light: 4 × 4 binning (64 × 64 bins over the same 256 px tile), the hit-clipped reference, and row and column destriping on the full frame. "
            "The noise floor comes from each frame's own region beyond 4σ (sigma-clipped), plus the shot-noise term scaled from the scintillator's photon transfer. "
            "Each pulse is also fitted with the shape fixed to the run's mean spot (amplitude and constant free), which gives the most precise amplitude.")]
rows = [['', 'PC 200 µs (n = %d)' % len(p200), 'PC 220 µs (n = %d)' % len(p220), 'Null frames (n = %d)' % len(pnull)],
        ['Fixed-shape peak (DN)', f3(p200, 'A_fixed'), f3(p220, 'A_fixed'), f3(pnull, 'A_fixed', '{:+.3f}')],
        ['Formal S/N, fixed shape', f3(p200, 'snr_fixed', '{:.0f}'), f3(p220, 'snr_fixed', '{:.0f}'), f3(pnull, 'snr_fixed', '{:.1f}')],
        ['σ major / minor (px)', f"{stat(p200,'sigma_major_px')[0]:.1f} / {stat(p200,'sigma_minor_px')[0]:.1f}", f"{stat(p220,'sigma_major_px')[0]:.1f} / {stat(p220,'sigma_minor_px')[0]:.1f}", 'no spot'],
        ['Fit error on σ major / minor (px)', f"±{stat(p200,'sigma_major_err_px')[0]:.2f} / ±{stat(p200,'sigma_minor_err_px')[0]:.2f}", f"±{stat(p220,'sigma_major_err_px')[0]:.2f} / ±{stat(p220,'sigma_minor_err_px')[0]:.2f}", '—'],
        ['Fit error on centroid x / y (px)', f"±{stat(p200,'x_err_px')[0]:.2f} / ±{stat(p200,'y_err_px')[0]:.2f}", f"±{stat(p220,'x_err_px')[0]:.2f} / ±{stat(p220,'y_err_px')[0]:.2f}", '—'],
        [f'{X2} whole tile', f3(p200, 'chi2_red'), f3(p220, 'chi2_red'), f3(pnull, 'chi2_red')],
        [f'{X2} core ≤ 2σ', f3(p200, 'chi2_red_core2sig'), f3(p220, 'chi2_red_core2sig'), '—'],
        [f'{X2} background only', f3(p200, 'chi2_far'), f3(p220, 'chi2_far'), f3(pnull, 'chi2_far')],
        ['Δχ², free Gaussian vs no spot', f3(p200, 'delta_chi2_null_minus_free', '{:.0f}'), f3(p220, 'delta_chi2_null_minus_free', '{:.0f}'), f3(pnull, 'delta_chi2_null_minus_free', '{:.0f}')],
        ['R² inside 3σ', f3(p200, 'r2_3sig'), f3(p220, 'r2_3sig'), f3(pnull, 'r2_3sig')]]
story += [table(rows, [1.9 * inch, 1.7 * inch, 1.7 * inch, 1.7 * inch]), P('Median and 5th–95th percentile across pulses.', CAP)]
story += bullets([
    f"<b>A Gaussian fits the PC pulses to the noise level.</b> Whole-tile {X2} is 1.02 and 0.99, against 1.00 in background-only pixels. The core sits slightly above 1 (1.1), "
    "consistent with the scintillator's ~2% misfit pattern. At 1.4 DN that is about 0.03 DN, below the per-pulse noise.",
    f"<b>Per-pulse amplitude is precise; the beam itself varies.</b> The null scatter (±{nullA.std():.3f} DN) gives a measurement precision of about {100*nullA.std()/A200.mean():.1f}% per pulse. "
    f"The observed pulse-to-pulse spread is {100*A200.std()/A200.mean():.0f}% (200 µs) and {100*A220.std()/A220.mean():.0f}% (220 µs), so most of it is real variation in light per pulse.",
    f"<b>Per-pulse widths</b> scatter by {np.std([q['sigma_major_px'] for q in p200]):.1f} / {np.std([q['sigma_minor_px'] for q in p200]):.1f} px (200 µs), several times the fit errors. "
    "That suggests real size variation, as on the scintillator, but correlated background could also inflate it, so dark frames are needed before treating it as beam physics.",
    "<b>A faint tail</b> extends 50–100 px below-right of the PC spot in many pulses (Fig. 8, and the red lobe in Fig. 13c). It is about 10% of the peak, below per-pulse noise but clear in the mean. "
    "It does not appear on the scintillator, so it is plausibly light travelling within the PC sheet or reflecting from the aluminium tape."])
story += [fig(PCD + 'pc_heatmaps_200us_20261001.png', f'<b>Figure 8.</b> Net light for each of the {len(p200)} fully-on PC pulses at 200 µs (4 × 4 binned, destriped), with each pulse\'s 1σ fit ellipse.')]
story += [fig(PCD + 'pc_residuals_200us_20261001.png', '<b>Figure 9.</b> Residuals of each PC pulse\'s fit, in units of the expected noise. No systematic structure rises above the noise in single pulses.')]
story += [fig(PCD + 'pc_goodness_of_fit_20261001.png', '<b>Figure 10.</b> Per-pulse PC results for both runs (220 µs offset by +140 frames): fixed-shape amplitude including the null frames, reduced χ² for the whole tile and the core, and fitted widths with ±1 fit error.', maxh=7.2 * inch)]
story += [fig(PCD + 'pc_null_frames_20261001.png', f'<b>Figure 11.</b> Null test: the {len(pnull)} target-out frames through the same pipeline with a leave-one-out reference. Tile titles give the fixed-shape amplitude at the spot position.', maxh=4.5 * inch)]
story += [fig(PCD + 'pulses/pc_200us_frame_120.png', '<b>Figure 12.</b> A typical PC pulse (200 µs, frame 120). Per-pulse images for all 168 PC pulses are in <i>docs/analysis/20261001/pc_fits/pulses/</i>.')]
story.append(PageBreak())
# ------------- section 3 -------------
story += [P('3  Same beam on both targets: how consistent are the profiles?', H1)]
story += [P("To compare the targets fairly, the mean fully-on spot of each run was processed identically: 4 × 4 binning, rows destriped against pixels beyond 4σ, "
            "a Gaussian plus tilted-plane background, and model-free widths (second moments inside 3σ, corrected for truncation) and FWHM. Errors come from 200 bootstrap resamples of the pulses. "
            "Scintillator frames with the edge in the tile are excluded. The runs were taken in the order PC 200 µs (19:44), scintillator (19:47), PC 220 µs (19:53), "
            "so the two PC runs bracket the scintillator and show how far the beam itself drifted.")]
k = lambda n, q: f"{CMP[n][q][0]:.1f} ± {CMP[n][q][1]:.1f}"
rows = [['', 'Scintillator', 'PC 200 µs', 'PC 220 µs'],
        ['σ major (px)', k('scint', 's_major'), k('pc200', 's_major'), k('pc220', 's_major')],
        ['σ minor (px)', k('scint', 's_minor'), k('pc200', 's_minor'), k('pc220', 's_minor')],
        ['Model-free rms major / minor (px)', f"{CMP['scint']['rms_major'][0]:.1f} / {CMP['scint']['rms_minor'][0]:.1f}", f"{CMP['pc200']['rms_major'][0]:.1f} / {CMP['pc200']['rms_minor'][0]:.1f}", f"{CMP['pc220']['rms_major'][0]:.1f} / {CMP['pc220']['rms_minor'][0]:.1f}"],
        ['FWHM major / minor (px)', f"{CMP['scint']['fwhm_major'][0]:.1f} / {CMP['scint']['fwhm_minor'][0]:.1f}", f"{CMP['pc200']['fwhm_major'][0]:.1f} / {CMP['pc200']['fwhm_minor'][0]:.1f}", f"{CMP['pc220']['fwhm_major'][0]:.1f} / {CMP['pc220']['fwhm_minor'][0]:.1f}"],
        ['Long-axis angle (°)', k('scint', 'theta'), k('pc200', 'theta'), k('pc220', 'theta')],
        ['Centroid x, y (px)', f"{CMP['scint']['x'][0]:.1f}, {CMP['scint']['y'][0]:.1f}", f"{CMP['pc200']['x'][0]:.1f}, {CMP['pc200']['y'][0]:.1f}", f"{CMP['pc220']['x'][0]:.1f}, {CMP['pc220']['y'][0]:.1f}"]]
story += [table(rows, [2.2 * inch, 1.6 * inch, 1.6 * inch, 1.6 * inch]), Spacer(1, 6)]
story += bullets([
    "<b>The profiles agree to within a few percent, which is less than the beam's own drift.</b> Against the PC run 3 minutes earlier, the scintillator is 2.4% wider in σ along the long axis and 1.4% narrower across it. "
    "The model-free rms agrees to 0.4% (long) and 4.6% (short). The angle agrees to 0.7°. The same PC target 9 minutes later had shrunk by 4% and 10%.",
    "<b>Small but significant differences remain.</b> The scintillator's FWHM is 5% larger along the long axis and it has a heavier wing on one side of that axis. The PC shows the extra lobe below-right noted in §2.3. "
    "Together these point to target-specific light transport: diffusion in a few-mm block vs light piping in a 0.5 mm sheet. They are second-order next to the shared Gaussian core.",
    "<b>The centroids differ by about 8 px in x and 5–6 px in y.</b> That is expected because the camera views the targets at an angle and the two targets sit at different depths, so the same beam lands at different image positions. "
    "Comparing positions in beam coordinates needs the grid calibration.",
    "<b>Conclusion:</b> either target gives the beam's transverse shape to a few percent. The scintillator offers about 90× more light per pulse; the PC is thinner and perturbs the beam less. "
    "At current light levels the PC already gives per-pulse amplitude to about 1.4%."])
story += [fig('/home/claude/cmp/profile_comparison_20261001.png', '<b>Figure 13.</b> (a, b) Normalised mean profiles along the long and short axes. (c) Normalised difference map, PC 200 µs minus scintillator, aligned on the fitted centroids. (d) PC shape parameters relative to the scintillator. (e) Parameter table.')]
# ------------- section 4 -------------
story += [P('4  Limitations and next steps', H1)]
story += bullets([
    "<b>No dark frames.</b> Every background reference here is a set of target-out frames. Those contain heavy radiation hits, moved scene objects and, for the scintillator, glowing edges in other places. "
    "Take lens-capped frames with the beam on and off at the same delay and gate, plus a target-out reference without moving anything else in view.",
    "<b>Unattributed 0.13 DN correlated background</b> in the PC tile. Dark frames will show whether it comes from the sensor or the beam.",
    "<b>Pixels, not millimetres.</b> The camera views the targets at an angle, so ellipse axes and centroids are in image coordinates. Photograph a printed grid at the target plane to get the scale and correct for the viewing angle.",
    "<b>No flat field.</b> Pixel response non-uniformity (≈0.7% from the photon-transfer curve) and vignetting are not corrected. Take a flat field after the aperture is set.",
    "<b>Gain is not logged.</b> The capture JSON should record analog gain so that DN can be compared between sessions.",
    "<b>The Gaussian misfit</b> (~2% on the scintillator) should be tested against a double Gaussian or a skewed profile once the background is clean."])
story += [P('Files', H2), P("Workspace folder <i>docs/analysis/20261001/</i>: <i>pulse_fits/</i> (scintillator heatmaps, residuals, goodness-of-fit, per-pulse images, CSV, scripts), "
                            "<i>pc_fits/</i> (the same for polycarbonate, plus background figures), and <i>profile_comparison_20261001.png</i>. "
                            "Raw captures remain on pi-06-ioc in <i>dose_cam/captures/Al_PC</i> and <i>Scint</i>.", SM)]
def deco(c, d):
    c.saveState(); c.setFont('DV', 7.5); c.setFillColor(MUTED)
    c.drawString(0.75 * inch, 0.5 * inch, 'DoseCam pulse-by-pulse spot analysis · 1 Oct 2026 runs')
    c.drawRightString(7.75 * inch, 0.5 * inch, str(d.page)); c.restoreState()
doc = SimpleDocTemplate('/mnt/user-data/outputs/DoseCam_pulse_analysis_20261001.pdf', pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                        topMargin=0.7 * inch, bottomMargin=0.75 * inch, title='DoseCam pulse-by-pulse spot analysis', author='Duke FEL Lab (analysis by Claude)')
doc.build(story, onFirstPage=deco, onLaterPages=deco)
print('built')
