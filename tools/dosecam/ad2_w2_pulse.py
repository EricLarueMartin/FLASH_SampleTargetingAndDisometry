#!/usr/bin/env python3
"""Generate one guarded positive pulse on an Analog Discovery 2 wavegen output."""

import argparse
from ctypes import byref, c_bool, c_double, c_int, cdll, create_string_buffer
import os
import sys
import time


DEFAULT_SDK = r"C:\Program Files (x86)\Digilent\WaveFormsSDK\samples\py"
DEFAULT_DLL = r"C:\Program Files (x86)\Digilent\WaveForms3\dwf.dll"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", type=int, default=2, choices=(1, 2))
    parser.add_argument("--volts", type=float, default=5.0)
    parser.add_argument("--width-us", type=float, default=100.0)
    args = parser.parse_args()
    if args.volts <= 0 or args.width_us <= 0:
        parser.error("volts and width-us must be positive")

    sdk_path = os.environ.get("DIGILENT_WAVEFORMS_PY", DEFAULT_SDK)
    dll_path = os.environ.get("DIGILENT_DWF_DLL", DEFAULT_DLL)
    sys.path.insert(0, sdk_path)
    from dwfconstants import (  # pylint: disable=import-error,import-outside-toplevel
        AnalogOutNodeCarrier,
        DwfAnalogOutIdleOffset,
        funcSquare,
    )

    dwf = cdll.LoadLibrary(dll_path)
    handle = c_int()
    channel = c_int(args.channel - 1)
    dwf.FDwfDeviceOpen(c_int(-1), byref(handle))
    if handle.value == 0:
        error = create_string_buffer(512)
        dwf.FDwfGetLastErrorMsg(error)
        raise RuntimeError(f"Could not open Analog Discovery: {error.value.decode()}")

    try:
        minimum = c_double()
        maximum = c_double()
        dwf.FDwfAnalogOutNodeAmplitudeInfo(
            handle,
            channel,
            AnalogOutNodeCarrier,
            byref(minimum),
            byref(maximum),
        )
        if args.volts > maximum.value:
            raise ValueError(
                f"Requested {args.volts:g} V exceeds W{args.channel} maximum "
                f"of {maximum.value:g} V"
            )

        dwf.FDwfDeviceAutoConfigureSet(handle, c_int(0))
        dwf.FDwfAnalogOutNodeEnableSet(
            handle, channel, AnalogOutNodeCarrier, c_bool(True)
        )
        dwf.FDwfAnalogOutIdleSet(handle, channel, DwfAnalogOutIdleOffset)
        dwf.FDwfAnalogOutNodeFunctionSet(
            handle, channel, AnalogOutNodeCarrier, funcSquare
        )
        dwf.FDwfAnalogOutNodeFrequencySet(
            handle, channel, AnalogOutNodeCarrier, c_double(0)
        )
        dwf.FDwfAnalogOutNodeAmplitudeSet(
            handle, channel, AnalogOutNodeCarrier, c_double(args.volts)
        )
        dwf.FDwfAnalogOutNodeOffsetSet(
            handle, channel, AnalogOutNodeCarrier, c_double(0)
        )
        dwf.FDwfAnalogOutRunSet(
            handle, channel, c_double(args.width_us / 1_000_000.0)
        )
        dwf.FDwfAnalogOutWaitSet(handle, channel, c_double(0))
        dwf.FDwfAnalogOutRepeatSet(handle, channel, c_int(1))
        if not dwf.FDwfAnalogOutConfigure(handle, channel, c_bool(True)):
            error = create_string_buffer(512)
            dwf.FDwfGetLastErrorMsg(error)
            raise RuntimeError(error.value.decode())

        applied = c_double()
        dwf.FDwfAnalogOutNodeAmplitudeGet(
            handle, channel, AnalogOutNodeCarrier, byref(applied)
        )
        print(
            f"Applied one W{args.channel} pulse: "
            f"configured={applied.value:.3f} V width={args.width_us:g} us"
        )
        time.sleep(max(0.1, args.width_us / 1_000_000.0 + 0.05))
    finally:
        dwf.FDwfAnalogOutConfigure(handle, channel, c_bool(False))
        dwf.FDwfDeviceClose(handle)


if __name__ == "__main__":
    main()
