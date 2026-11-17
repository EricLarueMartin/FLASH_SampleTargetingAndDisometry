# Integrated FLASH rig: roadmap

Planning document, 2026-10-16. Both Pis are shut down and there is no site access
for roughly two weeks, so everything here is designed to be **written and tested
against simulators first**, with a single hardware session when access returns.

Supersedes the step list in `COMBINE_SINGLE_PI.md` for the access-day work. That
document is still the reference for the *fallback* configuration (ESP8266 retained,
DoseCam on its own Pi) and for the verified-from-source compatibility findings.

## End state

One Pi (**elm-ioc-00**), one microcontroller (**the stepper ESP32**), one web page
with tabs, EPICS on top, and a sequencer that walks a loaded tray of targets firing
a prescribed pulse pattern at each one while measuring dose and watching fiducials.

```
            opto ──► ESP32 ──► camera XTR            steppers ◄── ESP32
                       │                                            ▲
elm-ioc-00 ────────────┴── /dev/ttyACM0 ──► motor_control (device server, :8081)
   ├── OV5647 (free-running)  ──► positioner view + fiducial tracking
   ├── IMX296 (ext. trigger)  ──► dose-cam (device server, :8000)
   ├── flash-sequencer (orchestrator + EPICS IOC, :8090)
   └── nginx :80  ──► tabbed shell { Motor | DoseCam | Run }
```

Two device servers that each own exactly one piece of hardware, one orchestrator
that owns the experiment, one front door. Nothing gets merged into a monolith.

## Phase 0 — now, no hardware (the next two weeks)

Everything in this phase is written and unit-tested off-site.

### 0.1 ESP32 firmware: absorb the delay generator

Port `DDG/DDG.ino` into `StepperController` as `MyDDG.h`. Design rationale and the
flash-cache constraint are in `StepperController/DDG_ON_ESP32.md`; the essentials:

- Handlers `IRAM_ATTR`, GPIO interrupt allocated with `ESP_INTR_FLAG_IRAM`.
- Only `volatile uint32_t` / `volatile bool` in the handler path. No `String`, no
  ArduinoJson, nothing that can fault to flash.
- Register the interrupt from `setup()` so it lands on **core 1**. Core 0 stays the
  stepper task's alone.
- Use a hardware timer for the delay and the width, exactly as the ESP8266 version
  does. If jitter still matters after measurement, have the ISR start an **RMT**
  one-shot instead, which removes the delay/width jitter entirely.

New serial commands, in the existing word-command style of `MySerial.h`:

| Command | Effect |
| --- | --- |
| `SETDELAY <us>` | Delay from trigger edge to shutter assert |
| `SETWIDTH <us>` | Shutter gate width |
| `GETDELAY` / `GETWIDTH` | Report |
| `ARM 0\|1` | Enable/disable the output |
| `GETARMED` | Report armed state and remaining arm timeout |
| `TRIG` | Software trigger, for bench use |
| `DDGSTATUS` | One line: armed, delay, width, shots since arm, last trigger age |

**Interlock — the reason to do this at all.** Two processors cannot enforce "never
fire while moving"; one can:

- `ARM 1` is refused while any `steppers[ct]->isRunning()`.
- `MOVE` / `MOVEABS` are refused while armed, with a distinct error string so the
  sequencer can tell this apart from a bad argument.
- Arm auto-expires after a configurable timeout (default 60 s) so a forgotten arm
  does not sit live.
- Both states appear in `UPDATE` so the existing 1 s/10 s push already carries them.

Testable now: build it, and exercise the parser and the interlock state machine on a
desktop with a stub `AccelStepper`. The timing itself cannot be verified without a
scope, so leave that explicitly marked unverified until the access session.

### 0.2 motor_control becomes the only serial owner

One microcontroller means one port, and `dose_cam` can no longer open it itself. Add
to `camera_stream/app.py`:

```
GET  /ddg/status            -> {armed, delay_us, width_us, shots, interlock}
POST /ddg/config            {delay_us, width_us}
POST /ddg/arm               {armed: bool, timeout_s: int}
POST /ddg/trigger           software TRIG, bench only
```

These reuse the existing `serial_lock` semaphore, so no new concurrency surface.

In `dose_cam/camera_core.py`, `_configure_esp_serial()` and `_disable_esp_serial()`
gain an HTTP path behind a new env var:

- `DOSECAM_DDG_URL` set (e.g. `http://127.0.0.1:8081`) -> talk to motor_control.
- unset -> the current `pyserial` path to the ESP8266.

That one switch keeps **pi-06-ioc working unchanged as the fallback** while the new
hardware comes up. Do not delete the serial path.

### 0.3 Tabbed shell

nginx on :80 serves a small static shell with three tabs; each tab is an **iframe**
onto the app that already exists:

| Tab | Source |
| --- | --- |
| Motor | `http://<pi>:8081/` (motor_control) |
| DoseCam | `/` on :8000 via the existing nginx proxy |
| Run | `http://<pi>:8090/` (sequencer, phase 3) |

Iframes rather than subpath proxying, deliberately. Both apps serve from their own
root today; re-pathing them means `SCRIPT_NAME` handling, Socket.IO `path=` rewrites,
and MJPEG buffering rules, all for cosmetics. Iframes need **zero** change to either
app, keep their independent rollback, and keep `/video_feed` and Socket.IO working
exactly as they do now. Revisit only if shared cross-tab state is needed, and by then
the sequencer owns that state anyway.

Shell carries one global element outside the tabs: a persistent **ABORT** button and
a status strip (armed? moving? sequence running?), polling `/ddg/status` and the
sequencer. That must be visible on every tab.

### 0.4 Simulator

