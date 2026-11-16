"""Decode rpicam-raw R16 unpacked IMX296 streams (1456x1088, stride 2944 B, 10-bit left-aligned).

Set DOSECAM_CAPTURES to the folder that holds the 2026-10-13 captures
(e.g. the off-Pi copy FLASH/SynchronizedCameraDosimeter/captures_backup_20261013/).
Frames are returned in sensor orientation; callers rotate 180 deg to match the UI / fit CSV.
"""
import os
import numpy as np

D = os.environ.get("DOSECAM_CAPTURES", ".").rstrip("/") + "/"

def load(name):
    a = np.fromfile(D + name, dtype="<u2")
    n = a.size // (1088 * 1472)
    a = a[: n * 1088 * 1472].reshape(n, 1088, 1472)[:, :, :1456]
    return (a >> 6).astype(np.float64)
