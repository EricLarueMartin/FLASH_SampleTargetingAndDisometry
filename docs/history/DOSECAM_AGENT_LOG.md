# Synchronized Camera Dosimeter Project Notes

This repository is for a new scintillation-light dosimetry system for the Duke FLASH experiment at FELL. It is expected to be worked on by multiple people and multiple AI assistants. ChatGPT is expected to be the primary AI collaborator, but keep the project notes and workflow tool-agnostic.

## Markdown Organization

- `README.md`: stable setup, operation, hardware, wiring, service, firmware, API, and safety instructions. Keep this useful for a new person setting up or operating the system.
- `AGENT.md`: current snapshot, historical investigation notes, open questions, and chronological change log. Keep this useful for future AI/person handoff and debugging continuity.
- When information graduates from an experiment or chat note into stable operating knowledge, update `README.md` first and then add only a concise historical note here.

## Current System Snapshot

2026-09-18 follow-up: User prefers compression before download with visible progress. ZIP buttons now POST `/api/exports` to build a disk-backed level-6 archive, poll progress, and automatically download when ready. Added cancellation, retry link, single-worker limit, disk-space check, 24-hour opportunistic cleanup, and frame progress for PNG exports. Archive job files live in `/var/tmp/dosecam-exports`; no captured data is modified. Tests cover archive integrity, byte progress, and cancellation cleanup.

2026-09-18: User reports successful linac test at 200 us delay and 100 us gate, saved under `laser_input_test/`. Directory is about 2 GiB. ZIP endpoint previously built the complete compressed archive in a BytesIO before responding; nginx logged a cancelled request (499, zero bytes). Replaced directory/current-run RAW and PNG ZIP responses with bounded-queue streaming, ZIP64, low-cost deflate, disconnect cancellation, and disabled proxy buffering. Added integrity/ZIP64/disconnect tests in `tools/test_zip_stream.py` and deployed to Pi.

2026-09-15: Added Options Wi-Fi controls for a password-protected hotspot and personal WPA/WPA2 client mode. `wifi_control.py` manages only `dosecam-hotspot`/`dosecam-client` with asynchronous activation, validation, hidden saved passwords, and recovery to the prior profile after a failed join. Hotspot SSID is `DoseCam`, address `192.168.50.1/24`; credentials were supplied to the user in chat, not stored in the repository. Added and deployed `dosecam-wifi-isolation.service` and its dedicated nftables table to block Wi-Fi forwarding into the facility network. Ethernet remains at `192.168.16.62` with preferred routing. Successful client association still requires testing where a network is available.

As of 2026-07-27, the stable operator/developer reference is `README.md`. It now includes fresh-Pi setup instructions, service/nginx installation, ESP firmware notes, verification steps, access paths, wiring, timing model, UI behavior, file formats, API notes, and operating workflow. Keep this `AGENT.md` file for detailed handoff notes and historical change log.

Git/GitHub status as of 2026-07-27:

- Remote `origin` is configured as `https://github.com/EricLarueMartin/SynchronizedCameraDosimeter`.
- The project has an initial `main` commit prepared for push.
- Runtime captures, probe images, raw data, logs, and Python cache files are excluded by `.gitignore`.

Current deployment:

- Pi hostname: `pi-06-ioc`.
- Current control-system-network address observed via DHCP: `192.168.16.62/24`.
- Current gateway/tunnel host used by the user: `daffy.fel.duke.edu`.
- Working tunnel command from the user's machine:

  ```bash
  ssh -N -L 2222:192.168.16.62:22 -L 8080:192.168.16.62:80 test@daffy.fel.duke.edu
  ```

- Web UI through that tunnel: `http://127.0.0.1:8080/`.
- SSH maintenance through that tunnel: `codex@127.0.0.1 -p 2222`.
- Authorized automation identity on the current Windows workstation: `~/.ssh/shv_bias_filter_agent_ed25519` with Pi user `codex`. Despite its historical filename, this is the key installed on `pi-06-ioc`; `flash_agent_ed25519` is not accepted by this Pi.
- `dose-cam.service` and `nginx.service` are enabled and active.
- Nginx listens on port 80 and proxies to Flask on `127.0.0.1:8000`.

Current acquisition model:

- The camera is always externally triggered.
- GPIO26 is only a prototype Pi-generated bench/test trigger into ESP8266 GPIO12.
- ESP8266 GPIO14 is the optoisolated laser charging/timing input. The installed optoisolator inverts a positive input pulse, so this path uses ESP input active LOW/falling-edge.
- ESP8266 GPIO13 is the active-low camera XTR output.
- ESP8266 GPIO15 is the monitor output to Pi GPIO16.
- Physical wire order last confirmed and bench-verified on 2026-09-15: short Feather header from battery-connector end has three empty pins, then white optoisolator J2 pin 2 signal on GPIO14, brown/white on GPIO12, white on GPIO13 to camera J3 `Trig+` / `XTR`, then green/white on GPIO15. Other Feather header from USB-connector end has reset empty, grey optoisolator J2 pin 3 VCC on 3V3, one NC empty, then black optoisolator J2 pin 1 ground on GND. Raspberry Pi GPIO header viewed from above with USB/Ethernet at right has the even-pin row away from the PCB and odd-pin row next to the PCB: physical pin 39 is black camera J3 `Trig-` ground, pin 37 / GPIO26 is brown/white to ESP GPIO12, and pin 36 / GPIO16 is green/white from ESP GPIO15. Camera viewed from the back/component side with ribbon down uses J3 for external trigger and J2 for strobe; on J3, black `Trig-` is closest to the camera PCB edge. Corrected-J2 test: one 4.999 V, 100 us AD2 W2 pulse produced one camera frame and a GPIO16 monitor high of about 898.8 us for a configured 1000 us gate.
- High-rate acquisition uses a background `rpicam-raw` stream and saves unpacked `R16` raw stream files.
- Raw mode is `1456:1088:10:U`, 1456 x 1088, 2944 bytes/row, 3,203,072 bytes/frame.
- Saved raw DN data is linear 10-bit data in the range 0-1023.
- Browser preview is autoscaled for visibility and is not linear dosimetry data.
- Capture tab displays linear frame stats, including brightest pixel DN and coordinates. The stats footnote derives the valid DN range from the raw mode bit depth, currently 0-1023 for 10-bit mode.
- Targeting and Dosimetry gate-width profiles are separate and persist separately in browser `localStorage`.
- Minimum camera gate width is enforced as 30 us in the HTML, browser JavaScript, Flask API, and backend acquisition code.

## Project Purpose

Use camera imaging of scintillation light as a dosimetry signal for approximately 30 MeV electrons near the spectrometer area after the first acceleration stage.

The first milestone is not polished dosimetry. The first milestone is a reliable synchronized camera exposure that can be triggered from the accelerator timing environment and verified on the bench before going into the beamline area.

## Experimental Context

- Site: Duke, FELL / FLASH experiment.
- Beam context: samples are placed in a spectrometer area shortly after the first acceleration stage, around 30 MeV electron energies.
- Intended signal: scintillation light from irradiated samples.
- Background concern: area lighting is LED-based. Common scintillators may emit near the blue component used in white LEDs, so optical background may overlap the signal.
- Near-term optical plan: no filter required for first timing tests.
- Later optical plan: add an optical filter to reduce LED/background contribution once triggering and acquisition work reliably.

## Hardware Known So Far