A fake ESP32 (pty speaking the serial protocol, including the interlock) and a fake
camera pair. Enough to run the whole stack on a laptop. This is what makes the next
two weeks productive, and it pays for itself again every time the rig is unavailable.

## Phase 1 — the access session

Order matters: do all the wiring in one pass, then bring up software.

1. Record stepper positions (`UPDATE`) **before** anything. Last known: motor 0 =
   134620, motor 1 = 0. Powering down zeroes them; restore with `SETPOS`, never by
   homing.
2. **Dump `LIST`** from the ESP32 and commit the settings JSON, and recover the
   flashed sketch. The repo copy is stale - this gates the pinout.
3. Move the IMX296 to elm-ioc-00 CAM/DISP 0 (OV5647 stays on CAM/DISP 1, cable
   undisturbed). Bring the 15-to-22-pin adapter cable.
4. Rewire the trigger chain from the ESP8266 to the ESP32 per the pinout below. Fit
   the XTR pull-up. Retire the ESP8266 to the fallback kit - keep it wired as a unit
   so pi-06-ioc can be restored by moving the camera and one USB lead back.
5. `config.txt`: `camera_auto_detect=0`, `dtoverlay=imx296,cam0`, `dtoverlay=ov5647,cam1`.
6. Bring up software (`COMBINE_SINGLE_PI.md` steps 3-6 and 10-14, minus everything
   about the ESP8266's USB port, which no longer exists).
7. **Scope the trigger chain.** This is the one thing simulation cannot do: opto
   input edge to XTR assert, measured over a few hundred shots. Record min / max /
   jitter at 200 us delay, 100 us width, and compare against the ESP8266 numbers so
   the "occasional long delay" either disappears or is quantified.
8. Verify the interlock on real hardware: `ARM 1` during a move must be refused;
   `MOVE` while armed must be refused.
9. Two libcamera processes concurrently - still the one unverified compatibility
   claim. `rpicam-hello --camera 0 & rpicam-hello --camera 1`.

## Pinout

### Target board: Adafruit Feather ESP32-S3, No PSRAM — chosen 2026-10-16

The operator has several unused, and prefers to keep the Feather ESP32 V2 boards free
for general use. The S3 is a good fit for this job - better than the V2 in the ways
that matter here:

- **No input-only pins.** Every ESP32-S3 GPIO is bidirectional with internal pull-up
  and pull-down. The classic ESP32's GPIO34-39 problem (inputs that cannot bias
  themselves, the reason the current limit switches float) does not exist.
- **No-PSRAM leaves GPIO35-37 free.** Those are taken by octal PSRAM on other S3
  variants; here they are ordinary pins on the SCK/MOSI/MISO header positions.
- **Fewer strapping pins on the headers.** The S3's straps are GPIO0, 3, 45 and 46.
  Only GPIO3 (the SDA position) reaches a header, and it only matters if the JTAG
  source eFuse has been burned. GPIO0 is the BOOT button; 45/46 are not broken out.
- Same dual-core Xtensa arrangement, so the core-0 stepper task / core-1 everything
  else split carries over unchanged. Same flash-cache rule: DDG handlers `IRAM_ATTR`,
  interrupt allocated with `ESP_INTR_FLAG_IRAM`.

**Correction to earlier notes.** An earlier draft of this plan (and the 2026-10-16
chat) said the S3's Event Task Matrix could make the delay generator fully hardware.
That was wrong: **the ESP32-S3 has no ETM** - it arrived with the ESP32-C6 / H2 / P4.
The S3 has the same tools for this as the classic ESP32: GPTimer driven from an ISR
(the plan of record), RMT for an exact delay-then-pulse once started, and MCPWM, whose
GPIO sync input can start a timer whose comparators set and clear the output with no
CPU involvement at all. MCPWM is the zero-jitter path on either chip; prototype it
after the ISR version works, not instead of it.

#### Keep the external USB-serial adapter - do not use the S3's native USB for the link

The S3 has native USB, which is tempting to use as the serial link to the Pi. Don't.
Today the ESP32 talks on a hardware UART through a **separate** USB-serial adapter,
and that is exactly why restarting `motor_control.service` does not reset the board
and zero the positions (observed October 2026, four restarts). On native USB:

- the host can drive a reset through the port's line state (Espressif documents the
  controller putting the chip into download mode automatically); whether pyserial's
  default open trips it is unverified, which is reason enough not to depend on it, and
- any chip reset re-enumerates the USB device, so `/dev/ttyACM*` vanishes and
  reappears under the Flask app's open file handle.

Either would turn every service restart into a position loss. So: the existing
adapter on a hardware UART carries the link, motor_control opens the **adapter's**
`/dev/serial/by-id/` path, and the S3's own USB-C is used for power and for flashing
only. Nothing on the Pi ever opens the native port during operation.

#### Map

Grouped by header so each function lands on a contiguous run of pins - six motor
outputs on one side, limit switches together, delay generator together.

| Function | Silkscreen | GPIO | Config |
| --- | --- | --- | --- |
| UART RX from adapter | RX | 38 | `MySerial.begin(115200, SERIAL_8N1, 38, 39)` |
| UART TX to adapter | TX | 39 | |
| Motor A step | 5 | 5 | output |
| Motor A dir | 6 | 6 | output |
| Motor A enable | 9 | 9 | output |
| Motor B step | 10 | 10 | output |
| Motor B dir | 11 | 11 | output |
| Motor B enable | 12 | 12 | output |
| X min limit / X home | A0 | 18 | `INPUT_PULLUP`, switch to GND |
| X max limit | A1 | 17 | `INPUT_PULLUP`, switch to GND |
| Z min limit | A2 | 16 | `INPUT_PULLUP`, switch to GND |
| Z max limit / Z home | A3 | 15 | `INPUT_PULLUP`, switch to GND |
| Opto trigger in | A4 | 14 | `INPUT_PULLUP`, falling edge |
| Camera XTR out | A5 | 8 | output, active LOW |
| Monitor out to Pi | SCK | 36 | output |
| Pi bench trigger in | MOSI | 35 | `INPUT_PULLDOWN`, falling edge |

