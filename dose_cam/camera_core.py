from gpiozero import LED
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

PI_TRIGGER_GPIO = 26
TRIGGER_MODE_PATH = "/sys/module/imx296/parameters/trigger_mode"
WIDTH, HEIGHT = 1456, 1088
RAW_MODE = "1456:1088:10:U"
RAW_STRIDE_BYTES = 2944
RAW_FRAME_BYTES = RAW_STRIDE_BYTES * HEIGHT
RAW_BIT_DEPTH = int(RAW_MODE.split(":")[2])
RAW_MIN_DN = 0
RAW_MAX_DN = (1 << RAW_BIT_DEPTH) - 1
RAW_CONTAINER_SHIFT = max(0, 16 - RAW_BIT_DEPTH)
MIN_CAMERA_GATE_US = 30
RAM_SPOOL_DIR = "/dev/shm/dose_cam"
RAM_SPOOL_MIN_FREE_BYTES = 512 * 1024 * 1024
# Sensor DoseCam must use. On a Pi shared with the FLASH positioner camera (OV5647)
# every rpicam call names this camera explicitly. DOSECAM_CAMERA_INDEX overrides.
DOSECAM_CAMERA_MODEL = os.environ.get("DOSECAM_CAMERA_MODEL", "imx296").strip().lower()
DOSECAM_CAMERA_INDEX = os.environ.get("DOSECAM_CAMERA_INDEX", "").strip()
_CAMERA_LINE = re.compile(r"^\s*(\d+)\s*:\s*(\S+)")


def parse_camera_list(text):
    """[(index, model)] from `rpicam-hello --list-cameras` output."""
    cameras = []
    for line in text.splitlines():
        match = _CAMERA_LINE.match(line)
        if match:
            cameras.append((int(match.group(1)), match.group(2).lower()))
    return cameras


def select_camera_args(cameras, model=DOSECAM_CAMERA_MODEL):
    """rpicam arguments selecting `model` from [(index, model)].

    Returns [] when the only camera present is the right one (rpicam's default),
    so a single-camera Pi runs exactly as before. Raises if the model is missing,
    so a disconnected IMX296 can never make DoseCam capture from another camera.
    """
    for index, found in cameras:
        if found == model:
            return [] if len(cameras) == 1 else ["--camera", str(index)]
    listed = ", ".join(f"{i}:{m}" for i, m in cameras) or "none"
    raise RuntimeError(f"DoseCam camera {model} not detected (found {listed})")