- Architecture: control computer, external-trigger camera, and delayed shutter pulse generator.
- Prototype control computer: Raspberry Pi 5. A Pi 4 or similar Linux SBC should also be feasible if it supports the camera stack, GPIO, serial, and data throughput.
- Pi hostname on the Duke network: `pi-06-ioc`.
- Preferred FQDN: `pi-06-ioc.fel.duke.edu`.
- Original DHCP IP observed on 2026-06-10: `10.236.58.53`.
- Control-system-network DHCP IP observed on 2026-07-23: `192.168.16.62`.
- `.local` resolution also works on the current same-router network, but do not rely on it if the Pi moves elsewhere.
- Project access account on the Pi: `codex`.
- Prototype camera: InnoMaker GS Camera Module for Raspberry Pi with IMX296 mono sensor and external trigger support.
- Camera detected on 2026-06-10 by `rpicam-hello --list-cameras` as `imx296 [1456x1088 10-bit MONO]`, mode `R10_CSI2P`, 1456x1088 at about 60.38 fps.
- Prototype delayed shutter pulse generator: Adafruit Feather HUZZAH with ESP8266. ESP32 or another timing-capable microcontroller should be fine if it can accept a timing input, apply a programmable delay, and generate a programmable-width shutter output pulse.
- The pulse generator is not simply delaying and copying the input pulse. It accepts an input edge, waits a configured delay, then generates a new camera shutter pulse with a configured width.
- ESP8266 USB serial bridge detected on 2026-06-10 as Silicon Labs CP2104 at `/dev/ttyUSB0`, with stable symlink `/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_023312DB-if00-port0`.
- Existing camera code is in `dose_cam/`.
- Existing ESP8266 / Arduino delayed-shutter-pulse firmware is in `DDG/DDG.ino`.
- Camera manual currently present at `ComponentManuals/CAM-IMX296RAW-UserManual-V2.0.pdf`.
- Likely camera purchase link: `https://www.amazon.com/dp/B093BY2TK2`.
- Lens purchase link: `https://www.amazon.com/dp/B08PYMBX9T`.
- Current optical setup as of 2026-06-10: lens cover removed, camera aimed out the office window, manual focus/zoom lens installed.
- Web interface default URL when directly reachable: `http://pi-06-ioc.fel.duke.edu/` or the current Pi IP. Through the current SSH tunnel use `http://127.0.0.1:8080/`. Nginx listens on port 80 and proxies to the Flask app on `127.0.0.1:8000`.
- Flask boot service: `dose-cam.service`, installed at `/etc/systemd/system/dose-cam.service`, runs as user `codex` from `/home/codex/SynchronizedCameraDosimeter/dose_cam`.
- Nginx site config: `/etc/nginx/sites-available/dose-cam`, symlinked into `/etc/nginx/sites-enabled/dose-cam`; the stock nginx default site is disabled.

## Current Wiring Notes

- ESP8266 pin 13 is wired as output for the camera shutter trigger.
- ESP8266 pin 12 is wired as an input from Raspberry Pi GPIO26 for troubleshooting/development triggers.
- ESP8266 pin 15 is wired as a monitor/test output to Raspberry Pi GPIO16.
- ESP8266 pin 14 is intended as the second input for the laser charging signal, but no laser pulse input is connected yet.
- The ESP8266 is connected to the Pi by USB for power and serial communication.

## Timing Model

The linac applies RF power for a window of some microseconds. In normal operation, a laser pulse generates photoelectrons for injection timing. For this experiment, the narrow injection timing requirement is not the goal, and thermal electron emission may be sufficient.

However, there is a laser charging signal or pulse some microseconds before RF power is applied. That earlier signal is intended as a timing reference. The desired behavior is:

1. Receive either a pulse from the Raspberry Pi or the accelerator/laser charging signal.
2. Delay it by a configurable number of microseconds using the ESP8266.
3. Generate a camera trigger pulse.
4. Capture a frame during the relevant beam/scintillation window.

Near-term development should use the Pi-generated pulse into the ESP8266 input for troubleshooting. The real experimental trigger should eventually come from the laser charging signal.

The camera manual says the external trigger uses XTR/Trig+ and GND/Trig-. The trigger pulse is active-low: exposure time is the low pulse width plus about 14.26 us. Keep the ESP8266 output configured as active LOW unless bench measurements show the wiring/interface inverts it. The application enforces a conservative 30 us minimum gate width because Raspberry Pi's IMX296/global-shutter product page describes exposures as low as 30 us.

## Data Format Notes

Experiment synchronization has priority over raw pixel format. The first production-relevant capture path must be externally triggered from the laser charging/timing signal through the ESP/camera trigger path. Raw sensor values are preferred after that, but a raw path that only works with prompt Pi-generated test triggers is not acceptable as the experiment-mode default.

Current capture modes:

1. Experiment/default mode: external trigger, lossless PNG.
   - The Flask app arms the camera and waits for the ESP/camera external trigger input.
   - It does not generate the Pi GPIO26 test pulse internally.
   - The saved measurement file is a PNG, which avoids JPEG/lossy compression artifacts.
   - Current limitation: this is 8-bit RGB/ISP output from `rpicam-still`, not true raw ADC/DN10 data.

2. Bench/raw development mode: Pi test pulse, raw TIFF.
   - The Flask app generates Pi GPIO26 test pulses into ESP GPIO12 shortly after arming the camera.
   - It stores a zlib/Deflate-compressed TIFF containing decoded 10-bit IMX296 DN values in a `uint16` image.
   - This mode is useful for validating raw handling, but is not the experiment-mode default because the current Picamera2 raw path times out if it is armed too long without a trigger.

3. High-rate batch mode: background `rpicam-raw` stream.
   - The Flask web GUI exposes this from the Capture tab as the normal acquisition mode while the web server remains running.
   - Tested mode writes one `.raw` stream file plus `.json` metadata and optional `.log`, rather than launching one process per image.
   - The raw file is now `rpicam-raw` unpacked `R16` data using mode `1456:1088:10:U`, 1456 x 1088 with 2944 bytes/row stride, 3,203,072 bytes/frame.
   - The page polls progress; it does not attempt to display every frame at acquisition rate.
   - For targeting, the Capture button sends a GPIO26 test pulse and then updates the browser preview from the newest complete raw frame. In Dosimetry mode while armed, the Capture button sends one GPIO26 test trigger into the active raw acquisition without refreshing the displayed preview, which supports repeated multi-frame testing. The Update Image button refreshes the display from the newest complete raw frame without sending a GPIO26 pulse.
   - The Capture tab has a `Capture mode` selector with `Targeting` and `Dosimetry`. The selected mode chooses which ESP/camera gate width is used for arming and preview captures.
   - Gate widths are configured on the Options tab as two profiles: targeting gate width for useful setup/aiming images and dosimetry gate width for beam/scintillation captures. Delay is a single shared setting because the laser-charging-to-RF timing should not depend on targeting vs dosimetry.
   - The Options tab also has an image rotation selector. It defaults to 180 degrees because the current mounted camera view is upside down. Rotation is applied only to browser preview JPEGs; saved raw stream data remains in sensor coordinates.
   - The Options tab has an `Input trigger active high` toggle. A new page load reads `/api/esp_status`, which queries the ESP8266 over serial and sets the toggle from the ESP firmware state.
   - The preview display supports client-side zoom: drag a rectangle on the displayed preview image to zoom into that region, and use `Restore View` to return to the full-frame display. This is display-only and does not crop or transform saved raw data.
   - Normal experiment-style use is to arm this mode, wait until it reports `Armed`, then let laser/external pulses arrive. The GUI Capture button sends a Pi GPIO26 test pulse into the same ESP8266/camera external-trigger path for bench/targeting pulses while armed.
   - Do not present GPIO26 as an alternate camera trigger source. The camera is always externally triggered; GPIO26 is only a test signal injected into that external trigger chain.
   - This is currently the credible path for 50 fps bench testing through Pi GPIO26 -> ESP8266 -> camera XTR.

Raw bench path details:

