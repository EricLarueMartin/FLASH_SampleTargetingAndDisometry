#ifdef WiFi_h

#ifndef MyServer_h
#define MyServer_h

#define CONFIG_ASYNC_TCP_RUNNING_CORE 1
#define CONFIG_ASYNC_TCP_USE_WDT 0

#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include "WebPages.h"

AsyncWebServer server(80);
AsyncEventSource events("/events");

bool serverOn = false;

const unsigned long EventUpdatePeriod = 300 / portTICK_PERIOD_MS; // update period in milliseconds

TaskHandle_t eventTaskHandle;

String hsl2rgb(float h, float s, float l) {
  float c = (1 - abs(2 * l - 1)) * s;
  while (h >= 360.0f) h -= 360.0;
  while (h < 0.0) h += 360.0;
  h /= 60.0;
  float hmod2 = h;
  while (hmod2 < 0.0) hmod2 += 2.0;
  while (hmod2 > 2.0) hmod2 -= 2.0;
  float x = c * (1 - abs(hmod2 - 1));
  float r = 0.0;
  float g = 0.0;
  float b = 0.0;
  if (h < 1.0) {
    r = c;
    g = x;
  }
  else if (h < 2.0) {
    g = c;
    r = x;
  }
  else if (h < 3.0) {
    g = c;
    b = x;
  }
  else if (h < 4.0) {
    b = c;
    g = x;
  }
  else if (h < 5.0) {
    b = c;
    r = x;
  }
  else if (h < 6.0) {
    r = c;
    b = x;
  }
  float m = l - c / 2.0;
  // convert from float between 0 and 1 to int between 0 and 255
  int R = 255 * (r + m);
  int G = 255 * (g + m);
  int B = 255 * (b + m);
  // construct hex color string and pad with 0s
  return ((R < 0x10) ? "0" : "") + String(R, HEX) + ((G < 0x10) ? "0" : "") + String(G, HEX) + ((B < 0x10) ? "0" : "") + String(B, HEX);
}

boolean isInteger(String str) {
  unsigned int stringLength = str.length();

  if (stringLength == 0) {
    return false;
  }

  boolean seenDecimal = false;

  for (unsigned int i = 0; i < stringLength; ++i) {
    if (!isDigit(str.charAt(i))) {
      return false;
    }
    return true;
  }
}

boolean isNumeric(String str) {
  unsigned int stringLength = str.length();

  if (stringLength == 0) {
    return false;
  }

  boolean seenDecimal = false;

  for (unsigned int i = 0; i < stringLength; ++i) {
    if (isDigit(str.charAt(i))) {
      continue;
    }

    if (str.charAt(i) == '.') {
      if (seenDecimal) {
        return false;
      }
      seenDecimal = true;
      continue;
    }
    return false;
  }
  return true;
}

// Replaces placeholder with stored values
String webProcessor(const String & var) {
  static int whichStepper = 0;
  if (var.startsWith("whichStepper=")) {
    whichStepper = var.substring(13).toInt();
    Serial.printf("Stepper %i selected.\n", whichStepper);
    return "";
  }
  if (var == "running")
    return (steppers[whichStepper]->isRunning()) ? "RUNNING" : "STOPPED";
  if (var == "speed")
    return String(steppers[whichStepper]->speed());
  if (var == "maxSpeed")
    return String(steppers[whichStepper]->maxSpeed());
  if (var == "currentPosition")
    return String(steppers[whichStepper]->currentPosition());
  if (var == "targetPosition")
    return String(steppers[whichStepper]->targetPosition());
  if (var == "acceleration")
    return String(steppers[whichStepper]->acceleration());
  if (var == "distanceToGo")
    return String(steppers[whichStepper]->distanceToGo());
  if (var == "stepperLabel")
    return settings["steppers"][whichStepper]["label"].as<String>();

  if (var.startsWith("!check") && (!settings.containsKey(var.substring(6)) || !settings[var.substring(6)])) return String(" selected");
  if (var.startsWith("check") && (settings.containsKey(var.substring(5)) && settings[var.substring(5)].as<bool>())) return String(" selected");
  if (var == "macAddress") return String(WiFi.macAddress());
  if (var == "localIP") {
    if (WiFi.status() == WL_CONNECTED)
    {
      IPAddress ip = WiFi.localIP();
      String r = String(ip[0]);
      for (int ct = 1; ct < 4; ++ct)
        r += "." + String(ip[ct]);
      return r;
    }
    else
      return "not connected";
  }
  if (var == "softAPIP") return String(WiFi.softAPIP());
  if (var.startsWith("enable") && settings.containsKey(var)) return (settings[var]) ? "enabled" : "disabled";
  if (settings.containsKey(var)) { // string
    String test = var;
    test.toLowerCase();
    if (test.indexOf("password") < 0) // mask passwords
      return settings[var].as<String>();
    else
      return "********";
  }
  return String("missing parameter");
}