class CameraCore:
    def __init__(self):
        self._camera_args_cache = None
        self.store = {}
        self.allow_disk_writes = True
        self.capture_dir = "captures"
        self.save_counter = 0
        self._capture_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._active_proc = None
        self._batch_lock = threading.Lock()
        self._batch_cancel_event = threading.Event()
        self._batch_proc = None
        self._batch_status = {
            "running": False,
            "ok": False,
            "message": "Idle",
            "frames_requested": 0,
            "frames_written": 0,
            "fps": 0,
            "files": [],
        }
        self._focus_stop_event = threading.Event()
        self._focus_proc = None
        self._focus_condition = threading.Condition()
        self._focus_frame = None
        self._focus_sequence = 0
        self._focus_status = {
            "running": False,
            "message": "Idle",
            "fps": 0,
            "width": 0,
            "height": 0,
            "frames": 0,
            "focus_score": None,
            "best_focus_score": None,
            "relative_focus_percent": None,
        }

    def _camera_args(self):
        """["--camera", N] for the DoseCam sensor, [] on a single-camera Pi."""
        if DOSECAM_CAMERA_INDEX:
            return ["--camera", DOSECAM_CAMERA_INDEX]
        if self._camera_args_cache is None:
            proc = subprocess.run(
                ["rpicam-hello", "--list-cameras"],
                capture_output=True, text=True, timeout=15,
            )
            self._camera_args_cache = select_camera_args(
                parse_camera_list(proc.stdout + "\n" + proc.stderr)
            )
        return list(self._camera_args_cache)

    @staticmethod
    def _picamera2_index(picamera2_cls):
        """Picamera2 camera number of the DoseCam sensor (by model, not by order)."""
        cameras = [
            (i, str(info.get("Model", "")).lower())
            for i, info in enumerate(picamera2_cls.global_camera_info())
        ]
        args = select_camera_args(cameras)
        return int(args[1]) if args else 0

    def _set_kernel_trigger_mode(self, enabled):
        value = "1" if enabled else "0"
        subprocess.run(
            ["sudo", "sh", "-c", f"echo {value} > {TRIGGER_MODE_PATH}"],
            check=True,
            timeout=5,
        )

    def trigger_esp(self, width_us=1000, count=1, interval_s=0.05):
        """Send a HIGH pulse from GPIO26 to ESP8266 GPIO12."""
        pi_trigger = LED(PI_TRIGGER_GPIO)
        try:
            for _ in range(count):
                pi_trigger.on()
                time.sleep(width_us / 1_000_000.0)
                pi_trigger.off()
                if count > 1:
                    time.sleep(interval_s)
        finally:
            pi_trigger.close()

    def _pulse_gpio26_pinctrl(self, width_s=0.001):
        subprocess.run(["pinctrl", "set", "26", "op", "dl"], check=True)
        time.sleep(0.001)
        subprocess.run(["pinctrl", "set", "26", "op", "dh"], check=True)
        time.sleep(width_s)
        subprocess.run(["pinctrl", "set", "26", "op", "dl"], check=True)

    def _restore_gpio26_input(self):
        subprocess.run(["pinctrl", "set", "26", "ip", "pd"], check=False)

    def send_test_trigger(self, width_us=1000):
        self._pulse_gpio26_pinctrl(max(float(width_us) / 1_000_000.0, 0.00001))
        self._restore_gpio26_input()
        return True

    def current_raw_frame_count(self):
        path = self._active_raw_path_from_status()
        if not path:
            return 0
        if not os.path.exists(path):
            return 0
        return os.path.getsize(path) // RAW_FRAME_BYTES

    def update_preview_from_latest_raw(self, min_frames=1, timeout_s=0.0, rotation_degrees=180):
        status = self.batch_status()
        raw_path = status.get("raw_path")
        path = self._active_raw_path_from_status(status)
        if not path:
            raise RuntimeError("No active or recent raw acquisition")
        deadline = time.monotonic() + float(timeout_s)
        frames = 0
        while True:
            if os.path.exists(path):
                frames = os.path.getsize(path) // RAW_FRAME_BYTES
            if frames >= int(min_frames):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("No complete raw frame is available yet")
            time.sleep(0.05)

        with open(path, "rb") as f:
            f.seek((frames - 1) * RAW_FRAME_BYTES)
            frame = f.read(RAW_FRAME_BYTES)
        if len(frame) != RAW_FRAME_BYTES:
            raise RuntimeError("Latest raw frame is incomplete")

        rotation_degrees = self._normalize_rotation(rotation_degrees)
        dn = self._decode_raw_stream_frame(frame)
        stats = self._frame_stats(dn)
        jpg = self._preview_jpeg(dn, rotation_degrees=rotation_degrees)
        self.store["jpg"] = jpg
        self.store["preview_mime"] = "image/jpeg"
        self.store["meta"] = {
            "format": "raw-stream-preview",
            "raw_path": raw_path,
            "frame_index": frames - 1,
            "frames_available": frames,
            "width": WIDTH,
            "height": HEIGHT,
            "preview_rotation_degrees": rotation_degrees,
            "stored_values": "display preview derived from rpicam-raw stream bytes",
            "frame_stats": stats,
        }
        return {
            "raw_path": raw_path,
            "frame_index": frames - 1,
            "frames_available": frames,
            "preview_rotation_degrees": rotation_degrees,
            "frame_stats": stats,
        }

    def send_test_trigger_and_update_preview(self, width_us=1000, timeout_s=3.0, rotation_degrees=180):
        target_frames = self.current_raw_frame_count() + 1
        self.send_test_trigger(width_us=width_us)
        return self.update_preview_from_latest_raw(
            min_frames=target_frames,
            timeout_s=timeout_s,
            rotation_degrees=rotation_degrees,
        )

    def _normalize_rotation(self, rotation_degrees):
        try:
            rotation = int(rotation_degrees)
        except (TypeError, ValueError):
            rotation = 180
        if rotation not in (0, 90, 180, 270):
            rotation = 180
        return rotation

    def _decode_raw_to_dn10(self, raw):
        import numpy as np

        if raw.dtype == np.uint8:
            if raw.shape[1] < WIDTH * 2:
                raise RuntimeError(f"Raw byte row is too short: {raw.shape}")
            decoded = raw[:, : (raw.shape[1] // 2) * 2].view("<u2")
            decoded = decoded[:, :WIDTH]
        else:
            decoded = raw.astype(np.uint16, copy=False)
            decoded = decoded[:HEIGHT, :WIDTH]

        decoded = decoded.astype(np.uint16, copy=False)
        if decoded.max() > RAW_MAX_DN and RAW_CONTAINER_SHIFT:
            decoded = decoded >> RAW_CONTAINER_SHIFT
        return np.clip(decoded, RAW_MIN_DN, RAW_MAX_DN).astype(np.uint16)

    def _frame_stats(self, dn):
        import numpy as np

        arr = dn.astype(np.uint16, copy=False)
        max_index = int(np.argmax(arr))
        max_y, max_x = np.unravel_index(max_index, arr.shape)
        percentiles = np.percentile(arr, (50, 90, 99, 99.9))
        return {
            "min_dn": int(arr.min()),
            "max_dn": int(arr.max()),
            "max_x": int(max_x),
            "max_y": int(max_y),
            "mean_dn": float(arr.mean()),
            "median_dn": float(percentiles[0]),
            "p90_dn": float(percentiles[1]),
            "p99_dn": float(percentiles[2]),
            "p999_dn": float(percentiles[3]),
            "valid_min_dn": RAW_MIN_DN,
            "valid_max_dn": RAW_MAX_DN,
            "bit_depth": RAW_BIT_DEPTH,
            "valid_range": f"{RAW_MIN_DN}-{RAW_MAX_DN}",
        }

    def _tiff_bytes(self, dn):
        import tifffile

        buf = io.BytesIO()
        tifffile.imwrite(
            buf,
            dn,
            photometric="minisblack",
            compression="zlib",
            metadata={
                "camera": "IMX296 mono",
                "stored_values": "10-bit sensor DN values in uint16 container",
                "valid_range": f"{RAW_MIN_DN}-{RAW_MAX_DN}",
            },
        )
        return buf.getvalue()

    def _preview_jpeg(self, dn, rotation_degrees=180):
        import numpy as np
        from PIL import Image

        rotation_degrees = self._normalize_rotation(rotation_degrees)
        arr = dn.astype(np.float32)
        lo, hi = np.percentile(arr, (0.5, 99.5))
        if hi <= lo:
            hi = lo + 1.0
        preview = np.clip((arr - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)
        buf = io.BytesIO()
        image = Image.fromarray(preview, mode="L")
        if rotation_degrees:
            image = image.rotate(rotation_degrees, expand=True)
        image.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    def _preview_png(self, dn, rotation_degrees=180):
        import numpy as np
        from PIL import Image

        rotation_degrees = self._normalize_rotation(rotation_degrees)
        arr = dn.astype(np.float32)
        lo, hi = np.percentile(arr, (0.5, 99.5))
        if hi <= lo:
            hi = lo + 1.0
        preview = np.clip((arr - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)
        image = Image.fromarray(preview, mode="L")
        if rotation_degrees:
            image = image.rotate(rotation_degrees, expand=True)
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    def _decode_raw_stream_frame(self, frame):
        import numpy as np

        columns = RAW_STRIDE_BYTES // 2
        row = np.frombuffer(frame, dtype="<u2").reshape((HEIGHT, columns))
        decoded = row[:, :WIDTH].astype(np.uint16, copy=False)
        if decoded.max() > RAW_MAX_DN and RAW_CONTAINER_SHIFT:
            decoded = decoded >> RAW_CONTAINER_SHIFT
        return np.clip(decoded, RAW_MIN_DN, RAW_MAX_DN).astype(np.uint16)

    def _set_primary(self, key, ext, mime):
        self.store["primary_key"] = key
        self.store["primary_ext"] = ext
        self.store["primary_mime"] = mime

    def capture(self, exposure_us=None, timeout_s=300.0, trigger_source="pi_test_png"):
        if not self._capture_lock.acquire(blocking=False):
            raise RuntimeError("Capture already in progress; wait for it to finish or cancel it.")
        self._cancel_event.clear()
        try:
            if trigger_source == "pi_test_raw":
                return self.capture_pi_test_raw(exposure_us=exposure_us, timeout_s=20.0)
            if trigger_source in ("pi_test_png", "pi_test_external"):
                return self.capture_external_lossless(
                    exposure_us=exposure_us,
                    timeout_s=min(float(timeout_s), 20.0),
                    test_pulse=True,
                )
            if trigger_source != "external":
                raise ValueError(f"Unknown trigger source: {trigger_source}")
            return self.capture_external_lossless(
                exposure_us=exposure_us,
                timeout_s=timeout_s,
                test_pulse=False,
            )
        finally:
            self._active_proc = None
            self._cancel_event.clear()
            self._capture_lock.release()

    def cancel_capture(self):
        self._cancel_event.set()
        proc = self._active_proc
        if proc and proc.poll() is None:
            proc.terminate()
            return True
        return self._capture_lock.locked()

    def focus_status(self):
        with self._focus_condition:
            return dict(self._focus_status)

    def start_focus(
        self,
        fps=12.0,
        width=728,
        height=544,
        rotation_degrees=180,
        shutter_us=1000,
    ):
        fps = float(fps)
        width = int(width)
        height = int(height)
        rotation = self._normalize_rotation(rotation_degrees)
        shutter_us = max(int(shutter_us), MIN_CAMERA_GATE_US)
        if fps <= 0 or fps > 30:
            raise ValueError("Focus frame rate must be between 1 and 30 fps")
        if width < 160 or height < 120 or width > WIDTH or height > HEIGHT:
            raise ValueError("Invalid focus video dimensions")
        if self.batch_status().get("running"):
            raise RuntimeError("Stop the armed acquisition before starting focus video")
        if not self._capture_lock.acquire(blocking=False):
            raise RuntimeError("Camera is busy with another capture or acquisition")

        try:
            self._set_kernel_trigger_mode(False)
            cmd = [
                "rpicam-vid",
                *self._camera_args(),
                "-n",
                "-t", "0",
                "--codec", "mjpeg",
                "--width", str(width),
                "--height", str(height),
                "--framerate", str(fps),
                "--shutter", str(shutter_us),
                "--awbgains", "1,1",
                "-o", "-",
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            self._focus_proc = proc
            self._focus_stop_event.clear()
            with self._focus_condition:
                self._focus_frame = None
                self._focus_sequence = 0
                self._focus_status = {
                    "running": True,
                    "message": "Starting focus video",
                    "fps": fps,
                    "width": width,
                    "height": height,
                    "frames": 0,
                    "rotation_degrees": rotation,
                    "shutter_us": shutter_us,
                    "focus_score": None,
                    "best_focus_score": None,
                    "relative_focus_percent": None,
                }
                self._focus_condition.notify_all()
            threading.Thread(
                target=self._run_focus_stream,
                args=(proc, rotation),
                daemon=True,
            ).start()
            return self.focus_status()
        except Exception:
            self._focus_proc = None
            self._capture_lock.release()
            raise

    def _focus_score(self, image):
        """Return a contrast-normalized edge-detail score for lens focusing."""
        import numpy as np
        from PIL import Image

        gray = image.convert("L")
        sample_width = min(364, gray.width)
        sample_height = min(272, gray.height)
        if gray.size != (sample_width, sample_height):
            gray = gray.resize(
                (sample_width, sample_height),
                resample=Image.Resampling.BILINEAR,
            )
        arr = np.asarray(gray, dtype=np.float32)
        contrast = float(np.std(arr))
        if contrast < 1e-6 or arr.shape[0] < 3 or arr.shape[1] < 3:
            return 0.0
        gx = arr[:, 2:] - arr[:, :-2]
        gy = arr[2:, :] - arr[:-2, :]
        edge_rms = float(np.sqrt(np.mean(gx * gx) + np.mean(gy * gy)))
        return 100.0 * edge_rms / contrast

    def _run_focus_stream(self, proc, rotation):
        stderr_lines = []

        def drain_stderr():
            if not proc.stderr:
                return
            for raw_line in iter(proc.stderr.readline, b""):
                line = raw_line.decode(errors="replace").strip()
                if line:
                    stderr_lines.append(line)
                    del stderr_lines[:-20]

        stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
        stderr_thread.start()
        buffer = bytearray()
        frames = 0
        best_focus_score = 0.0
        error = None
        try:
            while not self._focus_stop_event.is_set():
                chunk = proc.stdout.read(65536) if proc.stdout else b""
                if not chunk:
                    if proc.poll() is not None:
                        break
                    continue
                buffer.extend(chunk)
                while True:
                    start = buffer.find(b"\xff\xd8")
                    if start < 0:
                        if len(buffer) > 1:
                            del buffer[:-1]
                        break
                    end = buffer.find(b"\xff\xd9", start + 2)
                    if end < 0:
                        if start:
                            del buffer[:start]
                        break
                    frame = bytes(buffer[start:end + 2])
                    del buffer[:end + 2]
                    from PIL import Image

                    image = Image.open(io.BytesIO(frame))
                    image.load()
                    if rotation:
                        image = image.rotate(-rotation, expand=True)
                        out = io.BytesIO()
                        image.save(out, format="JPEG", quality=88)
                        frame = out.getvalue()
                    focus_score = self._focus_score(image)
                    best_focus_score = max(best_focus_score, focus_score)
                    relative_focus = (
                        min(100.0, 100.0 * focus_score / best_focus_score)
                        if best_focus_score > 0 else 0.0
                    )
                    frames += 1
                    self.store["preview"] = frame
                    self.store["preview_mime"] = "image/jpeg"
                    with self._focus_condition:
                        self._focus_frame = frame
                        self._focus_sequence += 1
                        self._focus_status.update(
                            message="Focus video running",
                            frames=frames,
                            focus_score=round(focus_score, 2),
                            best_focus_score=round(best_focus_score, 2),
                            relative_focus_percent=round(relative_focus, 1),
                        )
                        self._focus_condition.notify_all()
        except Exception as exc:
            error = str(exc)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            stderr_thread.join(timeout=0.5)
            if not self._focus_stop_event.is_set() and proc.returncode not in (0, -15):
                tail = " | ".join(stderr_lines[-3:])
                error = error or tail or f"rpicam-vid exited with code {proc.returncode}"
            with self._focus_condition:
                self._focus_status.update(
                    running=False,
                    message=f"Focus video failed: {error}" if error else "Focus video stopped",
                    frames=frames,
                )
                self._focus_condition.notify_all()
            self._focus_proc = None
            self._focus_stop_event.clear()
            self._capture_lock.release()

    def stop_focus(self):
        with self._focus_condition:
            running = bool(self._focus_status.get("running"))
            if running:
                self._focus_status["message"] = "Stopping focus video"
        self._focus_stop_event.set()
        proc = self._focus_proc
        if proc and proc.poll() is None:
            proc.terminate()
        return running

    def focus_mjpeg_frames(self):
        sequence = None
        while True:
            with self._focus_condition:
                self._focus_condition.wait_for(
                    lambda: (
                        self._focus_frame is not None and self._focus_sequence != sequence
                    ) or not self._focus_status.get("running"),
                    timeout=2.0,
                )
                running = bool(self._focus_status.get("running"))
                frame = self._focus_frame
                current_sequence = self._focus_sequence
            if frame is not None and current_sequence != sequence:
                sequence = current_sequence
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-store\r\n\r\n" + frame + b"\r\n"
                )
            if not running:
                break

    def start_batch_raw(
        self,
        base=None,
        frames=100,
        fps=50.0,
        exposure_us=100,
        esp_delay_us=200,
        esp_width_us=100,
        trigger_source="external",
        capture_mode=None,
        start_delay_s=0.5,
        include_log=True,
    ):
        if self._batch_lock.locked() or self._capture_lock.locked():
            raise RuntimeError("Camera is busy with another capture or acquisition")
        frames = int(frames)
        fps = float(fps)
        if frames <= 0 or frames > 10000:
            raise ValueError("Frame count must be between 1 and 10000")
        if fps <= 0 or fps > 60:
            raise ValueError("FPS must be between 0 and 60")
        esp_width_us = max(int(esp_width_us), MIN_CAMERA_GATE_US)
        exposure_us = max(int(exposure_us), MIN_CAMERA_GATE_US)

        dirs, safe_base = self._split_base(base or "batch")
        directory = self._path_for_relative("/".join(dirs))
        os.makedirs(directory, exist_ok=True)
        self.save_counter += 1
        stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        stem = f"{safe_base}_{stamp}_{self.save_counter:06d}"
        raw_path = os.path.join(directory, f"{stem}.raw")
        meta_path = os.path.join(directory, f"{stem}.json")
        log_path = os.path.join(directory, f"{stem}.log")
        expected_bytes = frames * RAW_FRAME_BYTES
        active_raw_path = raw_path
        active_log_path = log_path
        ram_spooled = False
        ram_paths = self._ram_spool_paths(stem, expected_bytes, bool(include_log))
        if ram_paths:
            active_raw_path = ram_paths[0]
            active_log_path = ram_paths[1] or log_path
            ram_spooled = True

        with self._batch_lock:
            if self._batch_status.get("running"):
                raise RuntimeError("Acquisition already running")
            self._batch_cancel_event.clear()
            self._batch_status = {
                "running": True,
                "ok": False,
                "message": "Starting",
                "frames_requested": frames,
                "frames_written": 0,
                "fps": fps,
                "trigger_source": trigger_source,
                "capture_mode": capture_mode,
                "files": [],
                "raw_path": self._relative_path(raw_path),
                "raw_active_path": active_raw_path,
                "ram_spooled": ram_spooled,
                "started_utc": datetime.datetime.utcnow().isoformat() + "Z",
            }

        thread = threading.Thread(
            target=self._run_batch_raw,
            args=(
                active_raw_path,
                raw_path,
                meta_path,
                active_log_path,
                log_path,
                frames,
                fps,
                exposure_us,
                int(esp_delay_us),
                esp_width_us,
                trigger_source,
                capture_mode,
                float(start_delay_s),
                bool(include_log),
                ram_spooled,
            ),
            daemon=True,
        )
        thread.start()
        return self.batch_status()

    def batch_status(self):
        with self._batch_lock:
            return dict(self._batch_status)

    def cancel_batch(self):
        self._batch_cancel_event.set()
        proc = self._batch_proc
        if proc and proc.poll() is None:
            proc.terminate()
        with self._batch_lock:
            if self._batch_status.get("running"):
                self._batch_status["message"] = "Cancelling"
        return True

    def _update_batch_status(self, **updates):
        with self._batch_lock:
            self._batch_status.update(updates)

    def _configure_esp_serial(self, delay_us, width_us, enable=True):
        import serial

        port = (
            "/dev/serial/by-id/"
            "usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
        )
        if not os.path.exists(port):
            port = "/dev/ttyUSB0"
        with serial.Serial(port, 115200, timeout=0.5) as ser:
            time.sleep(0.2)
            ser.read(1024)
            commands = ["E0", f"D{delay_us}", f"W{width_us}"]
            if enable:
                commands.append("E1")
            for cmd in commands:
                ser.write((cmd + "\n").encode())
                ser.flush()
                time.sleep(0.05)

    def _disable_esp_serial(self):
        import serial

        port = (
            "/dev/serial/by-id/"
            "usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
        )
        if not os.path.exists(port):
            port = "/dev/ttyUSB0"
        with serial.Serial(port, 115200, timeout=0.5) as ser:
            time.sleep(0.1)
            ser.write(b"E0\n")
            ser.flush()

    def _send_test_trigger_burst(self, frames, fps, start_delay_s):
        interval_s = 1.0 / fps
        time.sleep(start_delay_s)
        t0 = time.monotonic()
        try:
            for index in range(frames):
                if self._batch_cancel_event.is_set():
                    break
                self._pulse_gpio26_pinctrl()
                next_t = t0 + interval_s * (index + 1)
                delay = next_t - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
        finally:
            self._restore_gpio26_input()

    def _run_batch_raw(
        self,
        raw_path,
        final_raw_path,
        meta_path,
        log_path,
        final_log_path,
        frames,
        fps,
        exposure_us,
        esp_delay_us,
        esp_width_us,
        trigger_source,
        capture_mode,
        start_delay_s,
        include_log,
        ram_spooled,
    ):
        proc = None
        trigger_thread = None
        capture_lock_acquired = False
        t0 = time.monotonic()
        expected_bytes = frames * RAW_FRAME_BYTES
        try:
            if not self._capture_lock.acquire(blocking=False):
                raise RuntimeError("Camera is busy with another capture")
            capture_lock_acquired = True
            self._configure_esp_serial(esp_delay_us, esp_width_us, enable=True)
            self._set_kernel_trigger_mode(True)
            cmd = [
                "rpicam-raw",
                *self._camera_args(),
                "-n",
                "-t", "0",
                "--frames", str(frames),
                "--mode", RAW_MODE,
                "--shutter", str(exposure_us),
                "--gain", "1",
                "--awbgains", "1,1",
                "-o", raw_path,
            ]
            self._update_batch_status(message="Armed")
            output_log_path = log_path if include_log else os.devnull
            with open(output_log_path, "wb") as log:
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
                self._batch_proc = proc
                if trigger_source == "pi_test":
                    trigger_thread = threading.Thread(
                        target=self._send_test_trigger_burst,
                        args=(frames, fps, start_delay_s),
                        daemon=True,
                    )
                    trigger_thread.start()

                deadline = None
                if trigger_source == "pi_test":
                    duration_s = start_delay_s + (frames / fps)
                    deadline = time.monotonic() + duration_s + 3.0

                while True:
                    if self._batch_cancel_event.is_set():
                        break
                    size = os.path.getsize(raw_path) if os.path.exists(raw_path) else 0
                    frames_written = size // RAW_FRAME_BYTES
                    self._update_batch_status(
                        message="Armed" if trigger_source == "external" else "Capturing",
                        frames_written=frames_written,
                    )
                    if frames_written >= frames:
                        break
                    if proc.poll() is not None:
                        break
                    if deadline is not None and time.monotonic() >= deadline:
                        break
                    time.sleep(0.1)

                if trigger_thread:
                    trigger_thread.join(timeout=2)
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2)

            elapsed = time.monotonic() - t0
            size = os.path.getsize(raw_path) if os.path.exists(raw_path) else 0
            frames_written = size // RAW_FRAME_BYTES
            remainder = size % RAW_FRAME_BYTES
            self._move_if_needed(raw_path, final_raw_path)
            if include_log:
                self._move_if_needed(log_path, final_log_path)
            files = [self._relative_path(final_raw_path)]
            if include_log and os.path.exists(final_log_path):
                files.append(self._relative_path(final_log_path))

            stopped = self._batch_cancel_event.is_set()
            full = frames_written >= frames
            ok = remainder == 0 and (full or stopped)
            meta = {
                "started_utc": self._batch_status.get("started_utc"),
                "finished_utc": datetime.datetime.utcnow().isoformat() + "Z",
                "ok": ok,
                "frames_requested": frames,
                "frames_written": frames_written,
                "fps_target": fps,
                "elapsed_s": elapsed,
                "raw_frame_bytes": RAW_FRAME_BYTES,
                "raw_stride_bytes": RAW_STRIDE_BYTES,
                "width": WIDTH,
                "height": HEIGHT,
                "format": "rpicam-raw R16 unpacked stream",
                "raw_mode": RAW_MODE,
                "trigger_source": trigger_source,
                "capture_mode": capture_mode,
                "esp_delay_us": esp_delay_us,
                "esp_width_us": esp_width_us,
                "external_trigger_gate_us": esp_width_us,
                "exposure_us": exposure_us,
                "output_bytes": size,
                "output_remainder_bytes": remainder,
                "ram_spooled": ram_spooled,
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            files.append(self._relative_path(meta_path))
            self._update_batch_status(
                running=False,
                ok=ok,
                message="Reached max frames" if full and ok else ("Stopped" if stopped and ok else "Incomplete"),
                frames_written=frames_written,
                files=files,
                elapsed_s=elapsed,
                raw_active_path="",
            )
        except Exception as exc:
            self._update_batch_status(running=False, ok=False, message=str(exc))
        finally:
            self._batch_proc = None
            try:
                self._set_kernel_trigger_mode(False)
            except Exception:
                pass
            try:
                self._disable_esp_serial()
            except Exception:
                pass
            self._restore_gpio26_input()
            if ram_spooled:
                for tmp_path in (raw_path, log_path):
                    try:
                        if tmp_path and os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    except Exception:
                        pass
            if capture_lock_acquired:
                self._capture_lock.release()
            self._batch_cancel_event.clear()

    def capture_external_lossless(self, exposure_us=None, timeout_s=300.0, test_pulse=False):
        exposure = int(exposure_us or 100)
        fd, path = tempfile.mkstemp(prefix="dose_cam_external_", suffix=".png")
        os.close(fd)
        log_path = path + ".log"
        cmd = [
            "rpicam-still",
            *self._camera_args(),
            "-n",
            "-t", str(int(timeout_s * 1000)),
            "--shutter", str(exposure),
            "--gain", "1",
            "--awbgains", "1,1",
            "--immediate",
            "--encoding", "png",
            "-o", path,
        ]
        proc = None
        trigger_thread = None
        try:
            self._set_kernel_trigger_mode(True)

            def delayed_test_trigger():
                time.sleep(0.5)
                self.trigger_esp(1000)

            with open(log_path, "wb") as log:
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
                self._active_proc = proc
                if test_pulse:
                    trigger_thread = threading.Thread(target=delayed_test_trigger, daemon=True)
                    trigger_thread.start()
                deadline = time.monotonic() + timeout_s + 10
                while proc.poll() is None:
                    if self._cancel_event.is_set():
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=3)
                        raise RuntimeError("Capture cancelled")
                    if time.monotonic() > deadline:
                        proc.kill()
                        proc.wait(timeout=3)
                        raise RuntimeError("Capture timed out")
                    time.sleep(0.05)
            if self._cancel_event.is_set():
                raise RuntimeError("Capture cancelled")
            if proc.returncode != 0:
                with open(log_path, "r", errors="replace") as log:
                    tail = "".join(log.readlines()[-40:])
                raise RuntimeError(f"rpicam-still failed with code {proc.returncode}: {tail}")
            with open(path, "rb") as f:
                png = f.read()
            if not png:
                raise RuntimeError("rpicam-still returned an empty PNG")
            log_blob = open(log_path, "rb").read() if os.path.exists(log_path) else b""
            summary = (
                f"utc={datetime.datetime.utcnow().isoformat()}Z\n"
                f"trigger={'Pi GPIO26 -> ESP8266 -> camera XTR' if test_pulse else 'external ESP/camera input; no Pi test pulse generated'}\n"
                f"sensor={WIDTH}x{HEIGHT} imx296 mono\n"
                f"control_exposure_us={exposure}\n"
                "format=png lossless externally triggered\n"
            ).encode("utf-8")
            self.store["png"] = png
            self.store["jpg"] = png
            self.store["log"] = summary + log_blob
            self._set_primary("png", "png", "image/png")
            self.store["preview_mime"] = "image/png"
            self.store["meta"] = {
                "format": "png",
                "bytes": len(png),
                "width": WIDTH,
                "height": HEIGHT,
                "stored_values": "lossless ISP output, not raw ADC",
                "compression": "png",
                "trigger": "Pi GPIO26 -> ESP8266 -> camera XTR" if test_pulse else "external ESP/camera input",
            }
            return ("png", len(png))
        finally:
            if trigger_thread:
                trigger_thread.join(timeout=1.0)
            if proc and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            try:
                self._set_kernel_trigger_mode(False)
            except Exception:
                pass
            for tmp in (path, log_path):
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass

    def capture_pi_test_raw(self, exposure_us=None, arm_delay_s=0.25, timeout_s=20.0):
        from libcamera import Transform
        from picamera2 import Picamera2

        exposure = int(exposure_us or 100)
        log = [
            f"utc={datetime.datetime.utcnow().isoformat()}Z",
            "trigger=Pi GPIO26 -> ESP8266 -> camera XTR",
            f"sensor={WIDTH}x{HEIGHT} imx296 mono 10-bit",
            f"control_exposure_us={exposure}",
            f"arm_delay_s={arm_delay_s}",
            f"timeout_s={timeout_s}",
            "format=tiff uint16 dn10 zlib",
        ]
        picam2 = None
        trigger_thread = None
        try:
            self._set_kernel_trigger_mode(True)

            picam2 = Picamera2(self._picamera2_index(Picamera2))
            cfg = picam2.create_still_configuration(
                main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
                raw={"size": (WIDTH, HEIGHT), "format": "R16"},
                transform=Transform(),
            )
            picam2.configure(cfg)
            picam2.set_controls({
                "AeEnable": False,
                "AnalogueGain": 1.0,
                "ExposureTime": exposure,
                "FrameDurationLimits": (33333, 33333),
            })

            def delayed_trigger():
                time.sleep(arm_delay_s)
                self.trigger_esp(1000, count=20, interval_s=0.05)

            trigger_thread = threading.Thread(target=delayed_trigger, daemon=True)
            trigger_thread.start()
            t0 = time.monotonic()
            picam2.start()
            raw = picam2.capture_array("raw")
            elapsed = time.monotonic() - t0
            dn = self._decode_raw_to_dn10(raw)
            tiff = self._tiff_bytes(dn)
            jpg = self._preview_jpeg(dn)
            log.extend([
                f"capture_elapsed_s={elapsed:.6f}",
                f"raw_shape={raw.shape}",
                f"raw_dtype={raw.dtype}",
                f"dn_shape={dn.shape}",
                f"dn_dtype={dn.dtype}",
                f"dn_min={int(dn.min())}",
                f"dn_max={int(dn.max())}",
                f"tiff_bytes={len(tiff)}",
                f"preview_jpeg_bytes={len(jpg)}",
            ])
            self.store["tiff"] = tiff
            self.store["jpg"] = jpg
            self.store["log"] = ("\n".join(log) + "\n").encode("utf-8")
            self._set_primary("tiff", "tiff", "image/tiff")
            self.store["preview_mime"] = "image/jpeg"
            self.store["meta"] = {
                "format": "tiff",
                "bytes": len(tiff),
                "preview_bytes": len(jpg),
                "width": WIDTH,
                "height": HEIGHT,
                "stored_values": "10-bit DN in uint16 TIFF",
                "compression": "zlib",
                "trigger": log[1].split("=", 1)[1],
            }
            return ("tiff", len(tiff))
        finally:
            if trigger_thread:
                trigger_thread.join(timeout=2.0)
            if picam2 is not None:
                try:
                    picam2.stop()
                except Exception:
                    pass
                try:
                    picam2.close()
                except Exception:
                    pass
            try:
                self._set_kernel_trigger_mode(False)
            except Exception:
                pass

    def download(self, fmt):
        if fmt == "data":
            return self.store.get(self.store.get("primary_key", ""))
        if fmt in ("tiff", "tif", "raw"):
            return self.store.get("tiff")
        if fmt == "png":
            return self.store.get("png")
        if fmt in ("jpg", "jpeg", "preview"):
            return self.store.get("jpg")
        if fmt == "log":
            return self.store.get("log")
        return None

    def mime_for(self, fmt):
        if fmt == "data":
            return self.store.get("primary_mime", "application/octet-stream")
        if fmt in ("tiff", "tif", "raw"):
            return "image/tiff"
        if fmt == "png":
            return "image/png"
        if fmt in ("jpg", "jpeg", "preview"):
            return self.store.get("preview_mime", "image/jpeg")
        if fmt == "log":
            return "text/plain"
        return "application/octet-stream"

    def extension_for(self, fmt):
        if fmt == "data":
            return self.store.get("primary_ext", "bin")
        if fmt in ("tiff", "tif", "raw"):
            return "tiff"
        if fmt == "png":
            return "png"
        if fmt in ("jpg", "jpeg", "preview"):
            return "jpg"
        if fmt == "log":
            return "log"
        return "bin"

    def _safe_segment(self, value, fallback):
        value = (value or fallback).strip()
        value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
        return value.strip("._-") or fallback

    def _split_base(self, base):
        raw = (base or "dose_cam").strip().replace("\\", "/")
        parts = [p for p in raw.split("/") if p and p not in (".", "..")]
        if not parts:
            return [], "dose_cam"
        dirs = [self._safe_segment(p, "run") for p in parts[:-1]]
        stem = self._safe_segment(parts[-1], "dose_cam")
        return dirs, stem

    def _capture_root(self):
        return os.path.abspath(self.capture_dir)

    def _path_for_relative(self, rel_path):
        root = self._capture_root()
        rel = (rel_path or "").replace("\\", "/")
        parts = [p for p in rel.split("/") if p and p not in (".", "..")]
        path = os.path.abspath(os.path.join(root, *parts))
        if path != root and not path.startswith(root + os.sep):
            raise ValueError("Path is outside save directory")
        return path

    def _relative_path(self, path):
        rel = os.path.relpath(path, self._capture_root()).replace(os.sep, "/")
        return "" if rel == "." else rel

    def _active_raw_path_from_status(self, status=None):
        status = status or self.batch_status()
        active = status.get("raw_active_path")
        if active and os.path.isabs(active):
            return active
        raw_path = status.get("raw_path")
        if not raw_path:
            return None
        return self._path_for_relative(raw_path)

    def _ram_spool_paths(self, stem, expected_bytes, include_log):
        if not os.path.isdir("/dev/shm"):
            return None
        try:
            usage = shutil.disk_usage("/dev/shm")
        except OSError:
            return None
        if expected_bytes + RAM_SPOOL_MIN_FREE_BYTES > usage.free:
            return None
        os.makedirs(RAM_SPOOL_DIR, exist_ok=True)
        raw_path = os.path.join(RAM_SPOOL_DIR, f"{stem}.raw")
        log_path = os.path.join(RAM_SPOOL_DIR, f"{stem}.log") if include_log else None
        return raw_path, log_path

    def _move_if_needed(self, source, destination):
        if not source or source == destination:
            return
        if os.path.exists(source):
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.move(source, destination)

    def saved_raw_frame_preview(self, rel_path, frame_index=-1, rotation_degrees=180):
        path = self._path_for_relative(rel_path)
        if not os.path.isfile(path):
            raise ValueError("Path is not a file")
        if not path.lower().endswith(".raw"):
            raise ValueError("Raw frame viewing is only available for .raw files")

        size = os.path.getsize(path)
        frames = size // RAW_FRAME_BYTES
        remainder = size % RAW_FRAME_BYTES
        if frames < 1:
            raise ValueError("Raw file does not contain a complete frame")

        index = int(frame_index)
        if index < 0:
            index = frames - 1
        if index < 0 or index >= frames:
            raise ValueError(f"Frame index must be between 0 and {frames - 1}")

        with open(path, "rb") as f:
            f.seek(index * RAW_FRAME_BYTES)
            frame = f.read(RAW_FRAME_BYTES)
        if len(frame) != RAW_FRAME_BYTES:
            raise ValueError("Raw frame is incomplete")

        dn = self._decode_raw_stream_frame(frame)
        png = self._preview_png(dn, rotation_degrees=rotation_degrees)
        stats = self._frame_stats(dn)
        name = os.path.splitext(os.path.basename(path))[0] + f"_frame{index:06d}.png"
        return {
            "png": png,
            "download_name": name,
            "frame_index": index,
            "frames_available": frames,
            "trailing_bytes": remainder,
            "frame_stats": stats,
            "width": WIDTH,
            "height": HEIGHT,
            "preview_rotation_degrees": self._normalize_rotation(rotation_degrees),
        }

    def saved_raw_frame_png(self, rel_path, frame_index=-1, rotation_degrees=180):
        return self.saved_raw_frame_preview(rel_path, frame_index, rotation_degrees)

    def saved_text_file(self, rel_path, max_bytes=2 * 1024 * 1024):
        path = self._path_for_relative(rel_path)
        if not os.path.isfile(path):
            raise ValueError("Path is not a file")
        if not path.lower().endswith((".json", ".log", ".txt")):
            raise ValueError("Text viewing is only available for JSON, log, and text files")
        size = os.path.getsize(path)
        if size > max_bytes:
            raise ValueError(f"Text file is too large to view in browser ({size} bytes)")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return {
                "path": self._relative_path(path),
                "name": os.path.basename(path),
                "size": size,
                "text": f.read(),
            }

    def associated_json_path(self, raw_path):
        base, _ = os.path.splitext(raw_path)
        json_path = base + ".json"
        return json_path if os.path.isfile(json_path) else None

    def write_raw_png_zip(self, zf, rel_path, prefix=None, rotation_degrees=180, include_json=True, progress=None):
        path = self._path_for_relative(rel_path)
        if not os.path.isfile(path):
            raise ValueError("Path is not a file")
        if not path.lower().endswith(".raw"):
            raise ValueError("PNG ZIP export is only available for .raw files")

        size = os.path.getsize(path)
        frames = size // RAW_FRAME_BYTES
        if frames < 1:
            raise ValueError("Raw file does not contain a complete frame")

        stem = os.path.splitext(os.path.basename(path))[0]
        clean_prefix = (prefix or stem).replace("\\", "/").strip("/")
        if not clean_prefix:
            clean_prefix = stem

        if include_json:
            json_path = self.associated_json_path(path)
            if json_path:
                zf.write(json_path, f"{clean_prefix}/{os.path.basename(json_path)}")

        with open(path, "rb") as f:
            for index in range(frames):
                if progress:
                    progress(0)
                frame = f.read(RAW_FRAME_BYTES)
                if len(frame) != RAW_FRAME_BYTES:
                    break
                dn = self._decode_raw_stream_frame(frame)
                png = self._preview_png(dn, rotation_degrees=rotation_degrees)
                zf.writestr(f"{clean_prefix}/frame_{index:06d}.png", png)
                if progress:
                    progress(len(frame))
        return frames

    def list_directory(self, rel_path=""):
        root = self._capture_root()
        directory = self._path_for_relative(rel_path)
        if not os.path.isdir(directory):
            raise ValueError("Path is not a directory")

        current = self._relative_path(directory)
        parent = ""
        if current:
            parent = self._relative_path(os.path.dirname(directory))

        dirs = []
        files = []
        for entry in os.scandir(directory):
            if entry.name.startswith("."):
                continue
            stat = entry.stat()
            item = {
                "name": entry.name,
                "path": self._relative_path(entry.path),
                "mtime": stat.st_mtime,
            }
            if entry.is_dir():
                # Newest file anywhere inside, so a folder shows when it last got data.
                item["latest_mtime"], item["file_count"] = self._latest_in_tree(entry.path)
                dirs.append(item)
            elif entry.is_file():
                item["size"] = stat.st_size
                files.append(item)

        dirs.sort(key=lambda item: item["name"].lower())
        files.sort(key=lambda item: item["name"].lower())
        return {
            "path": current,
            "parent": parent,
            "root": root,
            "directories": dirs,
            "files": files,
        }

    @staticmethod
    def _latest_in_tree(path):
        """(newest file mtime or None, number of files) below path, hidden entries skipped."""
        latest, count = None, 0
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.startswith("."):
                    continue
                try:
                    mtime = os.stat(os.path.join(dirpath, name)).st_mtime
                except OSError:
                    continue
                count += 1
                if latest is None or mtime > latest:
                    latest = mtime
        return latest, count

    def delete_saved_path(self, rel_path, expected_type):
        path = self._path_for_relative(rel_path)
        rel = self._relative_path(path)
        if not rel:
            raise ValueError("Refusing to delete the capture root")

        if expected_type == "file":
            if not os.path.isfile(path):
                raise ValueError("Path is not a file")
            os.unlink(path)
        elif expected_type == "directory":
            if not os.path.isdir(path):
                raise ValueError("Path is not a directory")
            shutil.rmtree(path)
        else:
            raise ValueError("Unknown delete type")

        return rel

    def files_for_base(self, base=None):
        dirs, stem = self._split_base(base)
        directory = self._path_for_relative("/".join(dirs))
        if not os.path.isdir(directory):
            return []
        matches = []
        prefix = f"{stem}_"
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name)
            if os.path.isfile(path) and name.startswith(prefix):
                matches.append(path)
        return matches

    def list_saved_files(self):
        root = self._capture_root()
        if not os.path.isdir(root):
            return []
        files = []
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                path = os.path.join(dirpath, name)
                stat = os.stat(path)
                files.append({
                    "path": self._relative_path(path),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
        files.sort(key=lambda item: item["mtime"], reverse=True)
        return files

    def save_to_disk(self, base=None, include_log=False):
        primary_key = self.store.get("primary_key")
        if not self.allow_disk_writes or not primary_key or primary_key not in self.store:
            return []
        dirs, safe_base = self._split_base(base)
        directory = self._path_for_relative("/".join(dirs))
        os.makedirs(directory, exist_ok=True)
        self.save_counter += 1
        stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        stem = f"{safe_base}_{stamp}_{self.save_counter:06d}"
        ext = self.store.get("primary_ext", "bin")
        path = os.path.join(directory, f"{stem}.{ext}")
        with open(path, "wb") as f:
            f.write(self.store[primary_key])
        out = [self._relative_path(path)]
        if include_log and self.store.get("log"):
            log_path = os.path.join(directory, f"{stem}.log")
            with open(log_path, "wb") as f:
                f.write(self.store["log"])
            out.append(self._relative_path(log_path))
        self.store["last_saved"] = out
        return out