- Sensor: IMX296 mono, 1456 x 1088.
- Camera stream: libcamera/Picamera2 raw `R16`, selected from sensor format `Y10_1X10`.
- Stored data: 10-bit sensor DN values decoded into a `uint16` image with valid range 0-1023.
- TIFF compression: zlib/Deflate, lossless.
- Browser preview: contrast-scaled JPEG generated from the raw frame for display only. It is not dosimetry data.

## Current Repository Layout

- `dose_cam/`: Raspberry Pi camera and web-control code.
  - `dose_cam.py`: Flask app exposing setup, ESP serial controls, capture, preview, saved-file listing/download, and optional autosave routes.
  - `camera_core.py`: current Picamera2 camera logic, external trigger mode, GPIO26 pulse to ESP8266, RAW capture, preview generation, and lossless TIFF/DN10 generation.
  - `camera_core_v0.py`: earlier camera implementation; useful for comparison.
  - `test_gpio26.py`: GPIO26 bench-test helper.
  - `list_controls.py`: likely Picamera2/libcamera control discovery helper.
  - `templates/setup.html` and `static/setup.js`: web UI.
- `DDG/`: ESP8266 delayed shutter pulse generator firmware.
  - `DDG.ino`: accepts serial commands for delay, width, output enable, active level, and software trigger.
- `ComponentManuals/`: hardware manuals and reference PDFs.

## Current State

An earlier attempt exists but did not work correctly. The reported failure was that the system was not triggering the camera and taking photos when expected.

Important nuance: the signal through the ESP8266 seemed to work fine, but it did not make the camera work correctly. Treat the ESP output as "promising but still must be verified electrically at the camera input," not as fully proven.

As of 2026-06-10, the basic software/hardware path has been smoke-tested successfully:

- SSH access to `pi-06-ioc` works as user `codex`.
- The Pi detects the ESP8266 serial bridge at `/dev/ttyUSB0`.
- The Pi detects the IMX296 camera with `rpicam-hello --list-cameras`.
- The ESP8266 responds to serial commands over USB.
- `rpicam-still` can capture a JPEG.
- The Flask app can start, connect to the camera, connect to the ESP8266, serve the setup page, configure ESP delay/width/active level, and complete one capture through the Pi GPIO -> ESP8266 -> camera trigger path.
- A preview PNG from that capture was retrieved and was not blank.

Important update from 2026-06-11: true driver-level external trigger mode is working for the bench development path. The proven path is Pi GPIO26 -> ESP8266 GPIO12 -> ESP8266 GPIO14 active-low -> camera XTR, with ESP GPIO15 still available as a monitor output to Pi GPIO16. The current Flask capture path uses Picamera2 raw capture while `/sys/module/imx296/parameters/trigger_mode` is set to `1`, and generates a short Pi test-trigger burst after the camera is armed.

The current Flask capture path is suitable for manual/test captures and web focusing. It is not the final high-rate acquisition architecture. Picamera2 reports camera frontend timeouts if it is armed for too long without a trigger, so the raw bench path uses a short arm delay around 0.25 s before sending Pi-generated test triggers. The default external PNG path has been verified with a 3 s simulated external wait, but 50 fps external-trigger operation is not yet proven and should be treated as an open engineering risk.

The current Flask app is a development server with no authentication. During 2026-06-11 testing, `/tmp/dose_cam.log` showed unsolicited network scanner/exploit-probe requests from `10.138.67.166`. Before this becomes a boot service on the Duke network, add authentication, firewalling, or bind restrictions appropriate for the lab workflow.

High-rate update from 2026-06-11: a background web/API batch capture using `rpicam-raw` succeeded while the Flask web server remained live. The verified burst test requested 100 frames at 50 fps through the Pi GPIO26 -> ESP8266 -> camera XTR path and produced exactly 100 frames, with a 160,153,600 byte `.raw` output file plus metadata/log files. The batch route validates success by raw file byte count because `rpicam-raw` does not always exit cleanly on its own after receiving the requested external-triggered frames; the app terminates it after the expected data has arrived, then restores trigger mode/GPIO/ESP state.

Armed-mode update from 2026-06-11: the raw acquisition API supports the intended operating pattern where acquisition sits armed waiting for external/laser pulses. A bench test started an external-trigger raw run, waited until status was `Armed`, waited one additional second for camera settling, then sent five separate GPIO26 test pulses. Result: 5/5 frames captured and finalized as `captures/armed/apitest_settled_20260611_184824_886253_000003.raw` with exact size 8,007,680 bytes. Pulses sent immediately during `Starting` or too soon after initial `Armed` can be missed, so for real use arm the camera before the accelerator timing pulses are expected.

UI correction from 2026-06-11: the user clarified that there should not be a separate Batch tab or a trigger-source dropdown. The visible web UI now has Capture, Files, and Trigger tabs only. The Capture tab arms external-trigger raw acquisition, the Capture button sends a GPIO26 test pulse, and Stop / Finalize closes the current raw stream. Backend routes `/api/acquisition/start`, `/api/acquisition/status`, `/api/acquisition/stop`, and `/api/acquisition/test_trigger` are the UI-facing routes for this flow and always use the camera external-trigger path.

Gate-width correction from 2026-06-11: do not label the Capture-tab timing field as camera exposure. In external-trigger mode, exposure is set by the length of the active-low ESP8266/camera trigger gate. The Capture tab now labels this as `Gate width (us)`. The acquisition start route maps `gate_width_us` to the ESP8266 pulse width (`esp_width_us`) and records `external_trigger_gate_us` in the metadata JSON. The `rpicam-raw --shutter` value is still set to the same number as a camera control, but the experiment-facing exposure concept is the external trigger gate width.

Preview update from 2026-06-11: the first raw stream implementation used packed/PiSP-compressed-looking bytes (`1456:1088:10:P`, 1472-byte stride), which produced a noisy/unusable direct preview. The app now records unpacked `R16` raw stream files (`1456:1088:10:U`, 2944-byte stride). This doubles file size but allows the backend to decode the latest complete frame into a contrast-scaled JPEG for focusing/targeting. A standalone 100-frame, 50 fps unpacked burst wrote exactly 320,307,200 bytes, so this path is viable in the current bench test. Continue watching disk throughput and available storage for long runs.

Reconnect update from 2026-06-12: after the system was powered down and mounted on a plate, the user confirmed the wiring is ESP IO12 from Pi GPIO26, ESP IO15 to Pi GPIO16 monitor, and ESP IO13 to the camera external trigger. The prior firmware still drove camera output on IO14 and treated IO13 as laser input, so the ESP monitor loop worked but the camera never saw a trigger. `DDG/DDG.ino` was patched and flashed so `PIN_OUT_CAMERA = 13` and `PIN_IN_LASER = 14`. After flashing, the GPIO26 -> ESP -> camera path worked again through the web capture-preview endpoint.

ESP8266 firmware update on 2026-06-10:

- Arduino CLI 1.5.1 and ESP8266 core 3.1.2 were installed on the Pi.
- `DDG/DDG.ino` was flashed to the Adafruit Feather HUZZAH over `/dev/ttyUSB0`.
- ESP GPIO13 is now the camera shutter output and should be configured active LOW for this camera.
- ESP GPIO14 is now reserved as the future laser charging input.
- ESP GPIO15 is now a monitor output to Pi GPIO16. It idles LOW and goes HIGH during the generated output pulse.
- ESP trigger input polarity is configurable as active HIGH or active LOW. The default firmware state is active HIGH, meaning the rising edge of a pulse on ESP GPIO12 or GPIO14 starts the shutter delay. The camera shutter output polarity is separate and remains fixed active LOW.
- The firmware responds to serial status/config commands and reports `DDG ready` after reset when the boot text is caught.
- Pi GPIO26 -> ESP GPIO12 -> ESP GPIO15 -> Pi GPIO16 test loop works.
- Observed GPIO16 monitor pulse widths using Linux/gpiozero callbacks: requested 10000 us measured about 10015 us; requested 1000 us measured about 951 us; requested 100 us and 50 us both produced detectable edges around 48 us. Treat the short-pulse measurements as evidence of pulse generation, not precision timing metrology.
- With output disabled and active LOW selected, Pi GPIO16 monitor reads low/inactive.

