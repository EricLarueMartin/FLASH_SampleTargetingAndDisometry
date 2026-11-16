# Faraday cup digitizer

Design note. Started 2026-10-19; hardware revised the same day to an **AD9226 ADC
module on a Digilent Arty A7**. Nothing built yet.

## Requirement

Read the Faraday cup sample-and-hold output **per beam pulse**, at a fixed pickoff
**5 us after its negative-going edge**, near the low energy spectrometer where
elm-ioc-00 sits. Today that reading is taken by eye on a LeCroy in the control room,
which has no usable network or remote interface.

Known (operator, 2026-10-19):

- Amplitude at the pickoff: **+/-1 V to +/-10 V**.
- Rep rate: **10-100 Hz**; 15 Hz is the near-term case.
- **Waveform: a noisy rise, then a clean exponential decay** once the noise settles.
  The 5 us pickoff reads a point on that decay.
- 20 MHz / tens of MS/s is ample.
- The fit does not have to be live: a near-time indication per shot, definitive
  analysis offline.

## Hardware: AD9226 module + Arty A7 (decided 2026-10-19)

**Use the Arty A7, not the Z7.** Neither is cheaper to buy: on 2026-10-19 Digilent
lists the Arty A7-100T and the Arty Z7 both at **$322**, and the A7-35T is retired. So
the choice is on fit, and for this job the A7 fits better:

- **No processor is needed.** The FPGA's whole job is: clock the ADC, watch for the
  edge, keep a pre-trigger history, timestamp, cut out one record per shot, send it.
  That is plain HDL - no MicroBlaze, no operating system, no SD card - booting from
  the QSPI flash in about a second with nothing to maintain. The Pi does all the
  software.
- **The link is the USB-UART that is already on the board** (FTDI FT2232HQ on both
  Artys - confirmed for the Z7 from its reference manual; the A7 uses the same part).
  The bandwidth fits easily; see "Link".
- **The Z7's strengths are not needed here.** Its dual Cortex-A9 with Linux, gigabit
  Ethernet and DDR would make the digitizer a standalone network instrument. With the
  Pi a USB cable away, that is a second computer to maintain for no gain. Keep the Z7
  for something that needs it. If a future version must stand alone on the network,
  the same HDL moves to the Z7's programmable logic unchanged.
- Either A7 variant works: the 35T's 225 KB of block RAM already holds a 64 KB
  circular history plus double-buffered records many times over.

**If several units are wanted later**, both Artys are expensive for this; a smaller
Digilent Artix-7 module with on-board USB-UART (the Cmod A7 family) runs the same
design - worth pricing at that point.

### The AD9226 module

Ordered 2026-10-19 (generic module, Walmart listing gives "input voltage 5 V").

**Datasheet facts** (AD9226 data sheet, Rev. B):

| | |
| --- | --- |
| AVDD (analog core) | **5 V** (4.75-5.25 V) - the module's 5 V input powers the ADC itself, so it does not "run on 3.3 V" internally |
| DRVDD (output drivers) | **2.85-5.25 V**, and it sets the logic-high level of D0-D11 and OTR: about 3 V outputs at DRVDD = 3 V, **about 5 V outputs at DRVDD = 5 V** |
| CLK input | VIH min 2.4 V, VIL max 0.8 V - a 3.3 V clock from the FPGA is within spec |
| Pipeline latency | 7 clock cycles (p. 4; p. 14 describes a nine-stage pipeline - measure it) |
| ADC span | 1 or 2 V p-p at the converter, set by VREF; the module's front end maps its stated input range onto that |
| Power | 475 mW typical for the ADC alone |

**The one thing that can damage the Arty:** whether the module ties DRVDD to its 5 V
input or to a 3.3 V regulator. A 3.3 V LDO on the board (often an AMS1117-3.3) is a
good sign but not proof. **Check before connecting to the Arty.**

### On arrival - checks in order

Nothing connected to the Arty until 1 and 2 pass.

