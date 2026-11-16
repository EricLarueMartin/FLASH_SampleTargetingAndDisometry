#ifndef MySerial_h
#define MySerial_h

// Using the normal serialEvent seems to work better than assigning serial parsing as a task on core 0
//#define AsyncSerialUpdate 
#define SerialUpdateTaskCore 0
#ifdef AsyncSerialUpdate
TaskHandle_t serialUpdateTaskHandle;
#endif

const unsigned long SerialUpdatePeriod = 1000 / portTICK_PERIOD_MS; // update period in milliseconds
const unsigned long SerialFullUpdatePeriod = 10000 / portTICK_PERIOD_MS; // update period in milliseconds

int readSerialCharacter() {
  int tStart = millis();
  while (millis() - tStart < 10) {
    if (MySerial.available())
      return MySerial.read();
    else {
      yield();
      delay(1);
    }
  }
  return 0;
}

String parseSerialString(bool bAllowSpaces = false) {
  String sOut;
  int cIn = readSerialCharacter();
  if (!bAllowSpaces) while (cIn == ' ') cIn = readSerialCharacter(); // remove leading spaces when searching just for a word
  for (sOut = ""; cIn >= 0 && !(cIn == '\n' || (cIn == ' ' && !bAllowSpaces)); cIn = readSerialCharacter())
    sOut += (char)cIn;
  return sOut;
}

#ifdef WiFi_h
void displayWiFi()  {
  MySerial.print(F("MAC address: "));
  MySerial.println(WiFi.macAddress());
  if (WiFi.status() == WL_CONNECTED) {
    MySerial.print(F("WIFI IP: "));
    MySerial.println(WiFi.localIP());
  }
  else
    MySerial.println(F("WiFi not connected."));
#ifdef SoftAP
  if (WiFi.softAP("ESPsoftAP_01", "pass-to-soft-AP")) {
    MySerial.print(F("Soft AP: "));
    MySerial.print(WiFi.softAPgetHostname());
    MySerial.print(F(" IP: "));
    MySerial.println(WiFi.softAPIP());
  }
#endif
}
#endif

void displayOptions() {
  MySerial.println(F("Command are not csse sensitive. Commands are:"));
#ifdef WiFi_h
  MySerial.println(F("   WIFI         - display WiFi info"));
#endif
  MySerial.println(F("   STOP #/ALL        - stop motor # or all motors"));
  MySerial.println(F("   MOVE # #          - move motor # for # steps (negative for counter clock-wise"));
  MySerial.println(F("   MOVEABS # #       - move motor # to position #"));
  MySerial.println(F("   GETPOS #          - get motor # position in steps"));
  MySerial.println(F("   GETSPEED #        - get motor # current speed in steps per second"));
  MySerial.println(F("   GETTARGET #       - get motor # target position in steps"));
  MySerial.println(F("   SETMAXSPEED # #   - set motor # max speed to # in steps per second"));
  MySerial.println(F("   GETMAXSPEED #     - get motor # max speed to # in steps per second"));
  MySerial.println(F("   SETACCEL # #      - set motor # acceleration to # in steps per second per second"));
  MySerial.println(F("   GETACCEL #        - get motor # acceleration in steps per second per second"));
  MySerial.println(F("   SETPOS # #        - change motor # origin so current position is # in steps"));
  MySerial.println(F("   ENABLE #          - set motor # enabled"));
  MySerial.println(F("   DISABLE #         - set motor # disabled"));
  MySerial.println(F("   GETENABLED #      - get if motor # is enabled"));
  MySerial.println(F("   UPDATE            - get position and speed of all motors"));
  MySerial.println(F("   LIST              - list settings"));
  MySerial.print(F("Serial events on core "));
  MySerial.println(xPortGetCoreID());
}

int getWhichStepper() {
  int which = MySerial.parseInt();
  if (which >= settings["steppers"].size()) {
    MySerial.printf("There is no stepper %i.\n", which);
    return -1;
  }
  return which;
}

void serialGetSpeed(int which) {
  if (which < 0) return;
  float speed = steppers[which]->speed();
  if (settings["moveByUnits"] | false) speed /= settings["steppers"][which]["steps"] | 200.0;
  MySerial.printf("GETSPEED %i %f\n", which, speed);
}

