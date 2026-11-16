Installing the Arduino IDE:

Install the [Arduino IDE](https://www.arduino.cc/en/software) 

Install the ESP32 board libraries by following the instructions on [learn.adafruit.com.](https://learn.adafruit.com/adafruit-esp32-feather-v2/arduino-ide-setup)

Wiring:

Example use with a NEMA 17 bipolar stepper motor and TB6600 driver.

Determine which pairs of wires to the stepper motor go together. One way is to use a multimeter and measure the resistance on different combinations. Another is to short two wires together and attempt to turn the motor by hand, it will become more difficult to turn when a pair of wires for one of the windings are shorted together.
connect one pair to A+/A- and the other to B+/B-. If one pair of leads are swapped the motor will simply run backwards.

Connect the negative terminal for pulse, direction, and enable on the driver all to the SoC (system on a chip, Adafruit Feather Huzzah 32 V2 in this example) ground. Connect the positive to the associated signal pin on the SoC.

Connect the power supply to the driver.

Programming:

Download this repository to a folder named StepperController. If the folder is not named StepperController the Arduino IDE will make a subfolder that is named StepperController and move the files to it.

Open StepperController.ino with the Arduino IDE.

Edit MyConfig.h and change the Json config settings if desired. Speeds, accelerations, and positions are in seconds and can be configured to use "units" or steps. The "steps" setting is how many microsteps it takes to move one unit.

Connect the SoC to the comptuer using a USB-C cable.

At the top menu select:

Tools->Board->ESP32 Arduino->Adafruit Feather ESP32 V2

Tools->Port->COMX (LilyGo T-Display)

Tools->Arduino Runs On->Core 1

Tools->Events Run On->Core 0

Sketch->Upload

This should upload the code to the SoC and reset the board when done.

Open the terminal window under Tools->Serial Monitor

Serial commands may be sent to the controller to run the motor. Enter ? for a list of commands.