Lossless capture update on 2026-06-11:

- Standalone Picamera2 raw-trigger probe succeeded in external-trigger mode.
- Picamera2 raw stream returns a padded byte buffer shaped `(1088, 2944)` for this sensor. Decode it as little-endian 16-bit samples, then crop each row to 1456 valid pixels.
- Decoded values are left-aligned 10-bit data in the 16-bit container; shift right by 6 to recover 0-1023 DN values.
- The web app now saves `.tiff` files, not `.jpg`, for measurement frames. Current-frame TIFF download and saved-file TIFF download both verified as 1456 x 1088, 16 bps, Deflate-compressed TIFFs.

## Initial Technical Suspicions

These are not conclusions. They are starting points for future debugging.

- Camera trigger electrical requirements may not match the ESP8266 output level, polarity, pulse width, impedance, or isolation requirements.
- The Picamera2/libcamera trigger configuration may not be correct for this camera or driver.
- `capture_array("raw")` may block until a frame is available, but the software ordering may not guarantee that the requested frame corresponds to the just-issued external trigger.
- `capture_array("raw")` returned a shape reported by the API as `2944x1088` during the 2026-06-10 smoke test, even though the sensor is 1456x1088. This is likely raw stride/format handling and should be investigated before relying on pixel dimensions or RAW10 packing.
- The external trigger mode and exposure/frame-duration controls may interact in a camera-specific way.
- The ESP8266 timer output should be verified with an oscilloscope at the actual camera trigger input, not only at the ESP pin.
- The ESP8266 firmware previously drove the output LOW when disabled, even when active-low output was selected. That is electrically active for the camera trigger. `DDG/DDG.ino` has been patched and flashed so disabled output is inactive for either polarity.
- A level shifter, optocoupler, pull-up/pull-down, BNC/TTL interface, or pulse conditioning stage may be required depending on the camera trigger input.
- If using accelerator timing signals, electrical isolation and facility-approved signal handling may be required.

## Bench Verification Checklist

Before beamline testing, try to establish each link independently.

1. Camera alone
   - Confirm the camera can capture normally without external trigger.
   - Confirm the camera can capture in external trigger mode using a known-good signal generator.
   - Record required trigger polarity, voltage, minimum pulse width, and any exposure timing constraints.

2. Raspberry Pi GPIO
   - Verify GPIO26 pulse width and voltage with an oscilloscope.
   - Confirm GPIO26 is only a test trigger into the ESP8266, not the final accelerator timing source.

3. Delayed shutter pulse generator
   - Verify both input pins and output pin with an oscilloscope.
   - Test serial commands: delay, width, enable, active level, software trigger.
   - Measure timing jitter if possible. The prototype ESP8266 may be acceptable for first tests, but should not be assumed to be precision timing hardware.

4. ESP8266 to camera
   - Verify the waveform at the camera trigger input, not just at the ESP8266 output.
   - Sweep pulse width and polarity.
   - Confirm the camera produces one frame per trigger and identify any dead time.

5. Full software path
   - Start the Flask app.
   - Set delay/width/output state through the UI or API.
   - Trigger via software and verify the captured frame corresponds to the trigger.
   - Only then test the accelerator timing reference.

## Coding Notes For Future Agents

- Do not assume hardware behavior from code alone. Any trigger fix should include a proposed oscilloscope test.
- Keep Raspberry Pi, ESP8266, and camera responsibilities separated in the code and docs.
- Preserve existing experimental code unless the user explicitly asks for cleanup or replacement.
- Prefer small, testable changes because the hardware feedback loop is slow.
- Log timing-relevant settings with every capture: delay, width, trigger source, active level, exposure time, frame duration, timestamp, and whether external trigger mode was active.
- When changing camera configuration, record the exact Picamera2/libcamera controls available on the Pi using `dose_cam/list_controls.py`.
- Be careful with Unicode copied from old code or notes. Some current files show mojibake in comments/strings such as microsecond symbols and dashes.

## Standalone Deployment Requirement

This system must be able to run as a standalone deployed instrument without depending on external hosted resources. Do not use CDN-hosted JavaScript, CSS, fonts, images, icons, maps, analytics, package-loader URLs, or other runtime web assets. If external code or assets are needed, vendor a local copy into the repository or install it locally on the Pi, serve it from the Pi, and document its source/version/license here.

As of 2026-06-11, the web UI does not use external runtime resources. `dose_cam/templates/setup.html` only loads `/static/setup.js`, and the CSS is inline/local. URLs in this document, such as hardware purchase links, are reference notes only and are not runtime dependencies.

## Safety And Facility Notes

- This project touches accelerator-area timing and radiation experiments. Do not connect electronics to facility timing or accelerator signals without approval from the responsible local personnel.
- Use proper electrical isolation, grounding, and signal conditioning when connecting lab electronics to accelerator timing signals.
- Do not put people, electronics, or optics into the beamline area without following Duke/FELL procedures.
- Treat dosimetry outputs as experimental until calibrated against trusted instrumentation.

## Open Questions

- Exact facility-side laser charging/timing signal voltage, polarity, impedance, connector, and whether level shifting or isolation is required before connecting it to ESP8266 GPIO14.
- Whether the ESP8266 trigger input path is electrically acceptable for the facility timing signal, or whether a dedicated buffer/isolator/level shifter should be inserted.
- Whether `192.168.16.62` will remain stable on the `fel.epics` subnet through DHCP reservation, DNS registration, or local network policy.
- Actual timing relationship among laser charging signal, RF power, thermal emission, electron arrival, and desired scintillation exposure.
- Expected scintillator material, emission spectrum, decay time, and light yield.
- Whether LED background can be measured with beam-off frames before adding filters.
- Calibration method from raw DN statistics or integrated image signal to delivered dose.
- Whether hottest-pixel statistics are sufficient as a diagnostic, or whether the analysis should use ROI sums, dark subtraction, flat-field correction, and beam-off/background frames.

## Handoff Template

When leaving work for the next person or AI, add a short note with:

- Date and person/agent.
- Hardware connected.
- Code/firmware versions changed.
- Exact commands run.
- Trigger source used.
- Delay, width, polarity, exposure, and frame-duration settings.
- Oscilloscope observations.
- Whether the camera produced a frame per trigger.
- Any captured data path or filenames.
- Next recommended test.

## Change Log