**16 signal pins of the 21 broken out.** Spare: MISO (GPIO37), D13 (GPIO13, shared with
the red LED), SDA (GPIO3), SCL (GPIO4). SDA/SCL are the board's I2C pair and carry **on-board 5 k
pull-ups** for the STEMMA QT connector, so they are not neutral pins - keep them for a
future I2C display or sensor rather than repurposing them. No on-board status
indication is planned: the controller sits outside the vault and nobody is in the
radiation exclusion area while firing, so armed / moving / fault state belongs in the
web shell's status strip, where the operator actually is. GPIO7 switches STEMMA QT
power; it is not on a header.

#### Verification (2026-10-16)

| Claim | Result | Source |
| --- | --- | --- |
| Every GPIO number in the map above | **Matches exactly** - A0-A5 = 18/17/16/15/14/8; SCK/MOSI/MISO = 36/35/37; RX/TX = 38/39; SDA/SCL = 3/4; D5/6/9/10/11/12/13 = GPIO 5/6/9/10/11/12/13; LED 13 | arduino-esp32 `variants/adafruit_feather_esp32s3_nopsram/pins_arduino.h` |
| No input-only pins on the S3 | **Confirmed** - `// No GPIO is input only` | ESP-IDF `components/soc/esp32s3/include/soc/soc_caps.h` |
| Strapping pins are GPIO0, 3, 45, 46 | **Confirmed** | ESP-IDF ESP32-S3 GPIO reference |
| No header pin is a problematic strap | **Confirmed** - Adafruit: "No pins are shared, and no pins are 'special' bootstrapping pins." GPIO3 (SDA) is a strap per Espressif but only for JTAG source select, effective only if that eFuse is burned | Adafruit ESP32-S3 Feather pinouts guide; ESP-IDF GPIO reference |
| GPIO35-37 free on No-PSRAM | **Confirmed** - they are claimed only with octal flash/PSRAM or on S3R8/S3R8V parts; this board is 8 MB flash, no PSRAM, and Adafruit routes them to the SPI header | ESP-IDF GPIO reference; Adafruit guide |
| GPIO19/20 (USB) and 26-32 (flash) unused by the map | **Confirmed** - none of them is on a header | ESP-IDF GPIO reference; variant file |
| S3 has no ETM | **Confirmed** - no ETM capability defined for the S3 | `soc_caps.h` |
| MCPWM and RMT available on S3 | **Confirmed** - `SOC_MCPWM_SUPPORTED 1`, `SOC_RMT_SUPPORTED 1` | `soc_caps.h` |
| Pin state during boot is undefined | **Consistent with Espressif**: "Do not rely on the default configurations values in the Technical Reference Manual" - the bootloader may change them. Hence the early-init mitigation rather than a reliance on reset defaults | ESP-IDF GPIO reference |
| Native USB can reset the chip from the host | **Partly confirmed** - "The USB Serial/JTAG Controller is able to put the ESP32-S3 into download mode automatically," i.e. the host can drive reset through line state, and the device disconnects whenever the USB peripheral goes away. Not confirmed that pyserial's *default* open trips it. The recommendation to keep the external adapter rests on preserving a known-good property, not on a demonstrated failure | ESP-IDF USB Serial/JTAG console guide |

Not verifiable from documentation, still for the bench: whether the camera biases
`Trig+` itself, and GPIO behaviour through an actual boot on a scope.

**No external resistors, and no Pi-side change for the bench trigger.** The S3's
internal pull-down on GPIO35 defines the line when the Pi releases GPIO26 to input
after each pulse, which the classic ESP32's input-only GPIO34 could not.

#### Boot-window behaviour, honestly stated

Between power-on and the firmware configuring its pins, S3 GPIOs are not guaranteed to
sit at the level we want, so XTR (active LOW) and the two enables are briefly
undefined. Without external parts, the mitigations are:

1. **Shrink the window.** Drive XTR HIGH and set both enables as the very first thing
   the firmware does - in an early-init hook (`initVariant()`, or a function marked
   `__attribute__((constructor))`), not after `deserializeJson()` in `setup()` as the
   current sketch would. That leaves only the ROM bootloader's ~100-300 ms.
2. **Check the camera side.** Measure `Trig+` to GND on the camera board, power off.
   If the camera already biases its own trigger input high - common for an active-low
   trigger - the window is a non-issue.
3. **Know what it costs if neither helps.** The camera only acts on XTR while DoseCam
   has set `trigger_mode=1` and a capture is running. The ESP resets only on Pi
   reboot, power loss, a USB unplug, or a reflash - none of which happen
   mid-acquisition in normal operation. The realistic worst case is one junk frame,
   and only if the board resets during a capture, in which case the zeroed stepper
   positions are the bigger problem.

The same window applies to the motor enables, and it does not matter: on the
vertical CoreXZ any reset means re-homing anyway (see "Power policy" below), so a
gantry that settles during the boot window costs nothing that homing doesn't already
pay for.

#### Bench checks before soldering

- ~~Confirm the silkscreen-to-GPIO mapping~~ - **verified 2026-10-16**, see
  "Verification" below. Still worth a glance at the physical silkscreen when wiring.
