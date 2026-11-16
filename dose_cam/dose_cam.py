from flask import Flask, render_template, request, jsonify, send_file, abort, Response, stream_with_context
from camera_core import CameraCore, MIN_CAMERA_GATE_US
import io
import datetime
import os
import serial
import threading
import time
import zipfile
from wifi_control import WifiControl
from urllib.parse import urlsplit
from zip_stream import stream_zip
from werkzeug.utils import secure_filename
from archive_jobs import ArchiveJobs

app = Flask(__name__)
wifi = WifiControl()
archives = ArchiveJobs()


@app.post("/api/exports")
def start_archive():
    data = request.get_json(silent=True) or {}
    try:
        if cam.batch_status().get("running"):
            raise ValueError("Stop / Finalize acquisition before preparing an archive")
        scope = data.get("scope", "directory")
        relative = data.get("path", "")
        root = os.path.realpath(cam._capture_root())
        if scope == "directory":
            directory = cam._path_for_relative(relative)
            if not os.path.isdir(directory):
                raise ValueError("Directory not found")
            paths = [os.path.join(folder, name) for folder, _, names in os.walk(directory) for name in sorted(names)]
        elif scope == "run":
            paths = cam.files_for_base(relative)
        elif scope == "file":
            paths = [cam._path_for_relative(relative)]
        else:
            raise ValueError("Invalid export scope")
        if not paths or any(os.path.commonpath([os.path.realpath(p), root]) != root for p in paths):
            raise ValueError("No files found, or path outside capture storage")
        png = data.get("format") == "png_zip"
        writer = None
        if png:
            paths = [p for p in paths if p.lower().endswith(".raw")]
            if not paths:
                raise ValueError("No RAW files to export")
            rotation = int(data.get("rotation", 180))
            def writer(archive, path, progress):
                rel = cam._relative_path(path)
                cam.write_raw_png_zip(archive, rel, prefix=os.path.splitext(rel)[0],
                                      rotation_degrees=rotation, progress=progress)
        name = secure_filename((os.path.basename(relative.rstrip("/")) or "captures") +
                               ("_png_frames.zip" if png else "_directory.zip"))
        job_id = archives.start(paths, name, root, writer)
        return jsonify(ok=True, id=job_id), 202
    except (ValueError, OSError) as exc:
        return jsonify(ok=False, error=str(exc)), 400


@app.get("/api/exports/<job_id>")
def archive_status(job_id):
    try:
        return jsonify(ok=True, **archives.status(job_id))
    except KeyError:
        return jsonify(ok=False, error="Export expired or service restarted; prepare it again"), 404


@app.post("/api/exports/<job_id>/cancel")
def cancel_archive(job_id):
    try:
        archives.cancel(job_id)
        return jsonify(ok=True)
    except KeyError:
        return abort(404)


@app.get("/api/exports/<job_id>/download")
def download_archive(job_id):
    try:
        path = archives.download_path(job_id)
        return send_file(path, as_attachment=True, download_name=archives.status(job_id)["name"],
                         mimetype="application/zip", conditional=True)
    except (KeyError, ValueError, FileNotFoundError):
        return abort(404)


@app.get("/api/wifi")
def api_wifi_status():
    try:
        return jsonify(ok=True, **wifi.status())
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 503


@app.post("/api/wifi")
def api_wifi_change():
    # Require JSON and same-origin browser requests for network configuration.
    if not request.is_json:
        return jsonify(ok=False, error="JSON required"), 415
    # nginx's $host drops the external SSH-forwarded port (e.g. 8080).
    origin = request.headers.get("Origin")
    if request.headers.get("Sec-Fetch-Site") == "cross-site" or (origin and
            urlsplit(origin).hostname != urlsplit(request.host_url).hostname):
        return jsonify(ok=False, error="Cross-origin request refused"), 403
    try:
        wifi.start(request.get_json())
        return jsonify(ok=True, message="Applying Wi-Fi settings; reconnect if your Wi-Fi changes"), 202
    except (ValueError, RuntimeError) as exc:
        return jsonify(ok=False, error=str(exc)), 400


cam = CameraCore()
autosave = {
    "enabled": False,
    "base": "dose_cam",
    "include_log": False,
}

ESP_PORT = (
    "/dev/serial/by-id/"
    "usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0"
)
if not os.path.exists(ESP_PORT):
    ESP_PORT = "/dev/ttyUSB0"

