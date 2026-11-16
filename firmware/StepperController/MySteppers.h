#include <AccelStepper.h> // may have timing issues at high speed, but accurately counts step pulses

#define AsyncSteppers
//#define AsyncLimits
#define StepperTaskCore 0 // tskNO_AFFINITY would use any available core
#define LimitsTaskCore 1

#define MAX_STEPPERS 1

AccelStepper* steppers[MAX_STEPPERS];

bool stepperEnabled[MAX_STEPPERS];
bool lowLimit[MAX_STEPPERS];
bool highLimit[MAX_STEPPERS];
bool homePosition[MAX_STEPPERS];
bool stopping[MAX_STEPPERS];

#ifdef AsyncSteppers
TaskHandle_t stepperTaskHandle;
#endif
#ifdef AsyncLimits
TaskHandle_t limitsTaskHandle;
#endif

int readLimitSwitches() {
  int r = 0;
  int nSteppers = settings["steppers"].size();
  for (int ct = 0; ct < nSteppers; ++ct) {
    if (settings["steppers"][ct].containsKey("lowPin")) {
      lowLimit[ct] = digitalRead(settings["steppers"][ct]["lowPin"]) xor (settings["steppers"][ct]["invertLow"] | true);
      if (lowLimit[ct]) r |= 0x1<<ct;
    }
    else
      lowLimit[ct] = false;
    if (settings["steppers"][ct].containsKey("highPin"))  {
      highLimit[ct] = digitalRead(settings["steppers"][ct]["highPin"]) xor (settings["steppers"][ct]["invertHigh"] | true);
      if (highLimit[ct]) r |= 0x10<<ct;
    }
    else
      highLimit[ct] = false;
    if (settings["steppers"][ct].containsKey("homePin"))  {
      homePosition[ct] = digitalRead(settings["steppers"][ct]["homePin"]) xor (settings["steppers"][ct]["invertHome"] | true);
      if (homePosition[ct]) r |= 0x100<<ct;
    }
    else
      highLimit[ct] = false;
  }
  return r;
}

int checkLimits() {
  int r = 0;
 // if a stepper is moving past the limit switch, stop it
  int nSteppers = settings["steppers"].size();
  for (int ct = 0; ct < nSteppers; ++ct) {
    if (!steppers[ct]->isRunning()) stopping[ct] = false;
    if (lowLimit[ct] && steppers[ct]->speed()<0 && !stopping[ct]){ 
      steppers[ct]->stop(); r |= 0x1<<ct; stopping[ct] = true;
    }
    if (highLimit[ct] && steppers[ct]->speed()>0 && !stopping[ct]){ 
      steppers[ct]->stop(); r |= 0x10<<ct; stopping[ct] = true;
    }
  }
  return r;
}

#ifdef AsyncSteppers
void stepperUpdateTask(void * pvParameters) {
  MySerial.printf("stepperUpdateTask running on core %i\n",xPortGetCoreID());
  
  int nSteppers = settings["steppers"].size();
  int ct;
  esp_task_wdt_add(NULL);         // NULL = current task  
  
  for (int stepCount = 0;;++stepCount) {
    for (ct = 0; ct < nSteppers; ++ct) steppers[ct]->run();
    if (stepCount % 100 == 0) esp_task_wdt_reset();
  }
}
#endif

#ifdef AsyncLimits
void limitsUpdateTask(void * pvParameters) {
  MySerial.printf("limitsUpdateTask running on core %i\n",xPortGetCoreID());
  int rLS = 0; 
  int cL = 0;
  int r;
  unsigned long lastTrigger = 0;
  for (;;) {
    r = readLimitSwitches();
    if (millis() > lastTrigger && r!=rLS) { 
      lastTrigger = millis() + 5; // don't allow retrigger update more than every 5 ms
      MySerial.print("Limit switch state "); 
      MySerial.println(r,BIN); 
      rLS = r;
    }
    r = checkLimits();
    if (r!=cL) { 
      MySerial.print("Stopping motors due to limit switchs "); 
      MySerial.println(r,BIN);     
      cL = r;
    }
  }
}
#endif

void initSteppers() {
  MySerial.printf("Initializing %i steppers.\n",settings["steppers"].size());
  for(int ct=0; ct<settings["steppers"].size(); ++ct) {
    steppers[ct] = new AccelStepper(AccelStepper::DRIVER,settings["steppers"][ct]["stepPin"],settings["steppers"][ct]["directionPin"]);
    steppers[ct]->setPinsInverted((settings["steppers"][ct]["directionInvert"]|false),(settings["steppers"][ct]["stepInvert"]|false),(settings["steppers"][ct]["enableInvert"]|false));
    steppers[ct]->setMaxSpeed(settings["steppers"][ct]["speed"]);
    if (settings["steppers"][ct].containsKey("minPulseWidth")) 
      steppers[ct]->setMinPulseWidth(settings["steppers"][ct]["minPulseWidth"].as<int>());
    if (settings["steppers"][ct].containsKey("enablePin")) {
      steppers[ct]->setEnablePin(settings["steppers"][ct]["enablePin"].as<int>());
      pinMode(settings["steppers"][ct]["enablePin"],OUTPUT);
      stepperEnabled[ct] = settings["steppers"][ct]["enabled"] | false;
      if (stepperEnabled[ct]) steppers[ct]->enableOutputs();
      else steppers[ct]->disableOutputs();    
    }
    steppers[ct]->setAcceleration(settings["steppers"][ct]["acceleration"]);
    if (settings["steppers"][ct].containsKey("lowPin")) 
      pinMode(settings["steppers"][ct]["lowPin"].as<int>(),INPUT_PULLDOWN);
    if (settings["steppers"][ct].containsKey("highPin")) 
      pinMode(settings["steppers"][ct]["highPin"].as<int>(),INPUT_PULLDOWN);
    if (settings["steppers"][ct].containsKey("homePin")) 
      pinMode(settings["steppers"][ct]["homePin"].as<int>(),INPUT_PULLDOWN);
  }  
#ifdef AsyncSteppers
  xTaskCreatePinnedToCore(
    stepperUpdateTask,          // Task function. 
    "stepperTask",              // String with name of task. 
    10000,                      // Stack size in bytes. 
    NULL,                       // Parameter passed as input of the task 
    3,                          // Priority of the task. 
    &stepperTaskHandle,         // handle
    StepperTaskCore             // core
    );
#endif    
#ifdef AsyncLimits
  xTaskCreatePinnedToCore(
    limitsUpdateTask,          // Task function. 
    "limitsTask",              // String with name of task. 
    10000,                      // Stack size in bytes. 
    NULL,                       // Parameter passed as input of the task 
    0,                          // Priority of the task. 
    &limitsTaskHandle,         // handle
    LimitsTaskCore             // core
    );
#endif    
}
