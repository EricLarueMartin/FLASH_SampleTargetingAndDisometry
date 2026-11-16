#ifndef MyDisplay_h
#define MyDisplay_h

/**************************************************************************
  This is an example for our Monochrome OLEDs based on SSD1306 drivers

  Pick one up today in the adafruit shop!
  ------> http://www.adafruit.com/category/63_98

  This example is for a 128x32 pixel display using SPI to communicate
  4 or 5 pins are required to interface.

  Adafruit invests time and resources providing this open
  source code, please support Adafruit and open-source
  hardware by purchasing products from Adafruit!

  Written by Limor Fried/Ladyada for Adafruit Industries,
  with contributions from the open source community.
  BSD license, check license.txt for more information
  All text above, and the splash screen below must be
  included in any redistribution.
 **************************************************************************/

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define AsyncDisplay
#define SoftAP    
#define DisplayTaskCore 0 // tskNO_AFFINITY would use any available core

#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels
#define SCREEN_RESET -1

#define SCREEN_ADDRESS 0x3C // if defined assumed screen uses I2C communication

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, SCREEN_RESET);

const unsigned long DisplayUpdatePeriod = 300 / portTICK_PERIOD_MS; // update period in milliseconds

String displayMsg = "";

#ifdef AsyncDisplay
TaskHandle_t displayTaskHandle;
#endif

void updateDisplay() {
  display.clearDisplay();   // Clear the buffer
  display.setCursor(16,0);
  display.print("speed");
  display.setCursor(64,0);
  display.print("position");
  display.setCursor(16,8);
  display.print(settings["units"].as<const char*>());
  display.print("/s");
  display.setCursor(64,8);
  display.print(settings["units"].as<const char*>());
  int nSteppers = settings["steppers"].size();
  for(int ct=0; ct<nSteppers; ++ct) {
    float steps = settings["steppers"][ct]["steps"].as<float>();
    display.setCursor(0,8*ct+16);
    display.print(settings["steppers"][ct]["label"].as<const char*>());
    display.setCursor(16,8*ct+16);
    display.print(steppers[ct]->speed()/steps);
    display.setCursor(64,8*ct+16);
    display.print(steppers[ct]->currentPosition()/steps);
    if (settings["steppers"][ct].containsKey("lowPin")) { 
      bool pinState = digitalRead(settings["steppers"][ct]["lowPin"].as<int>()) xor (settings["steppers"][ct]["invertLow"] | true); // default is active low
      if (pinState) // default is active low
        display.print(" L");
    }
    if (settings["steppers"][ct].containsKey("highPin")) { 
      bool pinState = digitalRead(settings["steppers"][ct]["highPin"].as<int>()) xor (settings["steppers"][ct]["invertHigh"] | true);
      if (pinState) // default is active low
        display.print(" H");
    }
  }

  if (displayMsg != "") {display.setCursor(0,8*nSteppers+16);display.print(displayMsg);}

#ifdef WiFi_h
  IPAddress currentIP;
  if (WiFi.status() == WL_CONNECTED)
    currentIP = WiFi.localIP();
#ifdef SoftAP    
  else 
    currentIP = WiFi.softAPIP();
#else
  else currentIP = {0, 0, 0, 0};
#endif
  display.setCursor(0, 48);
  if (WiFi.status() == WL_CONNECTED) {
    display.println(WiFi.SSID());
    display.print(WiFi.localIP());
  }
#ifdef SoftAP    
  else {
    display.println(WiFi.softAPgetHostname());
    display.print(WiFi.softAPIP());
  }
#else
  else {
    display.println("WiFi not connected.");
    display.print(WiFi.macAddress());
  }
#endif
#endif
  display.display();
}

#ifdef AsyncDisplay
void displayUpdateTask(void * pvParameters) {
  Serial.printf("displayUpdateTask running on core %i\n",xPortGetCoreID());
  for (;;) {
    updateDisplay();
//    esp_task_wdt_reset();
    vTaskDelay(DisplayUpdatePeriod);
  }
}
#endif

bool checkDisplay() {
#ifndef AsyncDisplay
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate < DisplayUpdatePeriod) return false;

  updateDisplay();

//  esp_task_wdt_reset();

  lastUpdate = millis();
#endif
  return true;
}

void initDisplay() {
  // SSD1306_SWITCHCAPVCC = generate display voltage from 3.3V internally
  if (!display.begin(SSD1306_SWITCHCAPVCC,SCREEN_ADDRESS)) {
    Serial.println(F("[ERROR] SSD1306 allocation failed"));
    return;
  }
  Serial.println(F("SSD1306 allocated"));
  display.clearDisplay();   // Clear the buffer
  display.setTextSize(1);
  display.setTextWrap(false);
  display.setTextColor(SSD1306_WHITE);
#ifdef AsyncDisplay
  xTaskCreatePinnedToCore(
    displayUpdateTask,          // Task function. 
    "displayTask",              // String with name of task. 
    10000,                      // Stack size in bytes. 
    NULL,                       // Parameter passed as input of the task 
    0,                          // Priority of the task. 
    &displayTaskHandle,         // handle
    DisplayTaskCore             // core
    );
#endif    
}

#endif // MyDisplay_h
