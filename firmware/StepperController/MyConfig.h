#include <ArduinoJson.h>

// while inefficient to use a json to store such data doing so simplifies the web interface
DynamicJsonDocument settings(8192);

HardwareSerial MySerial(2);

// Passwords are redacted in this public repo. Put the real values in before flashing
// (the FLASHED board still holds them; see flashed_settings_20261026.json).
// units for speed, acceleration, and position use steps and seconds.
const char default_settings[] PROGMEM = R"rawliteral({
  "deviceName":"Aperture Stepper Controller",
  "WiFi" : [{
    "ssid":"DukeOpen"
  },
  { "ssid":"nerdery",
    "password":"<SET-BEFORE-FLASHING>"
  }],
  "hostName":"ApertureSMC",
  "softAPssid":"ApertureSMC",
  "softAPpassword":"<SET-BEFORE-FLASHING>",
  "enableSoftAP":true,
  "enableWiFi":true,
  "softAPwithWiFi":true,
  "userName":"RINGOP",
  "password":"<SET-BEFORE-FLASHING>",
  "units" : "in",
  "moveByUnits" : false,
  "steppers": [{
      "label" : "X",
      "stepPin" : 14,
      "stepInvert" : false,
      "directionPin" : 32,
      "directionInvert" : false,
      "enablePin" : 15,
      "enableInvert" : true,
      "acceleration" : 3200,
      "speed" : 3200,
      "invertLow" : false,
      "invertHigh" : false,
      "steps" : 243840,
      "minPulseWidth" : 5,
      "highPin" : 34,
      "invertHigh" : true,
      "lowPin" : 36,
      "invertLow" : true,
      "homePin" : 39,
      "invertHome" : true
    }]
})rawliteral";
