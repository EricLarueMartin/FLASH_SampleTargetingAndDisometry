#include <Arduino.h>

// Feather HUZZAH / ESP8266 GPIO numbers.
const int PIN_IN_PI = 12;       // Trigger input from Raspberry Pi GPIO26.
const int PIN_IN_LASER = 14;    // Future trigger input from laser charging signal.
const int PIN_OUT_CAMERA = 13;  // Camera shutter trigger output.
const int PIN_OUT_MONITOR = 15; // Monitor output to Raspberry Pi GPIO16.

// Configurable in microseconds over serial.
volatile uint32_t delay_us = 200;  // boot default; 200 us matches laser-charge-to-scintillation timing (2026-10-14)
volatile uint32_t width_us = 100;  // boot default; 100 us dosimetry gate (2026-10-14)

volatile bool armed = true;
volatile bool enabled = false;
volatile bool input_active_level = HIGH; // Rising edge by default.
volatile bool timer_for_delay = true;

int cameraInactiveLevel() {
  return HIGH;
}

int cameraActiveLevel() {
  return LOW;
}

void setInactiveOutputs() {
  digitalWrite(PIN_OUT_CAMERA, cameraInactiveLevel());
  digitalWrite(PIN_OUT_MONITOR, LOW);
}

void setActiveOutputs() {
  digitalWrite(PIN_OUT_CAMERA, cameraActiveLevel());
  digitalWrite(PIN_OUT_MONITOR, HIGH);
}

void IRAM_ATTR triggerISR() {
  if (!armed || !enabled) return;

  armed = false;
  timer_for_delay = true;
  timer1_write(delay_us * 80); // 80 MHz clock, 80 ticks per microsecond.
  timer1_enable(TIM_DIV1, TIM_EDGE, TIM_SINGLE);
}

void IRAM_ATTR timerISR() {
  if (timer_for_delay) {
    setActiveOutputs();
    timer_for_delay = false;
    timer1_write(width_us * 80);
    timer1_enable(TIM_DIV1, TIM_EDGE, TIM_SINGLE);
  } else {
    setInactiveOutputs();
    armed = true;
  }
}

void printStatus() {
  Serial.printf(
    "STATUS enabled=%u armed=%u delay_us=%u width_us=%u input_active_level=%s camera_active_level=LOW\n",
    enabled ? 1 : 0,
    armed ? 1 : 0,
    delay_us,
    width_us,
    input_active_level == LOW ? "LOW" : "HIGH"
  );
}

void configureInputInterrupts() {
  int mode = (input_active_level == HIGH) ? RISING : FALLING;
  detachInterrupt(digitalPinToInterrupt(PIN_IN_PI));
  detachInterrupt(digitalPinToInterrupt(PIN_IN_LASER));
  attachInterrupt(digitalPinToInterrupt(PIN_IN_PI), triggerISR, mode);
  attachInterrupt(digitalPinToInterrupt(PIN_IN_LASER), triggerISR, mode);
}

void setup() {
  pinMode(PIN_OUT_CAMERA, OUTPUT);
  pinMode(PIN_OUT_MONITOR, OUTPUT);
  setInactiveOutputs();

  pinMode(PIN_IN_PI, INPUT);
  pinMode(PIN_IN_LASER, INPUT);
  configureInputInterrupts();

  timer1_attachInterrupt(timerISR);
  timer1_disable();

  Serial.begin(115200);
  delay(100);
  Serial.println("DDG ready");
  printStatus();
}

void loop() {
  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (!line.length()) return;

  char cmd = line[0];
  uint32_t val = line.substring(1).toInt();

  switch (cmd) {
    case 'D':
      delay_us = val;
      Serial.printf("Delay set to %u us\n", delay_us);
      break;
    case 'W':
      width_us = val;
      Serial.printf("Width set to %u us\n", width_us);
      break;
    case 'E':
      enabled = (val != 0);
      setInactiveOutputs();
      Serial.println(enabled ? "Output enabled." : "Output disabled.");
      break;
    case 'I':
      input_active_level = (val == 0) ? LOW : HIGH;
      setInactiveOutputs();
      configureInputInterrupts();
      Serial.println(input_active_level == HIGH ? "Input trigger active HIGH." : "Input trigger active LOW.");
      break;
    case 'L':
      Serial.println("Camera output active level is fixed LOW.");
      break;
    case 'T':
      triggerISR();
      Serial.println("Serial trigger initiated.");
      break;
    case '?':
    case 'S':
      printStatus();
      break;
    default:
      Serial.println("Unknown command.");
      break;
  }
}
