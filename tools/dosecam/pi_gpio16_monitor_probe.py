#!/usr/bin/env python3
"""Observe the ESP8266 GPIO15 monitor signal on Raspberry Pi GPIO16."""

import argparse
import threading
import time

from gpiozero import DigitalInputDevice


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    monitor = DigitalInputDevice(16, pull_up=False, bounce_time=None)
    lock = threading.Lock()
    transitions = []
    pulse_start = None
    completed = threading.Event()

    def record(level):
        nonlocal pulse_start
        now_ns = time.monotonic_ns()
        with lock:
            transitions.append((level, now_ns))
            if level:
                pulse_start = now_ns
            elif pulse_start is not None:
                completed.set()

    monitor.when_activated = lambda: record(1)
    monitor.when_deactivated = lambda: record(0)
    try:
        print(
            f"MONITOR_READY gpio=16 initial_level={int(monitor.value)} timeout_s={args.timeout}",
            flush=True,
        )
        completed.wait(args.timeout)
        with lock:
            captured = list(transitions)
        rising = next((stamp for level, stamp in captured if level == 1), None)
        falling = next(
            (stamp for level, stamp in captured if level == 0 and rising is not None and stamp > rising),
            None,
        )
        if rising is None or falling is None:
            print(f"MONITOR_FAIL transitions={[(level) for level, _ in captured]}", flush=True)
            return 2
        width_us = (falling - rising) / 1000.0
        print(
            f"MONITOR_PASS rising_edges=1 falling_edges=1 measured_high_us={width_us:.1f}",
            flush=True,
        )
        return 0
    finally:
        monitor.close()


if __name__ == "__main__":
    raise SystemExit(main())
