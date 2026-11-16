#!/usr/bin/env python3
"""Analog Discovery 2: sustained triggered-capture rate benchmark.

Question answered: can a Pi read out one triggered capture per beam pulse at the
FLASH Faraday-cup rate (target 15 Hz, design ceiling 100 Hz) without missing pulses?

Bench wiring (operator, 2026-10-19): W2 -> CH2.

W2 plays a synthetic Faraday-cup pulse at the requested rate: a noisy negative
step followed by an exponential decay back to baseline. CH2 hardware-triggers on
its falling edge, one buffer per pulse is read out, and the device's own trigger
timestamps reveal any pulse that was not captured.

Pure Python + ctypes against Digilent's libdwf (WaveForms runtime). No numpy.
Exits 0 when every rate tested had zero missed pulses, 1 otherwise, 2 on setup error.

Example:
    python3 ad2_trigger_rate_bench.py --rates 15 30 60 100 --seconds 30
"""
import argparse
import ctypes
import math
import random
import sys
import time
from ctypes import byref, c_double, c_int, c_ubyte, c_uint, create_string_buffer

# ---- libdwf constants (dwf.h) -------------------------------------------------
DwfStateDone = 2
trigsrcDetectorAnalogIn = 2
trigtypeEdge = 0
DwfTriggerSlopeFall = 1
acqmodeSingle = 0
acqmodeSingle1 = 5
funcCustom = 30
AnalogOutNodeCarrier = 0


def load_dwf():
    for name in ("libdwf.so", "libdwf.so.3", "/usr/lib/libdwf.so", "/usr/lib/aarch64-linux-gnu/libdwf.so"):
        try:
            return ctypes.cdll.LoadLibrary(name)
        except OSError:
            continue
    sys.exit("libdwf not found - install the Digilent Adept Runtime and WaveForms packages first")


dwf = load_dwf()


def check(ok, what):
    if not ok:
        msg = create_string_buffer(512)
        dwf.FDwfGetLastErrorMsg(msg)
        raise RuntimeError(f"{what} failed: {msg.value.decode(errors='replace').strip()}")


