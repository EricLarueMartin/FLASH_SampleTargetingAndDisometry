from gpiozero import LED
import time

led = LED(26)
print("Pulsing GPIO26 every second... (CTRL+C to stop)")

while True:
    led.on()
    time.sleep(0.1)   # 100 us is too short to see on a DMM, so use 100 ms.
    led.off()
    time.sleep(1)