void webInputParser(AsyncWebServerRequest * request) {
  static int whichStepper = 0;

  // first check which stepper is specified
  if (request->hasParam("whichStepper")) {
    AsyncWebParameter* param = request->getParam("whichStepper");
    whichStepper = param->value().toInt();
    Serial.printf("Stepper %i selected.\n", whichStepper);
  }

  // now parse remaining parameters
  for (int ctParam = 0; ctParam < request->params(); ++ctParam) {
    AsyncWebParameter* param = request->getParam(ctParam);
    Serial.print("Parsing ");
    Serial.print(param->name());
    Serial.print('=');
    Serial.println(param->value());
    if (param->name() == "stop") {
      steppers[whichStepper]->stop();
      Serial.println("Stopping.");
    }
    else if (param->name() == "setMaxSpeed") {
      steppers[whichStepper]->setMaxSpeed(param->value().toFloat());
      Serial.printf("Max speed set to %f steps/s.\n", steppers[whichStepper]->maxSpeed());
    }
    else if (param->name() == "setAcceleration") {
      steppers[whichStepper]->setAcceleration(param->value().toFloat());
      Serial.printf("Acceleration set to %f steps/s^2.\n", steppers[whichStepper]->acceleration());
    }
    else if (param->name() == "setCurrentPosition") {
      steppers[whichStepper]->setCurrentPosition(param->value().toInt());
      Serial.printf("Curent position set to %i.\n", steppers[whichStepper]->currentPosition());
    }
    else if (param->name() == "moveTo") {
      steppers[whichStepper]->moveTo(param->value().toInt());
      Serial.printf("Moving to absolute position %i.\n", steppers[whichStepper]->targetPosition());
    }
    else if (param->name() == "move") {
      steppers[whichStepper]->move(param->value().toInt());
      Serial.printf("Moving to absolute position %i relative position %s.\n", steppers[whichStepper]->targetPosition(), param->value());
    }
    else if (param->name() == "setOutputsEnabled") {
      stepperEnabled[whichStepper] = param->value() == "true";
      if (stepperEnabled[whichStepper])
        steppers[whichStepper]->disableOutputs();
      else
        steppers[whichStepper]->enableOutputs();
      Serial.printf("Outputs are now %s.\n", stepperEnabled[whichStepper] ? "enabled" : "disabled");
    }
    else  if (settings.containsKey(param->name())) {
      if (settings[param->name()].is<int>())
        settings[param->name()] = param->value().toInt();
      else if (settings[param->name()].is<double>())
        settings[param->name()] = param->value().toDouble();
      else if (settings[param->name()].is<bool>())
        settings[param->name()] = param->value().equalsIgnoreCase("true") ? true : false;
      else if (param->value() != "********")
        settings[param->name()] = param->value();
      settings.garbageCollect();
      Serial.printf("Changed value for %s to %s.\n", param->name(), param->value());
    }
  }
}

void serverUpdate() {
  static bool updateStopped[10];
  for (int ct = 0; ct < settings["steppers"].size(); ++ct) {
    if (!steppers[ct]->isRunning() && updateStopped[ct]) continue;
    updateStopped[ct] = !steppers[ct]->isRunning();
    String eventString = "running";
    eventString += String(ct);
    eventString += "=";
    eventString += (steppers[ct]->isRunning()) ? "RUNNING" : "STOPPED";
    eventString += ";speed";
    eventString += String(ct);
    eventString += "=";
    eventString += String(steppers[ct]->speed());
    eventString += ";currentPosition";
    eventString += String(ct);
    eventString += "=";
    eventString += String(steppers[ct]->currentPosition());
    events.send(eventString.c_str(), "data", millis());
    //    Serial.print("Updating client with "); Serial.println(eventString);
  }
}

void serverEvents() {
  static int nLastUpdate = 0;
  if (millis() - nLastUpdate < EventUpdatePeriod) return;
  nLastUpdate = millis();
  serverUpdate();
}

bool checkServer() {
#ifndef AsyncServerEvents
  if (serverOn) {
    serverEvents();
    return true;
  }
  if (WiFi.status() != WL_CONNECTED && !softAPon) return false;
  Serial.println(F("Starting server."));
  server.begin();
  serverOn = true;
  Serial.println(F("HTTP server started."));
#endif
  return true;
}

void eventUpdateTask(void * pvParameters) {
  Serial.printf("eventUpdateTask running on core %i\n", xPortGetCoreID());
  for (;;) {
    if (serverOn) {
      serverUpdate();
    }
    else if (WiFi.status() == WL_CONNECTED || softAPon) {
      Serial.println(F("Starting server."));
      server.begin();
      serverOn = true;
      Serial.println(F("HTTP server started."));
    }
    esp_task_wdt_reset();
    vTaskDelay(EventUpdatePeriod);
  }
}

bool initServer() {

  if (settings.containsKey("hostName"))
    WiFi.setHostname(settings["hostName"].as<const char*>()); //define hostname

  connectSoftAP();

  server.on("/", HTTP_GET, [] (AsyncWebServerRequest * request) {
    webInputParser(request);
    request->send_P(200, "text/html", index_html, webProcessor);
  });

  events.onConnect([](AsyncEventSourceClient * client) {
    if (!settings.containsKey("serial") || settings["serial"].as<bool>()) {
      if (client->lastId())
        Serial.printf("Client reconnected! Last message ID that it got was: %u\n", client->lastId());
      else
        Serial.println(F("Client connected!"));
    }
    //send event with message "hello!", id current millis
    // and set reconnect delay to 1 second
    client->send("hello!", NULL, millis(), 1000);
  });
  //HTTP Basic authentication
  //  events.setAuthentication("user", "pass");
  server.addHandler(&events);

  server.onNotFound([](AsyncWebServerRequest * request) {
    request->send(404);
  });
#ifdef AsyncServerEvents
  xTaskCreate(
    eventUpdateTask,          // Task function.
    "eventTask",              // String with name of task.
    10000,                    // Stack size in bytes.
    NULL,                     // Parameter passed as input of the task
    0,                        // Priority of the task.
    &eventTaskHandle          // Task handle.
  );
#endif
}

#endif // MyServer_h
#endif // WiFi_h
