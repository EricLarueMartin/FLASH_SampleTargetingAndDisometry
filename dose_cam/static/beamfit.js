/* Beam-profile background subtraction + 2D Gaussian fit.
   Added 2026-10-14. Mounts into #beamFitMain (Capture tab) and
   #beamFitViewer (Files tab viewer). Scale is DN until dn_calibration.json
   supplies dn_per_gy. Rollback: /home/codex/backups/restore_dose_cam.sh */
(function () {
  "use strict";

  var NBSP = "&nbsp;";

  function el(id) { return document.getElementById(id); }
  function rotation() {
    var r = el("image_rotation");
    return r ? parseInt(r.value || "180", 10) : 180;
  }
  function fmt(v, d) {
    if (v === null || v === undefined || !isFinite(v)) return "--";
    var a = Math.abs(v);
    if (a !== 0 && (a < 1e-2 || a >= 1e6)) return Number(v).toExponential(3);
    return Number(v).toFixed(d === undefined ? 2 : d);
  }

  function panelHtml(ns) {
    return '' +
      '<div class="beamfit">' +
      '  <div class="beamfit-head">Beam profile fit' +
      '    <span class="beamfit-units" id="' + ns + '_units">DN</span></div>' +
      '  <div class="beamfit-row">' +
      '    <label>Background' +
      '      <select id="' + ns + '_bg">' +
      '        <option value="none">None (fitted offset only)</option>' +
      '        <option value="baseline" selected>Local baseline (polynomial)</option>' +
      '        <option value="file">Reference capture</option>' +
      '      </select></label>' +
      '  </div>' +
      '  <div class="beamfit-row beamfit-bgfile hidden" id="' + ns + '_bgfilerow">' +
      '    <label>Ref .raw path<input id="' + ns + '_bgpath" type="text" placeholder="FLASH/background_000001.raw"></label>' +
      '    <label>Frames<input id="' + ns + '_bgframes" type="number" min="0" step="1" value="0" title="0 = all frames in the file"></label>' +
      '  </div>' +
      '  <div class="beamfit-row">' +
      '    <label>Baseline order<select id="' + ns + '_order">' +
      '      <option value="1">1 (plane)</option><option value="2" selected>2 (quadratic)</option></select></label>' +
      '    <label>Despike &gt;<input id="' + ns + '_despike" type="number" min="0" step="1" value="40" title="DN above the 3x3 median; removes direct radiation hits. 0 disables."> DN</label>' +
      '  </div>' +
      '  <div class="beamfit-row">' +
      '    <label class="check"><input id="' + ns + '_manualroi" type="checkbox"> Manual ROI</label>' +
      '    <button id="' + ns + '_draw" type="button" class="beamfit-mini" title="Arms one drag on the image to set the ROI; zoom drag works normally otherwise">Draw ROI on image</button>' +
      '    <button id="' + ns + '_auto' + '" type="button" class="beamfit-mini">Reset to auto</button>' +
      '  </div>' +
      '  <div class="beamfit-row hidden" id="' + ns + '_roirow">' +
      '    <label>x<input id="' + ns + '_rx" type="number" step="1" value="0"></label>' +
      '    <label>y<input id="' + ns + '_ry" type="number" step="1" value="0"></label>' +
      '    <label>w<input id="' + ns + '_rw" type="number" step="1" value="520"></label>' +
      '    <label>h<input id="' + ns + '_rh" type="number" step="1" value="520"></label>' +
      '  </div>' +
      '  <div class="beamfit-row">' +
      '    <label class="check"><input id="' + ns + '_show" type="checkbox" checked> Show subtracted image + ellipse</label>' +
      '  </div>' +
      '  <div class="beamfit-row">' +
      '    <label class="check"><input id="' + ns + '_sup" type="checkbox"> Suppress peak (background view), out to' +
      '      <input id="' + ns + '_supn" type="number" min="1" step="0.5" value="3" class="beamfit-narrow"> sigma</label>' +
      '  </div>' +
      '  <div class="button-row">' +
      '    <button id="' + ns + '_fit" type="button">Fit beam profile</button>' +
      '    <button id="' + ns + '_restore" type="button" class="beamfit-mini">Restore image</button>' +
      '  </div>' +
      '  <div id="' + ns + '_msg" class="status"></div>' +
      '  <div id="' + ns + '_out" class="beamfit-out hidden"></div>' +
      '</div>';
  }

  // value +/- error, error to 2 significant figures and the value to match
  function pm(v, e, unit, dflt) {
    if (v === null || v === undefined || !isFinite(v)) return "--";
    var u = unit ? NBSP + unit : "";
    if (e === null || e === undefined || !isFinite(e) || e <= 0) return fmt(v, dflt) + u;
    var d = Math.max(0, Math.min(6, 1 - Math.floor(Math.log10(e))));
    return Number(v).toFixed(d) + NBSP + "&plusmn;" + NBSP + Number(e).toFixed(d) + u;
  }

  function resultHtml(j) {
    var f = j.fit, g = j.gy || {}, cal = j.calibration || {}, em = j.error_model || {};
    var useGy = !!(cal.dn_per_gy && cal.display_units === "Gy");
    // value cell: primary unit first, the other in parentheses
    function dual(dnVal, dnErr, gyVal, gyErr, dDn, dGy, dnUnit, gyUnit) {
      var dn = pm(dnVal, dnErr, dnUnit, dDn);
      if (gyVal === undefined || gyVal === null) return dn;
      var gy = pm(gyVal, gyErr, gyUnit, dGy);
      return useGy ? gy + ' <span class="beamfit-gy">(' + dn + ')</span>'
                   : dn + ' <span class="beamfit-gy">(' + gy + ')</span>';
    }
    function pair(a, ea, b, eb, unit, d) {
      return pm(a, ea, "", d) + ", " + pm(b, eb, "", d) + NBSP + unit;
    }
    var q = j.quality || {};
    var rows = [
      ["Amplitude A", dual(f.amplitude_dn, f.amplitude_err_dn, g.amplitude_gy, g.amplitude_gy_err, 2, 4, "DN", "Gy")],
      ["Centre (x, y)", pair(f.center_x, f.center_x_err, f.center_y, f.center_y_err, "px", 1)],
      ["Sigma (x, y)", pair(f.sigma_x, f.sigma_x_err, f.sigma_y, f.sigma_y_err, "px", 2)],
      ["FWHM (x, y)", pair(f.fwhm_x, f.fwhm_x_err, f.fwhm_y, f.fwhm_y_err, "px", 1)],
      ["Rotation", pm(f.theta_deg, f.theta_err_deg, "&deg;", 2)],
      ["Offset", dual(f.offset_dn, f.offset_err_dn, g.offset_gy, g.offset_gy_err, 3, 5, "DN", "Gy")],
      ["Integral (fit)", dual(f.integrated_dn_fit, f.integrated_dn_fit_err, g.integrated_gypx2_fit, g.integrated_gypx2_fit_err, 1, 2, "DN&middot;px&sup2;", "Gy&middot;px&sup2;")],
      ["Integral (ROI sum)", dual(f.integrated_dn_sum, null, g.integrated_gypx2_sum, g.integrated_gypx2_sum_err, 1, 2, "DN&middot;px&sup2;", "Gy&middot;px&sup2;")],
      ["&chi;&sup2; reduced", fmt(f.chi2_reduced, 3) + (q.verdict ? ' <span class="beamfit-verdict ' + q.cls + '">' + q.verdict + "</span>" : "")],
      ["R&sup2; (over ROI)", fmt(f.r_squared, 4)],
      ["RMS residual", dual(f.rms_residual_dn, null, g.rms_residual_gy, null, 3, 5, "DN", "Gy")],
      ["Noise &sigma;", dual(f.noise_sigma_dn, null, g.noise_sigma_gy, null, 3, 5, "DN", "Gy")],
      ["Converged", f.converged ? "yes (" + f.n_eval + " evals)" : "NO - treat with care"],
      ["ROI", j.roi.w + "&times;" + j.roi.h + " at (" + j.roi.x + ", " + j.roi.y + ") [" + j.roi.source + "]"],
      ["Background", j.background.mode + (j.background.frames_averaged ? " (" + j.background.frames_averaged + " frames)" : "")],
      ["Despiked px", j.despike.pixels_replaced + (j.saturated_pixels ? "; saturated " + j.saturated_pixels : "")]
    ];
    if (cal.dn_per_gy) {
      var ce = cal.dn_per_gy_err_pct;
      var calTxt = fmt(cal.dn_per_gy, 4) + NBSP + "DN/Gy" +
        (ce !== null && ce !== undefined ? " &plusmn; " + fmt(ce, 2) + "%" : " (uncertainty not set)") +
        (cal.err_stat_pct !== null && cal.err_stat_pct !== undefined
          ? " (stat " + fmt(cal.err_stat_pct, 2) + "%, sys " + fmt(cal.err_sys_pct, 2) + "%)" : "") +
        " [" + (cal.source || "custom") + "]";
      rows.push(["Calibration", calTxt]);
      rows.push(["Gy errors", em.calibration_included ? "fit &oplus; calibration" : "fit only (statistical)"]);
    }
    if (f.errors_available === false) rows.push(["Fit errors", "unavailable (singular covariance)"]);
    var html = '<table class="beamfit-table">';
    for (var i = 0; i < rows.length; i++) {
      html += "<tr><th>" + rows[i][0] + "</th><td>" + rows[i][1] + "</td></tr>";
    }
    html += "</table>";
    html += '<div class="beamfit-foot">Errors are 1&sigma;. Fit errors are statistical (fit covariance scaled by the residual variance) and assume independent pixels.</div>';
    if (j.roi_warning) html += '<div class="beamfit-warn">' + j.roi_warning + "</div>";
    return html;
  }

  function roiWarning(j) {
    // A local baseline is fitted to the ROI border; if the border sits on the
    // spot's tails the baseline absorbs them and sigma/amplitude come out low.
    if (!j.background || j.background.mode !== "baseline") return "";
    var f = j.fit, s = Math.max(f.sigma_x, f.sigma_y);
    var half = Math.min(j.roi.w, j.roi.h) / 2;
    if (half < 3 * s) {
      return "ROI half-width " + Math.round(half) + " px is under 3&sigma; (" + Math.round(3 * s) +
        " px). The local baseline is fitted to the ROI border, so it is likely absorbing the beam tails: " +
        "enlarge the ROI to at least " + Math.round(6 * s) + " px square, or use a reference-capture background.";
    }
    return "";
  }

  function quality(f) {
    var c = f.chi2_reduced;
    if (!f.converged) return { verdict: "did not converge", cls: "bad" };
    if (!isFinite(c)) return { verdict: "n/a", cls: "" };
    if (c < 0.5) return { verdict: "over-fit / noise overestimated", cls: "warn" };
    if (c <= 1.5) return { verdict: "good", cls: "good" };
    if (c <= 3.0) return { verdict: "fair", cls: "warn" };
    return { verdict: "poor - check ROI / background", cls: "bad" };
  }


  /* ---- one-shot ROI drawing ------------------------------------------
     Armed by the "Draw ROI on image" button. While armed, the next drag on
     the image draws a box instead of zooming; afterwards the page's own
     drag-to-zoom is untouched. Coordinates come from the image's on-screen
     rectangle, which already includes the CSS zoom/pan transform, and are
     converted to display-orientation frame pixels (what beam_fit expects). */
  function frameDims() {
    var r = rotation() % 360;
    return (r === 90 || r === 270) ? { w: 1088, h: 1456 } : { w: 1456, h: 1088 };
  }

  function clientToFrame(imageEl, cx, cy) {
    var rect = imageEl.getBoundingClientRect();
    var nw = imageEl.naturalWidth || frameDims().w;
    var nh = imageEl.naturalHeight || frameDims().h;
    // honour object-fit: contain letterboxing if the stylesheet uses it
    var sc = Math.min(rect.width / nw, rect.height / nh);
    var cw = nw * sc, ch = nh * sc;
    var ox = rect.left + (rect.width - cw) / 2;
    var oy = rect.top + (rect.height - ch) / 2;
    var fx = (cx - ox) / cw, fy = (cy - oy) / ch;
    var d = frameDims();
    return {
      x: Math.max(0, Math.min(d.w, fx * d.w)),
      y: Math.max(0, Math.min(d.h, fy * d.h))
    };
  }

  function makeRoiDrawer(ns, wrapEl, imageEl, onDone) {
    var btn = el(ns + "_draw");
    var armed = false, start = null, band = null;

    function setArmed(on) {
      armed = on;
      btn.textContent = on ? "Drag a box on the image (Esc cancels)" : "Draw ROI on image";
      btn.classList.toggle("beamfit-armed", on);
      if (wrapEl) wrapEl.classList.toggle("beamfit-drawing", on);
      if (!on) { start = null; if (band) band.style.display = "none"; }
    }

    function ensureBand() {
      if (!band) {
        band = document.createElement("div");
        band.className = "beamfit-band";
        wrapEl.appendChild(band);
      }
      return band;
    }

    function drawBand(a, b) {
      var wr = wrapEl.getBoundingClientRect();
      var l = Math.min(a.cx, b.cx) - wr.left + wrapEl.scrollLeft;
      var t = Math.min(a.cy, b.cy) - wr.top + wrapEl.scrollTop;
      var bd = ensureBand();
      bd.style.left = l + "px"; bd.style.top = t + "px";
      bd.style.width = Math.abs(b.cx - a.cx) + "px";
      bd.style.height = Math.abs(b.cy - a.cy) + "px";
      bd.style.display = "block";
    }

    function onMove(e) {
      if (!start) return;
      e.preventDefault(); e.stopPropagation();
      drawBand(start, { cx: e.clientX, cy: e.clientY });
    }

    function onUp(e) {
      if (!start) return;
      e.preventDefault(); e.stopPropagation();
      window.removeEventListener("pointermove", onMove, true);
      window.removeEventListener("pointerup", onUp, true);
      var a = clientToFrame(imageEl, start.cx, start.cy);
      var b = clientToFrame(imageEl, e.clientX, e.clientY);
      setArmed(false);
      var x = Math.round(Math.min(a.x, b.x)), y = Math.round(Math.min(a.y, b.y));
      var w = Math.round(Math.abs(b.x - a.x)), h = Math.round(Math.abs(b.y - a.y));
      if (w < 8 || h < 8) { onDone(null); return; }
      onDone({ x: x, y: y, w: w, h: h });
    }

    if (wrapEl && imageEl) {
      // capture phase on the wrapper runs before the page's zoom handler
      wrapEl.addEventListener("pointerdown", function (e) {
        if (!armed || e.button !== 0) return;
        if (!imageEl.getAttribute("src")) return;
        e.preventDefault(); e.stopPropagation();
        start = { cx: e.clientX, cy: e.clientY };
        drawBand(start, start);
        window.addEventListener("pointermove", onMove, true);
        window.addEventListener("pointerup", onUp, true);
      }, true);
      // swallow the click that follows so nothing else reacts to it
      wrapEl.addEventListener("click", function (e) {
        if (armed || start) { e.preventDefault(); e.stopPropagation(); }
      }, true);
    }

    document.addEventListener("keydown", function (e) {
      if (armed && e.key === "Escape") {
        window.removeEventListener("pointermove", onMove, true);
        window.removeEventListener("pointerup", onUp, true);
        setArmed(false);
      }
    });

    btn.addEventListener("click", function () {
      if (!wrapEl || !imageEl) return;
      setArmed(!armed);
    });
  }

  function wire(ns, mount, getTarget, imageEl, wrapEl) {
    mount.innerHTML = panelHtml(ns);
    var bg = el(ns + "_bg"), bgrow = el(ns + "_bgfilerow");
    var manual = el(ns + "_manualroi"), roirow = el(ns + "_roirow");
    var msg = el(ns + "_msg"), out = el(ns + "_out");
    var originalSrc = null;

    bg.addEventListener("change", function () {
      bgrow.classList.toggle("hidden", bg.value !== "file");
    });
    manual.addEventListener("change", function () {
      roirow.classList.toggle("hidden", !manual.checked);
    });
    el(ns + "_auto").addEventListener("click", function () {
      manual.checked = false; roirow.classList.add("hidden");
    });
    el(ns + "_restore").addEventListener("click", function () {
      if (originalSrc && imageEl) { imageEl.src = originalSrc; originalSrc = null; }
    });

    async function runFit() {
      var target = getTarget();
      if (target.error) { msg.textContent = target.error; return; }
      var body = {
        source: target.source,
        path: target.path || "",
        frame: target.frame === undefined ? -1 : target.frame,
        background: bg.value,
        bg_path: el(ns + "_bgpath").value.trim(),
        bg_frames: parseInt(el(ns + "_bgframes").value || "0", 10),
        baseline_order: parseInt(el(ns + "_order").value || "2", 10),
        despike_dn: parseFloat(el(ns + "_despike").value || "0"),
        rotation: rotation(),
        png_mode: "subtracted",
        suppress_sigma: el(ns + "_sup").checked ? parseFloat(el(ns + "_supn").value || "3") : 0
      };
      if (manual.checked) {
        body.roi = {
          x: parseInt(el(ns + "_rx").value || "0", 10),
          y: parseInt(el(ns + "_ry").value || "0", 10),
          w: parseInt(el(ns + "_rw").value || "0", 10),
          h: parseInt(el(ns + "_rh").value || "0", 10)
        };
      }
      msg.textContent = "Fitting...";
      out.classList.add("hidden");
      try {
        var res = await fetch("/api/analysis/fit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        });
        var j = await res.json();
        if (!j.ok) { msg.textContent = "Error: " + (j.error || "fit failed"); return; }
        j.quality = quality(j.fit);
        j.roi_warning = roiWarning(j);
        msg.textContent = "Frame " + (j.frame_index + 1) +
          (j.frames_available ? " of " + j.frames_available : "") +
          " - " + (j.calibration && j.calibration.dn_per_gy
            ? ("units " + j.calibration.display_units + " (" + fmt(j.calibration.dn_per_gy, 4) + " DN/Gy, " +
               (j.calibration.source || "custom") + ")")
            : "DN (no Gy calibration loaded)");
        out.innerHTML = resultHtml(j);
        out.classList.remove("hidden");
        el(ns + "_units").textContent = (j.calibration && j.calibration.dn_per_gy && j.calibration.display_units === "Gy") ? "Gy" : "DN";
        if (!manual.checked) {
          el(ns + "_rx").value = j.roi.x; el(ns + "_ry").value = j.roi.y;
          el(ns + "_rw").value = j.roi.w; el(ns + "_rh").value = j.roi.h;
        }
        if (el(ns + "_show").checked && j.png_token && imageEl) {
          if (originalSrc === null) originalSrc = imageEl.getAttribute("src");
          imageEl.src = "/api/analysis/fit.png?token=" + encodeURIComponent(j.png_token);
        }
      } catch (e) {
        msg.textContent = "Error: " + e;
      }
    }

    el(ns + "_fit").addEventListener("click", runFit);

    makeRoiDrawer(ns, wrapEl, imageEl, function (roi) {
      if (!roi) { msg.textContent = "ROI too small - drag a larger box."; return; }
      el(ns + "_rx").value = roi.x; el(ns + "_ry").value = roi.y;
      el(ns + "_rw").value = roi.w; el(ns + "_rh").value = roi.h;
      manual.checked = true; roirow.classList.remove("hidden");
      msg.textContent = "ROI " + roi.w + "x" + roi.h + " at (" + roi.x + ", " + roi.y + ") - fitting...";
      runFit();
    });
  }


  /* ---- Options: dose calibration ---------------------------------------- */
  function wireCalibration() {
    var inp = el("cal_dn_per_gy"), errIn = el("cal_err_pct"), note = el("cal_note");
    var units = el("cal_display_units"), inc = el("cal_include_err");
    var status = el("cal_status"), src = el("cal_source");
    if (!inp || !units) return;
    var PM = String.fromCharCode(177);

    function esc(t) { return String(t || "").replace(/[<>&]/g, ""); }
    function has(v) { return v !== null && v !== undefined; }

    function show(c) {
      if (!c || c.dn_per_gy === undefined) return;
      inp.value = c.dn_per_gy ? c.dn_per_gy : "";
      errIn.value = has(c.dn_per_gy_err_pct) ? c.dn_per_gy_err_pct : "";
      note.value = c.source === "custom" ? (c.note || "") : "";
      inc.checked = c.include_cal_err !== false;
      units.value = c.display_units || "DN";
      var d = c.default || {};
      var errTxt = has(c.dn_per_gy_err_pct)
        ? " &plusmn; " + fmt(c.dn_per_gy_err_pct, 2) + "%" : " (uncertainty not set)";
      var split = has(c.err_stat_pct)
        ? " = " + fmt(c.err_stat_pct, 2) + "% statistical &oplus; " + fmt(c.err_sys_pct, 2) + "% systematic" : "";
      src.innerHTML = c.source === "custom"
        ? "Using <b>custom</b> calibration: " + fmt(c.dn_per_gy, 4) + NBSP + "DN/Gy" + errTxt +
          (c.note ? " - " + esc(c.note) : "") +
          "<br>Default (Reset): " + fmt(d.dn_per_gy, 4) + NBSP + "DN/Gy &plusmn; " + fmt(d.dn_per_gy_err_pct, 2) + "%"
        : "Using <b>default</b> calibration: " + fmt(c.dn_per_gy, 4) + NBSP + "DN/Gy" + errTxt + split +
          "<br>" + esc(c.note);
      ["bfm_units", "bfv_units"].forEach(function (id) {
        var u = el(id); if (u) u.textContent = c.display_units === "Gy" ? "Gy" : "DN";
      });
    }

    async function post(body, okText) {
      status.textContent = "Saving...";
      try {
        var r = await fetch("/api/analysis/calibration", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        });
        var c = await r.json();
        show(c);
        status.textContent = c.ok ? okText(c) : "Error: " + (c.error || "save failed");
      } catch (e) { status.textContent = "Error: " + e; }
    }

    el("cal_save").addEventListener("click", function () {
      var v = inp.value.trim(), e = errIn.value.trim();
      if (v === "" || !(parseFloat(v) > 0)) { status.textContent = "Enter a positive DN per Gy value."; return; }
      if (e !== "" && !(parseFloat(e) >= 0 && parseFloat(e) < 100)) { status.textContent = "Uncertainty must be 0-100 %."; return; }
      post({ dn_per_gy: parseFloat(v), dn_per_gy_err_pct: e === "" ? null : parseFloat(e), note: note.value.trim() },
        function (c) {
          return "Saved: " + c.dn_per_gy + " DN/Gy" +
            (has(c.dn_per_gy_err_pct) ? " " + PM + " " + c.dn_per_gy_err_pct + "%" : "") + ". Re-run a fit to apply.";
        });
    });
    el("cal_reset").addEventListener("click", function () {
      post({ reset_default: true }, function (c) {
        return "Reset to default: " + c.dn_per_gy + " DN/Gy " + PM + " " + c.dn_per_gy_err_pct + "%. Re-run a fit to apply.";
      });
    });
    inc.addEventListener("change", function () {
      post({ include_cal_err: inc.checked }, function (c) {
        return (c.include_cal_err ? "Gy errors include" : "Gy errors exclude") +
          " the calibration uncertainty. Re-run a fit to apply.";
      });
    });
    units.addEventListener("change", function () {
      post({ display_units: units.value }, function (c) {
        return "Display units: " + c.display_units + ". Re-run a fit to apply.";
      });
    });

    fetch("/api/analysis/calibration").then(function (r) { return r.json(); })
      .then(show).catch(function () {});
  }

  function init() {
    var mainMount = el("beamFitMain");
    if (mainMount) {
      wire("bfm", mainMount, function () {
        return { source: "live" };
      }, el("preview"), document.querySelector(".preview-wrap"));
    }
    var viewMount = el("beamFitViewer");
    if (viewMount) {
      wire("bfv", viewMount, function () {
        var title = el("fileViewerTitle");
        var path = title ? title.textContent.trim() : "";
        if (!path || path.toLowerCase().indexOf(".raw") < 0) {
          return { error: "Open a .raw capture in the viewer first." };
        }
        var fi = el("viewerFrameInput");
        var frame = fi ? parseInt(fi.value || "1", 10) - 1 : -1;
        return { source: "file", path: path, frame: isNaN(frame) ? -1 : frame };
      }, el("fileViewerImage"), el("fileViewerStage"));
    }
  }

  function start() { init(); wireCalibration(); }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