- **Firmware port.** Arduino-ESP32 3.x (IDF 5) for the S3: `esp_task_wdt_init()`'s
  signature changed from 2.x; `HardwareSerial MySerial(2)` is fine (the S3 has
  UART0-2); leave *USB CDC On Boot* enabled or not as you like, since `MySerial` is a
  hardware UART either way and is unaffected.
- **Flip the limit invert flags**, as for any move from pull-down to pull-up sense.

### Alternative: Feather HUZZAH32 V2

Kept for reference in case an S3 is unavailable. The S3 map above is the plan of record.


Earlier drafts of this document asked for four external resistors: one pull-up on the
camera XTR line, and pull-downs on GPIO34/36/39. **Both were artifacts of the pin
assignment, not of the design**, and both disappear by moving signals onto pins that
can bias themselves. The revised map below needs no external components.

#### V2: the two silicon facts that drive it

1. **GPIO34-39 are input-only and have no internal pull-up or pull-down at all.** They
   cannot bias anything. The current firmware's `pinMode(..., INPUT_PULLDOWN)` on
   GPIO34/36/39 is a silent no-op, so the limit and home inputs are floating *today* -
   which is worth fixing on its own, given the positioner redesign note already
   suspects RF pickup on those lines. Put mechanical switches and the open-collector
   opto output on **ordinary GPIOs with `INPUT_PULLUP`** and the external parts are
   unnecessary. Reserve 34/36/39 for sources that actively drive both levels.
2. **Only GPIO0, GPIO5 and GPIO15 come out of reset with an internal pull-up enabled.**
   Everything else floats from power-on until `setup()` runs. This is the whole reason
   the ESP8266 needs no XTR pull-up and the ESP32 appeared to: ESP8266 GPIOs come out
   of reset as inputs *with* weak pull-ups, ESP32 ones do not. Putting the active-low
   XTR output on **GPIO5** restores that behaviour for free - the line idles HIGH
   (inactive) through the whole boot window with no resistor. GPIO0 is tied to the
   auto-reset circuit; don't use it.

#### V2 map

Separate enables, as requested - the budget supports it with pins to spare.

| Function | Pin | Config | Note |
| --- | --- | --- | --- |
| UART2 RX from Pi | GPIO7 | - | existing |
| UART2 TX to Pi | GPIO8 | - | existing |
| Motor A step | GPIO14 | output | existing |
| Motor A dir | GPIO32 | output | existing |
| Motor A enable | GPIO15 | output | existing; internal pull-up at reset holds it HIGH, so an active-low driver is disabled through boot |
| Motor B step | GPIO33 | output | |
| Motor B dir | GPIO27 | output | |
| Motor B enable | GPIO13 | output | also the onboard red LED - a free "motors energised" indicator |
| X min limit / X home | GPIO19 | `INPUT_PULLUP` | switch to GND |
| X max limit | GPIO21 | `INPUT_PULLUP` | switch to GND |
| Z min limit | GPIO22 | `INPUT_PULLUP` | switch to GND |
| Z max limit / Z home | GPIO4 | `INPUT_PULLUP` | switch to GND; redesign note homes the vertical axis upward |
| Opto trigger in | GPIO25 | `INPUT_PULLUP`, falling edge | supplies the bias the ESP8266's reset-default pull-up provides today |
| Camera XTR out | **GPIO5** | output, active LOW | internal pull-up at reset - no external part |
| Monitor out to Pi | GPIO26 | output | diagnostics |
| Pi bench trigger in | GPIO34 | input only | see caveat below; first thing to cut |

**16 of roughly 20 broken-out pins. Spare: GPIO12, GPIO20, GPIO36, GPIO39.**

Home switches are deliberately **not** separate pins - homing against the same
switches that serve as limits is what the mechanical design calls for, and it saves
two pins over the current three-per-motor scheme.

#### V2 caveats

- **The breakout list is from memory.** Confirm against the board silkscreen and
  Adafruit's pinout page before soldering - in particular that GPIO4, 5, 13, 19, 21,
  22, 25, 26, 27 and 33 are all brought out on the V2. The V2 is the ESP32-PICO-MINI-02
  part, which is why GPIO7/8 (and GPIO20) are usable here at all.
- **Never put a pulled-high signal on GPIO12.** It is MTDI and is sampled at reset to
  set the flash voltage; held high at boot the module will not start. It is in the
  spare list, but only for an output that idles low, or for nothing.
- **GPIO5 is a strapping pin (sampled HIGH at reset).** Its internal pull-up is what we
  are relying on, so confirm nothing on the camera side pulls `Trig+` down: measure
  Trig+ to GND on the camera board with power off. If the camera already pulls Trig+
  up, this whole question was moot anyway. Also confirm with the scope - which will be
  out for the trigger-chain timing regardless - that GPIO5 is quiet during boot.
- **Flip the invert flags.** Moving from `INPUT_PULLDOWN` + switch-to-3V3 to
  `INPUT_PULLUP` + switch-to-GND inverts the sense of every limit and home input;
  `invertLow` / `invertHigh` / `invertHome` in the settings JSON change accordingly.
- **Pi bench trigger.** `camera_core.py` calls `_restore_gpio26_input()` after each
  pulse, leaving the Pi pin floating - which an input-only ESP32 pin cannot bias, so
  it would be open to spurious triggers. Either leave the Pi pin driven at its idle
  level (a one-line change, and better practice anyway), or drop this wire entirely:
  once the DDG lives on the ESP32 that motor_control already owns over serial, `TRIG`
  does the same job with no hardware, and the real interrupt edge can be exercised
  from the opto side with the AD2.

#### On common versus separate enable (either board)