void serialGetPos(int which) {
  if (which < 0) return;
  float fPos = steppers[which]->currentPosition();
  char chLimit = ' ';
  if (settings["moveByUnits"] | false) {
    fPos /= settings["steppers"][which]["steps"] | 200.0;
    MySerial.printf("GETPOS %i %f", which, fPos); 
  }
  else {
    MySerial.printf("GETPOS %i %i", which, (int)fPos); // position is always an integer if counted in steps
  }
  if (lowLimit[which]) MySerial.print('L');
  if (highLimit[which]) MySerial.print('U');
  if (homePosition[which]) MySerial.print('H');
  MySerial.println();
}

void fullSerialUpdate() {
  int nSteppers = settings["steppers"].size();
  for (int ct = 0; ct < nSteppers; ++ct) {
    serialGetPos(ct);
    serialGetSpeed(ct);
    MySerial.printf("GETENABLED %i %s\n", ct, stepperEnabled[ct] ? "ENABLED" : "DISABLED");
  }    
}

void parseSerial() {
  while (MySerial.available()) {
    String sRead = parseSerialString();
    if (sRead.equalsIgnoreCase("LIST")) serializeJsonPretty(settings, MySerial);
#ifdef WiFi_h
    else if (sRead.equalsIgnoreCase("WIFI")) displayWiFi();
#endif
    else if (sRead.equalsIgnoreCase("STOP")) {
      String sWhich = parseSerialString();
      if (sWhich.equalsIgnoreCase("ALL")) {
        for (int ct = 0; ct < settings["steppers"].size(); ++ct) {
          stopping[ct] = true;
          steppers[ct]->stop();
        }
        MySerial.println("STOP ALL");
      }
      else {
        int nWhich = sWhich.toInt();
        steppers[nWhich]->stop();
        stopping[nWhich] = true;
        MySerial.printf("STOP %i\n", nWhich);
      }
    }
    else if (sRead.equalsIgnoreCase("SETMAXSPEED")) {
      int which = getWhichStepper(); if (which < 0) return;
      float speed = MySerial.parseFloat();
      MySerial.printf("SETMAXSPEED %i %f\n", which, speed);      
      if (settings["moveByUnits"] | false) speed *= settings["steppers"][which]["steps"] | 200.0;
      settings["steppers"][which]["speed"] =  speed;
      steppers[which]->setMaxSpeed(speed);
      settings.garbageCollect();
    }
    else if (sRead.equalsIgnoreCase("GETMAXSPEED")) {
      int which = getWhichStepper(); if (which < 0) return;
      float maxSpeed = steppers[which]->maxSpeed();
      if (settings["moveByUnits"] | false) 
        maxSpeed /= settings["steppers"][which]["steps"] | 200.0;
      MySerial.printf("GETMAXSPEED %i %f\n", which, maxSpeed);
    }
    else if (sRead.equalsIgnoreCase("MOVE")) {
      int which = getWhichStepper(); if (which < 0) return;
      float fSteps = MySerial.parseFloat();
      if (settings["moveByUnits"] | false) { 
        MySerial.printf("MOVE %i %f\n", which, fSteps);
        fSteps *= settings["steppers"][which]["steps"] | 200.0;
      } else
        MySerial.printf("MOVE %i %i\n", which, (int)fSteps); // position is always an integer if counted in steps      
      steppers[which]->move(fSteps);
    }
    else if (sRead.equalsIgnoreCase("MOVEABS")) {
      int which = getWhichStepper(); if (which < 0) return;
      float fPos = MySerial.parseFloat();
      if (settings["moveByUnits"] | false) { 
        MySerial.printf("MOVEABS %i %f\n", which, fPos);
        fPos *= settings["steppers"][which]["steps"] | 200.0;
      } else
        MySerial.printf("MOVEABS %i %i\n", which, (int)fPos); // position is always an integer if counted in steps      
      steppers[which]->move(fPos - steppers[which]->currentPosition());    // moveTo seems to cause problems
    }
    else if (sRead.equalsIgnoreCase("GETPOS")) serialGetPos(getWhichStepper());
    else if (sRead.equalsIgnoreCase("GETSPEED")) serialGetSpeed(getWhichStepper());
    else if (sRead.equalsIgnoreCase("SETACCEL")) {
      int which = getWhichStepper(); if (which < 0) return;
      float a = MySerial.parseFloat();
      MySerial.printf("SETACCEL %i %f\n", which, a);
      if (settings["moveByUnits"] | false) a *= settings["steppers"][which]["steps"] | 200.0;
      steppers[which]->setAcceleration(a);
      settings["steppers"][which]["acceleration"] =  a;
      settings.garbageCollect();
    }
    else if (sRead.equalsIgnoreCase("SETPOS")) {
      int which = getWhichStepper(); if (which < 0) return;
      float fPos = MySerial.parseFloat();
      if (settings["moveByUnits"] | false) {
        MySerial.printf("SETPOS %i %f\n", which, fPos);
        fPos *= settings["steppers"][which]["steps"] | 200;
      }
      else
        MySerial.printf("SETPOS %i %i\n", which, (int)fPos); // position is always an integer if counted in steps
      steppers[which]->setCurrentPosition(fPos);      
    }
    else if (sRead.equalsIgnoreCase("GETTARGET")) {
      int which = getWhichStepper(); if (which < 0) return;
      float fTarget = steppers[which]->targetPosition();
      if (settings["moveByUnits"] | false) {
        fTarget /= settings["steppers"][which]["steps"] | 200.0;
        MySerial.printf("GETTARGET %i %f\n", which, fTarget);
      }
      else
        MySerial.printf("GETTARGET %i %i\n", which, (int)fTarget); // position is always an integer if counted in steps
    }
    else if (sRead.equalsIgnoreCase("GETACCEL")) {
      int which = getWhichStepper(); if (which < 0) return;
      float a = steppers[which]->acceleration();
      if (settings["moveByUnits"] | false) a /= settings["steppers"][which]["steps"] | 200.0;
      MySerial.printf("GETACCEL %i %f\n", which, a);
    }
    else if (sRead.equalsIgnoreCase("GETENABLED")) {
      int which = getWhichStepper(); if (which < 0) return;
      MySerial.printf("GETENABLED %i %s\n", which, stepperEnabled[which] ? "ENABLED" : "DISABLED");
    }
    else if (sRead.equalsIgnoreCase("ENABLE")) {
      int which = getWhichStepper(); if (which < 0) return;
      steppers[which]->enableOutputs();
      settings["steppers"][which]["enabled"] = true;
      stepperEnabled[which] = true;
      settings.garbageCollect();
      MySerial.printf("ENABLE %i\n", which);
    }
    else if (sRead.equalsIgnoreCase("DISABLE")) {
      int which = getWhichStepper(); if (which < 0) return;
      steppers[which]->disableOutputs();
      settings["steppers"][which]["enabled"] = false;
      stepperEnabled[which] = false;
      settings.garbageCollect();
      MySerial.printf("DISABLE %i\n", which);
    }
    else if (sRead.equalsIgnoreCase("UPDATE")) fullSerialUpdate();
    else if (sRead.equalsIgnoreCase("?")) displayOptions();
  }
}

