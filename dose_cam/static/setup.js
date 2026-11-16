const q = sel => document.querySelector(sel);

const statusEl = q("#status");
const captureMsgEl = q("#captureMsg");
const previewEl = q("#preview");
const frameStatsEl = q("#frameStats");
const espMsgEl = q("#espMsg");
const filesMsgEl = q("#filesMsg");
const filesListEl = q("#filesList");
const filesPathEl = q("#filesPath");
const confirmDeleteEl = q("#confirm_delete");
const saveDirPickerEl = q("#saveDirPicker");
const saveDirPathEl = q("#saveDirPath");
const saveDirListEl = q("#saveDirList");
const saveDirMsgEl = q("#saveDirMsg");
const fileViewerEl = q("#fileViewer");
const fileViewerTitleEl = q("#fileViewerTitle");
const fileViewerMsgEl = q("#fileViewerMsg");
const fileViewerImageEl = q("#fileViewerImage");
const fileViewerStatsEl = q("#fileViewerStats");
const fileViewerStageEl = q("#fileViewerStage");
const fileViewerZoomSelectionEl = q("#fileViewerZoomSelection");
const viewerFrameInputEl = q("#viewerFrameInput");
const viewerRestoreButton = q("#btnViewerRestore");
const acquisitionMsgEl = q("#batchMsg");
const acquisitionFilesEl = q("#batchFiles");
const armButton = q("#btnBatchStart");
const captureButton = q("#btnCap");
const stopButton = q("#btnBatchCancel");
const focusMsgEl = q("#focusMsg");
const focusIndicatorEl = q("#focusIndicator");
const focusQualityEl = q("#focusQuality");
const focusScoreEl = q("#focusScore");
const focusMeterFillEl = q("#focusMeterFill");
const outputEnabledEl = q("#output_enabled");
const previewWrapEl = q(".preview-wrap");
const zoomSelectionEl = q("#zoomSelection");
const previewToolbarEl = q(".preview-toolbar");
const MIN_CAMERA_GATE_US = 30;
const DEFAULT_SAVE_BASE = "default/run";
const DEFAULT_MAX_FRAMES = 10000;
const HARD_MAX_FRAMES = 10000;
let currentFilesPath = "";
let currentSaveDirPath = "";
let zoomDrag = null;
let previewViewState = "baseline";
let previewTransform = { scale: 1, tx: 0, ty: 0 };
let lastAcquisitionStatus = {};
let focusRunning = false;
let fileViewerState = { path: "", type: "", frame: -1, frames: 0 };
let fileViewerZoomDrag = null;
let fileViewerViewState = "baseline";
let fileViewerTransform = { scale: 1, tx: 0, ty: 0 };
previewEl.draggable = false;
fileViewerImageEl.draggable = false;

function setStatus(text) {
  statusEl.textContent = text || "";
}

function readLocalSetting(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (e) {
    return null;
  }
}

function writeLocalSetting(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (e) {
    // Browser storage can be disabled on some control-room systems.
  }
}

function setAcquisitionBusy(running) {
  const focusingSelected = captureMode() === "focusing";
  armButton.disabled = running || focusRunning || focusingSelected;
  stopButton.disabled = !running;
  captureButton.disabled = focusRunning || focusingSelected;
  q("#btnUpdatePreview").disabled = focusRunning || focusingSelected;
  armButton.textContent = running ? "Armed" : "Arm";
}

function restorePreviewView() {
  previewTransform = { scale: 1, tx: 0, ty: 0 };
  applyPreviewTransform();
  zoomSelectionEl.style.display = "none";
  previewViewState = "baseline";
  updateRestoreViewControl();
}

function applyPreviewTransform() {
  const { scale, tx, ty } = previewTransform;
  previewEl.style.transform = scale === 1 && tx === 0 && ty === 0
    ? ""
    : `matrix(${scale}, 0, 0, ${scale}, ${tx}, ${ty})`;
}

function setPreviewViewState(state) {
  previewViewState = state;
  updateRestoreViewControl();
}

function updateRestoreViewControl() {
  previewToolbarEl.classList.toggle("hidden", previewViewState === "baseline");
}

function previewDragMode() {
  return q("#preview_drag_mode").value || "zoom";
}

function applyPreviewDragMode() {
  const nativeDrag = previewDragMode() === "native";
  previewWrapEl.classList.toggle("native-drag", nativeDrag);
  previewEl.draggable = nativeDrag;
  if (nativeDrag) {
    zoomDrag = null;
    zoomSelectionEl.style.display = "none";
  }
}

function previewPoint(event) {
  const wrapRect = previewWrapEl.getBoundingClientRect();
  const baseLeft = previewEl.offsetLeft;
  const baseTop = previewEl.offsetTop;
  const displayLeft = baseLeft + previewTransform.tx;
  const displayTop = baseTop + previewTransform.ty;
  const displayRight = displayLeft + previewEl.offsetWidth * previewTransform.scale;
  const displayBottom = displayTop + previewEl.offsetHeight * previewTransform.scale;
  const wrapX = Math.max(displayLeft, Math.min(event.clientX - wrapRect.left, displayRight));
  const wrapY = Math.max(displayTop, Math.min(event.clientY - wrapRect.top, displayBottom));
  return {
    imageX: (wrapX - displayLeft) / previewTransform.scale,
    imageY: (wrapY - displayTop) / previewTransform.scale,
    wrapX,
    wrapY,
  };
}

function renderZoomSelection(a, b) {
  const left = Math.min(a.wrapX, b.wrapX);
  const top = Math.min(a.wrapY, b.wrapY);
  const width = Math.abs(b.wrapX - a.wrapX);
  const height = Math.abs(b.wrapY - a.wrapY);
  zoomSelectionEl.style.left = `${left}px`;
  zoomSelectionEl.style.top = `${top}px`;
  zoomSelectionEl.style.width = `${width}px`;
  zoomSelectionEl.style.height = `${height}px`;
  zoomSelectionEl.style.display = "block";
}