Separate, per the operator. Worth recording anyway: in CoreXY, **disabling one motor
and not the other is never a correct state** - the carriage moves and both belts carry
load - so `ENABLE` / `DISABLE` should act on the pair regardless of having two pins,
and the UI should not offer a per-motor disable.

#### Power policy: energised during use, off between runs, re-home on enable

Operator decision 2026-10-16. **No counterweight** - the CoreXZ belt path has no
practical place for one short of a separate pulley system. The motors stay energised
for the whole of a session and are switched off between runs to save power; when they
are switched off the gantry drops, and that is accepted. Position is re-established
by homing every time, not restored.

What this changes in the firmware and the plan:

- **`DISABLE` invalidates position.** The firmware should clear a `homed` flag on
  disable (and on reset), and report it in `UPDATE` and `DDGSTATUS`.
- **`MOVEABS` and `ARM 1` refuse while not homed**, with a distinct error string.
  Relative `MOVE` and `HOME` stay allowed so the axes can be recovered. This joins the
  moving/armed interlock from 0.1.
- **`ENABLE` does not imply a move.** Homing stays an explicit command; energising the
  motors must never start motion on its own.
- **The `SETPOS`-restore procedure retires with the old mechanism.** On today's rig a
  Pi reboot zeroes the counters and `SETPOS` restores them without moving, because the
  axes hold where they were. On the CoreXZ a reset or a disable means the gantry has
  physically moved, so a restored counter would be wrong; home instead. The
  `flash-operations` skill's "restore with SETPOS, never home" rule must be rewritten
  when the new mechanism goes in.
- **Sequencer**: a session begins with ENABLE -> HOME -> re-targeting origin, and the
  run record stores the homing result. Any abort that disables the motors forces a
  re-home before the next target.

### Raspberry Pi 40-pin header, elm-ioc-00

Viewed from above, USB/Ethernet at right; odd row nearest the PCB edge.

| Pi pin | BCM | Dir | To | Wire | Required |
| --- | --- | --- | --- | --- | --- |
| 37 | GPIO26 | out | S3 GPIO35 (MOSI) | brown/white | Optional once `TRIG` exists over serial, but keep it - it is the only path that exercises the real interrupt edge rather than the timer |
| 36 | GPIO16 | in | S3 GPIO36 (SCK, monitor) | green/white | Optional, bench monitor |
| 39 | GND | - | Camera J3 `Trig-` | black | **Yes** |

Verified from source: `camera_stream/app.py` and `camera_worker.py` claim no Pi GPIO
at all, so these three pins are free on elm-ioc-00.

### Signal chain after the change

```
laser charge pulse ──► OptoIsolator J2.2 ──► S3 GPIO14 / A4  (INPUT_PULLUP, falling edge)
                                                  │ delay_us
                                                  ▼
                                   S3 GPIO8 / A5 ──► camera J3 Trig+   (active LOW, width_us)
                                   camera J3 Trig- ──► Pi pin 39 GND
                                   S3 GPIO36 / SCK ──► Pi pin 36 / GPIO16 (monitor)
Pi pin 37 / GPIO26 ──► S3 GPIO35 / MOSI  (bench trigger, INPUT_PULLDOWN, optional)
```

Opto supply stays as it is: J2 pin 3 to 3V3, J2 pin 1 to GND - now on the S3's
rails rather than the ESP8266's.

### Resolved 2026-10-16: there are two steppers, and this repo copy is stale

Confirmed by the operator. `StepperController/MySteppers.h` here has
`#define MAX_STEPPERS 1` and `MyConfig.h`'s `default_settings` declares one stepper,
so **the firmware in this repository is not what is flashed on the ESP32.** Nothing
in `StepperController/` should be trusted as current until it is reconciled.

First task of the access session, before any soldering or firmware work:

1. `LIST` on the ESP32 and commit the settings JSON, which gives motor 1's step,
   direction, enable and limit pins.
2. Recover or rebuild the flashed sketch, commit it, and tag the commit with the
   build that is actually on the board.

Only then is the delay-generator pinout above final - motor 1's three or six pins
come out of the same budget. Current free-pin assumption (GPIO25/26/27/33) holds only
if motor 1 sits on pins outside that set.

### Kinematics change coming

The two motors are being re-mapped to **CoreXY-style belt kinematics** (holding one
motor and moving the other moves the head in both axes), with user coordinates
remaining X and Z. Two consequences that the rest of this document depends on, so
they are recorded here even though the kinematics work itself is out of scope:

- **Do the transform in firmware, not in the UI.** The firmware already owns step
  counts, limits and the stop logic; splitting the kinematic constants between
  firmware and JavaScript means any disagreement shows up as an unexplained position
  error. Report user coordinates on the wire; keep raw motor steps available behind a
  separate command for diagnostics.
- **"Arrived" is a property of the pair, not of one motor.** In CoreXY a user-axis
  move is not complete until both motors have stopped. The arrival event defined in
  "Telemetry" below must be emitted once, for the pair.

### Separate firmware finding

`initSteppers()` calls `pinMode(..., INPUT_PULLDOWN)` on GPIO34, 36 and 39, which is a
silent no-op - those pins have no internal pull resistors, so the limit and home
inputs are floating today. Given the positioner redesign note suspects RF pickup on
those lines, this is worth fixing independently of the delay generator. The pin map
above fixes it by moving the switches onto ordinary GPIOs with `INPUT_PULLUP`, which
needs no external parts.

## Telemetry: position reporting during a move

Current symptom: updates during a move are both too chatty and too late - the camera
shows the carriage has stopped before the reported position catches up.

