# Hardware wiring diagrams

These diagrams show the current synchronized-camera prototype wiring. Every drawing states its viewing orientation. SVG is the editable master; the matching PNG is intended for quick viewing on a phone or at the bench.

- `esp8266_feather_wiring`: both Feather HUZZAH ESP8266 headers, viewed from the component side with the USB/battery end at left.
- `pi_gpio_wiring`: all 40 Raspberry Pi GPIO pins, viewed from above with the board below the header and USB/Ethernet at right.
- `optoisolator_j2_wiring`: optoisolator PCB from the KiCad component/front side, with BNC at left and J2 at right.
- `camera_j2_j3_wiring`: camera back/component side with ribbon down, showing unused J2 strobe and wired J3 external trigger.
- `system_wiring_overview`: signal-flow summary across AD2, optoisolator, ESP8266, Pi, and camera.

## Verified optoisolator mapping

`OptoIsolator.kicad_pcb` defines J2 pin 1 as `GND2`, pin 2 as the optocoupler output signal, and pin 3 as `VCC`. The corrected installation is black J2 pin 1 to ESP ground, white J2 pin 2 to ESP GPIO14, and grey J2 pin 3 to ESP 3V3. This mapping was bench-verified on 2026-09-15: one 4.999 V, 100 us AD2 W2 pulse produced one camera frame and one GPIO16 monitor pulse measuring about 898.8 us for the configured 1000 us ESP gate.

The camera uses J3 for external trigger. White from ESP GPIO13 goes to J3 `Trig+`; black from J3 `Trig-`, which is closest to the camera PCB edge, returns to Raspberry Pi physical pin 39 ground. J2 is the camera strobe header and is unused in this prototype.

Sources: repository firmware/wiring notes, `OptoIsolator/OptoIsolator.kicad_pcb`, the official Adafruit Feather HUZZAH ESP8266 pinout, and the official Raspberry Pi 40-pin GPIO pinout.