function applyPreviewZoom(a, b) {
  const wrapRect = previewWrapEl.getBoundingClientRect();
  const selectionWidth = Math.abs(b.imageX - a.imageX);
  const selectionHeight = Math.abs(b.imageY - a.imageY);
  if (selectionWidth < 10 || selectionHeight < 10) {
    zoomSelectionEl.style.display = "none";
    return;
  }

  const scale = Math.min(wrapRect.width / selectionWidth, wrapRect.height / selectionHeight);
  const x = Math.min(a.imageX, b.imageX);
  const y = Math.min(a.imageY, b.imageY);
  const tx = (wrapRect.width - selectionWidth * scale) / 2 - previewEl.offsetLeft - x * scale;
  const ty = (wrapRect.height - selectionHeight * scale) / 2 - previewEl.offsetTop - y * scale;
  previewTransform = { scale, tx, ty };
  applyPreviewTransform();
  setPreviewViewState("zoom");
  zoomSelectionEl.style.display = "none";
}

function restoreFileViewerView() {
  fileViewerTransform = { scale: 1, tx: 0, ty: 0 };
  applyFileViewerTransform();
  fileViewerZoomSelectionEl.style.display = "none";
  fileViewerViewState = "baseline";
  updateFileViewerRestoreControl();
}

function applyFileViewerTransform() {
  const { scale, tx, ty } = fileViewerTransform;
  fileViewerImageEl.style.transform = scale === 1 && tx === 0 && ty === 0
    ? ""
    : `matrix(${scale}, 0, 0, ${scale}, ${tx}, ${ty})`;
}

function updateFileViewerRestoreControl() {
  viewerRestoreButton.classList.toggle("hidden", fileViewerViewState === "baseline");
}

function applyFileViewerDragMode() {
  const nativeDrag = previewDragMode() === "native";
  fileViewerStageEl.classList.toggle("native-drag", nativeDrag);
  fileViewerImageEl.draggable = nativeDrag;
  if (nativeDrag) {
    fileViewerZoomDrag = null;
    fileViewerZoomSelectionEl.style.display = "none";
  }
}

function fileViewerPoint(event) {
  const wrapRect = fileViewerStageEl.getBoundingClientRect();
  const baseLeft = fileViewerImageEl.offsetLeft;
  const baseTop = fileViewerImageEl.offsetTop;
  const displayLeft = baseLeft + fileViewerTransform.tx;
  const displayTop = baseTop + fileViewerTransform.ty;
  const displayRight = displayLeft + fileViewerImageEl.offsetWidth * fileViewerTransform.scale;
  const displayBottom = displayTop + fileViewerImageEl.offsetHeight * fileViewerTransform.scale;
  const wrapX = Math.max(displayLeft, Math.min(event.clientX - wrapRect.left, displayRight));
  const wrapY = Math.max(displayTop, Math.min(event.clientY - wrapRect.top, displayBottom));
  return {
    imageX: (wrapX - displayLeft) / fileViewerTransform.scale,
    imageY: (wrapY - displayTop) / fileViewerTransform.scale,
    wrapX,
    wrapY,
  };
}

function renderFileViewerZoomSelection(a, b) {
  const left = Math.min(a.wrapX, b.wrapX);
  const top = Math.min(a.wrapY, b.wrapY);
  const width = Math.abs(b.wrapX - a.wrapX);
  const height = Math.abs(b.wrapY - a.wrapY);
  fileViewerZoomSelectionEl.style.left = `${left}px`;
  fileViewerZoomSelectionEl.style.top = `${top}px`;
  fileViewerZoomSelectionEl.style.width = `${width}px`;
  fileViewerZoomSelectionEl.style.height = `${height}px`;
  fileViewerZoomSelectionEl.style.display = "block";
}

function applyFileViewerZoom(a, b) {
  const wrapRect = fileViewerStageEl.getBoundingClientRect();
  const selectionWidth = Math.abs(b.imageX - a.imageX);
  const selectionHeight = Math.abs(b.imageY - a.imageY);
  if (selectionWidth < 10 || selectionHeight < 10) {
    fileViewerZoomSelectionEl.style.display = "none";
    return;
  }

  const scale = Math.min(wrapRect.width / selectionWidth, wrapRect.height / selectionHeight);
  const x = Math.min(a.imageX, b.imageX);
  const y = Math.min(a.imageY, b.imageY);
  const tx = (wrapRect.width - selectionWidth * scale) / 2 - fileViewerImageEl.offsetLeft - x * scale;
  const ty = (wrapRect.height - selectionHeight * scale) / 2 - fileViewerImageEl.offsetTop - y * scale;
  fileViewerTransform = { scale, tx, ty };
  applyFileViewerTransform();
  fileViewerViewState = "zoom";
  updateFileViewerRestoreControl();
  fileViewerZoomSelectionEl.style.display = "none";
}

async function postJSON(url, data = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return await res.json();
}

function captureMode() {
  return q("#capture_mode").value || "targeting";
}

function gateInputForMode(mode = captureMode()) {
  return mode === "dosimetry" ? q("#dosimetry_gate_width") : q("#targeting_gate_width");
}

function clampGateWidthUs(value, fallback = 100) {
  const parsed = parseInt(value, 10);
  const usable = Number.isFinite(parsed) ? parsed : fallback;
  return Math.max(usable, MIN_CAMERA_GATE_US);
}

function selectedGateWidthUs() {
  const input = gateInputForMode();
  const value = clampGateWidthUs(input.value, 100);
  input.value = value;
  return value;
}

function saveGateWidthProfile(mode) {
  const input = gateInputForMode(mode);
  input.value = clampGateWidthUs(input.value, mode === "dosimetry" ? 100 : 1000);
  writeLocalSetting(`dosecam_${mode}_gate_width_us`, input.value);
}

function imageRotationDegrees() {
  return parseInt(q("#image_rotation").value || "180", 10);
}

function clampMaxFrames(value) {
  const parsed = parseInt(value, 10);
  const usable = Number.isFinite(parsed) ? parsed : DEFAULT_MAX_FRAMES;
  return Math.max(1, Math.min(usable, HARD_MAX_FRAMES));
}