The mechanism is the reporting *model*, not the rate. `updateSerial()` pushes
`GETPOS` plus `GETSPEED` per changed motor on a periodic tick, and that is the only
thing the UI has to go on. **There is no motion-complete event anywhere in the
protocol.** The page can therefore only infer that a move finished from the *absence*
of further updates, which costs it at least one full tick and is exactly what is
being seen. Raising the tick rate makes the stream noisier without fixing it; the
missing message is the problem.

Note the diagnosis above is read off the repo copy of the firmware, which is known
stale (see "Resolved 2026-10-16"). Confirm against the flashed sketch before changing
anything.

### Firmware

- **Add an explicit arrival event.** Edge-triggered when the move completes - for
  CoreXY, when *both* motors have stopped - carrying the final authoritative position:
  `DONE <x> <z>`. Sent exactly once per move. This removes the perceived lag outright,
  whatever the streaming rate is.
- **Make the streaming rate a setting**, and make it motion-dependent: a modest rate
  while running (10 Hz is plenty for a human watching a video feed), nothing at all
  while idle beyond the slow keep-alive.
- **One line per sample, not three.** Fold position, speed and limit flags for both
  axes into a single compact record rather than separate `GETPOS` / `GETSPEED` lines
  per motor. Fewer, denser lines cost less on the wire and less to parse at both ends.
- Keep the existing verbose `GETPOS` / `UPDATE` replies for the Terminal tab and for
  scripted use. This is about the unsolicited stream, not the command set.

### Pi side

- **Release `serial_lock` before emitting.** `read_serial()` currently holds the lock
  across `socketio.emit`, so outgoing commands queue behind inbound traffic. Read
  under the lock; parse and emit outside it. This matters well beyond UI smoothness -
  it is in the path of a `STOP`, and once firing is involved that is the abort path.
- **Coalesce instead of relaying.** Parse position records into a state dict and have
  a separate greenlet emit consolidated state at a fixed UI rate. Emit non-position
  lines (replies, errors, limit messages) immediately as terminal text. The browser
  then updates at a steady rate regardless of what the wire is doing.
- **Stop printing every line.** `print(f"Received: {data}")` on every message, under
  the lock, goes to the journal and is already why journal queries there have to be
  windowed and filtered. Log non-position lines, and position lines at most once a
  second.
- **Show staleness in the UI.** Timestamp each position and grey the reading when it
  is older than a few hundred milliseconds. A number that visibly goes stale is far
  better than a number that is silently wrong, and it makes this class of problem
  self-diagnosing in future.

### Why this is load-bearing later

The phase 0.1 interlock refuses `ARM` while any axis is running, and the phase 3
sequencer arms immediately after a settle dwell. Both need a trustworthy "stopped"
signal. Inferring it from a gap in a telemetry stream would make the sequencer's
timing depend on the telemetry rate - and a missed inference means either a stall or
an arm during motion. The arrival event is a prerequisite for the sequencer, not UI
polish.

## Phase 2 — EPICS

elm-ioc-00 is already named like an IOC; make it one.

Run a **caproto** `PVGroup` inside the sequencer process so PVs and the HTTP API
share one copy of the state rather than polling each other. Pure Python, no EPICS
base build, coexists with Flask.

Suggested PV surface (read-only first):

| PV | Meaning |
| --- | --- |
| `FLASH:POS:0`, `FLASH:POS:1` | Stepper positions, steps |
| `FLASH:MOVING` | Any axis running |
| `FLASH:DDG:DELAY`, `:WIDTH`, `:ARMED` | Delay generator |
| `FLASH:DOSE:LAST`, `:CUM` | Last-pulse and cumulative dose |
| `FLASH:FIDUCIAL:RESID` | Alignment residual, mm |
| `FLASH:SEQ:STATE`, `:TARGET`, `:PULSE` | Sequencer |
| `FLASH:FC:AMP`, `:BASE`, `:FLAT`, `:DELAY`, `:MISSED` | Faraday cup per-shot pickoff - see `docs/FARADAY_CUP_DIGITIZER.md` |
| `FLASH:ABORT` | Write-anything abort |

### Firing the linac

The operator already has a script, run as the `ringop` operator account, that fires
the linac with a **repetition count and a delay**. The FLASH GUI should drive that
same capability rather than reinvent the beam request.

**Status 2026-10-19: the script has not been located.** It is not in the curated parts
of the FEL EPICS Admin workspace (`docs/`, `projects/`, `tunl_fel_epics/`). The only
other candidate there is the `./users/` tree inside the 30 GB June 2026 archive, which
is privacy-sensitive and too large to list within this tooling's time limits. Needed
from the operator: its path and host, or a copy placed in this repository.

Questions the script answers, which shape everything below:

1. Which PVs it writes, in what order, and what it reads back.
2. Its arguments (count, delay - anything else?) and limits.
3. **Whether a burst can be stopped part-way**, and how. The dose-limit early stop and
   the abort path both depend on this.
4. What it reports per pulse and at the end - is there a fired/failed handshake, or
   does it only write and wait?
5. Which host it runs on.

#### Who is allowed to write: the gateway access-security file

The workspace's copy of the CA gateway access-security file
(`docs/legacy_admin_source/localProg_release/gateway/access_security.acf`, header
dated 2025-10-09 - **a legacy copy, not observed on the live gateway**) grants write
only to users `{ringop, ringphy}` and `{epicsdev}` **and** only from a listed set of
control-room hosts (`cr-0x-opi`, `cr-0x-ioc`, `ring-01-opi`, `bst-01-opi`, and
similar, plus their `.fel.epics` names). **elm-ioc-00 is not in that host list.** If
the live file matches, nothing running on elm-ioc-00 can write a linac PV today,
whatever account it runs as - which is the correct default.

Three ways to bridge that, in the order recommended:

