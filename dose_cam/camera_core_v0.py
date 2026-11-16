from gpiozero import LED  # keep for future trigger HW, not used yet
import io
import time
import numpy as np
from picamera2 import Picamera2
from libcamera import Transform
import tifffile as tiff
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WIDTH, HEIGHT = 1456, 1088       # IMX296 full frame
COLORMAP = "viridis"             # color scale for preview


class FrameStore:
    """Holds latest frame in RAM-only."""
    def __init__(self):
        self.raw16 = None  # np.uint16, 0..1023 DN
        self.png = None    # bytes (preview with legend)
        self.tiff = None   # bytes (16-bit TIFF)
        self.raw10 = None  # bytes (MIPI RAW10 packed)


def _to_dn10(raw16):
    """
    Ensure data is in 10-bit DN space (0..1023).
    Some pipelines left-shift the 10-bit value into 16 bits (0..65535 step 64).
    Detect that and shift down.
    """
    raw16 = raw16.astype(np.uint16, copy=False)
    mx = int(raw16.max())
    # Heuristic: if max > 4095, assume it's left-shifted by 6 bits.
    if mx > 4095:
        return (raw16 >> 6).astype(np.uint16)
    return raw16


def _pack_raw10(arr16):
    """
    Pack uint16 image (0..1023) into MIPI RAW10: 5 bytes per 4 pixels.
    """
    h, w = arr16.shape
    if w % 4:
        pad = 4 - (w % 4)
        arr16 = np.pad(arr16, ((0, 0), (0, pad)), mode="constant")
        h, w = arr16.shape
    p = (arr16 & 0x3FF).astype(np.uint16).reshape(h, w // 4, 4)
    b0 = (p[:, :, 0] & 0xFF).astype(np.uint8)
    b1 = (p[:, :, 1] & 0xFF).astype(np.uint8)
    b2 = (p[:, :, 2] & 0xFF).astype(np.uint8)
    b3 = (p[:, :, 3] & 0xFF).astype(np.uint8)
    b4 = ((p[:, :, 0] >> 8) |
          ((p[:, :, 1] >> 8) << 2) |
          ((p[:, :, 2] >> 8) << 4) |
          ((p[:, :, 3] >> 8) << 6)).astype(np.uint8)
    packed = np.stack([b0, b1, b2, b3, b4], axis=-1).reshape(h, (w // 4) * 5)
    return packed.tobytes()


def _preview_png(raw_dn):
    """
    Make a PNG preview with colorbar showing actual DN values,
    scaled between percentile-clipped min/max.
    """
    # robust clip: ignore extreme outliers
    lo, hi = np.percentile(raw_dn, 1.0), np.percentile(raw_dn, 99.0)
    if hi <= lo:
        lo, hi = int(raw_dn.min()), int(raw_dn.max())
    lo_i, hi_i = int(round(lo)), int(round(hi))

    imgf = np.clip((raw_dn.astype(np.float32) - lo) / max(1.0, (hi - lo)), 0.0, 1.0)

    fig, ax = plt.subplots(figsize=(6, 4))
    im = ax.imshow(imgf, cmap=COLORMAP, origin="upper")
    ax.set_axis_off()

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Sensor code (DN)", rotation=270, labelpad=15)

    ticks = [0.0, 0.25, 0.5, 0.75, 1.0]
    cbar.set_ticks(ticks)
    cbar.set_ticklabels([
        f"{int(lo_i + t * (hi_i - lo_i))}" for t in ticks
    ])

    ax.set_title(f"Scaled between {lo_i}–{hi_i} DN", fontsize=9, color="#333", pad=6)

    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _tiff_bytes(raw_dn):
    buf = io.BytesIO()
    tiff.imwrite(buf, raw_dn, photometric="minisblack")
    buf.seek(0)
    return buf.read()


class CameraCore:
    def __init__(self):
        self.picam2 = Picamera2()
        cfg = self.picam2.create_still_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
            raw={"size": (WIDTH, HEIGHT), "format": "R16"},  # 16-bit mono from PiSP
            transform=Transform()
        )
        self.picam2.configure(cfg)

        # Enable external trigger mode
        try:
            self.picam2.set_controls({"SyncMode": 1})
            self.picam2.set_controls({"FrameDurationLimits": (30000, 30000)})
            print("External trigger mode enabled (SyncMode=1).")
        except Exception as e:
            print("Warning: Could not enable SyncMode=1:", e)

        self.picam2.start()
        time.sleep(0.2)

        # GPIO trigger line reserved for future use (GPIO21)
        self.trig_gpio = LED(21)
        self.trig_gpio.off()

        self.store = FrameStore()
        self.allow_disk_writes = False  # can be toggled by the app

    def trigger_esp(self, width_us=100):
        """Send a short pulse to the ESP8266 input (GPIO21)."""
        self.pi_trigger.on()
        time.sleep(width_us / 1_000_000.0)
        self.pi_trigger.off()

    def capture(self, exposure_us: int | None):
        """
        Simple internal-trigger capture: set exposure, grab one RAW frame.
        External trigger not yet active.
        """
        if exposure_us:
            try:
                self.picam2.set_controls({"ExposureTime": int(exposure_us)})
            except Exception:
                # ignore if control is not supported / locked
                pass

        raw = self.picam2.capture_array("raw")

        raw_dn = _to_dn10(raw)
        raw_dn = np.clip(raw_dn, 0, 1023).astype(np.uint16)
        self.store.raw16 = raw_dn
        self.store.png = _preview_png(raw_dn)
        self.store.tiff = _tiff_bytes(raw_dn)
        self.store.raw10 = _pack_raw10(raw_dn)
        return raw_dn.shape

    def download(self, fmt: str) -> bytes | None:
        if self.store.raw16 is None:
            return None
        mapping = {
            "png": self.store.png,
            "tiff": self.store.tiff,
            "raw10": self.store.raw10,
        }
        return mapping.get(fmt)

    def save_to_disk(self, base: str) -> list[str]:
        """
        Optional disk save; no-op if allow_disk_writes is False or no frame.
        """
        if not self.allow_disk_writes or self.store.raw16 is None:
            return []
        import os
        os.makedirs("captures", exist_ok=True)
        out = []
        for fn, data in [
            (base + ".raw10", self.store.raw10),
            (base + ".tiff", self.store.tiff),
            (base + "_preview.png", self.store.png),
        ]:
            path = os.path.join("captures", fn)
            with open(path, "wb") as f:
                f.write(data)
            out.append(path)
        return out