function acquisitionPayload() {
  const mode = captureMode();
  const gateWidthUs = selectedGateWidthUs();
  const maxFrames = clampMaxFrames(q("#batch_frames").value);
  q("#batch_frames").value = maxFrames;
  saveGateWidthProfile(mode);
  return {
    base: q("#batch_base").value || DEFAULT_SAVE_BASE,
    capture_mode: mode,
    frames: maxFrames,
    fps: parseFloat(q("#batch_fps").value || "50"),
    gate_width_us: gateWidthUs,
    exposure_us: gateWidthUs,
    esp_delay_us: parseInt(q("#esp_delay").value || "200", 10),
    esp_width_us: gateWidthUs,
    image_rotation_degrees: imageRotationDegrees(),
    include_log: q("#batch_include_log").checked,
  };
}

async function applyGateSettings() {
  const delayUs = parseInt(q("#esp_delay").value || "200", 10);
  const gateWidthUs = selectedGateWidthUs();
  await postJSON("/api/set_delay", { delay_us: delayUs });
  await postJSON("/api/set_width", { width_us: gateWidthUs });
  await postJSON("/api/enable_output");
  outputEnabledEl.checked = true;
}

function renderEspStatus(status) {
  if (!status) return;
  if (Number.isFinite(status.delay_us)) q("#esp_delay").value = status.delay_us;
  if (status.input_active_level) {
    q("#input_trigger_active_high").checked = status.input_active_level === "HIGH";
  }
  if (Number.isFinite(status.enabled)) {
    outputEnabledEl.checked = Boolean(status.enabled);
  }
}

async function loadEspStatus() {
  try {
    const res = await fetch("/api/esp_status?ts=" + Date.now());
    const j = await res.json();
    if (!j.ok) {
      espMsgEl.textContent = "ESP status unavailable: " + (j.error || "read failed");
      return;
    }
    renderEspStatus(j.status || {});
    const level = q("#input_trigger_active_high").checked ? "HIGH" : "LOW";
    const outputState = outputEnabledEl.checked ? "enabled" : "disabled";
    const widthText = Number.isFinite(j.status && j.status.width_us)
      ? `; ESP currently programmed gate ${j.status.width_us} us`
      : "";
    espMsgEl.textContent = `ESP output ${outputState}; input trigger active ${level}${widthText}`;
  } catch (e) {
    espMsgEl.textContent = "ESP status unavailable: " + e;
  }
}

function renderAcquisitionStatus(status) {
  lastAcquisitionStatus = status || {};
  const requested = status.frames_requested || 0;
  const written = status.frames_written || 0;
  const frameText = requested ? `${written}/${requested}` : `${written}`;
  const message = status.message || "Idle";
  const spoolText = status.ram_spooled ? " (RAM spool)" : "";
  acquisitionMsgEl.textContent = `${message}: ${frameText} frames${spoolText}`;
  setAcquisitionBusy(Boolean(status.running));
  if (status.files && status.files.length) {
    acquisitionFilesEl.textContent = "Files: " + status.files.join(", ");
  }
  setStatus(status.running ? message : (status.ok ? "Complete" : "Ready"));
}

function formatDn(value, digits = 0) {
  if (!Number.isFinite(value)) return "--";
  return digits ? value.toFixed(digits) : Math.round(value).toString();
}

function frameStatsHtml(stats) {
  const maxLocation = Number.isFinite(stats.max_x) && Number.isFinite(stats.max_y)
    ? ` (${stats.max_x}, ${stats.max_y})`
    : "";
  const rows = [
    ["Brightest", `${formatDn(stats.max_dn)} DN${maxLocation}`],
    ["Mean", `${formatDn(stats.mean_dn, 1)} DN`],
    ["Median", `${formatDn(stats.median_dn, 1)} DN`],
    ["99.9%", `${formatDn(stats.p999_dn, 1)} DN`],
    ["99%", `${formatDn(stats.p99_dn, 1)} DN`],
    ["Range", stats.valid_range || "0-1023"],
  ];
  const validRange = stats.valid_range
    || `${Number.isFinite(stats.valid_min_dn) ? stats.valid_min_dn : 0}-${Number.isFinite(stats.valid_max_dn) ? stats.valid_max_dn : 1023}`;
  const bitDepth = Number.isFinite(stats.bit_depth) ? `${stats.bit_depth}-bit` : "current";
  return rows.map(([label, value]) => (
    `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`
  )).join("") + `<p class="stats-note">Brightness values are linear decoded DN for this frame; valid range is ${validRange} for the ${bitDepth} camera mode.</p>`;
}

function renderFrameStats(preview) {
  const stats = preview && preview.frame_stats;
  if (!stats) {
    frameStatsEl.classList.add("hidden");
    frameStatsEl.textContent = "";
    return;
  }
  frameStatsEl.innerHTML = frameStatsHtml(stats);
  frameStatsEl.classList.remove("hidden");
}

async function fetchAcquisitionStatus() {
  const res = await fetch("/api/acquisition/status?ts=" + Date.now());
  const j = await res.json();
  if (j.ok) renderAcquisitionStatus(j.status || {});
  return j;
}

async function pollAcquisitionStatus() {
  try {
    await fetchAcquisitionStatus();
  } catch (e) {
    acquisitionMsgEl.textContent = "Error: " + e;
  }
}

function renderFocusStatus(status) {
  const wasRunning = focusRunning;
  focusRunning = Boolean(status && status.running);
  focusMsgEl.textContent = status && status.message ? status.message : "Focus video idle";
  const focusingSelected = captureMode() === "focusing";
  focusIndicatorEl.classList.toggle("hidden", !focusingSelected);
  const score = Number(status && status.focus_score);
  const best = Number(status && status.best_focus_score);
  const relative = Number(status && status.relative_focus_percent);
  if (focusingSelected && Number.isFinite(score) && Number.isFinite(best) && best > 0) {
    const usableRelative = Math.max(0, Math.min(100, relative));
    const quality = usableRelative >= 97 ? "Best seen" : usableRelative >= 85 ? "Near best" : usableRelative >= 65 ? "Below best" : "Soft";
    focusQualityEl.textContent = `${quality} — ${usableRelative.toFixed(0)}%`;
    focusScoreEl.textContent = `Score ${score.toFixed(1)} · best ${best.toFixed(1)}`;
    focusMeterFillEl.style.width = `${usableRelative}%`;
    focusIndicatorEl.querySelector(".focus-meter").setAttribute("aria-valuenow", usableRelative.toFixed(0));
  } else if (focusingSelected) {
    focusQualityEl.textContent = "Measuring sharpness...";
    focusScoreEl.textContent = "";
    focusMeterFillEl.style.width = "0%";
    focusIndicatorEl.querySelector(".focus-meter").setAttribute("aria-valuenow", "0");
  }
  setAcquisitionBusy(Boolean(lastAcquisitionStatus.running));
  if (wasRunning && !focusRunning) {
    previewEl.src = "/api/preview.jpg?ts=" + Date.now();
  }
}

