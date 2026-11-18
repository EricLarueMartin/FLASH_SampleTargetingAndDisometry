# DoseCam light mechanism, camera gain and film uncertainty

Research date: 2026-11-16. Local analysis only; not deployed. This note supersedes
the unsupported mechanism and uncertainty claims in the original handoff.
Calculations: `scripts/light_budget.py`; numeric output: `light_budget.json`.

**Scope update, 2026-11-16:** Eric does not plan scintillation-versus-Cherenkov
separation measurements. The presentation simply notes that primary Cherenkov
light should be internally reflected in the current geometry. The component
fractions below are retained as exploratory sensitivity calculations, not a
measurement program or a validated decomposition. The primary-cone TIR result
does not depend on camera viewing angle; camera-angle examples below are
retained only as part of the exploratory collection model. All film wells are
treated on the same basis, with no row-dependent correction. The aluminum-tape
target is likely nonuniform, so spot motion can change the collected light;
this contribution has not been quantified.

## Findings and confidence

**Scintillation is a credible, potentially dominant source of the recorded spot.**
The statement “mostly Cherenkov” is unsupported. Undoped PC scintillates; doping
is not required. The user's geometry also strongly suppresses the direct,
primary-electron Cherenkov contribution into the camera. A unique experimental
percentage cannot be extracted from the four broadband frames.

A useful **conditional benchmark is about 70% scintillation / 30% Cherenkov**
after sensor QE weighting, if both mechanisms have equal optical throughput.
That is a sensitivity-model result, **not a measured split or a confidence interval**.
It uses a weakly established absolute scintillation-yield scale. In a single-bounce
rough-reflector model appropriate to the stated geometry, a worked example gives
about **73% scintillation / 27% Cherenkov**, assuming 20% relative UV throughput
and 10% diffuse reflection. Those two inputs are unmeasured: the example shows sensitivity to assumed optics, not a measured 73% fraction.
No component-separation measurement is planned.

The defensible present conclusion is **scintillation probably contributes substantially;
scintillation dominance is the working hypothesis for a mostly smooth target**.
The evidence does not establish a lower bound on its camera fraction. Strong UV
attenuation, foil facets, adhesive fluorescence, and secondary-electron light can
change the result. No measured uncertainty distribution exists for these effects.