void updateSerial() {
  static int lastPos[8] = {0,0,0,0,0,0,0,0};
  int nSteppers = settings["steppers"].size();
  for (int ct = 0; ct < nSteppers; ++ct) {
    if (steppers[ct]->currentPosition() != lastPos[ct]) {
      lastPos[ct] = steppers[ct]->currentPosition();
      serialGetPos(ct);
      serialGetSpeed(ct);
    }
  }  
}

bool checkSerial() {
#ifndef AsyncSerialUpdate
  static unsigned long lastUpdate = 0;
  static unsigned long lastFullUpdate = 0;
  if (millis() - lastUpdate < SerialUpdatePeriod) return false;
  lastUpdate = millis();
  
  if (millis() - lastFullUpdate < SerialFullUpdatePeriod) 
    updateSerial();
  else {
    lastFullUpdate = millis();
    fullSerialUpdate();
  }

//  esp_task_wdt_reset();

#endif
  return true;
}


#ifdef AsyncSerialUpdate
void serialUpdateTask(void * pvParameters) {
  MySerial.printf("serialUpdateTask running on core %i\n",xPortGetCoreID());
  
  for (;;) {
    updateSerial();
    vTaskDelay(SerialUpdatePeriod);    
  }
}
#endif

void initSerial() {
  MySerial.begin(115200, SERIAL_8N1, 7, 8);
#ifdef AsyncSerialUpdate
  xTaskCreatePinnedToCore(
    serialUpdateTask,          // Task function. 
    "serialUpdateTask",              // String with name of task. 
    10000,                      // Stack size in bytes. 
    NULL,                       // Parameter passed as input of the task 
    0,                          // Priority of the task. 
    &serialUpdateTaskHandle,         // handle
    SerialUpdateTaskCore             // core
    );
#endif    
}

/*
#ifndef AsyncSerial
void serialEvent() {
  static bool first = true;
  if (first) {
    MySerial.printf("serialEvent running on core %i\n",xPortGetCoreID());
    first = false;
  }
  parseSerial();
}
#endif
*/

#endif