async function pollFocusStatus() {
  try {
    const res = await fetch("/api/focus/status?ts=" + Date.now());
    const j = await res.json();
    if (j.ok) renderFocusStatus(j.status || {});
  } catch (e) {
    focusMsgEl.textContent = "Focus status unavailable: " + e;
  }
}

async function startFocusVideo() {
  focusMsgEl.textContent = "Starting focus video...";
  focusIndicatorEl.classList.remove("hidden");
  focusQualityEl.textContent = "Measuring sharpness...";
  focusScoreEl.textContent = "";
  focusMeterFillEl.style.width = "0%";
  try {
    saveGateWidthProfile("targeting");
    const targetingShutterUs = clampGateWidthUs(q("#targeting_gate_width").value, 1000);
    const j = await postJSON("/api/focus/start", {
      fps: 12,
      width: 728,
      height: 544,
      image_rotation_degrees: imageRotationDegrees(),
      shutter_us: targetingShutterUs,
    });
    if (!j.ok) {
      focusMsgEl.textContent = "Error: " + (j.error || "focus video failed to start");
      return;
    }
    renderFocusStatus(j.status || {});
    focusMsgEl.textContent = `Focus video running with ${targetingShutterUs} us targeting exposure`;
    renderFrameStats(null);
    restorePreviewView();
    previewEl.src = "/api/focus/stream.mjpg?ts=" + Date.now();
  } catch (e) {
    focusMsgEl.textContent = "Error: " + e;
  }
}

async function stopFocusVideo() {
  focusMsgEl.textContent = "Stopping focus video...";
  try {
    const j = await postJSON("/api/focus/stop", {});
    if (!j.ok) {
      focusMsgEl.textContent = "Error: " + (j.error || "focus video failed to stop");
      return;
    }
    renderFocusStatus(j.status || {});
  } catch (e) {
    focusMsgEl.textContent = "Error: " + e;
  }
}

async function handleCaptureModeChange() {
  const mode = captureMode();
  focusIndicatorEl.classList.toggle("hidden", mode !== "focusing");
  setAcquisitionBusy(Boolean(lastAcquisitionStatus.running));
  if (mode === "focusing") {
    if (!focusRunning) {
      await startFocusVideo();
    } else {
      focusMsgEl.textContent = "Focus video running";
      renderFrameStats(null);
      restorePreviewView();
      previewEl.src = "/api/focus/stream.mjpg?ts=" + Date.now();
    }
    return;
  }
  if (focusRunning) await stopFocusVideo();
  await loadEspStatus();
}

async function armAcquisition() {
  captureMsgEl.textContent = "";
  acquisitionFilesEl.textContent = "";
  acquisitionMsgEl.textContent = "Arming...";
  setAcquisitionBusy(true);
  setStatus("Arming");
  try {
    await applyGateSettings();
    const j = await postJSON("/api/acquisition/start", acquisitionPayload());
    if (!j.ok) {
      acquisitionMsgEl.textContent = "Error: " + (j.error || "arm failed");
      setAcquisitionBusy(false);
      setStatus("Arm failed");
      return;
    }
    renderAcquisitionStatus(j.status || {});
  } catch (e) {
    acquisitionMsgEl.textContent = "Error: " + e;
    setAcquisitionBusy(false);
    setStatus("Arm failed");
  }
}

async function stopAcquisition() {
  stopButton.disabled = true;
  acquisitionMsgEl.textContent = "Stopping...";
  setStatus("Stopping");
  try {
    const j = await postJSON("/api/acquisition/stop", {});
    if (!j.ok) {
      acquisitionMsgEl.textContent = "Error: " + (j.error || "stop failed");
      return;
    }
    renderAcquisitionStatus(j.status || {});
    refreshFiles();
  } catch (e) {
    acquisitionMsgEl.textContent = "Error: " + e;
  }
}

async function capture() {
  const mode = captureMode();
  captureMsgEl.textContent = mode === "dosimetry" ? "Sending dosimetry test trigger..." : "Capturing preview frame...";
  try {
    await applyGateSettings();
    const statusResult = await fetchAcquisitionStatus();
    const running = Boolean(statusResult.ok && statusResult.status && statusResult.status.running);
    if (mode === "dosimetry" && running) {
      const j = await postJSON("/api/acquisition/test_trigger", { width_us: 1000 });
      if (!j.ok) {
        captureMsgEl.textContent = "Error: " + (j.error || "test trigger failed");
        setStatus("Capture failed");
        return;
      }
      renderAcquisitionStatus(j.status || {});
      const stillRunning = Boolean(j.status && j.status.running);
      captureMsgEl.textContent = stillRunning
        ? "Sent one dosimetry test trigger"
        : `Sent one dosimetry test trigger; acquisition ${j.status && j.status.message ? j.status.message.toLowerCase() : "stopped"}`;
      return;
    }
    const j = await postJSON("/api/acquisition/capture_preview", {
      ...acquisitionPayload(),
      width_us: 1000,
      preview_timeout_s: 5,
    });
    if (!j.ok) {
      captureMsgEl.textContent = "Error: " + (j.error || "capture failed");
      setStatus("Capture failed");
      return;
    }
    const frameNumber = (j.preview && Number.isFinite(j.preview.frame_index))
      ? j.preview.frame_index + 1
      : "";
    captureMsgEl.textContent = frameNumber ? `Displayed frame ${frameNumber}` : "Displayed latest frame";
    renderFrameStats(j.preview);
    restorePreviewView();
    previewEl.src = "/api/preview.jpg?ts=" + Date.now();
    renderAcquisitionStatus(j.status || {});
  } catch (e) {
    captureMsgEl.textContent = "Error: " + e;
    setStatus("Capture failed");
  }
}