1. **Output logic level.** Power the module alone from 5 V. With a DMM, measure each
   data pin to ground; any bit that sits high reads DRVDD. Better: clock it from a
   function generator (3.3 V square wave, a few MHz), feed a slow ramp in, and look at
   D11 and D0 on a scope. **Highs must be about 3.3 V.** If they are about 5 V: find
   where DRVDD is fed (a jumper, 0 Ohm link or separate pin) and move it to 3.3 V. If
   that is not possible, a 3.3 V-powered 74LVC245 (5 V-tolerant inputs) between the
   module and the Pmods. Series resistors relying on the FPGA's clamp diodes are not an
   acceptable fix at 50 MHz.
2. **Input impedance.** Power off, ohmmeter from the input connector's centre to
   ground. **About 50 Ohm** means a termination resistor (a small 49.9 or 51 Ohm chip
   right beside the connector) - remove it. Anything from a few kOhm up: note the value;
   it sets the attenuator below.
3. **Coupling.** Look at the input path: a small 6-pin transformer (balun) between the
   connector and the ADC means **AC coupling** - unusable for this pulse without
   reworking a DC path. An op-amp means DC coupling, which is what is needed. Confirm by
   applying a DC voltage and seeing the output code follow it and stay.
4. **Input range and polarity.** Apply known DC levels (0, +/-1 V, +/-full scale) and
   record the codes: that gives the actual range, the gain, the offset and the coding
   (straight binary or two's complement) in one go. **The Faraday signal is negative**,
   so the key result is whether the module is **bipolar** (0 V reads mid-scale and
   negative inputs give valid codes - the usual +/-5 V op-amp front end) or
   **unipolar** (negative inputs clip at the bottom code; a single-supply op-amp cannot
   follow them).
   - Bipolar: nothing to change. The pulse uses the negative half of the range, which
     costs one bit (still 7.3 mV per code at the input with 3:1, and the tail fit
     averages hundreds of samples). The trigger already fires on the falling edge and
     the fit takes a negative amplitude.
   - Unipolar: shift the level in the attenuator itself, still passive - add a third
     resistor from the divider's output node to a stable positive reference, so 0 V
     input sits near the top of the range and the most negative input near the bottom.
     Use a reference IC (e.g. an LM4040-class shunt) rather than the module's 5 V rail;
     per-shot baseline subtraction removes slow drift, but rail noise at microsecond
     timescales would land in the measurement. An inverting op-amp stage is the active
     alternative.

### Power

The module needs 5 V at roughly 150-250 mA (475 mW for the ADC plus its op-amps and
regulators). Do not run the Arty plus the module from the Pi's USB: the Pi 5 allows
600 mA total per its USB budget unless it detects a 5 A supply. Power the Arty from its
own barrel-jack supply and feed the module from the Arty's 5 V header pin, or give the
module its own 5 V supply with the grounds joined at the Arty.

### Attenuator (air-wired in a grounded enclosure)

Rules, then an example; final values after check 2 and 4.

- **Input impedance at least 10 kOhm.** If the S&H drives the line through a 50 Ohm
  back-termination, a load R at the T lowers the voltage there by about 50/R: 10 kOhm
  costs 0.5 %, 100 kOhm costs 0.05 %. If it is driven straight from an op-amp, loading
  barely matters. The LeCroy acceptance test settles it either way.
- **Division:** put the largest expected excursion - including the noisy rise, not just
  the 5 us value - at about 70 % of the module's full scale. For a +/-5 V module and a
  signal reaching -10 V, that is **3:1**. Resolution is not the limit: 12 bits over
  +/-5 V is 2.4 mV, 7.3 mV referred to the input, and the tail fit averages hundreds of
  samples.
- **Divider output impedance well below the module's input impedance**, or the module
  forms part of the divider. That only changes the gain (calibrated out), but keep it
  small so the gain does not depend on the module's input tolerance.
- **Bandwidth:** output impedance x (module input capacitance + wiring) sets a corner;
  keep it above about 1 MHz. A slightly slowed edge only shifts t0 by a constant, which
  is common to every shot and absorbed by the gain calibration. If wanted, a small
  capacitor across the top resistor (about R2 x C_in / R1) compensates it like a scope
  probe; trim it on a square wave.
- **Protection:** the top resistor limits fault current into the module's input
  clamps - 20 kOhm holds a 50 V transient to 2.5 mA.

Example, for a module with high input impedance (100 kOhm or more) and a +/-5 V range:
**R1 = 20 kOhm in series, R2 = 10 kOhm to ground** - 30 kOhm input, 6.7 kOhm output,
3:1, corner around 2 MHz with 10 pF. Metal film, 25 ppm/degC or better so the gain does
not drift with temperature (absolute tolerance does not matter - the ratio is
calibrated); dissipation is a few mW. Enclosure: grounded metal box, BNC in, short leads
to the module's input connector, divider ground at the output connector.

If the module input is about 50 Ohm and the termination cannot be removed, a passive
divider cannot be both high impedance and drive it (1 kOhm into 50 Ohm is already 21:1
and still only 1 kOhm at the T); use a buffer.

### Clocking

- Generate the ADC clock in the FPGA from the 100 MHz oscillator with an MMCM and run
  at **40-50 MS/s, not 65**. The signal does not need more, and the slower clock gives
  generous timing margin over Pmod wiring.
- Capture the data with a second MMCM output whose phase is adjustable; sweep it once
  with a known input, pick the middle of the stable window, and fix it in the build.
- The AD9226 has a fixed **pipeline latency** - 7 clocks per the datasheet (which also
  describes a nine-stage pipeline, so measure it). It shifts the ADC samples against
  anything timestamped digitally: correct for it as a constant, and verify it once with
  the same step on both the analog input and the timing-reference input.

### Wiring to the Arty A7

| Signals | Arty A7 port | Why |
| --- | --- | --- |
| ADC D0-D7 | Pmod **JB** pins 1-4, 7-10 | high-speed port: no series resistors |
| ADC D8-D11, OTR (overrange), ADC CLK out, 2 spare | Pmod **JC** pins 1-4, 7-10 | high-speed port |
| Timing reference in (S3 monitor out, GPIO36), optional opto trigger copy, optional debug trigger out | Pmod **JA** | standard port - its series resistors are fine for slow logic |

Pins 5/11 are GND and 6/12 are 3.3 V on every Pmod. Keep the data and clock wiring
short; a ribbon with a ground lead beside the clock is better than loose jumpers.
**Take the FPGA pin assignments from Digilent's Arty A7 master XDC** - not from this
note. The high-speed/standard split of JA-JD above is from memory (Digilent's A7
manual page would not load on 2026-10-19); check it against the manual or the XDC.

## Connection to the Faraday line

```
S&H amp ──coax──► BNC T ──────── long run ────────► LeCroy (control room)
                    │
                    └─ short stub (≤ 30 cm) ─► input board / AD9226 module (high-Z, DC)
                                                   │ Pmod JB, JC
                                               Arty A7 ── USB (FT2232HQ) ── elm-ioc-00
```

- **T at the source end, short stub.** At 20 MHz the wavelength in coax is around 10 m,
  so a 30 cm stub is invisible.
- **No terminator at the T**, and none on the module (item 1 above).
- **Acceptance test before trusting either reading:** the LeCroy's 5 us value must be
  unchanged with the T in place and the digitizer connected, **powered and
  unpowered**.
- **Grounds.** The module's input ground ties the coax shield to the Arty and, through
  USB, to the Pi, the cameras and the stepper-driver returns. The TMC drivers keep
  chopping at standstill, so **measure the baseline noise with the motors energised and
  off**. If it matters, an isolated supply for the drivers comes first; a differential
  input stage on the input board is the next step.
- **Radiation.** The Arty is an SRAM-based FPGA, so a neutron upset can corrupt its
  configuration. Keep it beside the Pi, outside the vault as the positioner note
  already requires for controllers, and enable the 7-series configuration CRC check
  (or the soft-error-mitigation core) so an upset is detected and reported rather than
  silently producing wrong data.

## Timing reference

The S3 monitor output (GPIO36, mirroring the camera shutter gate) goes to a **digital
input on the Arty** rather than a second analog channel. The FPGA timestamps its edge
on the same sample clock as the Faraday edge, which gives:

1. **One-to-one pairing** of every Faraday record with its DoseCam frame and DDG shot.
2. **A per-shot check of the 200 us delay**, to within one sample clock.
3. **A missed-shot count that does not depend on the readout**: the FPGA counts
   timing-reference edges and Faraday triggers independently of whether a record made
   it to the Pi.

## FPGA design

```
100 MHz ─► MMCM ─► ADC clock (50 MHz) ──────────────► AD9226
                 └► capture clock (phase-tuned) ◄─── D0-D11, OTR
                          │
                 circular history in BRAM (e.g. 32 Ki samples = 655 us)
                          │
  trigger: falling crossing of a level, hysteresis, holdoff   ◄── registers
  64-bit sample-clock timestamp, shot sequence number
  timing-ref edge timestamps                                  ◄── Pmod JA
                          │
  per-shot record builder (full-rate edge region + boxcar tail) ─► record FIFO (double-buffered)
                          │
                       UART TX ─► FT2232HQ ─► USB ─► Pi
  UART RX ◄── simple register writes: level, hysteresis, holdoff, window lengths,
              decimation factor, record on/off, full-capture diagnostic mode
```

- **Zero dead time.** The history buffer never stops filling; a trigger only marks
  where to cut. The next shot can trigger while the previous record is still being
  sent.
- If records are produced faster than the link drains them, the oldest pending record
  is dropped **and counted** - the sequence numbers and the FPGA's own trigger counter
  both show the gap. Never a silent loss.
- Overrange (OTR) is carried in the record header so a clipped shot is flagged.
- Keep the FPGA deliberately simple: no fitting, no thresholds beyond the trigger. All
  analysis is on the Pi, where it can change without a rebuild.

### Per-shot record

| Part | Content | Size at 50 MS/s |
| --- | --- | --- |
| Header | sync word, sequence number, trigger timestamp, timing-ref edge timestamp(s), trigger counter, flags (OTR, dropped-before-this) | ~32 B |
| Baseline + edge | full rate, about -20 us to +10 us | 1500 samples, 3 KB |
| Tail | boxcar-averaged (e.g. x16 -> 3.1 MS/s) out to about 3 tau | ~600 samples, 1.2 KB |

About **5 KB a shot**. A diagnostic mode sends the whole history window instead, for
the pole-zero investigation.

### Link

FT2232H UART rates that divide exactly are 3, 6 and 12 Mbaud; derive the UART clock
from the MMCM so the chosen rate is exact.

| Rate | Data | Needs | Choose |
| --- | --- | --- | --- |
| 15 Hz | 75 KB/s | ~0.8 Mbaud | 3 Mbaud, 4x margin |
| 100 Hz | 500 KB/s | ~5 Mbaud | 12 Mbaud, 2x margin |

Prove the chosen rate end to end on the Pi with a loopback pattern before trusting it.

## Per-shot processing: fit the decay, evaluate it at the pickoff

The signal after the noisy rise is an exponential decay, so the right estimator is a
**model fit to the clean tail, evaluated at exactly trigger + 5 us** - not a single
sample, and not a window average (which would be biased by the curvature). Every
sample on the tail contributes, so the amplitude noise falls roughly as
1/sqrt(samples in the fit window) instead of being one sample's noise.

**Near-time and offline are separate (operator, 2026-10-19).** The fit does not have
to be live. What runs per shot is a near-time indication; the definitive numbers come
from offline analysis of the saved waveforms, at leisure.

| | Near-time (per shot, seconds behind) | Offline (at leisure) |
| --- | --- | --- |
| Purpose | Faraday tab display, run-record preview, and the sequencer's checks: missed shot, delay out of tolerance, per-pulse outlier against the running median | The reported amplitudes |
| Method | the fixed-tau linear fit below, or even a short window mean at 5 us - whichever is cheap and stable | free-tau fits, careful t0, the pole-zero investigation, re-runs with improved settings |
| Feeds | `FLASH:FC:*` PVs, abort decisions | the analysis CSV beside the run, like the DoseCam `analysis_*` outputs |

Consequence: **every shot's raw waveform is saved**, not just its result, so the
offline analysis can be redone any time. The FPGA already sends exactly the useful part
(see "Per-shot record"): the full-rate edge region plus a boxcar-averaged tail, about
5 KB a shot - 75 KB/s at 15 Hz, 500 KB/s at 100 Hz, small beside DoseCam's 3.2 MB raw
frames. Keep a switch to save full captures for diagnostic runs (the
pole-zero investigation will want them). Store per burst - one file per target's burst -
with the sample rate, decimation, range, calibration and near-time t0 in the metadata.
The run record carries the near-time value and gains the offline value when the
analysis has been run.

Model, absolute time, negative-going signal:

    V(t) = B + C * exp(-(t - t0) / tau)          for t >= t0 + t_settle

    amplitude at pickoff  =  V(t0 + 5 us) - B  =  C * exp(-5 us / tau)

| Step | Default | Notes |
| --- | --- | --- |
| Trigger | falling crossing of a set level, hysteresis, 5 ms holdoff | holdoff under the 10 ms period at 100 Hz |
| Trigger time t0 | linear interpolation of the threshold crossing between the two straddling samples, on a lightly smoothed copy of the rise | target about half a sample or better; the rise is noisy, so smooth before interpolating, and use the same filter every shot so any fixed bias is common to all shots and calibrates out |
| Baseline B | mean over -20 to -1 us | from before the edge; fixed in the fit |
| Settle point t_settle | measured once from data | first time after the edge where residuals of the exponential fit stop showing the rise noise; stored as a setting |
| Fit window | t0 + t_settle to t0 + about 3 tau | |
| Fit, per shot | **tau fixed**, C free -> linear least squares, closed form | no iteration, no convergence failures, deterministic at 100 Hz |
| Fit, diagnostic | tau free (non-linear) on every Nth shot or in a calibration batch | tracks tau drift; the per-shot fixed tau is the median of recent free fits |
| Quality | residual RMS, reduced chi-squared, fitted tau vs the fixed value | flag the shot, never drop it silently |
| Delay check | FC t0 to the timing-reference edge | per shot; both are timestamped by the FPGA on the same sample clock |

Per shot, keep: timestamp, t0, amplitude at pickoff, C, tau used, B, fit residual,
window, delay, and a short decimated waveform.

### How the trigger-time error enters

The pickoff is defined relative to t0, so an error dt in t0 becomes an amplitude error
through the slope of the decay: **relative error = dt / tau**. That makes tau, which
we do not know yet, the number that decides how fine the sampling has to be:

| tau | half-sample at 50 MS/s (10 ns) | half-sample at 5 MS/s (100 ns) |
| --- | --- | --- |
| 10 us | 0.1 % | 1 % |
| 50 us | 0.02 % | 0.2 % |
| 200 us | 0.005 % | 0.05 % |

The FPGA records the edge at the full sample rate, so the left column applies. Only a
tau of a few microseconds would make the sample rate matter; measure tau on the LeCroy
to confirm, and it also sets how far the decimated tail has to run.

### Offset versus jitter in t0 (2026-10-19)

Only the shot-to-shot **scatter** in t0 costs accuracy: sigma_A / A = sigma_t / tau. A
constant offset in t0 - from the edge filter, the threshold level, the ADC pipeline
latency - multiplies every shot by the same exp(-offset / tau), and the gain
calibration absorbs it. The scatter of an analog-edge t0 is set by the noise on the rise
divided by the edge slope, not by the sample period, because the crossing is
interpolated.

Because the capture also records the laser-charge trigger and the DDG gate as
sample-exact digital edges, there is a second way to define t0: a fixed delay after the
digital trigger, which carries the accelerator's timing jitter instead of the analog
edge noise. Each shot gives both, so their difference across many shots measures the
beam-arrival jitter directly. Use whichever has the smaller scatter; with tau of 10 us
or more and scatter of tens of nanoseconds, either is at the 0.1 % level or better, and
the operator's expectation (2026-10-19) is that it will not matter much.

### Open: pole-zero

Expected to be unnecessary - even at 100 Hz the 10 ms period should be many decay
times - but to investigate once the system is running:

- Confirm the tail returns fully to baseline before the next pulse.
- Look for **undershoot** below baseline after the decay; that is the signature of an
  uncompensated pole-zero (an AC-coupling or shaping time constant in the chain).
- Check the pre-trigger baseline window is not sitting on a previous shot's residual
  tail. Per-shot baseline subtraction would partly hide that, so fit a slope across
  the baseline window as well and alarm if it is non-zero.

## Where it sits in the architecture

A third device server, consistent with the roadmap's one-server-per-hardware rule:
`fc-digitizer` owns the Arty's serial port, parses records, computes the near-time
value, saves the raw records per burst, exposes `GET /fc/latest`, `POST /fc/config` and
a WebSocket stream, and the sequencer consumes it.

- **EPICS** (caproto, as in roadmap phase 2): `FLASH:FC:AMP`, `FLASH:FC:BASE`,
  `FLASH:FC:FLAT`, `FLASH:FC:DELAY`, `FLASH:FC:RATE`, `FLASH:FC:MISSED`.
- **Sequencer run record**: one column set per pulse, beside the DoseCam fit. Faraday
  charge per pulse is a second, independent dose-rate proxy, which makes the "dose
  outlier against the running median" self-abort far more trustworthy than DoseCam
  alone.
- **Shell**: a Faraday panel with the last waveform, the pickoff window marked, and a
  rolling amplitude trend.

**Open question that affects the sequencer**: where the cup sits relative to the
samples. If it intercepts the beam, it cannot read while a sample is being irradiated
and is a between-target monitor; if it reads beam that passes or is split off, it
normalises every pulse.

## Cheaper option: Raspberry Pi Pico 2 instead of an FPGA (proposed 2026-10-19)

**Operator, 2026-10-19: will try the Pico 2** (plain Pico 2, not the Pico 2 W - no
wireless needed). **Three ordered from PiShop US on 2026-10-19.** The Arty A7 design
above stays as the fallback.

Asked: is there something better than the Arty A7 for far less? Recommended answer:
**a Raspberry Pi Pico 2 (RP2350), $5** - not an FPGA, but its PIO state machines do the
one thing the FPGA was there for, and the rest of the job is easier on it.

| Board | Price (2026-10-19) | Capture | Link to the Pi | Tools |
| --- | --- | --- | --- | --- |
| **Raspberry Pi Pico 2** (RP2350) | **$5** | PIO + DMA into a ring in 520 KB SRAM | native USB 1.1 (CDC) | Pico SDK (C) or the Arduino-Pico core |
| iCEBreaker (iCE40UP5K) | $79.95 | FPGA | on-board USB bridge (FT2232H, from memory) | open-source yosys / nextpnr |
| Digilent Cmod A7-35T | $107 | FPGA - the Arty design almost unchanged | on-board USB-UART | Vivado |
| Digilent Arty A7-100T | $322 | FPGA | FT2232HQ | Vivado |

### Why the Pico 2 fits

- **The trigger can be digital.** The laser-charge pulse that triggers the DDG arrives
  about 200 us *before* the beam - that is why the DoseCam delay is 200 us. Tee that
  opto output to the Pico as well, and the capture is armed by a clean logic edge with
  the Faraday pulse expected 200-300 us later. No analog-level hardware trigger is
  needed; software finds the Faraday edge inside a short, known window.
- **Timing references ride inside every sample.** PIO reads 16 consecutive pins per
  sample: D0-D11, OTR, the opto trigger, the DDG gate (S3 monitor) and a spare. The
  trigger and gate edges are therefore located to the exact sample with no separate
  timestamping logic, and the per-shot 200 us delay check falls out for free.
- **PIO also makes the ADC clock** (side-set) in the same program that reads the data,
  so capture is synchronous and the sampling phase is a fixed, tunable number of
  system-clock cycles.
- **Rate:** at the stock 150 MHz, 4 cycles per sample gives **37.5 MS/s** with a 50 %
  duty clock (3 cycles gives 50 MS/s but a 6.7 ns half-period - check it against the
  AD9226's clock-pulse-width spec first). At 37.5 MS/s a half-sample is 13 ns: 0.13 %
  at tau = 10 us, 0.03 % at 50 us.
- **Memory:** a 256 KB DMA ring holds about 3.5 ms at 37.5 MS/s - many shots' worth of
  history. DMA traffic is 75 MB/s, well inside the RP2350's bus.
- **CPU:** per shot, the Cortex-M33 locates the trigger, scans roughly 30 k samples for
  the Faraday edge, builds the ~5 KB record (full-rate edge region + boxcar tail) and
  sends it - a millisecond or two of a 10 ms period even at 100 Hz.
- **Link:** USB 1.1 CDC realistically carries about 1 MB/s; 100 Hz x 5 KB is 0.5 MB/s,
  15 Hz is 75 KB/s. No FTDI chip, no baud-rate arithmetic.
- **Radiation:** an upset crashes or resets a microcontroller (watchdog, and the record
  sequence numbers show the gap) rather than silently reconfiguring logic as it can in
  an SRAM FPGA.
- **Spares cost nothing**, and the firmware is C in the same style as the ESP32 work.

### Costs and checks

- **The logic-level check still applies** (DRVDD at 3.3 V). Do not rely on RP2350 pin
  tolerance to 5 V without confirming it in Raspberry Pi's datasheet.
- **Sampling phase** must be tuned on the bench, exactly as for the FPGA.
- **Tee the opto output** at the opto board: it is an open-collector output pulled up by
  the S3's `INPUT_PULLUP`; enable the Pico's pull-up on that pin too, so it stays
  defined if the S3 is unpowered.
- A software-only "analog trigger" mode, for commissioning without the laser-charge
  pulse, is possible but slower; the digital trigger is the normal path.

### Pico 2 pin map (proposed)

| GPIO | Signal |
| --- | --- |
| GP0-GP11 | AD9226 D0-D11 |
| GP12 | OTR |
| GP13 | Opto trigger (laser charge), tee from the opto board, pull-up on |
| GP14 | DDG gate (S3 monitor out, GPIO36) |
| GP15 | spare (completes the 16-bit read) |
| GP16 | AD9226 CLK out (PIO side-set) |

GP0-GP15 are contiguous on the Pico 2 header, which is what a single 16-pin PIO read
needs.

## Alternatives considered

- **Analog Discovery 2** (the plan earlier on 2026-10-19). Works without building
  anything, but its readout is a USB round trip per shot with an unpublished streaming
  rate, and it ties up a general-purpose instrument. The benchmark written for it
  (`fc_digitizer/tools/ad2_trigger_rate_bench.py`) never ran - the AD2 was not
  enumerated on either test host - and is superseded.
- **Arty Z7** with the same HDL: the right choice only if the digitizer must stand
  alone on the network.
- **XADC instead of an external ADC** (1 MS/s, 12-bit, either Arty): enough for a held
  level, but too slow to place the edge well on this signal.
- **Red Pitaya STEMlab 125-14**: networked standalone alternative, not priced here.

## Next steps

Off-site:

1. On arrival, run the four module checks above **before** connecting it to the Arty;
   then build the attenuator.
2. HDL: clocking and capture first, then the history buffer and trigger, then the
   record builder and UART. Simulate the trigger and record builder against a
   synthetic waveform (noisy negative step + exponential decay at a known amplitude
   and tau) before hardware.
3. Bench: drive the module from a function generator (the operator's AD3 or AD2 W1
   playing the synthetic pulse); tune the capture phase; measure the pipeline latency
   with a step on both inputs; prove 3 and 12 Mbaud end to end; run at 15 and 100 Hz
   and confirm zero missed shots.
4. Pi side: the `fc-digitizer` service - record parser, near-time value, per-burst
   storage, offline fit tool.

On site:

5. Capture the waveform on the LeCroy - pre-edge baseline, where the rise noise
   settles, and **tau** - then insert the T and run the acceptance test.

