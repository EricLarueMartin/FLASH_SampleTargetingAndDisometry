# Putting the delay generator on the stepper ESP32

Design note, 2026-10-16. Nothing implemented. The question: can the DDG currently
running on the ESP8266 (`SynchronizedCameraDosimeter/DDG/DDG.ino`) move onto the
ESP32 that runs the steppers, without disturbing stepping?

## Short answer

Yes, and the timing should get *better*, not worse. The firmware side is small. The
awkward part is on the Pi: one microcontroller means one serial port, and two
services want to talk to it.

## Why stepping is not at risk

`MySteppers.h` pins `stepperUpdateTask` to **core 0** at priority 3, and that task is
a bare `for(;;)` calling `AccelStepper::run()`. Arduino `loop()` - serial parsing,
limit-switch reads - runs on **core 1**. That separation is the whole reason stepping
is smooth today.

An interrupt registered from `setup()` or `loop()` is installed on the core that
registers it, so a DDG interrupt lands on **core 1** and core 0 never sees it. Even if
it did: the handler is roughly 1 us, twice per shot, at a few Hz, against a 3200
steps/s ceiling - a 312 us step period. There is no mechanism by which it costs a step.

## The one real coupling: flash cache

On the ESP32 an SPI-flash erase or write disables the instruction cache on **both**
cores. Any code not resident in IRAM stalls, stepper task included. That risk already
exists today - `SETMAXSPEED` and `SETACCEL` persist settings - and it would newly
apply to the DDG if its handlers live in flash.

So:

- Mark both handlers `IRAM_ATTR` and allocate the GPIO interrupt with
  `ESP_INTR_FLAG_IRAM`.
- Nothing the handlers touch may be a `String`, an `ArduinoJson` value, or anything
  else that reaches into flash. Plain `volatile uint32_t` only, as the ESP8266 version
  already does.
- Do not persist settings during a run.

With that, the DDG is immune to cache stalls - which is more than can be said for the
present ESP8266 arrangement.

## About the occasional long delay

The suspicion that "the processor is busy doing something else" is close, but the
mechanism is probably narrower than that. `DDG.ino` computes the delay *inside* the
GPIO ISR (`timer1_write(delay_us * 80)`), so anything that postpones ISR entry is
added directly to the delay. On the ESP8266 the usual cause is not CPU load but the
flash cache: when code running from flash takes a cache miss, the SPI read blocks
interrupts for tens of microseconds. That matches "every once in a while it delays a
bit longer than usual" far better than scheduling would - scheduling does not block
ISRs at all.

A plain IRAM-safe ISR on ESP32 core 1 should take that from occasional tens of
microseconds down to well under 1 us, which is already negligible against a 200 us
delay and a 100 us gate.

If exact is wanted rather than good enough: have the ISR do nothing but start an
**RMT** or **MCPWM** one-shot that emits delay-then-pulse from the peripheral. Delay
and width then have *zero* relative jitter (12.5 ns resolution) and only the single
ISR entry carries any. Neither the classic ESP32 nor the ESP32-S3 has an Event Task
Matrix (that arrived with the C6/H2/P4), so a fully hardware-triggered path with no ISR
at all goes through MCPWM on either chip: its GPIO sync input starts a timer whose
comparators set and clear the output. That is the zero-jitter option; prototype it
after the ISR version works, not instead of it.

## The real win: interlocking

Two separate processors cannot enforce "never fire while moving". One can:

- Refuse to arm while any `steppers[ct]->isRunning()`.
- Refuse `MOVE` / `MOVEABS` while armed.
- Report both states in one `STATUS` line.

That is a safety property the current split architecture simply cannot have.

## The real cost: one serial port

Today `dose_cam` owns `/dev/ttyUSB0` (CP2104 -> ESP8266) and `motor_control` owns
`/dev/ttyACM0` (ESP32). Merging the firmware merges the ports, and two processes
cannot both own one. Either:

- **motor_control becomes the sole serial owner** and exposes the DDG commands over
  its existing Socket.IO / HTTP interface; `dose_cam`'s `_configure_esp_serial()` and
  `_disable_esp_serial()` become HTTP calls instead of `pyserial`. Preferred - it
  reuses the locking that is already there.
- Or a small broker daemon owns the port and both services talk to it.

This is a bigger change than the firmware, and it is the part worth scheduling
deliberately. The `D`/`W`/`E`/`I`/`T`/`S` commands themselves drop straight into
`MySerial.h`'s parser alongside `SETPOS` and friends.

## Proposed pinout

**Superseded 2026-10-16** - the target board is now a Feather ESP32-S3 (No PSRAM), with
a zero-external-resistor map in `docs/ROADMAP_INTEGRATED_RIG.md`. Kept for the record.

Already used (`MyConfig.h`): GPIO14 step, GPIO32 direction, GPIO15 enable, GPIO34 high
limit, GPIO36 low limit, GPIO39 home, GPIO7/8 UART2 to the Pi.

| Function | Proposed pin | Why |
| --- | --- | --- |
| Trigger in from optoisolator (falling edge) | **GPIO27** | Not a strapping pin, has an internal pull-up, full interrupt support |
| Camera XTR out (active LOW) | **GPIO33** | Not a strapping pin, not driven during reset, no boot-time traffic |
| Monitor out (optional) | **GPIO26** | Spare, diagnostics only |

Alternates if any of those are already committed on your board: GPIO25, GPIO4,
GPIO21, GPIO22. Avoid GPIO0, 2, 5 and 12 (strapping) and GPIO13 (onboard LED).

**One hardware requirement.** The camera trigger is active LOW, so the line must be
HIGH through reset and boot. ESP32 pins float during reset - floating is not high.
Fit an external 10 k pull-up from the XTR line to 3V3. The ESP8266 arrangement gets
away without one; do not assume the ESP32 will.

Marked *proposed*, not verified: I have not seen the Feather's silkscreen or your
wiring, so confirm GPIO27/33/26 are unconnected on the board before soldering.

## Noticed while reading the firmware

`initSteppers()` calls `pinMode(..., INPUT_PULLDOWN)` on the limit and home pins,
which are GPIO34, 36 and 39. **GPIO34-39 on the ESP32 are input-only and have no
internal pull-up or pull-down at all** - that call silently does nothing, and those
three inputs are floating unless something external pulls them down. Given the
positioner redesign note already flags accelerator RF pickup on long switch lines as a
cause of spurious mid-move triggers, this is worth a look independently of the DDG:
fit external 10 k pull-downs at the ESP32 end.
