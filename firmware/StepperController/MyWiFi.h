#ifdef WiFi_h

#ifndef MyWiFi_h
#define MyWiFi_h

bool softAPon = false;
int WiFiRequests = 0; // counter of routines requesting WiFi access available, such as email or GroveStreams

const unsigned long checkWiFiPeriod = 15000 / portTICK_PERIOD_MS; // update period in milliseconds

#ifdef AsyncWiFiConnect
TaskHandle_t connectWiFiTaskHandle;
#define WiFiTaskCore 1 // tskNO_AFFINITY would use any available core
#endif

void disconnectSoftAP() {
  if (softAPon) {
    Serial.println(F("Disabeling access point..."));
    WiFi.softAPdisconnect(true);
    softAPon = false;
  }
}

void connectSoftAP() {
  static unsigned long lastAttempt = (settings.containsKey("ssid") &&  (settings["enableWiFi"] | false)) ? 10000 : 0;
  if (softAPon || WiFi.status() == WL_CONNECTED) return;
  if (millis() - lastAttempt < 60000 && lastAttempt != 0) return; // only try once a minute
  lastAttempt = millis();
  if (settings.containsKey("softAPssid") && (settings["enableSoftAP"] | true) ) {
    Serial.print(F("Configuring access point..."));
    if (settings.containsKey("softAPpassword"))
      softAPon = WiFi.softAP(settings["softAPssid"].as<const char*>(), settings["softAPpassword"].as<const char*>());
    else
      softAPon = WiFi.softAP(settings["softAPssid"].as<const char*>());
    Serial.print(F("AP IP address: "));
    Serial.println(WiFi.softAPIP());
  }
}

void connectWiFi() {
  static int whichWiFi = -1;
  static long lastAttempt = 0;
  static bool connectionPrinted = false;
  if (!connectionPrinted && WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected to ");
    Serial.println(WiFi.SSID());
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());      
    connectionPrinted = true;
  }
  if (WiFi.status() == WL_CONNECTED) return;
  if (lastAttempt != 0 && millis()-lastAttempt < 15000) return;
  lastAttempt = millis();
  ++whichWiFi;
  if (whichWiFi >= settings["WiFi"].size()) whichWiFi = 0;
  Serial.print("Connecting to ");
  Serial.print(settings["WiFi"][whichWiFi]["ssid"].as<const char*>());
  if (settings["WiFi"][whichWiFi].containsKey("password")) {
    WiFi.begin(settings["WiFi"][whichWiFi]["ssid"].as<const char*>(),settings["WiFi"][whichWiFi]["password"].as<const char*>());
    Serial.print(" with password ");
    Serial.print(settings["WiFi"][whichWiFi]["password"].as<const char*>());
  }
  else
    WiFi.begin(settings["WiFi"][whichWiFi]["ssid"].as<const char*>());
  Serial.println();
}

void disconnectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(F("Disconnecting WiFi..."));
    WiFi.disconnect();
  }
}

void checkWiFi() {
#ifndef AsyncWiFiConnect
  if ((settings["enableWiFi"] | false) || WiFiRequests > 0)
    connectWiFi();
  else
    disconnectWiFi();
#endif
}

#ifdef AsyncWiFiConnect
void connectWiFiTask(void * pvParameters) {
  static int whichWiFi = 0;
  Serial.printf("connectWiFiTask running on core %i\n",xPortGetCoreID());
  while (WiFi.status() != WL_CONNECTED) {
    ++whichWiFi;
    if (whichWiFi >= settings["WiFi"].size()) whichWiFi = 0;
    Serial.print("Connecting to ");
    Serial.print(settings["WiFi"][whichWiFi]["ssid"].as<const char*>());
    if (settings["WiFi"][whichWiFi].containsKey("password")) {
      WiFi.begin(settings["WiFi"][whichWiFi]["ssid"].as<const char*>(),settings["WiFi"][whichWiFi]["password"].as<const char*>());
      Serial.print(" with password ");
      Serial.print(settings["WiFi"][whichWiFi]["password"].as<const char*>());
    }
    else
      WiFi.begin(settings["WiFi"][whichWiFi]["ssid"].as<const char*>());
    esp_task_wdt_reset();
    vTaskDelay(checkWiFiPeriod);
  }
  Serial.printf("Connected to %s with IP ", settings["WiFissid"].as<String>());
  Serial.println(WiFi.localIP());
  // WiFi must be connected to get here, disable SoftAP if necessary.
  if (softAPon && !(settings["softAPandWiFi"]|false))
    disconnectSoftAP();
  Serial.println(F("WiFi connection task complete."));
  vTaskDelete(NULL);
}
#endif

void initWiFi() {
  Serial.print(F("MAC address: "));
  Serial.println(WiFi.macAddress());
  WiFi.mode(WIFI_STA);  
  // Set up soft AP first if configured
  if (settings.containsKey("softAPssid") && (settings["enableSoftAP"] | true) ) {
    Serial.print(F("Configuring access point..."));
    if (settings.containsKey("softAPpassword"))
      softAPon = WiFi.softAP(settings["softAPssid"].as<const char*>(), settings["softAPpassword"].as<const char*>());
    else
      softAPon = WiFi.softAP(settings["softAPssid"].as<const char*>());
    Serial.print(F("AP IP address: "));
    Serial.println(WiFi.softAPIP());
  }
#ifdef AsyncWiFiConnect
  // Start a task to connect WiFi
  if ((settings["enableWiFi"] | false) && settings.containsKey("WiFissid"))
    xTaskCreatePinnedToCore(
      connectWiFiTask,            // Task function. 
      "connectWiFiTask",          // String with name of task. 
      10000,                      // Stack size in bytes. 
      NULL,                       // Parameter passed as input of the task 
      0,                          // Priority of the task. 
      &connectWiFiTaskHandle,     // Task handle. 
      WiFiTaskCore                // core
      );
  else
    Serial.println(F("Not set to connect to WiFi."));    
#endif    
}

#endif // MyWiFi_h

#endif // WiFi_h