1. **Operator in the loop (build first).** The sequencer does everything except the
   beam request. At each target it stops, shows the operator the exact command for
   the burst (count and delay), and waits; the operator runs the script in the
   control room as today; the sequencer watches the pulses arrive on the Faraday
   digitizer and DoseCam, verifies the count, and moves on. No facility change, and
   every other part of the system gets proven first.
2. **A narrow access-security rule (the long-term answer).** A dedicated `ASG` covering
   only the firing PVs, with its own `UAG` and `HAG` naming one service account on
   elm-ioc-00. Not an addition to the existing `ASG1`, which grants write to *every*
   channel - far too broad for a positioning Pi. This is a facility controls change:
   it goes through the Git refactor's review-and-promotion path (feature branch,
   release candidate on Electron, production tag on Daffy) with the controls group's
   approval, and it is theirs to decide.
3. **Not recommended: a remote-execution bridge** that runs the script as `ringop` on a
   control-room host on the GUI's behalf. It reaches the same capability with a worse
   posture - a shared operator account driven from another network, outside the
   access-security model that is supposed to govern beam writes.

#### Safety boundaries

- The FLASH software is **not a safety system** and must not stand in for one. Search
  and secure of the radiation exclusion area, the personnel safety system and machine
  protection stay exactly as they are; the GUI never bypasses or reads past them, and
  a firing request that the facility refuses is reported, never retried
  automatically.
- Firing is enabled per plan by an explicit operator action in the GUI, logged with
  who and when, and disabled again by any abort, any fault and the end of the plan.
- The burst is bounded by the plan: count and delay come from the plan, not from free
  text.

The lab's existing EPICS machinery (`fel-epics-admin`, epicsweb, espnow) is the place
to look for conventions - PV naming, the archiver, and how other IOCs there are
deployed and promoted.

## Phase 3 — plan builder and sequencer

The feature you actually want: load a tray, say which positions have samples and what
each gets, press go. The system moves to each in turn, verifies alignment with the
cameras and fiducials, delivers the burst, records the Faraday cup and DoseCam for
every pulse, moves on, and finishes parked for unloading - in the shortest time the
plan allows.

### One experiment GUI

The tabbed shell from 0.3 becomes the FLASH experiment GUI:

| Tab | Device server / source |
| --- | --- |
| Motor | motor_control |
| DoseCam | dose-cam |
| Faraday | fc-digitizer: AD9226 + Arty A7 over USB-UART (`docs/FARADAY_CUP_DIGITIZER.md`) |
| Linac | the firing backend, phase 2 - status, last burst, and firing enable |
| Run | the plan builder and the sequencer |

The persistent status strip and ABORT sit above all five.

### Target model

```json
{
  "session": {"origin": {"x": 134620, "z": 0}, "set_on": "2026-11-xx"},
  "park": "home_corner",
  "targets": [
    {"id": "A1", "holder": 0, "tube": 0, "dx_mm": 0.0,  "dz_mm": 0.0,
     "sample": true,  "pulses": 3, "delay_s": 2.0, "dose_limit_gy": null},
    {"id": "A2", "holder": 0, "tube": 1, "dx_mm": 18.0, "dz_mm": 0.0,
     "sample": false},
    {"id": "A3", "holder": 0, "tube": 2, "dx_mm": 36.0, "dz_mm": 0.0,
     "sample": true,  "pulses": 1, "delay_s": 0.0, "dose_limit_gy": 8.0}
  ]
}
```

`pulses` and `delay_s` are exactly the firing script's repetition count and delay, so
a target's burst is one call of the firing backend. The Run tab shows the holders as
a grid; ticking a position marks a sample present and opens its pulse count, delay and
optional dose ceiling.

Holder and tube indices map to offsets through the holder geometry; the session
origin comes from the daily beam re-targeting. Absolute accuracy does not matter -
within-session repeatability does - which is exactly what the origin-plus-offsets
model expresses.

### Motion

- **Hysteresis dominates ordering.** The redesign note is explicit: always approach
  the final position from the same direction, because hysteresis does not calibrate
  out. So every move ends with an overshoot-and-return in a fixed direction.
- That makes a general travelling-salesman optimisation the wrong tool. **Sort
  targets monotonically along the approach axis** so the fixed-direction approach is
  absorbed into the sweep instead of costing an overshoot at every stop. With 9-12
  targets this is both faster in practice and far easier to reason about than a tour
  optimiser.
- CoreXZ couples the axes: travel time is set by the larger of the two motor
  excursions, not by Euclidean distance in sample space. Cost moves in **motor**
  space when ordering.
- **Settle dwell** after each move, before arming. Belts under continuous gravity
  load ring. Measure the settle time once on hardware (fiducial position versus time
  after a move) and make it a configured constant with the measurement recorded.

### Shortest time, and where the time actually goes

Plan time = sum of (pulses x delay) + per-target settle, fiducial check and background
frame + travel. **Only travel can be optimised**; beam-on time is fixed by the plan.
So the planner's job is narrow:

- Start from park, **sweep monotonically right and down**, visiting only positions
  with samples, then make one move back to park. Because park is top-left, that sweep
  also gives the fixed-direction approach for free - every target is approached
  moving right and down, so no overshoot is needed except where the layout forces a
  reversal.
- Before running, the Run tab shows the order and a **time estimate split into
  beam-on, per-target overhead and travel**, so it is obvious when travel is not
  what's limiting.

### Park and load

Park is the sample holder **all the way left and up**, for easiest access when people
load and unload.

- With the pin map above, left/up is the **X-min and Z-max corner, which are both home
  switches** - if "left" turns out to be X-min once the CoreXZ kinematics are defined.
  Then park is the home corner and **every plan ends with a HOME**, which re-verifies
  position at the end of each run for free. Either way, store park as a named,
  configurable position, not a hard-coded one.
