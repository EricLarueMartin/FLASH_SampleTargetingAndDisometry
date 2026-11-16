/*
  Stepper controller using dual core ESP32, such as the Adafruit Feather Huzzah 32 V2

  To ensure the stepper motor runs smoothly everything not related to stepping the stepper motors goes on a different core than the stepper task.
  Set arduino to run on core 1
  Set events to run on core 0

*/

//#include <WiFi.h>
#ifndef WiFi_h
//#define WiFi_h
#endif
#include <esp_task_wdt.h>

#include "MyConfig.h"
#include "MySteppers.h"
//#include "MyDisplay.h"
//#include "MyWiFi.h"
#include "MySerial.h"
//#include "MyServer.h"

//#define LATTE

#ifdef LATTE

#define X_POS_PIN 19
#define X_NEG_PIN 21
#define Z_POS_PIN 7
#define Z_NEG_PIN 8

void checkInterlocks() {
  // if x isn't at low limit, don't allow z movement
  if (!lowLimit[0] && steppers[1]->isRunning()) steppers[1]->stop();
  // if z isn't at high limit, don't allow x movement
  if (!highLimit[1] && steppers[0]->isRunning()) steppers[0]->stop();
}

void checkMovement() {
  // trying to move X out
  bool xIn = digitalRead(X_POS_PIN);
  bool xOut = digitalRead(X_NEG_PIN);
  bool zIn = digitalRead(Z_POS_PIN);
  bool zOut = digitalRead(Z_NEG_PIN);
  if (xIn && highLimit[1] && !lowLimit[0])
    steppers[0]->move(settings["steppers"][0]["lowLimit"].as<int>() - steppers[0]->currentPosition());
  else if (xOut && highLimit[1] && !highLimit[0])
    steppers[0]->move(settings["steppers"][0]["HighLimit"].as<int>() - steppers[0]->currentPosition());
  else if (!xIn && !xOut && steppers[0]->isRunning()) steppers[0]->stop();
  if (zIn && lowLimit[0] && !lowLimit[1])
    steppers[1]->move(settings["steppers"][1]["lowLimit"].as<int>() - steppers[1]->currentPosition());
  else if (zOut && lowLimit[0] && !highLimit[1])
    steppers[1]->move(settings["steppers"][1]["HighLimit"].as<int>() - steppers[1]->currentPosition());
  else if (!zIn && !zOut && steppers[1]->isRunning()) steppers[1]->stop();
}

#endif

void setup(void) {
  deserializeJson(settings, default_settings);

  initSerial();
  initSteppers();

  MySerial.print("portTICK_PERIOD_MS=");
  MySerial.println(portTICK_PERIOD_MS);

#ifdef MyWiFi_h
  initWiFi();
#endif
  delay(100);
#ifdef MyDisplay_h
  initDisplay();
#endif
  delay(100);
#ifdef MyServer_h
  initServer();
#endif

#ifdef LATTE
  pinMode(X_POS_PIN, INPUT);
  pinMode(X_NEG_PIN, INPUT);
  pinMode(Z_POS_PIN, INPUT);
  pinMode(Z_NEG_PIN, INPUT);
#endif

  MySerial.printf("Arduino running on core %i\n", xPortGetCoreID());

  disableCore0WDT();
  //  disableCore1WDT();
  //  disableLoopWDT();

}

void loop(void) {
#ifndef AsyncLimits
  static int rLS = 0;
  static unsigned long lastLimitsUpdate = 0;
  int r = readLimitSwitches();
  if (r != rLS && millis() > lastLimitsUpdate + 1000) {
    MySerial.print("Limit switch state ");
    MySerial.println(r, BIN);
    lastLimitsUpdate = millis();
  }
  rLS = r;
  static int cL = 0;
  r = checkLimits();
  if (r != cL) {
    MySerial.print("Stopping motors due to limit switchs ");
    MySerial.println(r, BIN);
  }
  cL = r;
#endif
#ifdef LATTE
  checkInterlocks();
  checkMovement();
#endif
#if defined(MyWiFi_h) and !defined(AsyncWiFiConnect)
  connectWiFi();
#endif
#if defined(MyServer_h) and !defined(AsyncServerEvents)
  checkServer();
#endif
#if defined(MyDisplay_h) and !defined(AsyncDisplay)
  checkDisplay();
#endif
#if defined(MySerial_h) and !defined(AsyncSerialUpdate)
  checkSerial();
#endif

#ifndef AsyncSteppers
  static int nSteppers = settings["steppers"].size();
  for (int ct = 0; ct < nSteppers; ++ct) steppers[ct]->run();
#endif
  parseSerial();
}