- 2026-06-10: Created project coordination notes from the initial project description and current repository layout.
- 2026-06-10: Added Pi hostname/account, current wiring, ESP8266 USB identity, detected IMX296 camera mode, and current office-window optical setup.
- 2026-06-10: Smoke-tested Pi access, ESP8266 serial communication, camera detection, `rpicam-still`, Flask startup, API controls, and one triggered capture. Also noted manual trigger polarity/exposure behavior and the raw shape/stride issue.
- 2026-06-10: Tested true kernel external trigger mode. Camera blocked waiting for trigger and did not accept the ESP/Pi test pulse, so the real external-trigger path still needs bench debugging. Patched ESP firmware source so disabled output is inactive, but firmware upload remains to be done.
- 2026-06-10: Installed Arduino CLI/ESP8266 toolchain on the Pi, updated and flashed `DDG/DDG.ino`, added GPIO15 monitor output to Pi GPIO16, and verified Pi GPIO26-triggered monitor pulses down to short pulse widths.
- 2026-06-10: Retested true camera external trigger mode after flashing the fixed ESP8266 firmware. `rpicam-still` still timed out waiting for a valid sensor trigger, so the ESP logic path is now verified but the camera XTR/electrical trigger path remains unresolved.
- 2026-06-10: User moved camera trigger return/ground from Pi ground to ESP8266 ground. ESP monitor path still worked, but true camera external trigger mode still timed out. Added `tools/pi_direct_camera_trigger_probe.sh` for the next bypass test: temporarily wire Pi GPIO26 directly to camera J3 Trig+/XTR and shared ground to camera J3 Trig-/GND.
- 2026-06-10: Direct Pi GPIO26 -> camera Trig+/XTR test succeeded after fixing `rpicam-still` settings to use `--gain 1 --awbgains 1,1 --immediate`. A burst trigger test also succeeded. Conclusion: the camera external trigger input and driver mode are capable; early failures were largely due to camera pipeline/auto/preview settling and too-sparse trigger tests. Updated ESP-path `tools/pi_rpicam_trigger_probe.sh` to use the same fixed settings.
- 2026-06-10: User moved wiring back to ESP path. End-to-end Pi GPIO26 -> ESP GPIO12 -> ESP GPIO14 active-low camera trigger succeeded with `tools/pi_rpicam_trigger_probe.sh`. The test used a 5 us ESP delay and 10000 us pulse width; camera captured `/tmp/rpicam_trigger_probe.jpg`. The image was overexposed outdoors, as expected for a 10 ms trigger pulse, but proves the synchronized ESP camera trigger path works.
- 2026-06-10: ESP camera trigger path also succeeded with a 100 us active-low pulse (`WIDTH_US=100`), producing `/tmp/rpicam_trigger_100us.jpg`. The image was dark but recognizable, appropriate for a short daylight exposure.
- 2026-06-10: Web app backend was refactored to use the proven `rpicam-still` + kernel trigger mode path instead of the earlier Picamera2 `SyncMode` capture. Web API smoke test succeeded: set delay 5 us, pulse width 100 us, active LOW, capture returned `{"ok": true}` and `/api/preview.jpg` returned a JPEG. Current test server runs at `http://pi-06-ioc.fel.duke.edu:8000/` while `python3 dose_cam.py` is running.
- 2026-06-11: Web interface reorganized into Capture and Trigger tabs. Capture tab now has autosave controls with base name and optional log saving; Trigger tab contains ESP delay, pulse width, output enable, and active-level controls. Backend autosave writes files under `dose_cam/captures/` as `<base>_<UTC timestamp>_<counter>.jpg`. HTTP smoke test with autosave enabled succeeded and saved `captures/webtest_20260611_134243_774255_000001.jpg`. Current backend remains one `rpicam-still` subprocess per capture, so it is functional for single-shot/low-rate work but not the final up-to-50-fps acquisition architecture.
- 2026-06-11: Added Files tab and saved-file download endpoints. Save base names can include subdirectories using either `/` or `\`; both are normalized under `dose_cam/captures/` and cannot escape that save root. Capture tab also has a "Download Matching Base" button that zips all files matching the current manual save base. Smoke test with autosave base `runA\sample1` saved `runA/sample1_...jpg` and `.log`; individual file download and ZIP-by-base download both worked.
- 2026-06-11: Converted the measurement capture path from JPEG to raw Picamera2 capture plus lossless TIFF output. The saved/downloaded raw bench frame is a zlib/Deflate-compressed TIFF containing decoded 10-bit IMX296 DN values in a `uint16` image. JPEG remains only a contrast-scaled browser preview in raw bench mode. Verified current-frame download and saved-file download with `file`: little-endian TIFF, 1456 x 1088, 16 bps, Deflate compression. Autosave with subdirectory base `lossless/rawtest` wrote `captures/lossless/rawtest_20260611_144536_625650_000002.tiff` plus `.log`.
- 2026-06-11: Reprioritized capture modes so experiment/default mode is externally triggered first. Added Flask/API trigger source `external`, which arms the camera and waits for an ESP/camera trigger without internally generating a Pi test pulse. Because `rpicam-still --raw` fails for this mono path with `unsupported Bayer format`, the externally triggered experiment-mode artifact is currently lossless PNG, not raw ADC. Verified by starting web capture, sending an independent GPIO26 -> ESP test pulse 3 s later, and saving `captures/external/pngtest_20260611_145430_896340_000001.png` plus `.log`; `file` reports PNG, 1456 x 1088, 8-bit/color RGB. Raw bench mode remains available as `pi_test_raw` and saved `captures/lossless/rawtest_20260611_145504_594027_000002.tiff`. Current Flask server PID during verification: `18360`, serving `http://pi-06-ioc.fel.duke.edu:8000/`.
- 2026-06-11: Fixed web capture collisions in external-trigger mode. The Flask app is threaded, and an external capture can hold the camera while waiting for a trigger; a second capture request previously caused `Pipeline handler in use by another process` / `failed to acquire camera`. Added a capture mutex, `/api/capture/cancel`, and a Cancel button. Overlap probe now returns `Capture already in progress; wait for it to finish or cancel it.`; cancel probe leaves trigger mode at `0` with no `rpicam-still` process. Re-verified normal external capture with a simulated independent GPIO26 -> ESP pulse; saved `captures/external/pngtest_20260611_155825_914228_000001.png` plus `.log`. Current Flask server PID during verification: `18905`.
- 2026-06-11: Adjusted the web Capture button default. The prior default was `external`, meaning it armed the camera and waited for a real external/laser input; with no laser input connected, the button appeared to do nothing. The UI now defaults to `Pi GPIO26 test trigger` (`pi_test_png`), which arms the camera in external-trigger mode and then sends a GPIO26 -> ESP8266 -> camera XTR pulse. Verified via `tools/pi_api_button_capture_probe.py`; saved `captures/button/pngtest_20260611_164929_918108_000001.png`, and the saved log records `trigger=Pi GPIO26 -> ESP8266 -> camera XTR`. Flask server PID during verification: `19488`.
- 2026-06-11: Upgraded the Files tab from a flat recursive list to a directory browser rooted at `dose_cam/captures/`. The API now supports `GET /api/files?path=<dir>` for one directory level and `GET /api/files/download_dir?path=<dir>` for recursive ZIP download. The UI shows the current path, folder rows with Open/ZIP actions, an Up button, Refresh, and Download Directory for the current folder. Verified root listing, entering `button/`, returning Up, and downloading `button/` as `/tmp/button_dir.zip`; the ZIP contained the expected PNG/log files. Flask server PID during verification: `19682`.
- 2026-06-11: Added deletion to the Files tab. File and folder rows now have Delete buttons; the browser shows a confirmation dialog before sending `POST /api/files/delete`. The backend deletes only paths resolved under `dose_cam/captures/`, supports file deletion and recursive directory deletion, and refuses to delete the capture root itself. Verified with `tools/pi_api_delete_probe.py`: deleted `delete_probe/subdir/test.txt`, deleted recursive folder `delete_probe`, and confirmed root deletion returns `Refusing to delete the capture root`. Flask server PID during verification: `19944`.
- 2026-06-11: Measured repeated GPIO26 -> ESP -> camera XTR capture rate. Added `tools/pi_gpio26_capture_rate_probe.py` for low-level one-`rpicam-still`-process-per-frame testing and `tools/pi_api_button_rate_probe.py` for web API/button-path testing. With lossless PNG and 100 us ESP/camera pulse, low-level results were: 0.5 s arm delay, 10/10 at about 1.6 fps; 0.25 s, 10/10 at about 2.7 fps; 0.20 s, 10/10 at about 3.1 fps; 0.15 s, 30/30 at about 3.7 fps; 0.125 s, 10/10 at about 4.0 fps; 0.11 s, 5/5 at about 4.0 fps; 0.105 s and 0.10 s both failed 0/N with camera frontend timeouts. Current web/API button path, which still uses a conservative 0.5 s internal trigger delay, measured 10/10 at about 1.44 fps with autosave disabled. Conclusion: the current single-shot `rpicam-still`/PNG path is reliable only at a few fps and is not a credible 50 fps acquisition architecture.
- 2026-06-11: Added web/API background raw batch acquisition so high-rate tests do not require stopping the web server. New routes: `POST /api/batch/start`, `GET /api/batch/status`, `POST /api/batch/cancel`, and `POST /api/batch/test_trigger`; new Batch tab controls base path, trigger source, max frame count, test-burst fps, exposure, ESP delay/width, and log saving. Verified through the live Flask server: requested 100 frames at 50 fps using Pi GPIO26 test burst, wrote `captures/batch/webapi_50fps_20260611_183737_400528_000001.raw` plus `.log`/`.json`, with 100/100 frames and exact raw size 160,153,600 bytes. Reworked the UI/default path toward armed external acquisition; after waiting for `Armed` plus a 1 s settle, five individual GPIO26 test-trigger API calls captured 5/5 raw frames in `captures/armed/apitest_settled_20260611_184824_886253_000003.raw`. Cleanup verification after the run: camera trigger mode `0`, GPIO26 input, and Flask server running as PID `23652`.
- 2026-06-11: Simplified the visible web UI after user feedback. Removed the Batch tab and trigger-source dropdown. The Capture tab now has Save base, Max frames, Expected max rate, Gate width, Arm, Capture, Stop / Finalize, and Download Run Files. The Capture button calls `/api/acquisition/test_trigger`, which only sends a GPIO26 test pulse; acquisition itself is armed through `/api/acquisition/start` and always uses camera external trigger mode. Verified through live Flask server PID `24150`: armed `ui_simplified/test` for 3 external-trigger raw frames, waited for `Armed` plus 1 s, sent three GPIO26 Capture/test pulses, and produced 3/3 frames in `captures/ui_simplified/test_20260611_190116_792843_000001.raw` with exact size 4,804,608 bytes. Final state: trigger mode `0`, GPIO26 input, no `rpicam` process.
- 2026-06-11: Renamed Capture-tab `Exposure (us)` to `Gate width (us)` and wired that value to the ESP8266 gate width used during acquisition start. Removed the duplicate pulse-width control from the Trigger tab. Verified through live Flask server PID `24873`: armed a 1-frame acquisition with `gate_width_us=150`, captured one frame, and confirmed metadata contains `esp_width_us: 150` and `external_trigger_gate_us: 150` in `captures/gate_width/check_20260611_190925_990505_000001.json`. The live UI no longer contains the word Exposure on the Capture tab. Final state: trigger mode `0`, GPIO26 input, no `rpicam` process.
- 2026-06-11: Added targeting preview refresh. New routes: `POST /api/acquisition/capture_preview`, which sends a GPIO26 test pulse and updates `/api/preview.jpg` from the newest complete raw frame, and `POST /api/acquisition/update_preview`, which refreshes the displayed image without sending a trigger. The Capture tab now includes an Update Image button. Switched acquisition stream from packed `1456:1088:10:P` to unpacked `1456:1088:10:U` (`R16`, 2944-byte stride, 3,203,072 bytes/frame) so raw frames can be decoded for preview and later conversion. Verified: one-click targeting capture wrote `captures/targeting/r16preview_20260611_194155_180989_000001.raw`, updated `/api/preview.jpg`, and the preview visibly showed the office-window trees. Also verified standalone 100-frame, 50 fps unpacked burst wrote exact expected size 320,307,200 bytes. Final state: trigger mode `0`, GPIO26 input, Flask PID `26603`, no `rpicam` process.
- 2026-06-12: Reconnected after plate mount and found the physical camera trigger wire on ESP IO13, while firmware was still outputting camera trigger on IO14. A hung reconnect probe left `pi_rpicam_trigger_probe.sh` and `rpicam-still` running for about 2 h 20 min; cleaned up stale processes and restored trigger mode to `0`. Patched and flashed `DDG/DDG.ino` so IO13 is camera output and IO14 is the future laser input. Verified GPIO26 -> ESP -> GPIO15 monitor pulse still works, then verified web capture-preview path: `captures/reconnect/io13_fix_20260612_190347_629977_000002.raw` captured 1/1 frame and `/api/preview.jpg` showed real image data. Final state: trigger mode `0`, GPIO26 input, Flask PID `1802`, no `rpicam` process.
- 2026-06-12: Split gate-width control into two Trigger-tab profiles: targeting gate width and dosimetry gate width. The Capture tab now selects `Targeting` or `Dosimetry`, and the selected profile supplies `gate_width_us`/`esp_width_us` when arming or taking a preview capture. Saved acquisition metadata now includes `capture_mode` along with `external_trigger_gate_us`.
- 2026-06-15: Installed boot deployment. Added repo-tracked templates under `deploy/systemd/dose-cam.service` and `deploy/nginx/dose-cam`, installed them to the Pi, enabled `dose-cam.service` and `nginx.service`, and disabled the stock nginx default site. Reboot verification succeeded: after reboot, `dose-cam.service` was enabled/active, nginx was enabled/active, Flask was listening on port 8000, nginx was listening on port 80, and `http://pi-06-ioc.fel.duke.edu/` returned the DoseCam page.
- 2026-07-22: Renamed the web `Trigger` tab to `Options` and added an `Image rotation` selector with 0, 90, 180, and 270 degree choices. The default is 180 degrees for the current camera mount. Preview generation now accepts `image_rotation_degrees`, applies it to the display JPEG only, and reports `preview_rotation_degrees` in the preview API response. Verified live capture-preview through GPIO26 with 180 degree rotation: `captures/rotation/test_20260722_183019_514161_000001.raw`, 1/1 frame.
- 2026-07-22: Split ESP input trigger polarity from camera output polarity. Patched and flashed `DDG/DDG.ino` so the camera output remains fixed active LOW, while ESP inputs GPIO12/GPIO14 can trigger on active HIGH/rising edge or active LOW/falling edge. Firmware default is active HIGH. Added `/api/esp_status` to query the ESP status line and `/api/input_trigger_level` to set input polarity; the Options page now loads the toggle from the ESP status. Also changed the Pi GPIO26 test pulse helper to idle low with pulldown and create a clean low-high-low pulse. Verified active HIGH capture `captures/input_trigger/high_20260722_183741_434160_000001.raw` and active LOW capture `captures/input_trigger/low_20260722_183755_787320_000002.raw`, both 1/1 frames. Final state: ESP output disabled, input active HIGH, trigger mode `0`, GPIO26 input pulldown low, web service active.
- 2026-07-22: Added client-side preview zoom. The preview area now supports click-and-drag rectangle selection to zoom the displayed image, plus a `Restore View` button. This changes only the browser display transform; captured raw stream files and backend preview generation are unchanged. Deployed `templates/setup.html` and `static/setup.js` and verified the default page serves the new controls and zoom script.
- 2026-07-22: Fixed preview zoom drag being intercepted by the browser's native image-drag behavior. The preview image is now `draggable="false"`, CSS disables user dragging/selection on the image, and pointer handlers call `preventDefault()` plus block `dragstart`. Deployed the frontend fix and verified the live template/script include it.
- 2026-07-22: Added an Options-tab `Preview drag action` selector with `Zoom window` and `Native copy image`. Zoom remains the default and intercepts preview dragging for rectangle zoom; native mode restores browser image dragging/copy behavior by making the preview image draggable and letting drag events pass through. The setting is stored in browser `localStorage`.
- 2026-07-22: Made `Restore View` state-driven. The preview toolbar is hidden when the displayed preview is already at the baseline view and appears only after a client-side view change such as zoom. New captures/update-preview calls reset the preview to baseline, so the restore control does not obstruct the image when it has no effect.
- 2026-07-22: Changed the default preview layout to fit within the available browser window. The preview panel now uses a viewport-height-based size and the image uses `object-fit: contain`/max dimensions for the baseline view, avoiding page scroll just to see the full preview. Zoom still operates inside the clipped preview panel.
- 2026-07-22: Updated preview zoom so repeated drag-zooms operate on the current displayed view instead of restoring to full-frame on mouse down. The pointer start/end coordinates are now measured against the current rendered image box, so users can zoom progressively; only new captures, Update Image, or Restore View reset to baseline.
- 2026-07-22: Narrowed Options-tab controls. Options now uses a compact max-width control area with 180 px inputs/selects and modest spacing, while mobile still uses full-width controls. This avoids Options fields stretching across the full browser window.
- 2026-07-22: Reworked preview zoom to keep an explicit client-side transform state (`scale`, `tx`, `ty`) and convert pointer coordinates through that state into baseline image coordinates. This should make repeated zooms center and scale based on the currently displayed view rather than drifting away from the selected rectangle.
- 2026-07-23: Added a Files-tab `Confirm before delete` checkbox, checked by default. When unchecked, file/folder delete buttons skip the browser confirmation dialog for faster cleanup; backend path safety checks remain in place. The checkbox state is stored in browser `localStorage`.
- 2026-07-23: Replaced the Options-tab Enable Output/Disable Output buttons with a single `Shutter output enabled` toggle loaded from ESP status. Added short descriptions to the Options-tab display, timing, and ESP trigger settings; the text notes that rotation affects the preview/export path only and does not alter saved RAW dosimetry files.
- 2026-07-23: Fixed Targeting/Dosimetry gate-width profile separation. The Options page no longer copies the ESP's currently programmed `width_us` into whichever capture mode is selected when status is loaded, which had allowed the Targeting gate width to overwrite the Dosimetry field. Targeting and Dosimetry gate widths now persist separately in browser `localStorage`; Arm/Capture and Set Selected Gate Width send only the currently selected profile to the ESP.
- 2026-07-23: Added linear raw-frame stats to the Capture tab while keeping the image preview autoscaled. `update_preview_from_latest_raw` now returns `frame_stats` from the decoded 10-bit DN frame, including brightest pixel DN and coordinates, mean, median, p99, p99.9, min, and valid range. The browser displays the key stats below the capture message; saved RAW data and preview autoscaling are unchanged.
- 2026-07-23: Enforced a conservative 30 us minimum camera gate width. Raspberry Pi GS/IMX296 docs describe external-trigger exposure as the XTR low pulse plus about 14.26 us, and the product brief lists exposures as low as 30 us; a 10 us gate is below that practical floor. The Options inputs now have `min=30`, browser payloads clamp saved/typed values below 30 us, `/api/set_width` reports clamping, and `CameraCore.start_batch_raw` clamps `esp_width_us`/`exposure_us` to at least `MIN_CAMERA_GATE_US`.
- 2026-07-27: Fixed AlmaLinux/Firefox compatibility issue where `localStorage.setItem` raised `NS_ERROR_FAILURE` in `saveGateWidthProfile`, blocking Capture/Arm. Browser storage is now wrapped in safe read/write helpers; if a locked-down browser refuses storage, settings may not persist but acquisition controls continue.
- 2026-07-27: Changed Capture-tab `Save rpicam log` default to unchecked. Added a restricted save-directory picker next to `Save base`; it browses only the capture save root/subdirectories through `/api/files`, can create subdirectories through `/api/files/mkdir`, and sets the save base to `<selected folder>/run` with `run` as the default base name.
- 2026-07-27: Fixed log-saving semantics. `_run_batch_raw` previously always created `<stem>.log` as the `rpicam-raw` stdout/stderr target and merely omitted it from the status file list when `include_log` was false. It now sends output to `os.devnull` unless log saving is enabled, and API routes default omitted `include_log` to false.
- 2026-07-27: Local-only pending UI/timing updates; not yet uploaded to the Pi per user request. Added camera-mode-derived DN range fields to `frame_stats` and a Capture-tab brightness footnote. Replaced the Save base `Browse` text button with a folder icon button. Changed default Save base to `default/run`. Removed manual `Set Delay` and `Set Selected Gate Width` buttons; Arm and Capture program current delay/gate settings automatically. Changed Capture behavior so Targeting mode still triggers and updates preview, while Dosimetry mode during an active armed acquisition sends a single GPIO26 test trigger without preview refresh for multi-frame testing.
- 2026-07-27: Reorganized `README.md` so setup starts with hardware wiring/verification, then splits software installation into an AI-assisted path and a manual path. Moved current access and GitHub/repository status later as reference material.
- 2026-07-27: Corrected first-acceleration-stage beam-energy context from about 10 MeV to about 30 MeV.
- 2026-07-27: Added `-t 0` to the `rpicam-raw` acquisition command so externally triggered dosimetry runs do not stop from the default app timeout while waiting for sparse triggers. `Max frames` or `Stop / Finalize` should now be the normal stopping conditions.
- 2026-07-27: Added Files-tab raw stream viewing endpoints and UI. `.raw` rows now have a `View` action that loads one decoded frame at a time as an autoscaled PNG with raw DN stats, including Previous/Next/Latest navigation. This supports near-time inspection of saved or still-growing acquisitions without converting the authoritative raw data.
- 2026-07-27: Extended Files-tab exports/viewing. `.json`, `.log`, and `.txt` rows now have a text `View` action. The prior single-frame PNG download was replaced by PNG ZIP export for `.raw` streams: one autoscaled PNG per complete frame plus matching metadata JSON if present. Directory and current-run downloads also support PNG ZIP mode; each raw stream is placed in its own subdirectory within the archive.
- 2026-07-27: Improved Files-tab raw viewer ergonomics. Image display is now left of side-panel frame controls/stats, frame navigation has First/Previous/specific-frame/Next/Last controls, and the viewer uses the same Options-tab drag mode as the live preview for zoom-window vs native image dragging.
- 2026-07-27: Added conservative RAM spooling for raw acquisition to reduce SD-card wear. If `frames_requested * RAW_FRAME_BYTES` fits in `/dev/shm` while leaving 512 MiB free, `rpicam-raw` writes to `/dev/shm/dose_cam` and the file is moved to `captures/` on finalize. If the requested run is too large for RAM, acquisition falls back to direct disk capture. Status reports `ram_spooled` so the UI can show `(RAM spool)`.
- 2026-07-27: Widened the Files-tab file list and action column so normal desktop/control-room widths keep file action buttons on one row; narrow/mobile layouts still wrap.
- 2026-07-30: Diagnosed black preview after captures. Camera was detected and normal `rpicam-still` produced a dark image, but saved raw stream words were mostly around 3840 and multiples of 64, indicating 10-bit samples left-shifted in a 16-bit container. The decoder now shifts raw stream values down when they exceed the active 10-bit range before clipping/statistics/preview generation.
- 2026-08-26: Added and deployed `Focusing (live video)` as a third Capture mode. Selecting it automatically starts a 728 x 544, 12 fps MJPEG preview backed by `rpicam-vid`; selecting Targeting or Dosimetry stops the focus stream. Focus mode disables external triggering, uses the existing rotation setting, holds the camera lock against armed acquisition, and leaves its last frame displayed when stopped. Live verification through nginx produced 25 frames in about three seconds and stopped cleanly at 28 frames. Deployment confirmed the Pi's authorized automation pairing is user `codex` with local key `shv_bias_filter_agent_ed25519`.
- 2026-08-26: Added a live focus-quality indicator based on a contrast-normalized edge-detail score. The Focusing UI shows the current score, best score seen during that focus session, and current percentage of that peak so the operator can focus by maximizing the measurement and recognize when the lens has moved past the optimum.
- 2026-08-26: Bench-tested the newly connected optoisolated laser-input path using Analog Discovery 2 W2. The AD2 reported a 5.0 V maximum, so tests used one 100 us, 4.999 V committed pulse rather than the requested 5.5 V. Active-HIGH ESP input produced no response; active-LOW/falling-edge produced GPIO15 -> Pi GPIO16 monitor edges (about 890 us measured for a configured 1 ms output gate). Two separately armed camera trials each captured exactly 1/1 frame from the same W2 stimulus configuration, saved under `captures/laser_input/`. Linux GPIO callbacks missed the monitor edge during camera-loaded trials even with a 10 ms gate, so monitor timing remains qualitative; the no-camera monitor trial and camera frame trials together verify the chain. Added `tools/ad2_w2_pulse.py` and `tools/pi_gpio16_monitor_probe.py` for repeatable follow-up tests.
- 2026-08-26: Focusing mode now uses the Targeting gate-width profile as the free-running video's per-frame `rpicam-vid --shutter` value. This does not involve the ESP gate while focus video is active; it makes focus-preview brightness use the operator's targeting exposure setting.