async function updatePreview() {
  captureMsgEl.textContent = "Updating image...";
  try {
    const j = await postJSON("/api/acquisition/update_preview", {
      timeout_s: 0,
      image_rotation_degrees: imageRotationDegrees(),
    });
    if (!j.ok) {
      captureMsgEl.textContent = "Error: " + (j.error || "no frame available");
      return;
    }
    const frameNumber = (j.preview && Number.isFinite(j.preview.frame_index))
      ? j.preview.frame_index + 1
      : "";
    captureMsgEl.textContent = frameNumber ? `Displayed frame ${frameNumber}` : "Displayed latest frame";
    renderFrameStats(j.preview);
    restorePreviewView();
    previewEl.src = "/api/preview.jpg?ts=" + Date.now();
    renderAcquisitionStatus(j.status || {});
  } catch (e) {
    captureMsgEl.textContent = "Error: " + e;
  }
}

function downloadMatchingBase() {
  const base = q("#batch_base").value || DEFAULT_SAVE_BASE;
  prepareArchive("run", base);
}

function downloadMatchingBaseAsPngZip() {
  const params = new URLSearchParams({
    base: q("#batch_base").value || DEFAULT_SAVE_BASE,
    format: "png_zip",
    rotation: String(imageRotationDegrees()),
  });
  prepareArchive("run", params.get("base"), "png_zip", imageRotationDegrees());
}

function downloadSavedFile(path) {
  window.location.href = "/api/files/download?path=" + encodeURIComponent(path);
}

function downloadSavedFileAsPngZip(path) {
  const params = new URLSearchParams({
    path,
    rotation: String(imageRotationDegrees()),
  });
  prepareArchive("file", path, "png_zip", imageRotationDegrees());
}

function downloadDirectory(path = currentFilesPath) {
  prepareArchive("directory", path || "");
}

function downloadDirectoryAsPngZip(path = currentFilesPath) {
  const params = new URLSearchParams({
    path: path || "",
    format: "png_zip",
    rotation: String(imageRotationDegrees()),
  });
  prepareArchive("directory", path || "", "png_zip", imageRotationDegrees());
}

async function openTextViewer(path) {
  fileViewerState = { path, type: "text", frame: -1, frames: 0 };
  fileViewerEl.classList.remove("hidden");
  fileViewerEl.classList.add("text-mode");
  fileViewerTitleEl.textContent = path;
  fileViewerMsgEl.textContent = "Loading text...";
  fileViewerImageEl.removeAttribute("src");
  fileViewerStatsEl.classList.add("hidden");
  restoreFileViewerView();
  try {
    const res = await fetch("/api/files/text?path=" + encodeURIComponent(path) + "&ts=" + Date.now());
    const j = await res.json();
    if (!j.ok) {
      fileViewerMsgEl.textContent = "Error: " + (j.error || "text load failed");
      return;
    }
    fileViewerMsgEl.textContent = `${j.name}: ${formatSize(j.size)}`;
    fileViewerStatsEl.classList.remove("hidden");
    fileViewerStatsEl.innerHTML = `<pre class="text-viewer"></pre>`;
    fileViewerStatsEl.querySelector("pre").textContent = j.text;
    q("#btnViewerPrev").disabled = true;
    q("#btnViewerNext").disabled = true;
    q("#btnViewerFirst").disabled = true;
    q("#btnViewerGo").disabled = true;
    q("#btnViewerLatest").disabled = true;
    viewerFrameInputEl.disabled = true;
    fileViewerEl.scrollIntoView({ block: "nearest" });
  } catch (e) {
    fileViewerMsgEl.textContent = "Error: " + e;
  }
}

async function openRawViewer(path, frame = -1) {
  fileViewerState = { path, type: "raw", frame, frames: 0 };
  fileViewerEl.classList.remove("hidden");
  fileViewerEl.classList.remove("text-mode");
  viewerFrameInputEl.disabled = false;
  q("#btnViewerGo").disabled = false;
  restoreFileViewerView();
  await loadRawViewerFrame(frame);
  fileViewerEl.scrollIntoView({ block: "nearest" });
}

async function loadRawViewerFrame(frame) {
  if (!fileViewerState.path) return;
  fileViewerMsgEl.textContent = "Loading frame...";
  fileViewerStatsEl.classList.add("hidden");
  const params = new URLSearchParams({
    path: fileViewerState.path,
    frame: String(frame),
    rotation: String(imageRotationDegrees()),
    ts: String(Date.now()),
  });
  try {
    const res = await fetch("/api/files/raw_frame?" + params.toString());
    const j = await res.json();
    if (!j.ok) {
      fileViewerMsgEl.textContent = "Error: " + (j.error || "frame load failed");
      return;
    }
    fileViewerState.frame = j.frame_index;
    fileViewerState.frames = j.frames_available;
    viewerFrameInputEl.max = j.frames_available;
    viewerFrameInputEl.value = j.frame_index + 1;
    fileViewerTitleEl.textContent = fileViewerState.path;
    fileViewerMsgEl.textContent = `Frame ${j.frame_index + 1} of ${j.frames_available}`;
    if (j.trailing_bytes) {
      fileViewerMsgEl.textContent += `; ${j.trailing_bytes} trailing bytes not shown`;
    }
    fileViewerImageEl.src = "/api/files/raw_frame.png?" + params.toString();
    if (j.frame_stats) {
      fileViewerStatsEl.innerHTML = frameStatsHtml(j.frame_stats);
      fileViewerStatsEl.classList.remove("hidden");
    }
    q("#btnViewerFirst").disabled = j.frame_index <= 0;
    q("#btnViewerPrev").disabled = j.frame_index <= 0;
    q("#btnViewerNext").disabled = j.frame_index >= j.frames_available - 1;
    q("#btnViewerLatest").disabled = false;
  } catch (e) {
    fileViewerMsgEl.textContent = "Error: " + e;
  }
}

function closeRawViewer() {
  fileViewerState = { path: "", type: "", frame: -1, frames: 0 };
  fileViewerImageEl.removeAttribute("src");
  fileViewerStatsEl.classList.add("hidden");
  fileViewerEl.classList.add("hidden");
  fileViewerEl.classList.remove("text-mode");
  restoreFileViewerView();
}