def synthetic_pulse(n, window_s, rise_s, tau_s, noise):
    """Normalised samples (-1..1) for one W2 period window: baseline 0, a noisy
    negative step at 10 % of the window, exponential decay with tau."""
    rnd = random.Random(1)
    t_edge = 0.1 * window_s
    out = []
    for i in range(n):
        t = i * window_s / n
        if t < t_edge:
            v = 0.0
        else:
            dt = t - t_edge
            v = -math.exp(-dt / tau_s)
            if dt < rise_s:
                v += noise * (rnd.random() - 0.5)
        out.append(max(-1.0, min(1.0, v)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rates", type=float, nargs="+", default=[15.0, 30.0, 60.0, 100.0])
    ap.add_argument("--seconds", type=float, default=30.0, help="duration per rate")
    ap.add_argument("--fs", type=float, default=100e6, help="capture sample rate, Hz")
    ap.add_argument("--samples", type=int, default=0, help="capture buffer per shot; 0 = device maximum")
    ap.add_argument("--pretrig-us", type=float, default=20.0)
    ap.add_argument("--amplitude", type=float, default=1.0, help="synthetic pulse amplitude, V")
    ap.add_argument("--tau-us", type=float, default=30.0, help="synthetic decay constant")
    ap.add_argument("--wgen-ch", type=int, default=1, help="0 = W1, 1 = W2")
    ap.add_argument("--scope-ch", type=int, default=1, help="0 = CH1, 1 = CH2")
    ap.add_argument("--config", type=int, default=-1, help="device configuration index (FDwfDeviceConfigOpen); -1 = default")
    ap.add_argument("--mode", choices=["single", "single1"], default="single")
    args = ap.parse_args()

    ver = create_string_buffer(32)
    dwf.FDwfGetVersion(ver)
    print(f"libdwf {ver.value.decode()}", flush=True)

    hdwf = c_int()
    if args.config >= 0:
        check(dwf.FDwfDeviceConfigOpen(c_int(-1), c_int(args.config), byref(hdwf)), "FDwfDeviceConfigOpen")
    else:
        check(dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf)), "FDwfDeviceOpen")
    dwf.FDwfDeviceAutoConfigureSet(hdwf, c_int(0))

    worst_missed = 0
    try:
        bmin, bmax = c_int(), c_int()
        dwf.FDwfAnalogInBufferSizeInfo(hdwf, byref(bmin), byref(bmax))
        nbuf = args.samples or bmax.value
        nbuf = max(bmin.value, min(bmax.value, nbuf))
        span = nbuf / args.fs
        print(f"capture: {nbuf} samples at {args.fs/1e6:g} MS/s = {span*1e6:.1f} us per shot "
              f"(device buffer {bmin.value}..{bmax.value})", flush=True)

        # ---- scope: CH2 hardware falling-edge trigger, one buffer per shot ----
        ch = c_int(args.scope_ch)
        dwf.FDwfAnalogInChannelEnableSet(hdwf, c_int(-1), c_int(0))
        dwf.FDwfAnalogInChannelEnableSet(hdwf, ch, c_int(1))
        dwf.FDwfAnalogInChannelRangeSet(hdwf, ch, c_double(5.0))
        dwf.FDwfAnalogInChannelOffsetSet(hdwf, ch, c_double(0.0))
        dwf.FDwfAnalogInFrequencySet(hdwf, c_double(args.fs))
        dwf.FDwfAnalogInBufferSizeSet(hdwf, c_int(nbuf))
        dwf.FDwfAnalogInAcquisitionModeSet(hdwf, c_int(acqmodeSingle1 if args.mode == "single1" else acqmodeSingle))
        dwf.FDwfAnalogInTriggerAutoTimeoutSet(hdwf, c_double(0))          # never auto-trigger
        dwf.FDwfAnalogInTriggerSourceSet(hdwf, c_ubyte(trigsrcDetectorAnalogIn))
        dwf.FDwfAnalogInTriggerTypeSet(hdwf, c_int(trigtypeEdge))
        dwf.FDwfAnalogInTriggerChannelSet(hdwf, ch)
        dwf.FDwfAnalogInTriggerLevelSet(hdwf, c_double(-0.5 * args.amplitude))
        dwf.FDwfAnalogInTriggerHysteresisSet(hdwf, c_double(0.05 * args.amplitude))
        dwf.FDwfAnalogInTriggerConditionSet(hdwf, c_int(DwfTriggerSlopeFall))
        # 0 = trigger at buffer centre; positive moves it earlier, leaving more post-trigger data.
        dwf.FDwfAnalogInTriggerPositionSet(hdwf, c_double(span / 2 - args.pretrig_us * 1e-6))
        check(dwf.FDwfAnalogInConfigure(hdwf, c_int(1), c_int(0)), "FDwfAnalogInConfigure")

        buf = (c_double * nbuf)()
        sts = c_ubyte()
        sec, tick, tps = c_uint(), c_uint(), c_uint()
        i_pre = int(args.pretrig_us * 1e-6 * args.fs)

        for rate in args.rates:
            # ---- W2: synthetic pulse, one per period, via run/wait/repeat ----
            window = min(0.5 / rate, 10 * args.tau_us * 1e-6 + 50e-6)
            wch = c_int(args.wgen_ch)
            amin, amax = c_int(), c_int()
            dwf.FDwfAnalogOutNodeDataInfo(hdwf, wch, c_int(AnalogOutNodeCarrier), byref(amin), byref(amax))
            nawg = max(amin.value, min(4096, amax.value or 4096))
            data = (c_double * nawg)(*synthetic_pulse(nawg, window, 2e-6, args.tau_us * 1e-6, 0.2))
            dwf.FDwfAnalogOutNodeEnableSet(hdwf, wch, c_int(AnalogOutNodeCarrier), c_int(1))
            dwf.FDwfAnalogOutNodeFunctionSet(hdwf, wch, c_int(AnalogOutNodeCarrier), c_ubyte(funcCustom))
            dwf.FDwfAnalogOutNodeDataSet(hdwf, wch, c_int(AnalogOutNodeCarrier), data, c_int(nawg))
            dwf.FDwfAnalogOutNodeFrequencySet(hdwf, wch, c_int(AnalogOutNodeCarrier), c_double(1.0 / window))
            dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, wch, c_int(AnalogOutNodeCarrier), c_double(args.amplitude))
            dwf.FDwfAnalogOutNodeOffsetSet(hdwf, wch, c_int(AnalogOutNodeCarrier), c_double(0.0))
            dwf.FDwfAnalogOutRunSet(hdwf, wch, c_double(window))
            dwf.FDwfAnalogOutWaitSet(hdwf, wch, c_double(1.0 / rate - window))
            dwf.FDwfAnalogOutRepeatSet(hdwf, wch, c_int(0))
            check(dwf.FDwfAnalogOutConfigure(hdwf, wch, c_int(1)), "FDwfAnalogOutConfigure")
            time.sleep(0.2)

            period = 1.0 / rate
            shots, missed, gaps = 0, 0, 0
            lat = []
            last_t = None
            amp_sum = 0.0
            cpu0, wall0 = time.process_time(), time.monotonic()
            dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))          # arm
            t_end = wall0 + args.seconds
            while time.monotonic() < t_end:
                t_wait = time.monotonic()
                while True:
                    check(dwf.FDwfAnalogInStatus(hdwf, c_int(1), byref(sts)), "FDwfAnalogInStatus")
                    if sts.value == DwfStateDone:
                        break
                    if time.monotonic() - t_wait > 5 * period + 1:
                        raise RuntimeError(f"no trigger for {5*period+1:.1f} s - is W2 wired to CH2?")
                t_done = time.monotonic()
                dwf.FDwfAnalogInStatusTime(hdwf, byref(sec), byref(tick), byref(tps))
                dwf.FDwfAnalogInStatusData(hdwf, ch, buf, c_int(nbuf))
                if args.mode == "single":
                    dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))      # re-arm as early as possible
                # near-time value: baseline mean minus mean of a 1 us window at +5 us
                base = sum(buf[max(0, i_pre - 1500):i_pre - 100]) / max(1, len(buf[max(0, i_pre - 1500):i_pre - 100]))
                j = i_pre + int(5e-6 * args.fs)
                w = int(0.5e-6 * args.fs)
                pick = sum(buf[j - w:j + w]) / (2 * w)
                amp_sum += pick - base
                lat.append(time.monotonic() - t_done)
                t_trig = sec.value + tick.value / max(1, tps.value)
                if last_t is not None:
                    n = round((t_trig - last_t) / period)
                    if n > 1:
                        missed += n - 1
                        gaps += 1
                last_t = t_trig
                shots += 1
            wall = time.monotonic() - wall0
            cpu = time.process_time() - cpu0
            dwf.FDwfAnalogOutConfigure(hdwf, c_int(args.wgen_ch), c_int(0))
            lat.sort()
            p = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))] * 1e3 if lat else float("nan")
            expected = round(wall * rate)
            print(f"rate {rate:6.1f} Hz | captured {shots:6d} of ~{expected:6d} | missed {missed:5d} in {gaps:4d} gaps | "
                  f"readout+rearm ms p50 {p(0.5):.2f} p99 {p(0.99):.2f} max {p(1.0):.2f} | "
                  f"cpu {100*cpu/wall:5.1f}% | mean near-time amp {amp_sum/max(1,shots):+.3f} V", flush=True)
            worst_missed = max(worst_missed, missed)
    finally:
        dwf.FDwfAnalogOutReset(hdwf, c_int(-1))
        dwf.FDwfDeviceCloseAll()
    return 0 if worst_missed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
