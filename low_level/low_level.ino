#include <Servo.h>  
// ใช้ Servo library สำหรับควบคุมเซอร์โวมอเตอร์

/* =========================
   ส่วนที่ 1: ค่าคงที่ของระบบ
   ========================= */

// จำนวนเซอร์โวมอเตอร์ที่ใช้งาน
const int NUM_SERVOS = 4;

// จำนวนลำดับท่าทาง (motion steps)
// *** แก้ไขแล้ว: ใช้ space ปกติ ไม่มี hidden character ***
const int NUM_STEPS = 8;

/* =========================
   ส่วนที่ 2: ตัวแปรฮาร์ดแวร์
   ========================= */

// ประกาศอ็อบเจกต์ Servo จำนวน 4 ตัว
Servo servos[NUM_SERVOS];

// ขาที่ต่อกับ Servo แต่ละตัว (เรียงตาม index)
int servoPins[NUM_SERVOS] = {9, 10, 11, 12};

/* =========================
   ส่วนที่ 3: ตารางลำดับการเคลื่อนที่
   ========================= */

// ตารางกำหนดตำแหน่งเซอร์โวในแต่ละ step
// รูปแบบ: {servo0, servo1, servo2, servo3}
// หน่วยเป็นองศา (0–180)
int positions[NUM_STEPS][NUM_SERVOS] = {
  { 90,  90,  90,  40},  // Step 1: ท่าเริ่มต้น
  { 66,  40,   5,  40},  // Step 2
  { 66,  40,   5,  70},  // Step 3
  { 66,  40,  40,  70},  // Step 4
  {145,  40,  40,  70},  // Step 5
  {145,  40,   5,  70},  // Step 6
  {145,  40,   5,  40},  // Step 7
  {145,  40,  40,  40}   // Step 8
};

/* =========================
   ส่วนที่ 4: สถานะปัจจุบันของเซอร์โว
   ========================= */

// ตำแหน่งปัจจุบันของเซอร์โวแต่ละตัว
// ใช้เป็นฐานในการขยับแบบ smooth
int currentPos[NUM_SERVOS] = {90, 90, 90, 50};

/* =========================
   ส่วนที่ 5: พารามิเตอร์ด้านเวลา
   ========================= */

// หน่วงเวลาระหว่างการขยับทีละ 1 องศา
// ค่ายิ่งน้อย การเคลื่อนที่จะยิ่งลื่น
int stepDelay = 25;    

// หน่วงเวลาหลังจากถึงตำแหน่งเป้าหมายแต่ละ step
int holdDelay = 1000;  

/* =========================
   ส่วนที่ 6: ตัวแปรควบคุมคำสั่ง Stop
   ========================= */

// flag สำหรับบอกว่ามีการสั่งหยุดหรือไม่
bool stopRequested = false;

// ใช้เก็บข้อความที่รับมาทาง Serial (ทีละบรรทัด)
String rxLine = "";

/* =========================
   ฟังก์ชัน setup()
   ========================= */

void setup() {
  // เปิด Serial communication
  Serial.begin(115200);

  // ผูกเซอร์โวแต่ละตัวเข้ากับขาที่กำหนด
  // และตั้งค่าเริ่มต้นให้ตรงกับ currentPos
  for (int i = 0; i < NUM_SERVOS; i++) {
    servos[i].attach(servoPins[i]);
    servos[i].write(currentPos[i]);
  }
}

/* =========================
   ฟังก์ชัน loop()
   ========================= */

void loop() {

  // วนลำดับท่าทางทั้งหมดอย่างต่อเนื่อง
  for (int step = 0; step < NUM_STEPS; step++) {

    // ตรวจสอบว่ามีการร้องขอ stop หรือไม่
    if (stopRequested) {
      handleStop();
      step = -1;  // รีเซ็ต loop กลับไปเริ่ม step 0 ใหม่
      continue;
    }

    // เคลื่อนที่ไปยังตำแหน่งของ step ปัจจุบันแบบ smooth
    moveSmooth(positions[step]);

    // ค้างตำแหน่ง แต่ยังฟัง Serial ระหว่างค้าง
    if (delayWithSerialCheck(holdDelay)) {
      handleStop();
      step = -1;
      continue;
    }
  }
}

/* =========================
   ส่วนที่ 7: การรับคำสั่งทาง Serial
   ========================= */

// อ่านข้อมูลจาก Serial แบบ non-blocking
void pollSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    // เมื่อเจอจบบรรทัด
    if (c == '\n' || c == '\r') {
      if (rxLine.length() > 0) {

        rxLine.trim();         // ตัดช่องว่างหัว-ท้าย
        rxLine.toLowerCase();  // แปลงเป็นตัวพิมพ์เล็ก

        // ตรวจคำสั่ง "stop"
        if (rxLine == "stop") {
          stopRequested = true;
        }

        // ล้าง buffer เพื่อรอคำสั่งใหม่
        rxLine = "";
      }
    } else {
      // ป้องกัน String โตเกินไป (ลดปัญหา heap fragmentation)
      if (rxLine.length() < 32) {
        rxLine += c;
      }
    }
  }
}

/* =========================
   หน่วงเวลาแบบยังฟัง Serial
   ========================= */

// คืนค่า true หากพบ stop ระหว่างหน่วงเวลา
bool delayWithSerialCheck(unsigned long ms) {
  unsigned long start = millis();

  while (millis() - start < ms) {
    pollSerial();           // ตรวจ Serial ตลอดเวลา
    if (stopRequested) {
      return true;
    }
    delay(5);               // หน่วงสั้น ๆ เพื่อลดโหลด CPU
  }

  return false;
}

/* =========================
   ฟังก์ชันจัดการเมื่อสั่ง stop
   ========================= */

void handleStop() {

  // เคลียร์ flag เพื่อเตรียมรับคำสั่งใหม่
  stopRequested = false;

  // เคลื่อนกลับไปยังท่าเริ่มต้น (Step 0)
  moveSmooth(positions[0]);

  // ค้าง 3 วินาที โดยยังฟัง Serial
  delayWithSerialCheck(3000);
}

/* =========================
   ฟังก์ชันเคลื่อนที่แบบ Smooth
   ========================= */

void moveSmooth(int target[]) {

  bool moving = true;

  // ขยับจนกว่าจะถึงทุกแกน
  while (moving) {

    moving = false;

    // ฟัง Serial ตลอดการเคลื่อนที่
    pollSerial();
    if (stopRequested) {
      return;  // หยุดทันทีเพื่อความปลอดภัย
    }

    // ตรวจทุก servo ทีละตัว
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

    // หน่วงระหว่าง step แต่ยังตรวจ stop
    if (delayWithSerialCheck(stepDelay)) {
      return;
    }
  }
}