**Camera noise accounting:** the four archived peak fits have **0.35–0.39%
nominal 1σ** errors from residual-scaled covariance. This is one combined
contribution: photon and read/background noise are not added again. Gain-dependent
component projections are diagnostics; see the reproducible
[audit](https://github.com/EricLarueMartin/FLASH_SampleTargetingAndDisometry/blob/main/docs/analysis/20261116_film_comparison/scripts/fit_noise_audit.json).
Use **10.7 e-/DN** only as a manufacturer-camera gain proxy, with **8–12 e-/DN**
as a sensitivity interval, not a calibrated uncertainty.

**Film, updated 2026-11-18:** the supplied workbook reports **intensity SD**, not
a complete dose uncertainty. The earlier interpretation of 1.9–2.4% as supplied
standard dose uncertainties is superseded. **~3% (k = 1)** is a protocol-dependent
literature benchmark, not an established uncertainty for our 40 Gy readings.
No independent film peak-fit error is available. The mixed rate-response
literature remains a minor caveat; no rate-related bias is established for this run.

## 1. Evidence for intrinsic PC scintillation

[Nakamura et al. (2014), Jpn. J. Health Phys. 49, 98–101,
doi:10.5453/jhps.49.98](https://www.jstage.jst.go.jp/article/jhps/49/2/49_98/_article)
tested undoped Teijin PC with conversion electrons. Their relative light output
was 0.67 of undoped PET; they describe PET as approximately one-seventh of a
typical organic scintillator. Their optically excited spectrum peaks near 350 nm.
This establishes the mechanism but supplies neither an absolute photon yield
for our sheet nor a spectrum measured during our beam pulse. The source used a
5 mm plate and PMT coupling, unlike our 0.5 mm sheet and remote camera.

The reported ratio is a **relative detector light output**, not an independently
calibrated intrinsic photons/MeV measurement. Wavelength-dependent collection,
PMT sensitivity and Cherenkov contamination in the electron-source measurement
limit transfer to our apparatus. Treat it as an order-of-magnitude anchor.

[PDG (2024), Particle Detectors at Accelerators, sections 35.3 and 35.5](https://pdg.lbl.gov/2024/reviews/rpp2024-rev-particle-detectors-accel.pdf)
describes aromatic-matrix scintillation and wavelength-shifting dopants, gives
the typical organic scintillator scale of one photon per 100 eV, and states the
Cherenkov yield including collection and detector efficiency separately.

## 2. Photon-production estimate

Inputs from the experiment: 30 MeV electrons, 0.5 mm PC. Use n = 1.585 as a
constant-index approximation. Real dispersion increases n toward the UV, so
this approximation is sufficient for scale estimates, not precision optics.
Beta = sqrt(1 - [1 + 30/0.511]^-2) = 0.99986.

Frank–Tamm, with wavelength and path length expressed in consistent units:

    N_C = 2 pi alpha L (1 - 1/(beta n)^2) (1/lambda_min - 1/lambda_max)

The computed yield per traversing primary electron is **14.8 photons in
400–700 nm**, **26.3 in 300–700 nm**, or **33.4 in 300–1100 nm**. Thus the old
“15 visible photons” scale is reasonable only with its 400–700 nm band stated.
It does not establish which component reaches the camera. Cherenkov photons
below 300 nm are excluded here; absorption and possible wavelength conversion
would require an additional transport model.

For scintillation, take the relative-output chain as a proxy:

    Y_S,proxy = (0.67/7) * 10,000 = approximately 960 photons/MeV
    DeltaE_proxy = (1.20 g/cm3) * (0.05 cm) * (2.0 MeV cm2/g) = 0.12 MeV
    N_S,proxy = approximately 115 photons/electron

[PDG's PC material table](https://pdg.lbl.gov/2023/AtomicNuclearProperties/HTML/polycarbonate_Lexan.html)
supplies density 1.20 g/cm3. **The 2.0 MeV cm2/g collision stopping power is a
rounded scaling assumption, not a retrieved ESTAR value at 30 MeV.** NIST's
definition distinguishes excitation/ionization loss from bremsstrahlung; the
30 MeV beam energy must not be substituted for local energy deposition in a
thin sheet. Escaping delta rays also make collision loss an imperfect local
deposition estimator. See [NIST ESTAR](https://physics.nist.gov/PhysRefData/Star/Text/ESTAR.html)
and [NIST definitions](https://pml.nist.gov/PhysRefData/Star/Text/appendix.html).

These assumptions give a **production proxy of 77% scintillation / 23% Cherenkov
over 300–1100 nm**. Allowing a factor of two either way in the scintillation
normalization moves the scintillation fraction to 63–87%. That factor of two is
a stress test, not a measured uncertainty or assurance that the true yield lies
inside it. An exact 80/20 claim is not justified.

## 3. QE, lens and geometry: production is not camera signal

[Teledyne FLIR's IMX296 monochrome EMVA page](https://softwareservices.flir.com/FFY-U3-16S2-DL/latest/EMVA/EMVA.html)
includes the spectral-response curve preserved in the slide assets. Approximate readings
are QE 20% at 350 nm, 43% at 400 nm and 60–65% at 450–550 nm; its tabulated
525 nm QE is 64.28%. The curve belongs to a complete Firefly camera and is a
proxy for our module's response, not its factory calibration.

Our hardware log identifies an **InnoMaker mono IMX296** and records a detected
10-bit MONO mode. The handoff's description as a Raspberry Pi-branded GS camera
was imprecise. Color Bayer-channel QE values must not be used for this module.

The supplied curve and Fig. 4 of the PC paper were sampled approximately by eye.
All points are preserved in the calculation script and JSON. Integrating the PC
emission proxy and the 1/lambda^2 Cherenkov spectrum against QE, over 300–1100 nm,
gives mean QE approximately **0.254 for scintillation** and **0.365 for Cherenkov**.
Their yield-weighted signals are approximately **29 and 12**, before solid angle,
transmission or reflection losses. They are not detected electron counts in our
camera. With equal throughput, their ratio implies **70.5% scintillation**.
Halving/doubling the yield proxy moves that benchmark to 54–83%.

User-supplied optical geometry (2026-11-16): beam normal to PC within a couple
of degrees; camera about 30 degrees from sheet normal, viewing the untaped face;
Arducam 8–50 mm C-mount zoom lens with C-CS adapter. If the observed face is
different, revise the reflection model. The
[Arducam LN057 product page](https://www.arducam.com/arducam-8-50mm-varifocal-c-mount-lens-for-raspberry-pi-hq-camera-with-c-cs-adapter-ln057.html)
and [C/CS lens documentation](https://docs.arducam.com/Optics-and-Lenses/Types-of-Lenses/C-CS-Mount-Lens/)
were located, but **no quantitative 330–420 nm transmission curve was found**.
An absence of an IR filter would not establish UV transmission. Sensor QE alone
cannot remove this uncertainty. PC grade, adhesive, coatings and sensor window
transmission also matter.

From Snell's law and the Cherenkov relation:

    theta_C = arccos(1/(beta*n)) = 50.88 degrees about the electron direction
    theta_critical = arcsin(1/n) = 39.12 degrees at a PC-air boundary
    theta_camera,internal = arcsin(sin(30 degrees)/n) = 18.39 degrees

At 2 degrees sheet tilt, primary-cone incidence on the free surface is still
approximately 49–53 degrees: all of that cone undergoes total internal reflection
in the ideal planar model. A flat, parallel aluminum reflector reverses the
normal component of the ray but does not reduce its incidence angle. It cannot
alone extract the primary cone into the camera. A cone ray needs roughly a
16-degree mirror-facet tilt to turn 51 degrees toward the camera's 18-degree
internal ray in a favorable plane. There is no measured foil-facet distribution.

This excludes **direct plus flat-specular primary-cone light**, not all Cherenkov:
roughness, foil wrinkles, edges, multiple reflections, secondary electrons, and
scattering can contribute. Cherenkov-excited fluorescence is a further mixed
mechanism. A spatially sharp imaged spot favors local light paths, but does not
measure their proportions.

### Independent verification of the angular claim

PDG Eq. 35.5 gives the cone half-angle. [OpenStax, equations 25.15–25.17](https://openstax.org/books/college-physics/pages/25-4-total-internal-reflection)
gives Snell's law and the critical-angle condition. Substitution gives

    sin(theta_air) = n sin(theta_C) = sqrt(n^2 - 1/beta^2) = 1.2296 > 1.

There is no real refracted angle for that ideal cone. Normal-incidence primary-cone
trapping occurs if n^2 > 1 + 1/beta^2, approximately n > sqrt(2). A separate numerical 3D ray check swept all azimuths
and beam tilts from -2 to +2 degrees: for n = 1.575, 1.585 and 1.64, the
minimum reflected incidence angles were 48.58, 48.88 and 50.42 degrees,
respectively, each above its critical angle. This is a
calculation from cited laws, not a measurement on our target. The 18.39-degree
number traces the camera's 30-degree external ray backward; it is not the outgoing
refraction angle of the 51-degree cone.

A directly relevant theoretical example is [Beloshitskii, Mikheev and Tulupov,
Sov. Phys. JETP 58, 1010 (1983)](https://jetp.ras.ru/cgi-bin/dn/e_058_05_1010.pdf):
they distinguish primary-electron Cherenkov light blocked by internal reflection
from secondary-electron Cherenkov light that can escape. Their crystal calculation
does not supply a numerical fraction for our amorphous PC target. The
[DIRC detector review](https://www.sciencedirect.com/science/article/pii/S0168900220300401)
also describes retention of angular information through specular reflections.

A straight long track at fixed wavelength produces radiation concentrated on a
conical shell, whose intersection with a distant transverse plane is a ring.
Real finite tracks have angular width and sidelobes; dispersion, scattering and
secondary-electron directions broaden the distribution. Do not claim that all
real emission inside the primary cone is identically zero. Interface/transition
radiation is another contribution outside the bulk-cone calculation.

As a purely kinematic example, an electron directed along the normal with about
0.173 MeV kinetic energy has a Cherenkov angle of 18.4 degrees in PC and can
feed a 30-degree external ray after a suitable reflection. Real delta-electron
energy and direction are correlated; this example is not their transport model.
The secondary-electron contribution has not been calculated. Its omission means
that primary-cone trapping alone cannot establish the camera's total light split.

### A transparent rough-reflector sensitivity model

For a single bounce, assume Al reflectivity R = 0.9, an isotropic scintillation
source with direct and mirror-return contributions, and a fraction d of
Cherenkov light redistributed as a Lambertian field at the backing. R and d are
scenario inputs, not measured properties of this tape. Fresnel transmission
and the solid-angle refraction factor cancel approximately for a common exit
direction. The relative angular collection is then

    G_C/G_S = 4 R d cos(theta_camera,internal)/(1+R) = approximately 1.80 d
    f_S = 29.17 T / (29.17 T + 12.20 * 1.80 d)

T is the scintillation-spectrum-weighted throughput relative to Cherenkov after
QE; it represents the *relative* remaining losses, not lens transmission at one
wavelength. This effective two-number model does not simulate repeated bounces
or localized specular glare. It cannot be fitted with these four images.

| Assumed relative UV throughput T | Assumed diffuse fraction d | Predicted scintillation / Cherenkov |
|---:|---:|---:|
| 100% | 1% | 99% / 1% |
| 100% | 10% | 93% / 7% |
| 20% | 1% | 96% / 4% |
| 20% | 10% | 73% / 27% |
| 1% | 1% | 57% / 43% |
| 1% | 10% | 12% / 88% |

This table shows why **a precise “likely percentage” is not defensible yet**.
Scintillation dominance is physically plausible and favored by the ideal
geometry, while severe UV loss can reverse the result. Neither 20% transmission
nor 10% diffusion has been measured or sourced as a property of this apparatus.
The old 1% brightness ratio to an unidentified thicker scintillator was not
dose-normalized and supplies no independent decomposition.

## 4. Conversion gain and photon-count noise

The [Firefly mono IMX296 EMVA data](https://softwareservices.flir.com/FFY-U3-16S2-DL/latest/EMVA/EMVA.html)
report a **10-bit ADC**, 10,276-electron saturation capacity, 4.69-electron temporal
dark noise and 10.74 e-/ADU conversion gain. Their ratio 4.69/0.44 = 10.66 e-/DN
and 10,276/10.74 = 957 useful DN are consistent with native 10-bit code units.
The 16-bit transport-container wording does not justify multiplying gain by 64.
Our own >>6 unpacking also produces 10-bit codes.

[Raspberry Pi libcamera's IMX296 helper](https://raw.githubusercontent.com/raspberrypi/libcamera/main/src/ipa/rpi/cam_helper/cam_helper_imx296.cpp)
maps linear analogue gain 1 to register code 0 (0 dB). The
[kernel driver](https://raw.githubusercontent.com/raspberrypi/linux/rpi-6.12.y/drivers/media/i2c/imx296.c)
sets sensor controls and a native 10-bit output; the
[Pi 5 tuning file](https://raw.githubusercontent.com/raspberrypi/libcamera/main/src/ipa/rpi/pisp/data/imx296.json)
has black level 3840 in 16-bit scale, corresponding to 60 native DN. Neither
source calibrates our e-/DN or proves that its ADC clip point equals full well.
In particular, a tuning noise-model coefficient is not a conversion-gain
measurement. These web versions are not verified as the installed Pi versions.

Use **10.7 e-/DN** with an **8–12 sensitivity interval**, not a statistical
confidence interval. The existing background-pair method, reapplied to all
34 Alanine frames, gives **0.5078 DN** per-pixel background RMS. This already
includes quantization and correlated background effects; no separate
quantization term is added to it. Dark frames alone do not calibrate conversion
gain. The vendor gain is from another camera using IMX296, not this module.

| Statistic | At 10.7 e-/DN | Across 8–12 e-/DN |
|---|---:|---:|
| Peak pixel, 42 DN | 449 e-; 4.72% shot noise | 4.45–5.46% |
| 10 x 10 pixel ideal window, 4200 DN | 44,940 e-; 0.472% | 0.445–0.546% |
| Whole spot, 180,000 DN | 1.926 million e-; 0.0721% | 0.0680–0.0833% |
| Ideal Poisson-weighted Gaussian peak floor, 1.42/sqrt(N) | 0.102% | 0.0966–0.118% |

The 10 x 10 camera window is a hypothetical constant-peak approximation.
The ideal peak floor assumes a Poisson-weighted Gaussian, effectively full
spatial support and no fitted background penalty. It is not the uncertainty
of the actual unweighted robust fit, nor an additional budget term.

### Residual-covariance error and component audit

The fitter uses unweighted DN residuals with `soft_l1` loss. Reported errors
use the plain model Jacobian and `C=s²*inv(J.T@J)`, where
`s²=sum(residual²)/(N_pixels-7)`. The amplitude standard error is
`sqrt(C[0,0])`. Archived baseline-fit parameters and residual RMS reproduce
**0.1602, 0.1664, 0.1480 and 0.1531 DN**, or **0.379, 0.388, 0.349 and
0.370%**, for B1/A1/A2/A3. No peak is refitted. This is a nominal
independent-pixel covariance, not an exact robust/spatial-covariance treatment.

At the gain proxy, the measured spot occupies approximately **3970–4482
equivalent Gaussian pixels**, with **443–459 electrons per peak pixel**.
Thus approximately two million electrons are localized in the spot, rather
than spread uniformly over the full sensor.

The same amplitude influence vector propagates independent photon noise to
**0.121–0.127%** peak SE. Projection of all 34 background frames after the same
40 DN positive-hit despiking and quadratic baseline subtraction gives
**0.124–0.133%** from background variability, including its correlations.
Their conditional quadrature diagnostic is approximately **0.18%**. Gain is
not calibrated and these no-beam backgrounds do not uniquely partition the
signal-frame residuals, so the slide uses the **combined 0.35–0.39% nominal
fit error**. Neither component diagnostic is added to it. Masking sensitivity
also is not assumed independent for a quadrature total. The
[audit script and outputs](https://github.com/EricLarueMartin/FLASH_SampleTargetingAndDisometry/tree/main/docs/analysis/20261116_film_comparison/scripts)
preserve the calculation and assumptions.

Under the Poisson model, shot noise is too small to explain the observed scatter.
Common variations in beam charge or target response remain possible.
Operator delay/duration scans established full-signal plateaus, with the chosen
gate margins much larger than expected jitter; gate clipping is not expected
to contribute appreciably under those settings. Four frames cannot establish which systematic dominates. The Fano-factor
discussion was removed at the user's request; it is not needed for this comparison.

## 5. EBT-XD at 40 Gy

### Range, conventional uncertainty and FLASH bias

The usual manufacturer ranges, reproduced in the primary dosimetry studies,
are **0.1–60 Gy dynamic** and **0.4–40 Gy optimum**. The
[Ashland protocol](https://www.ashland.com/file_source/Ashland/Documents/PHA21-011_Gafchromic%20EBT-XD%20Protocol.pdf)
explains that declining slope raises high-dose uncertainty; 40 Gy is at the
optimum range's upper edge, not a hard optical saturation threshold. The PDF
was indexed by search but could not be downloaded during this session.

[León-Marroquín et al. (2019), doi:10.1002/mp.13708](https://pubmed.ncbi.nlm.nih.gov/31297824/)
report approximately 3.1% red-channel uncertainty over 5–40 Gy and 2.4% green
over 8–50 Gy when transferring calibrations between beam qualities. These
values are not a universal budget for our scanner or a red-versus-multichannel
comparison. The often-repeated 2.3% electron result is protocol dependent;
do not substitute it for absolute FLASH uncertainty.

[Smyth et al. (2024), doi:10.1007/s13246-024-01430-z](https://link.springer.com/article/10.1007/s13246-024-01430-z)
compared channel combinations through 30 Gy, with seven-day readout rather than
24-hour readout. Green-only and RGB averaging had
check-film scale-factor SDs of about 2.5–3.0%. RGB averaging is not automatically
the same as a multichannel disturbance-correction algorithm. No matched
40 Gy, 24-hour, multichannel absolute uncertainty for our protocol was established.

[Del Sarto et al. (2025), doi:10.3389/fphy.2025.1474416](https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2025.1474416/full)
used 24-hour flatbed readout at about 40 Gy total. Electron pulses spanned
0.7–19.3 Gy and instantaneous rates up to 4.82 MGy/s. They reported a possible
**7% +/- 3.3% dose overestimate** at the high-rate extreme relative to flashDiamond,
conditional on that reference. This is a possible bias, not a 1-sigma film
uncertainty or a correction to apply to our data. Their ~5% working film allowance
does not validate ours. At 40 Gy in a 1–4 us pulse, our instantaneous rate would
be 10–40 MGy/s, an extrapolation beyond that study. Gate duration is not beam
pulse duration. Our beam pulse width needs independent confirmation.

The literature uses different beam conditions and measurement methods and
reports mixed evidence on rate dependence. No rate correction is assigned to
this run. The workbook audit and absolute-dose benchmark below replace the
earlier film-uncertainty assumption; historical code allowances are unchanged.

### Workbook audit and absolute-dose uncertainty (2026-11-18)

Eric supplied `Film41_Scintillation.xlsx` on 2026-11-18. Read-only ZIP/XML
inspection found one `ROIs` sheet, numeric values and no cell formulas. Its
headers separate `Mean_Intensity`, `Standard_Deviation`, `Optical_Density` and
`Dose_Gy`; there is **no dose uncertainty column, calibration covariance, or
definition of the SD estimator**. The calibration is labelled EBTXD lot 06092501,
24 hr (Sep-2026), using `Global_I0 = 45459.659129`. All six ROI rows say
`Statistic = max`, `Window_px = 10`. That metadata does not establish a fitted
film-peak standard error. The workbook was not changed or copied into the repository.

The first four ROI doses match the four comparison film values (ROI 4, 1, 2, 3
in pulse order). The intensity entries are:

| Workbook cells / ROI | Mean intensity | Intensity SD | SD / intensity | Dose (Gy) |
|---|---:|---:|---:|---:|
| G3:J3 / ROI 1 | 14412.62 | 158.766125 | 1.102% | 39.612909 |
| G4:J4 / ROI 2 | 14384.71 | 176.901462 | 1.230% | 39.745937 |
| G5:J5 / ROI 3 | 14393.88 | 176.246973 | 1.224% | 39.702168 |
| G6:J6 / ROI 4 | 14139.85 | 199.909645 | 1.414% | 40.937639 |

The optical densities agree with `OD = log10(I0 / I)`. Propagation through a
dose calibration `D = f(OD)` requires its derivative and parameter covariance:
`u_OD = u_I / (I ln(10))` if I0 is fixed, then `u_D,reading = |f'(OD)| u_OD`.
Uncertainty in I0 and calibration parameters must also be included, with their
covariances where relevant. The workbook does not supply these. A local slope
inferred from neighbouring dose/OD pairs is consistent with the historical
1.9–2.4% dose-spread range, but does **not** turn that spread into a verified
standard error or a complete absolute-dose uncertainty.

If this is spatial pixel SD, it can contain real dose gradients, film
nonuniformity and scanner noise. It need not be purely statistical. The file
does not specify whether pixels, window means or repeated scans generated SD;
no SD-to-SEM reduction is made here.

Published budgets establish performance of calibrated film/scanner protocols,
rather than a universal EBT-XD absolute-accuracy specification:

[Jung et al. (2025), Table 4, doi:10.1002/mp.70022](https://doi.org/10.1002/mp.70022):
  24-hour red-channel electron-FLASH budget at ~22 Gy, **3.5% (k = 1)**,
  including assumed **2.0% beam stability**. The other grouped terms are
  reference dosimetry 0.9%, calibration fit 2.1%, scanner uniformity 0.5%, and
  film reading 1.6%. Our quadrature calculation excluding delivery stability is
  `sqrt(0.9² + 2.1² + 0.5² + 1.6²) = 2.83%`. This illustrates a combined film
  benchmark without attributing shared delivery fluctuations to a simultaneous
  camera/film comparison; it is not a validation at 40 Gy for this scanner.

[Raj et al. (2024), Table 1, doi:10.1002/pro6.1236](https://doi.org/10.1002/pro6.1236):
  red/green combined **1.52% (k = 1)**, approximately **3% expanded (k = 2)**,
  for a 24-hour protocol tested over 0.5–30 Gy. Their budget excludes lateral
  scanner response, with films near the scanner centre. This is achievable
  protocol performance, not a matching 40 Gy uncertainty or a universal limit.

[AAPM TG-235 (2020), §6.H, doi:10.1002/mp.14497](https://doi.org/10.1002/mp.14497):
  each setup needs its own uncertainty evaluation, including reference-dose
  calibration, scanner properties, film uniformity and calibration fitting.
  Its example values are k = 1 unless stated otherwise. Manufacturer response
  uniformity specifications do not establish the whole absolute-dose budget.

The slide therefore uses **~3% (k = 1) as a provisional literature benchmark**.
It does not assign measured film error bars from that benchmark. A full
published total already contains reading and nonuniformity terms: **do not add
that total in quadrature with the workbook SD**. A common calibration-scale
uncertainty affects absolute camera calibration and is correlated across the
four wells; it does not behave as independent scatter between those wells.

### Film treatment in this comparison

All film wells use the same calibration and are assumed comparable, as instructed
by Eric on 2026-11-16. No row-dependent offset, uncertainty term or dose correction
is assigned. The measured film values and 1.0563 DN/Gy camera calibration are unchanged.

The 2026-11-18 workbook audit above supersedes the 2026-11-17 assumption that
the historical 1.9–2.4% range represented supplied standard dose uncertainties.
No independent film peak-fit uncertainty or complete scanner-specific dose
uncertainty is calculated here.
Four pulse/well pairs cannot separate real beam
variation, camera response and target effects. The recorded frame/well mapping is taken
as correct for this analysis, as instructed by Eric on 2026-11-16.

## 6. Remaining camera and film checks

No scintillation-versus-Cherenkov separation measurement is planned. The
presentation’s optical conclusion is the expected internal reflection of the
primary cone, with the ideal-geometry qualification stated.

1. Obtain uniform-light flat sequences for a photon-transfer curve on the
   mono module at gain 1 and the same raw format; existing background frames
   alone do not calibrate conversion gain.
2. Repeat >=10 pulses on a stationary target patch with an independent charge
   monitor, and add a second dose level. The recorded frame/well order is accepted.

## Sources and audit trail

All source links are placed next to their claims above and on the relevant
slides. Downloaded literature reading copies and page renders in `sources/`
are local analysis aids, excluded from Git; use the linked publisher copy of
the principal material study. The original
FLIR QE PNG is preserved in the slide `img/` directory with a source attribution
in the deck. Curve points, assumptions and all recomputed quantities are in the
script/JSON pair; the calculation requires NumPy >=2.0. Rerunning it does not
read captures or access hardware.

No Pi access, EPICS actions, motor changes, deployment or GitHub push occurred.