function goToViewerFrameFromInput() {
  const requested = parseInt(viewerFrameInputEl.value || "1", 10);
  const frame = Math.max(1, Math.min(requested, fileViewerState.frames || 1)) - 1;
  loadRawViewerFrame(frame);
}

function joinSaveBase(directory, stem = "run") {
  const cleanDir = (directory || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  return cleanDir ? `${cleanDir}/${stem}` : stem;
}

async function loadSaveDirectoryPicker(path = currentSaveDirPath) {
  saveDirMsgEl.textContent = "Loading...";
  saveDirListEl.textContent = "";
  saveDirPathEl.textContent = "/" + (path || "");
  try {
    const res = await fetch("/api/files?path=" + encodeURIComponent(path || "") + "&ts=" + Date.now());
    const j = await res.json();
    if (!j.ok) {
      saveDirMsgEl.textContent = "Error: " + (j.error || "directory list failed");
      return;
    }
    currentSaveDirPath = j.path || "";
    saveDirPathEl.textContent = "/" + currentSaveDirPath;
    q("#btnSaveDirUp").disabled = !currentSaveDirPath;
    saveDirListEl.innerHTML = "";

    if (!(j.directories || []).length) {
      const empty = document.createElement("div");
      empty.className = "directory-row";
      empty.textContent = "No subfolders";
      saveDirListEl.append(empty);
    }

    (j.directories || []).forEach(dir => {
      const row = document.createElement("div");
      row.className = "directory-row";

      const name = document.createElement("span");
      name.textContent = dir.name;

      const openButton = document.createElement("button");
      openButton.type = "button";
      openButton.textContent = "Open";
      openButton.addEventListener("click", () => loadSaveDirectoryPicker(dir.path));

      row.append(name, openButton);
      saveDirListEl.append(row);
    });
    saveDirMsgEl.textContent = "Save base will use this folder with base name run.";
  } catch (e) {
    saveDirMsgEl.textContent = "Error: " + e;
  }
}

function openSaveDirectoryPicker() {
  const base = q("#batch_base").value || DEFAULT_SAVE_BASE;
  const parts = base.replace(/\\/g, "/").split("/").filter(Boolean);
  parts.pop();
  currentSaveDirPath = parts.join("/");
  saveDirPickerEl.classList.remove("hidden");
  loadSaveDirectoryPicker(currentSaveDirPath);
}

function closeSaveDirectoryPicker() {
  saveDirPickerEl.classList.add("hidden");
}

async function createSaveDirectory() {
  const name = window.prompt("New folder name");
  if (!name) return;
  const clean = name.replace(/\\/g, "/").split("/").filter(part => part && part !== "." && part !== "..").join("/");
  if (!clean) {
    saveDirMsgEl.textContent = "Folder name is empty or invalid.";
    return;
  }
  const path = currentSaveDirPath ? `${currentSaveDirPath}/${clean}` : clean;
  saveDirMsgEl.textContent = "Creating folder...";
  try {
    const j = await postJSON("/api/files/mkdir", { path });
    if (!j.ok) {
      saveDirMsgEl.textContent = "Error: " + (j.error || "folder create failed");
      return;
    }
    await loadSaveDirectoryPicker(j.path || currentSaveDirPath);
  } catch (e) {
    saveDirMsgEl.textContent = "Error: " + e;
  }
}

function useSaveDirectory() {
  q("#batch_base").value = joinSaveBase(currentSaveDirPath, "run");
  closeSaveDirectoryPicker();
}

async function deleteSavedPath(path, type) {
  const label = path || "/";
  const message = type === "directory"
    ? `Delete folder "${label}" and all files inside it? This cannot be undone.`
    : `Delete file "${label}"? This cannot be undone.`;
  if (confirmDeleteEl.checked && !window.confirm(message)) return;

  filesMsgEl.textContent = "Deleting...";
  try {
    const j = await postJSON("/api/files/delete", { path, type });
    if (!j.ok) {
      filesMsgEl.textContent = "Error: " + (j.error || "delete failed");
      return;
    }
    filesMsgEl.textContent = "Deleted: " + j.deleted;
    refreshFiles();
  } catch (e) {
    filesMsgEl.textContent = "Error: " + e;
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatTime(seconds) {
  return new Date(seconds * 1000).toLocaleString();
}

// Compact local date-time for the file list: 2026-10-27 09:32:27
function formatStamp(seconds) {
  if (seconds === null || seconds === undefined) return "";
  const d = new Date(seconds * 1000);
  const p = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

async function refreshFiles() {
  filesMsgEl.textContent = "Loading...";
  filesListEl.textContent = "";
  filesPathEl.textContent = "/" + (currentFilesPath || "");
  try {
    const res = await fetch("/api/files?path=" + encodeURIComponent(currentFilesPath) + "&ts=" + Date.now());
    const j = await res.json();
    if (!j.ok) {
      filesMsgEl.textContent = "Error: " + (j.error || "file list failed");
      return;
    }
    currentFilesPath = j.path || "";
    filesPathEl.textContent = "/" + currentFilesPath;
    q("#btnUpFiles").disabled = !currentFilesPath;
    const dirCount = (j.directories || []).length;
    const fileCount = (j.files || []).length;
    filesMsgEl.textContent = `${dirCount} folder${dirCount === 1 ? "" : "s"}, ${fileCount} file${fileCount === 1 ? "" : "s"}`;
    filesListEl.innerHTML = "";
    if (dirCount || fileCount) {
      const head = document.createElement("div");
      head.className = "file-row file-head";
      ["Name", "Modified", "Size", ""].forEach(label => {
        const cell = document.createElement("div");
        cell.textContent = label;
        head.append(cell);
      });
      filesListEl.append(head);
    }

    (j.directories || []).forEach(dir => {
      const row = document.createElement("div");
      row.className = "file-row directory";

      const name = document.createElement("div");
      name.className = "file-name";
      name.textContent = "[dir] " + dir.name;

      const modified = document.createElement("div");
      modified.className = "file-date";
      modified.textContent = dir.file_count ? formatStamp(dir.latest_mtime) : "empty";

      const size = document.createElement("div");
      size.textContent = `${dir.file_count || 0} file${dir.file_count === 1 ? "" : "s"}`;

      const actions = document.createElement("div");
      actions.className = "button-row";

      const openButton = document.createElement("button");
      openButton.textContent = "Open";
      openButton.addEventListener("click", () => {
        currentFilesPath = dir.path;
        refreshFiles();
      });

      const downloadButton = document.createElement("button");
      downloadButton.textContent = "ZIP";
      downloadButton.addEventListener("click", () => downloadDirectory(dir.path));

      const pngZipButton = document.createElement("button");
      pngZipButton.textContent = "PNG ZIP";
      pngZipButton.addEventListener("click", () => downloadDirectoryAsPngZip(dir.path));

      const deleteButton = document.createElement("button");
      deleteButton.textContent = "Delete";
      deleteButton.addEventListener("click", () => deleteSavedPath(dir.path, "directory"));

      actions.append(openButton, downloadButton, pngZipButton, deleteButton);
      row.title = (dir.file_count ? `Newest file inside: ${formatTime(dir.latest_mtime)}\n` : "Empty folder\n")
        + `Folder entry changed: ${formatTime(dir.mtime)}`;
      row.append(name, modified, size, actions);
      filesListEl.append(row);
    });

    (j.files || []).forEach(file => {
      const row = document.createElement("div");
      row.className = "file-row";

      const name = document.createElement("div");
      name.className = "file-name";
      name.textContent = file.name;

      const modified = document.createElement("div");
      modified.className = "file-date";
      modified.textContent = formatStamp(file.mtime);

      const size = document.createElement("div");
      size.textContent = formatSize(file.size);

      const downloadButton = document.createElement("button");
      downloadButton.textContent = "Download";
      downloadButton.addEventListener("click", () => downloadSavedFile(file.path));

      const viewButton = document.createElement("button");
      viewButton.textContent = "View";
      viewButton.title = "Open this raw stream in the frame viewer";
      viewButton.addEventListener("click", () => openRawViewer(file.path));

      const textViewButton = document.createElement("button");
      textViewButton.textContent = "View";
      textViewButton.title = "Open this text file in the viewer";
      textViewButton.addEventListener("click", () => openTextViewer(file.path));

      const pngZipButton = document.createElement("button");
      pngZipButton.textContent = "PNG ZIP";
      pngZipButton.title = "Download all complete raw frames as autoscaled PNG images plus matching JSON";
      pngZipButton.addEventListener("click", () => downloadSavedFileAsPngZip(file.path));

      const deleteButton = document.createElement("button");
      deleteButton.textContent = "Delete";
      deleteButton.addEventListener("click", () => deleteSavedPath(file.path, "file"));

      const actions = document.createElement("div");
      actions.className = "button-row";
      const lowerName = file.name.toLowerCase();
      actions.append(downloadButton);
      if (lowerName.endsWith(".raw")) actions.append(viewButton, pngZipButton);
      if (lowerName.endsWith(".json") || lowerName.endsWith(".log") || lowerName.endsWith(".txt")) {
        actions.append(textViewButton);
      }
      actions.append(deleteButton);

      row.title = `Modified ${formatTime(file.mtime)}`;
      row.append(name, modified, size, actions);
      filesListEl.append(row);
    });
  } catch (e) {
    filesMsgEl.textContent = "Error: " + e;
  }
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const id = tab.dataset.tab;
      document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === tab));
      document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.toggle("active", panel.id === `tab-${id}`);
      });
      if (id === "files") refreshFiles();
    });
  });
}

