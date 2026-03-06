#include <Servo.h>

Servo panServo;
Servo tiltServo;

// Variables to track where the servos are currently
int currentPan = 90;
int currentTilt = 90;

// SPEED CONTROL: Increase this number to go slower (milliseconds between steps)
// 10 = Fast/Smooth | 20 = Medium | 50 = Very Slow
int stepDelay = 20; 

void setup() {
  Serial.begin(9600);

  panServo.attach(9);
  tiltServo.attach(10);

  // Initialize servos to center immediately on startup
  panServo.write(currentPan);
  tiltServo.write(currentTilt);
}

void loop() {
  if (Serial.available() > 0) {
    // Read the incoming string (e.g., "120,45")
    String data = Serial.readStringUntil('\n');
    int commaIndex = data.indexOf(',');

    if (commaIndex > 0) {
      // Parse the target angles
      int targetPan = data.substring(0, commaIndex).toInt();
      int targetTilt = data.substring(commaIndex + 1).toInt();

      // Constrain for safety
      targetPan = constrain(targetPan, 0, 180);
      targetTilt = constrain(targetTilt, 0, 180);

      // Move toward the target positions slowly
      moveToTarget(targetPan, targetTilt);
    }
  }
}

// Function to step the servos toward the target
void moveToTarget(int tPan, int tTilt) {
  // Keep looping until both servos have reached their targets
  while (currentPan != tPan || currentTilt != tTilt) {
    
    // Move Pan Servo one step closer to target
    if (currentPan < tPan) {
      currentPan++;
    } else if (currentPan > tPan) {
      currentPan--;
    }
    panServo.write(currentPan);

    // Move Tilt Servo one step closer to target
    if (currentTilt < tTilt) {
      currentTilt++;
    } else if (currentTilt > tTilt) {
      currentTilt--;
    }
    tiltServo.write(currentTilt);

    // The magic "speed" pause
    delay(stepDelay); 
  }
}
