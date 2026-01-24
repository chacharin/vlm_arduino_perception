#include <Servo.h>  

/* =========================
   Part 1: System Constants
   ========================= */
const int NUM_SERVOS = 4;
const int NUM_STEPS = 8;

/* =========================
   Part 2: Hardware Variables
   ========================= */
Servo servos[NUM_SERVOS];
int servoPins[NUM_SERVOS] = {9, 10, 11, 12};

/* =========================
   Part 3: Motion Table
   ========================= */
int positions[NUM_STEPS][NUM_SERVOS] = {
  { 90,  90,  90,  40},  // Step 0: Start
  { 66,  40,   5,  40},  // Step 1
  { 66,  40,   5,  70},  // Step 2 (CHECKPOINT)
  { 66,  90,  40,  70},  // Step 3 (CHECKPOINT)
  {145,  90,  40,  70},  // Step 4 (CHECKPOINT)
  {145,  40,   5,  70},  // Step 5 (CHECKPOINT)
  {145,  40,   5,  40},  // Step 6
  {145,  40,  40,  40}   // Step 7
};

/* =========================
   Part 4: Servo State
   ========================= */
int currentPos[NUM_SERVOS] = {90, 90, 90, 50};

/* =========================
   Part 5: Time Parameters
   ========================= */
int stepDelay = 25;     
int holdDelay = 1000;   

/* =========================
   Part 6: Control Flags
   ========================= */
bool stopRequested = false;
String rxLine = "";

/* =========================
   SETUP
   ========================= */
void setup() {
  Serial.begin(115200);
  while (!Serial) { ; } // Wait for serial port to connect

  for (int i = 0; i < NUM_SERVOS; i++) {
    servos[i].attach(servoPins[i]);
    servos[i].write(currentPos[i]);
  }
  
  // Initial Handshake to say "I am ready"
  Serial.println("arduino_ready");
}

/* =========================
   LOOP
   ========================= */
void loop() {
  for (int step = 0; step < NUM_STEPS; step++) {

    // 1. Check Global Stop
    if (stopRequested) {
      handleStop();
      step = -1; 
      continue;
    }

    // 2. Move to position
    moveSmooth(positions[step]);

    // 3. AI CHECKPOINT LOGIC (Steps 2, 3, 4, 5)
    if (step == 2 || step == 3 || step == 4|| step == 5) {
       // Send request to PC
       Serial.println("request_check"); 
       
       // Wait specifically for "pass" or "stop"
       bool permission = waitForDecision(); 
       
       if (!permission) {
          // If PC says "stop" (or timeout), we abort
          handleStop();
          step = -1;
          continue;
       }
       // If permission == true, we continue to next lines
    }

    // 4. Standard delay (still checking for emergency stop)
    if (delayWithSerialCheck(holdDelay)) {
      handleStop();
      step = -1;
      continue;
    }
  }
}

/* =========================
   Part 7: Serial Communication
   ========================= */

// Standard non-blocking poll
void pollSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (rxLine.length() > 0) {
        rxLine.trim();
        rxLine.toLowerCase();
        if (rxLine == "stop") {
          stopRequested = true;
        }
        rxLine = "";
      }
    } else {
      if (rxLine.length() < 32) rxLine += c;
    }
  }
}

// *** NEW FUNCTION: BLOCKING WAIT FOR DECISION ***
// Returns TRUE if "pass", FALSE if "stop"
bool waitForDecision() {
  String localBuffer = "";
  
  // Wait indefinitely or add a timeout if you prefer
  // Here we wait until we get a clear answer
  while (true) {
    if (Serial.available() > 0) {
      char c = (char)Serial.read();
      
      if (c == '\n' || c == '\r') {
        localBuffer.trim();
        localBuffer.toLowerCase();
        
        if (localBuffer == "pass") {
          return true; // Go to next step
        }
        if (localBuffer == "stop") {
          stopRequested = true; 
          return false; // Trigger Stop
        }
        localBuffer = ""; // Reset buffer
      } else {
        localBuffer += c;
      }
    }
  }
}

/* =========================
   Helpers
   ========================= */

bool delayWithSerialCheck(unsigned long ms) {
  unsigned long start = millis();
  while (millis() - start < ms) {
    pollSerial(); 
    if (stopRequested) return true;
    delay(5); 
  }
  return false;
}

void handleStop() {
  stopRequested = false;
  moveSmooth(positions[0]); // Return to Home
  delayWithSerialCheck(3000);
}

void moveSmooth(int target[]) {
  bool moving = true;
  while (moving) {
    moving = false;
    pollSerial();
    if (stopRequested) return;

    for (int i = 0; i < NUM_SERVOS; i++) {
      if (currentPos[i] < target[i]) {
        currentPos[i]++;
        servos[i].write(currentPos[i]);
        moving = true;
      }
      else if (currentPos[i] > target[i]) {
        currentPos[i]--;
        servos[i].write(currentPos[i]);
        moving = true;
      }
    }
    if (delayWithSerialCheck(stepDelay)) return;
  }
}