## 2026-10-14 - Beam-profile fit, dose calibration, timing defaults (pi-06-ioc)

Deployed live on pi-06-ioc at operator request (Eric, during the 10/13-10/14 run window, with rollback required).
Status: **verified** 2026-10-14 by API tests and browser tests against
`FLASH/PolyAlDosCal_20261013_161112_732305_000006.raw`, except where noted.

What changed (code in this folder is synced to what is deployed):
- New `dose_cam/beam_fit.py`: despike (3x3 median, default 40 DN), background
  (`none` | `baseline` 2D poly fitted to ROI border | `file` = mean of a reference .raw),
  rotated elliptical 2D Gaussian + offset (scipy least_squares, soft_l1),
  GOF = reduced chi^2 (noise from ROI border), R^2, RMS residual. Works in DISPLAY
  orientation (frame rotated like the UI) so ROI and overlay match the screen.
- New endpoints in `dose_cam.py`: `POST /api/analysis/fit`, `GET /api/analysis/fit.png?token=`,
  `GET|POST /api/analysis/calibration`.
- New `static/beamfit.js` (+ CSS and two mount divs in `templates/setup.html`): "Beam profile fit"
  panel under the main-page image and in the Files viewer. Auto ROI with manual override;
  "Draw ROI on image" button arms ONE drag (normal drag-to-zoom unaffected) - verified while zoomed.
  Rendered result image has the ROI box and 1/2-sigma ellipses burned in; optional peak suppression.
  Warns when baseline-mode ROI half-width < 3 sigma (tight ROIs bias sigma/amplitude low).