# Initialize serial to ESP8266 (for delay generator)
try:
    esp = serial.Serial(ESP_PORT, 115200, timeout=0.5)
    print(f"Connected to ESP8266 on {ESP_PORT}")
except Exception as e:
    esp = None
    print(f"Warning: could not open {ESP_PORT}:", e)
esp_lock = threading.Lock()


def esp_exchange(command, status=False):
    if not esp:
        raise RuntimeError("ESP not connected")
    with esp_lock:
        esp.reset_input_buffer()
        esp.write((command + "\n").encode())
        esp.flush()
        lines = []
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            raw = esp.readline()
            if not raw:
                continue
            line = raw.decode(errors="replace").strip()
            if line:
                lines.append(line)
            if status and line.startswith("STATUS "):
                break
            if not status and lines:
                break
        return lines


def parse_esp_status(lines):
    status_line = next((line for line in lines if line.startswith("STATUS ")), "")
    parsed = {}
    for token in status_line.split()[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parsed[key] = value
    for key in ("enabled", "armed", "delay_us", "width_us"):
        if key in parsed:
            parsed[key] = int(parsed[key])
    return parsed


def coerce_gate_width_us(value):
    return max(int(value), MIN_CAMERA_GATE_US)


@app.route("/")
def setup_page():
    return render_template("setup.html")


@app.get("/api/autosave")
def get_autosave():
    return jsonify({"ok": True, **autosave})


@app.post("/api/autosave")
def set_autosave():
    data = request.get_json(silent=True) or {}
    if "enabled" in data:
        autosave["enabled"] = bool(data["enabled"])
    if "base" in data:
        autosave["base"] = str(data.get("base") or "dose_cam")
    if "include_log" in data:
        autosave["include_log"] = bool(data["include_log"])
    return jsonify({"ok": True, **autosave})


# ---------------- ESP8266 DELAY GENERATOR CONTROL ----------------
@app.get("/api/esp_status")
def esp_status():
    try:
        lines = esp_exchange("S", status=True)
        status = parse_esp_status(lines)
        return jsonify({"ok": True, "status": status, "lines": lines})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/set_delay", methods=["POST"])
def set_delay():
    try:
        val = int(request.json.get("delay_us", 0))
        esp_exchange(f"D{val}")
        return jsonify({"ok": True, "delay_us": val})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/set_width", methods=["POST"])
def set_width():
    try:
        requested = int(request.json.get("width_us", 0))
        val = coerce_gate_width_us(requested)
        esp_exchange(f"W{val}")
        return jsonify({
            "ok": True,
            "width_us": val,
            "requested_width_us": requested,
            "min_width_us": MIN_CAMERA_GATE_US,
            "clamped": val != requested,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/enable_output", methods=["POST"])
@app.route("/api/esp_enable", methods=["POST"])
def enable_output():
    try:
        esp_exchange("E1")
        return jsonify({"ok": True, "enabled": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/disable_output", methods=["POST"])
@app.route("/api/esp_disable", methods=["POST"])
def disable_output():
    try:
        esp_exchange("E0")
        return jsonify({"ok": True, "enabled": False})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/input_trigger_level", methods=["POST"])
@app.route("/api/active_level", methods=["POST"])
@app.route("/api/esp_active_level", methods=["POST"])
def active_level():
    try:
        val = int(request.json.get("level", 1))
        level = 1 if val else 0
        esp_exchange(f"I{level}")
        return jsonify({"ok": True, "level": level, "input_active_level": "HIGH" if level else "LOW"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------- CAPTURE AND FILE HANDLING ----------------
@app.post("/api/capture")
def api_capture():
    try:
        data = request.get_json(silent=True) or {}
        exposure_us = data.get("exposure_us")
        trigger_source = data.get("trigger_source") or "pi_test_png"
        timeout_s = float(data.get("timeout_s") or 300)
        if esp:
            esp_exchange("E1")
        fmt, nbytes = cam.capture(
            exposure_us=exposure_us,
            timeout_s=timeout_s,
            trigger_source=trigger_source,
        )
        files = []
        if autosave["enabled"]:
            files = cam.save_to_disk(autosave["base"], autosave["include_log"])
        return jsonify({"ok": True, "meta": f"{fmt} {nbytes} bytes", "files": files})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/capture/cancel")
def api_capture_cancel():
    try:
        cancelled = cam.cancel_capture()
        if esp:
            esp_exchange("E0")
        return jsonify({"ok": True, "cancelled": cancelled})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/batch/start")
def api_batch_start():
    data = request.get_json(silent=True) or {}
    try:
        status = cam.start_batch_raw(
            base=data.get("base") or "batch",
            frames=data.get("frames", 100),
            fps=data.get("fps", 50),
            exposure_us=data.get("exposure_us", 100),
            esp_delay_us=data.get("esp_delay_us", 200),
            esp_width_us=coerce_gate_width_us(data.get("esp_width_us", 100)),
            trigger_source=data.get("trigger_source") or "pi_test",
            capture_mode=data.get("capture_mode"),
            start_delay_s=data.get("start_delay_s", 0.5),
            include_log=bool(data.get("include_log", False)),
        )
        return jsonify({"ok": True, "status": status})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/acquisition/start")
def api_acquisition_start():
    data = request.get_json(silent=True) or {}
    try:
        gate_width_us = coerce_gate_width_us(data.get("gate_width_us", data.get("esp_width_us", 100)))
        status = cam.start_batch_raw(
            base=data.get("base") or "run",
            frames=data.get("frames", 10000),
            fps=data.get("fps", 50),
            exposure_us=data.get("exposure_us", gate_width_us),
            esp_delay_us=data.get("esp_delay_us", 200),
            esp_width_us=gate_width_us,
            trigger_source="external",
            capture_mode=data.get("capture_mode") or "targeting",
            include_log=bool(data.get("include_log", False)),
        )
        return jsonify({"ok": True, "status": status})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/api/batch/status")
def api_batch_status():
    return jsonify({"ok": True, "status": cam.batch_status()})


@app.get("/api/acquisition/status")
def api_acquisition_status():
    return jsonify({"ok": True, "status": cam.batch_status()})


@app.post("/api/batch/cancel")
def api_batch_cancel():
    try:
        return jsonify({"ok": True, "cancelled": cam.cancel_batch(), "status": cam.batch_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/acquisition/stop")
def api_acquisition_stop():
    try:
        return jsonify({"ok": True, "stopping": cam.cancel_batch(), "status": cam.batch_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/batch/test_trigger")
def api_batch_test_trigger():
    data = request.get_json(silent=True) or {}
    try:
        width_us = int(data.get("width_us", 1000))
        cam.send_test_trigger(width_us=width_us)
        return jsonify({"ok": True, "width_us": width_us, "status": cam.batch_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/acquisition/test_trigger")
def api_acquisition_test_trigger():
    data = request.get_json(silent=True) or {}
    try:
        width_us = int(data.get("width_us", 1000))
        cam.send_test_trigger(width_us=width_us)
        return jsonify({"ok": True, "width_us": width_us, "status": cam.batch_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/acquisition/update_preview")
def api_acquisition_update_preview():
    data = request.get_json(silent=True) or {}
    try:
        preview = cam.update_preview_from_latest_raw(
            min_frames=int(data.get("min_frames", 1)),
            timeout_s=float(data.get("timeout_s", 0)),
            rotation_degrees=data.get("image_rotation_degrees", 180),
        )
        return jsonify({"ok": True, "preview": preview, "status": cam.batch_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/acquisition/capture_preview")
def api_acquisition_capture_preview():
    data = request.get_json(silent=True) or {}
    try:
        status = cam.batch_status()
        started_for_preview = False
        if not status.get("running"):
            gate_width_us = coerce_gate_width_us(data.get("gate_width_us", data.get("esp_width_us", 100)))
            cam.start_batch_raw(
                base=data.get("base") or "targeting",
                frames=1,
                fps=data.get("fps", 50),
                exposure_us=data.get("exposure_us", gate_width_us),
                esp_delay_us=data.get("esp_delay_us", 200),
                esp_width_us=gate_width_us,
                trigger_source="external",
                capture_mode=data.get("capture_mode") or "targeting",
                include_log=bool(data.get("include_log", False)),
            )
            started_for_preview = True

        deadline = time.monotonic() + float(data.get("arm_timeout_s", 5.0))
        while time.monotonic() < deadline:
            status = cam.batch_status()
            if status.get("message") == "Armed":
                break
            if not status.get("running"):
                raise RuntimeError(status.get("message") or "Acquisition is not running")
            time.sleep(0.05)
        else:
            raise RuntimeError("Timed out waiting for camera to arm")

        default_settle_s = 1.0 if started_for_preview else 0.0
        settle_s = float(data.get("settle_s", default_settle_s))
        if settle_s > 0:
            time.sleep(settle_s)

        preview = cam.send_test_trigger_and_update_preview(
            width_us=int(data.get("width_us", 1000)),
            timeout_s=float(data.get("preview_timeout_s", 5.0)),
            rotation_degrees=data.get("image_rotation_degrees", 180),
        )
        return jsonify({"ok": True, "preview": preview, "status": cam.batch_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "status": cam.batch_status()}), 500


@app.get("/api/preview.png")
def api_preview():
    blob = cam.download("preview")
    if not blob:
        return abort(404)
    return send_file(io.BytesIO(blob), mimetype=cam.mime_for("preview"), as_attachment=False)


@app.get("/api/preview.jpg")
def api_preview_jpg():
    blob = cam.download("preview")
    if not blob:
        return abort(404)
    return send_file(io.BytesIO(blob), mimetype=cam.mime_for("preview"), as_attachment=False)


@app.post("/api/focus/start")
def api_focus_start():
    data = request.get_json(silent=True) or {}
    try:
        status = cam.start_focus(
            fps=data.get("fps", 12),
            width=data.get("width", 728),
            height=data.get("height", 544),
            rotation_degrees=data.get("image_rotation_degrees", 180),
            shutter_us=coerce_gate_width_us(data.get("shutter_us", 1000)),
        )
        if esp:
            try:
                esp_exchange("E0")
            except Exception:
                cam.stop_focus()
                raise
        return jsonify({"ok": True, "status": status})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "status": cam.focus_status()}), 500


@app.get("/api/focus/status")
def api_focus_status():
    return jsonify({"ok": True, "status": cam.focus_status()})


@app.post("/api/focus/stop")
def api_focus_stop():
    try:
        stopped = cam.stop_focus()
        return jsonify({"ok": True, "stopped": stopped, "status": cam.focus_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/api/focus/stream.mjpg")
def api_focus_stream():
    if not cam.focus_status().get("running"):
        return abort(409)
    return Response(
        stream_with_context(cam.focus_mjpeg_frames()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/api/download/<fmt>")
def api_download(fmt):
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt == "tif":
        fmt = "tiff"
    if fmt not in ("data", "tiff", "png", "jpg", "log"):
        return abort(400)
    blob = cam.download(fmt)
    if not blob:
        return abort(404)
    name = f"frame.{cam.extension_for(fmt)}"
    mt = cam.mime_for(fmt)
    return send_file(io.BytesIO(blob), mimetype=mt,
                     as_attachment=True, download_name=name)


@app.post("/api/save")
def api_save():
    data = request.get_json(silent=True) or {}
    base = data.get("name") or datetime.datetime.utcnow().strftime("imx296_%Y%m%d_%H%M%S")
    include_log = bool(data.get("include_log", False))
    files = cam.save_to_disk(base, include_log)
    if not files:
        return jsonify({"ok": False, "error": "No frame"}), 400
    return jsonify({"ok": True, "files": files})


@app.get("/api/files")
def api_files():
    rel_path = request.args.get("path")
    if rel_path is None:
        return jsonify({"ok": True, "files": cam.list_saved_files()})
    try:
        return jsonify({"ok": True, **cam.list_directory(rel_path)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/files/download")
def api_file_download():
    rel_path = request.args.get("path", "")
    try:
        path = cam._path_for_relative(rel_path)
    except ValueError:
        return abort(400)
    if not os.path.isfile(path):
        return abort(404)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.get("/api/files/download_png")
def api_file_download_png():
    rel_path = request.args.get("path", "")
    rotation = request.args.get("rotation", "180")
    try:
        path = cam._path_for_relative(rel_path)
        safe_name = os.path.splitext(os.path.basename(path))[0] or "raw_frames"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            cam.write_raw_png_zip(zf, rel_path, prefix=safe_name, rotation_degrees=rotation)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{safe_name}_png_frames.zip",
    )


@app.get("/api/files/text")
def api_file_text():
    rel_path = request.args.get("path", "")
    try:
        return jsonify({"ok": True, **cam.saved_text_file(rel_path)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/files/raw_frame.png")
def api_file_raw_frame_png():
    rel_path = request.args.get("path", "")
    frame = request.args.get("frame", "-1")
    rotation = request.args.get("rotation", "180")
    try:
        converted = cam.saved_raw_frame_preview(
            rel_path,
            frame_index=int(frame),
            rotation_degrees=rotation,
        )
    except ValueError:
        return abort(400)
    return send_file(io.BytesIO(converted["png"]), mimetype="image/png", as_attachment=False)


@app.get("/api/files/raw_frame")
def api_file_raw_frame():
    rel_path = request.args.get("path", "")
    frame = request.args.get("frame", "-1")
    rotation = request.args.get("rotation", "180")
    try:
        converted = cam.saved_raw_frame_preview(
            rel_path,
            frame_index=int(frame),
            rotation_degrees=rotation,
        )
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    converted.pop("png", None)
    return jsonify({"ok": True, **converted})


@app.post("/api/files/delete")
def api_file_delete():
    data = request.get_json(silent=True) or {}
    rel_path = data.get("path", "")
    expected_type = data.get("type", "")
    try:
        deleted = cam.delete_saved_path(rel_path, expected_type)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "deleted": deleted})


@app.post("/api/files/mkdir")
def api_files_mkdir():
    data = request.get_json(silent=True) or {}
    rel_path = data.get("path", "")
    try:
        directory = cam._path_for_relative(rel_path)
        os.makedirs(directory, exist_ok=True)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "path": cam._relative_path(directory)})


@app.get("/api/files/download_dir")
def api_directory_download():
    rel_path = request.args.get("path", "")
    export_format = request.args.get("format", "raw_zip")
    rotation = request.args.get("rotation", "180")
    try:
        directory = cam._path_for_relative(rel_path)
    except ValueError:
        return abort(400)
    if not os.path.isdir(directory):
        return abort(404)

    paths = []
    for dirpath, _, filenames in os.walk(directory):
        for filename in sorted(filenames):
            path = os.path.join(dirpath, filename)
            # Revalidate each member; never follow a symlink outside capture storage.
            if os.path.commonpath([os.path.realpath(path), os.path.realpath(cam._capture_root())]) != os.path.realpath(cam._capture_root()):
                return abort(400)
            paths.append(path)
    if export_format == "png_zip" and not any(p.lower().endswith(".raw") for p in paths):
        return abort(404)

    def write_entries(zf):
        if export_format == "png_zip":
            for path in paths:
                if path.lower().endswith(".raw"):
                    rel = cam._relative_path(path)
                    prefix = os.path.splitext(rel)[0].replace("\\", "/")
                    cam.write_raw_png_zip(zf, rel, prefix=prefix, rotation_degrees=rotation)
        else:
            for path in paths:
                zf.write(path, cam._relative_path(path))
    safe_name = cam._split_base(rel_path)[1] if rel_path else "captures"
    suffix = "png_frames" if export_format == "png_zip" else "directory"
    return zip_download_response(write_entries, f"{safe_name}_{suffix}.zip")


def zip_download_response(write_entries, name):
    return Response(stream_zip(write_entries), mimetype="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{secure_filename(name) or "captures.zip"}"',
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-store",
    })


@app.get("/api/files/download_all")
def api_files_download_all():
    base = request.args.get("base", "")
    export_format = request.args.get("format", "raw_zip")
    rotation = request.args.get("rotation", "180")
    paths = cam.files_for_base(base)
    if not paths:
        return abort(404)
    if export_format == "png_zip" and not any(p.lower().endswith(".raw") for p in paths):
        return abort(404)

    def write_entries(zf):
        if export_format == "png_zip":
            for path in paths:
                if not path.lower().endswith(".raw"):
                    continue
                rel = cam._relative_path(path)
                prefix = os.path.splitext(rel)[0].replace("\\", "/")
                cam.write_raw_png_zip(zf, rel, prefix=prefix, rotation_degrees=rotation)
        else:
            for path in paths:
                zf.write(path, cam._relative_path(path))
    safe_name = cam._split_base(base)[1]
    suffix = "png_frames" if export_format == "png_zip" else "files"
    name = f"{safe_name or 'captures'}_{suffix}.zip"
    return zip_download_response(write_entries, name)


# ---------------- BEAM PROFILE ANALYSIS (added 2026-10-14) ----------------
# Background subtraction + rotated 2D Gaussian fit of the beam spot.
# Scale is DN; drop a dn_calibration.json beside this file to add Gy.
# Rollback: bash /home/codex/backups/restore_dose_cam.sh

_ANALYSIS_PNGS = {}
_ANALYSIS_LOCK = threading.Lock()


def _analysis_params(data):
    roi = data.get("roi")
    if roi:
        if isinstance(roi, dict):
            x = int(roi.get("x", 0)); y = int(roi.get("y", 0))
            w = int(roi.get("w", 0)); h = int(roi.get("h", 0))
        else:
            x, y, w, h = [int(v) for v in roi]
        roi = (x, x + w, y, y + h) if w > 0 and h > 0 else None
    return dict(
        source=str(data.get("source", "file")),
        path=str(data.get("path", "")),
        frame=int(data.get("frame", -1)),
        background=str(data.get("background", "none")),
        bg_path=str(data.get("bg_path", "")),
        bg_frames=int(data.get("bg_frames", 0)),
        baseline_order=int(data.get("baseline_order", 2)),
        roi=roi,
        despike_dn=float(data.get("despike_dn", 40.0)),
        rotation_degrees=int(data.get("rotation", 180)),
        png_mode=str(data.get("png_mode", "subtracted")),
        suppress_sigma=float(data.get("suppress_sigma", 0.0)),
    )


@app.post("/api/analysis/fit")
def api_analysis_fit():
    data = request.get_json(silent=True) or {}
    try:
        params = _analysis_params(data)
    except (TypeError, ValueError) as e:
        return jsonify({"ok": False, "error": f"Bad parameters: {e}"}), 400
    try:
        import beam_fit
        result = beam_fit.analyze(cam, want_png=True, **params)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:  # noqa: BLE001 - surface fit failures to the operator
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

    png = result.pop("png", None)
    token = None
    if png:
        token = f"{int(time.time()*1000):x}"
        with _ANALYSIS_LOCK:
            _ANALYSIS_PNGS[token] = png
            for old in list(_ANALYSIS_PNGS)[:-4]:
                _ANALYSIS_PNGS.pop(old, None)
    result["png_token"] = token
    return jsonify({"ok": True, **result})


@app.get("/api/analysis/fit.png")
def api_analysis_fit_png():
    token = request.args.get("token", "")
    with _ANALYSIS_LOCK:
        blob = _ANALYSIS_PNGS.get(token)
    if not blob:
        return abort(404)
    return send_file(io.BytesIO(blob), mimetype="image/png", as_attachment=False)


@app.get("/api/analysis/calibration")
def api_analysis_calibration_get():
    import beam_fit
    return jsonify({"ok": True, **beam_fit.load_calibration()})


@app.post("/api/analysis/calibration")
def api_analysis_calibration_set():
    """Body may contain any of:
      dn_per_gy          number > 0, or null/'' to drop the custom value (default applies)
      dn_per_gy_err_pct  number >= 0 (1-sigma %), or null/'' to drop it
      note               str
      display_units      'DN' | 'Gy'
      include_cal_err    bool - add calibration error to Gy fit errors
      reset_default      bool - drop custom value, error and note
    Unset keys keep their value."""
    import beam_fit
    data = request.get_json(silent=True) or {}
    kwargs = {}
    if data.get("reset_default"):
        kwargs["reset"] = True
    if "dn_per_gy" in data:
        raw = data.get("dn_per_gy")
        if raw in (None, ""):
            kwargs["dn_per_gy"] = None
        else:
            try:
                v = float(raw)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "DN per Gy must be a number"}), 400
            if not (v > 0):
                return jsonify({"ok": False, "error": "DN per Gy must be positive"}), 400
            kwargs["dn_per_gy"] = v
    if "dn_per_gy_err_pct" in data:
        raw = data.get("dn_per_gy_err_pct")
        if raw in (None, ""):
            kwargs["dn_per_gy_err_pct"] = None
        else:
            try:
                e = float(raw)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "Calibration uncertainty must be a number"}), 400
            if not (0 <= e < 100):
                return jsonify({"ok": False, "error": "Calibration uncertainty must be 0-100 %"}), 400
            kwargs["dn_per_gy_err_pct"] = e
    if "note" in data:
        kwargs["note"] = str(data.get("note") or "")
    if "display_units" in data:
        units = str(data.get("display_units"))
        if units not in ("DN", "Gy"):
            return jsonify({"ok": False, "error": "display_units must be DN or Gy"}), 400
        kwargs["display_units"] = units
    if "include_cal_err" in data:
        kwargs["include_cal_err"] = bool(data.get("include_cal_err"))
    cal = beam_fit.save_calibration(**kwargs)
    return jsonify({"ok": True, **cal})


# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)