q("#btnBatchStart").addEventListener("click", armAcquisition);
q("#btnBatchCancel").addEventListener("click", stopAcquisition);
q("#btnCap").addEventListener("click", capture);
q("#btnUpdatePreview").addEventListener("click", updatePreview);
q("#btnDownloadBase").addEventListener("click", downloadMatchingBase);
q("#btnDownloadBasePngZip").addEventListener("click", downloadMatchingBaseAsPngZip);
q("#btnBrowseSaveBase").addEventListener("click", openSaveDirectoryPicker);
q("#btnCloseSaveDir").addEventListener("click", closeSaveDirectoryPicker);
q("#btnSaveDirUp").addEventListener("click", () => {
  if (!currentSaveDirPath) return;
  const parts = currentSaveDirPath.split("/").filter(Boolean);
  parts.pop();
  loadSaveDirectoryPicker(parts.join("/"));
});
q("#btnSaveDirNew").addEventListener("click", createSaveDirectory);
q("#btnUseSaveDir").addEventListener("click", useSaveDirectory);
q("#btnRefreshFiles").addEventListener("click", refreshFiles);
q("#btnUpFiles").addEventListener("click", () => {
  if (!currentFilesPath) return;
  const parts = currentFilesPath.split("/").filter(Boolean);
  parts.pop();
  currentFilesPath = parts.join("/");
  refreshFiles();
});
q("#btnDownloadDir").addEventListener("click", () => downloadDirectory());
q("#btnDownloadDirPngZip").addEventListener("click", () => downloadDirectoryAsPngZip());
q("#btnViewerFirst").addEventListener("click", () => loadRawViewerFrame(0));
q("#btnViewerPrev").addEventListener("click", () => loadRawViewerFrame(fileViewerState.frame - 1));
q("#btnViewerGo").addEventListener("click", goToViewerFrameFromInput);
q("#btnViewerNext").addEventListener("click", () => loadRawViewerFrame(fileViewerState.frame + 1));
q("#btnViewerLatest").addEventListener("click", () => loadRawViewerFrame(-1));
q("#btnViewerClose").addEventListener("click", closeRawViewer);
q("#btnViewerRestore").addEventListener("click", restoreFileViewerView);
viewerFrameInputEl.addEventListener("keydown", event => {
  if (event.key === "Enter") goToViewerFrameFromInput();
});
q("#btnRestoreView").addEventListener("click", restorePreviewView);
confirmDeleteEl.addEventListener("change", () => {
  writeLocalSetting("dosecam_confirm_delete", confirmDeleteEl.checked ? "1" : "0");
});

previewWrapEl.addEventListener("pointerdown", event => {
  if (previewDragMode() === "native") return;
  if (event.target.closest(".preview-toolbar") || !previewEl.getAttribute("src")) return;
  event.preventDefault();
  zoomDrag = { start: previewPoint(event), pointerId: event.pointerId };
  previewWrapEl.setPointerCapture(event.pointerId);
  renderZoomSelection(zoomDrag.start, zoomDrag.start);
});