- Options tab "Dose calibration": DN per Gy + note, Display units DN/Gy (Gy only selectable when
  calibrated). Stored in `~/.config/dosecam/dn_calibration.json` (outside the read-only code dir;
  survives rollback). Per-pixel values convert to Gy; integrals are reported in Gy*px^2.
  Currently EMPTY (test values were cleared).
- Timing defaults: delay fallback 5 -> 200 us (setup.html, setup.js, dose_cam.py x3, camera_core.start_batch_raw).
  Dosimetry width default was already 100 us.

Not tested: main-page ("live") fit through the UI after a fresh capture - the restart cleared the
loaded frame and no trigger was sent. Same code path was tested via the module with a stub.

ESP8266 boot defaults FIXED (reflashed 2026-10-14 ~09:54 EDT, operator-requested): `DDG/DDG.ino` now
boots with `delay_us = 200`, `width_us = 100` (was 100 / 10; an ESP reset silently reverted the delay,
the likely cause of the 2026-10-13 mistimed shots). No other firmware change. **Verified**: upload hash
verified; `/api/esp_status` right after the post-upload reset reported `enabled=0 armed=1 delay_us=200
width_us=100 input_active_level=HIGH`. Not re-tested: GPIO26 -> ESP -> camera trigger path (logic unchanged).
Build: `arduino-cli compile --fqbn esp8266:esp8266:huzzah`, upload over the CP2104 by-id port with
dose-cam stopped (it holds the port). Firmware rollback: `bash /home/codex/backups/restore_esp_firmware.sh`
(writes the full 4 MB image read before flashing; copy also in `analysis_20261014/`).