- **Load mode.** Parked "up" for loading means the motors are energised (disabled, the
  gantry drops), so people's hands are next to a powered gantry. Entering park puts
  the system in load mode: every motion command is refused - from the GUI, the API and
  EPICS - until an operator confirms "loading finished, area clear" in the GUI. The
  pinch hazard is the reason; a stray click or a queued command must not move it.

### Fire loop, per target

```
plan start:   ENABLE -> HOME -> re-targeting origin -> leave load mode on operator confirm
per target:   move(target) -> settle dwell -> fiducial check (OV5647)
              -> DoseCam background frame (no beam) for this target
              -> ARM 1 (refused if moving or not homed)
              -> fire burst via the firing backend (pulses, delay_s)
                   per pulse, paired by the Faraday ch2 timing reference:
                     DoseCam gated frame -> beam_fit -> dose
                     Faraday near-time amplitude (raw waveform saved for offline fit)
                     accumulate; stop early at dose_limit_gy (needs a stoppable burst)
              -> ARM 0 -> verify pulse count -> fiducial check
plan end:     move to park -> HOME -> load mode
```

The DDG re-arms itself after each gate, so it is armed once per burst rather than per
pulse. A **per-target background frame** taken at the target, just before the burst,
is the background for that target's DoseCam fits.

Dose comes from the existing `beam_fit.py` path; it reports Gy automatically once
`dn_calibration.json` has a `dn_per_gy` value, and DN until then. **Support both stop
conditions** - pulse count and cumulative dose - with dose always acting as a ceiling
even when counting pulses.

### Fiducial monitoring

**Plan update, 2026-11-17:** Eric plans dedicated fiducial features in the
**DoseCam view** for position calibration and monitoring. The 13 October
100 us beam exposures show target/holder feature contrast; the earlier blanket
claim that this camera cannot see such features is superseded. Calibrate image
coordinates from features at known target positions, then monitor their pose
relative to the fitted beam centroid and a reference image. Visibility and
tracking precision still need validation. The free-running OV5647 remains
available for a continuous view of the positioner.

- Add recognizable fiducial features at known physical positions in the target
  plane. Their geometry should support scale, orientation and perspective
  calibration. Select the mark design after checking contrast in the DoseCam
  exposure; no particular tag family or sub-pixel precision is established yet.
- Capture a reference pose at session start, right after the daily re-targeting.
  Check before and after each target; log the residual every time.
- **Threshold in sample-plane mm, not pixels**, tied to the beam size. The 2026-10-13
  fits give sigma 20 x 35 px; set the alarm at a defined fraction of the smaller sigma
  projected to the sample plane.
- On exceedance: **pause and alert, do not silently auto-correct.** A drift that large
  usually means something moved mechanically, and quietly applying a `SETPOS` offset
  would hide the fault and corrupt the run. Offer the correction to the operator,
  apply it only on confirmation, and log it loudly.
- Cherenkov caveat from the redesign note: PETG glows beam-on at 30 MeV, so anything
  in the DoseCam field of view is a *beam-correlated* background that a no-beam
  background frame will not subtract. Keep fiducial features outside the fitted
  dose ROI, and check whether the holder currently visible in the DoseCam background
  has a beam-on component being attributed to target signal. Fiducial monitoring
  uses that feature contrast separately from the dose fit.

### Run record

One CSV row per pulse, written as it goes, not at the end: timestamp, target id,
commanded and actual motor positions, delay and width, the full fit (A, sigma_x,
sigma_y, theta, centroid, chi2_red), dose DN and Gy, cumulative dose, fiducial
residual, the raw filename, the Faraday near-time amplitude and t0 (offline
fit added later from the saved waveform), the measured shutter delay, and the background frame used. Plus the session JSON,
the calibrations in effect, and the firing backend's log for every burst (arguments,
start and end times, what it reported).
That table is the experimental deliverable; the raws are the backup.

### Abort and dead-man

One abort path, reachable from the shell's persistent button, `FLASH:ABORT`, and the
sequencer API: disarm the DDG, `STOP ALL`, stop requesting pulses, write the partial
run record. The sequence also aborts itself on a failed fiducial check, a missed
frame, or a per-pulse dose deviating beyond a set fraction from the running median -
that last one is the cheapest early warning that the beam or the timing has moved.

## Order of work

| When | What |
| --- | --- |
| Now (no hardware) | 0.1 firmware + interlock, 0.2 serial-owner API and the `DOSECAM_DDG_URL` switch, 0.3 shell, 0.4 simulator, telemetry rework (arrival event + Pi-side coalescing) |
| Now, in parallel | Locate the ringop firing script and record what it writes and whether a burst can be stopped; Faraday cup digitizer: AD9226 module on an Arty A7 - check the module's input impedance, coupling and range, write and simulate the capture/trigger/record HDL, bench it with a function generator (`docs/FARADAY_CUP_DIGITIZER.md`); bench an S3 Feather off-site - port the firmware, check the pin map against the silkscreen, scope the DDG with a function generator; ask the controls group the three firing questions; design and print the ArUco fiducial plate |
| Access session | Phase 1 - one wiring pass, then bring-up, then scope the trigger chain |
| After bring-up | Phase 2 EPICS read-only PVs, then the plan builder and sequencer against the **operator-in-the-loop** firing backend |
| When controls signs off | A narrow access-security rule for the firing PVs, then the direct firing backend |

The sequencer is deliberately built against a manual firing backend first. It is the
piece with the most experimental value and the longest debugging tail, and there is no
reason for it to wait on a beam-controls conversation.