previewWrapEl.addEventListener("pointermove", event => {
  if (previewDragMode() === "native") return;
  if (!zoomDrag || zoomDrag.pointerId !== event.pointerId) return;
  event.preventDefault();
  renderZoomSelection(zoomDrag.start, previewPoint(event));
});

previewWrapEl.addEventListener("pointerup", event => {
  if (previewDragMode() === "native") return;
  if (!zoomDrag || zoomDrag.pointerId !== event.pointerId) return;
  event.preventDefault();
  const start = zoomDrag.start;
  const end = previewPoint(event);
  zoomDrag = null;
  previewWrapEl.releasePointerCapture(event.pointerId);
  applyPreviewZoom(start, end);
});

previewWrapEl.addEventListener("pointercancel", event => {
  if (previewDragMode() === "native") return;
  if (zoomDrag && zoomDrag.pointerId === event.pointerId) {
    event.preventDefault();
    zoomDrag = null;
    zoomSelectionEl.style.display = "none";
  }
});

previewWrapEl.addEventListener("dragstart", event => {
  if (previewDragMode() !== "native") event.preventDefault();
});

fileViewerStageEl.addEventListener("pointerdown", event => {
  if (fileViewerState.type !== "raw" || previewDragMode() === "native") return;
  if (!fileViewerImageEl.getAttribute("src")) return;
  event.preventDefault();
  fileViewerZoomDrag = { start: fileViewerPoint(event), pointerId: event.pointerId };
  fileViewerStageEl.setPointerCapture(event.pointerId);
  renderFileViewerZoomSelection(fileViewerZoomDrag.start, fileViewerZoomDrag.start);
});

fileViewerStageEl.addEventListener("pointermove", event => {
  if (fileViewerState.type !== "raw" || previewDragMode() === "native") return;
  if (!fileViewerZoomDrag || fileViewerZoomDrag.pointerId !== event.pointerId) return;
  event.preventDefault();
  renderFileViewerZoomSelection(fileViewerZoomDrag.start, fileViewerPoint(event));
});

fileViewerStageEl.addEventListener("pointerup", event => {
  if (fileViewerState.type !== "raw" || previewDragMode() === "native") return;
  if (!fileViewerZoomDrag || fileViewerZoomDrag.pointerId !== event.pointerId) return;
  event.preventDefault();
  const start = fileViewerZoomDrag.start;
  const end = fileViewerPoint(event);
  fileViewerZoomDrag = null;
  fileViewerStageEl.releasePointerCapture(event.pointerId);
  applyFileViewerZoom(start, end);
});

fileViewerStageEl.addEventListener("pointercancel", event => {
  if (fileViewerZoomDrag && fileViewerZoomDrag.pointerId === event.pointerId) {
    event.preventDefault();
    fileViewerZoomDrag = null;
    fileViewerZoomSelectionEl.style.display = "none";
  }
});

fileViewerStageEl.addEventListener("dragstart", event => {
  if (previewDragMode() !== "native") event.preventDefault();
});

q("#image_rotation").addEventListener("change", () => {
  writeLocalSetting("dosecam_image_rotation", q("#image_rotation").value);
});

q("#preview_drag_mode").addEventListener("change", () => {
  writeLocalSetting("dosecam_preview_drag_mode", previewDragMode());
  applyPreviewDragMode();
  applyFileViewerDragMode();
});

outputEnabledEl.addEventListener("change", async () => {
  const enabled = outputEnabledEl.checked;
  const j = await postJSON(enabled ? "/api/enable_output" : "/api/disable_output");
  if (j.ok) {
    outputEnabledEl.checked = Boolean(j.enabled);
    espMsgEl.textContent = j.enabled ? "ESP shutter output enabled" : "ESP shutter output disabled";
    return;
  }
  outputEnabledEl.checked = !enabled;
  espMsgEl.textContent = `Error: ${j.error || "output update failed"}`;
});

q("#input_trigger_active_high").addEventListener("change", async () => {
  const level = q("#input_trigger_active_high").checked ? 1 : 0;
  const j = await postJSON("/api/input_trigger_level", { level });
  espMsgEl.textContent = j.ok
    ? `ESP input trigger active ${j.input_active_level}`
    : `Error: ${j.error}`;
});

q("#capture_mode").addEventListener("change", handleCaptureModeChange);
q("#batch_frames").addEventListener("change", () => {
  q("#batch_frames").value = clampMaxFrames(q("#batch_frames").value);
});
q("#targeting_gate_width").addEventListener("change", () => saveGateWidthProfile("targeting"));
q("#dosimetry_gate_width").addEventListener("change", () => saveGateWidthProfile("dosimetry"));

bindTabs();
const savedRotation = readLocalSetting("dosecam_image_rotation");
if (["0", "90", "180", "270"].includes(savedRotation)) {
  q("#image_rotation").value = savedRotation;
}
const savedPreviewDragMode = readLocalSetting("dosecam_preview_drag_mode");
if (["zoom", "native"].includes(savedPreviewDragMode)) {
  q("#preview_drag_mode").value = savedPreviewDragMode;
}
const savedConfirmDelete = readLocalSetting("dosecam_confirm_delete");
if (savedConfirmDelete === "0") {
  confirmDeleteEl.checked = false;
}
const savedTargetingGate = readLocalSetting("dosecam_targeting_gate_width_us");
if (savedTargetingGate) {
  q("#targeting_gate_width").value = clampGateWidthUs(savedTargetingGate, 1000);
  saveGateWidthProfile("targeting");
}
const savedDosimetryGate = readLocalSetting("dosecam_dosimetry_gate_width_us");
if (savedDosimetryGate) {
  q("#dosimetry_gate_width").value = clampGateWidthUs(savedDosimetryGate, 100);
  saveGateWidthProfile("dosimetry");
}
applyPreviewDragMode();
applyFileViewerDragMode();
updateRestoreViewControl();
updateFileViewerRestoreControl();
loadEspStatus();
pollAcquisitionStatus();
pollFocusStatus();
setInterval(pollAcquisitionStatus, 1000);
setInterval(pollFocusStatus, 1000);
setStatus("Ready");