Rollback: `bash /home/codex/backups/restore_dose_cam.sh` (restores the 4 original files from
`/home/codex/backups/dose_cam_code_20261014_091500.tar.gz`, removes the 2 new files, restarts).
Off-Pi copy: `analysis_20261014/rollback_dose_cam_code_20261014_091500.tar.gz`.

## 2026-10-26 - Default DN->Gy calibration with uncertainty; fit-parameter errors

Status: **verified locally** (synthetic-frame tests of `beam_fit.py`, Flask test client against the real
routes with hardware modules stubbed, jsdom run of `setup.html` + `beamfit.js`). **Not deployed**: pi-06-ioc
did not answer through the tunnel on 2026-10-26 (SSH `kex_exchange_identification: Connection reset`).
Working-tree change only, not committed. Files: `dose_cam/beam_fit.py`, `dose_cam/dose_cam.py`,
`dose_cam/static/beamfit.js`, `dose_cam/templates/setup.html` (identical on master and combine-single-pi before this change).

- Built-in default calibration `DEFAULT_CALIBRATION` in `beam_fit.py`: **1.0563 DN/Gy +/- 3.19 % (1 sigma)**.
  k = mean fitted peak 42.251 DN (local-baseline fits, frames of PolyAlDosCal_..._000006) / mean film peak
  dose 39.9997 Gy (EBT-XD well_041: B1 40.94, A1 39.61, A2 39.75, A3 39.70; film ROI 1-6 = A1,A2,A3,B1,B2,B3).
  Statistical 1.09 % = sqrt(a^2/4 + b^2/4), a = 1.50 % camera per-shot sd, b = 1.57 % film per-well sd.
  Systematic 3.0 % = film absolute accuracy, **PROVISIONAL** (typical EBT-XD value; replace with the film
  group's stated figure). Single dose level, zero intercept; linearity untested.
  Replaces the earlier ~1.4 DN/Gy, which matched the pre-film expectation of ~30 Gy/pulse.
- A saved custom value (Options) still overrides the default; "Reset to default" removes it. Legacy files with
  `dn_per_gy: null` fall back to the default.
- Options: new "Calibration uncertainty (%, 1 sigma)" field and "Include calibration uncertainty in Gy errors"
  checkbox (default on, stored server-side as `include_cal_err`). Gy is always selectable now.
- Fit results now carry 1-sigma statistical errors for every parameter (Gauss-Newton covariance from the plain
  model Jacobian, scaled by residual variance). Checked against 40 synthetic frames: empirical scatter /
  reported error = 1.09 +/- 0.12. Real frames have correlated noise (hit streaks, row banding), so true fit
  errors are somewhat larger; measured shot-to-shot spread (1.5 %) is ~4x the fit error (0.36 %).
  Gy errors = fit error (+) calibration error in quadrature when the checkbox is on.

To deploy (when the Pi answers): back up the 4 files, copy them in, `chmod 505` the code dirs, restart
`dose-cam`, then POST `{"reset_default": true}` to `/api/analysis/calibration` so a previously saved custom
value (reportedly 1.4) no longer overrides the new default. Rollback: restore the 4 files from the backup.
