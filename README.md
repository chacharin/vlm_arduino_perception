# 🛠️ Virtual Proprioception: VLM--Grip Integration

ระบบนี้คือการพัฒนา **Virtual Proprioception** สำหรับหุ่นยนต์แขนกล
โดยใช้\
**Vision-Language Model (VLM)**
เป็นเซนเซอร์เสมือนเพื่อตรวจจับการหยิบพลาด\
(*slippage*) แบบกึ่ง real-time ผ่านกล้อง RGB ปกติ

แนวคิดหลักคือ: แทนที่จะติดตั้ง force sensor หรือ tactile sensor เพิ่ม\
เราใช้ AI วิเคราะห์ภาพ ณ จุดสำคัญของการเคลื่อนที่ แล้วตัดสินใจว่าจะ\
**"ผ่านต่อ" หรือ "หยุดทันที"**

------------------------------------------------------------------------

## 🎯 Concept Overview

หุ่นยนต์จะไม่วิเคราะห์ภาพตลอดเวลา แต่ใช้แนวคิด **Discrete Keyframe
Monitoring**\
กล่าวคือ ตรวจสอบเฉพาะจุด checkpoint ที่มีความเสี่ยงต่อการหลุดของวัตถุ\
เพื่อลด latency และภาระของโมเดล

ลูปการทำงานมี 3 ขั้น:

1.  Robot เคลื่อนที่ถึง checkpoint → ส่ง `request_check`
2.  Decision Node สั่งกล้อง capture และส่งภาพให้ VLM วิเคราะห์
3.  ระบบตัดสินใจ `pass` หรือ `stop`

------------------------------------------------------------------------

## 🏗️ System Architecture

### Perception Node

-   Python + OpenCV + PyZMQ\
-   จับภาพและ query VLM\
-   ZMQ (REP server)

### Decision Node

-   Python + Tkinter + PyZMQ\
-   Logic หลัก + GUI + Threshold control\
-   Serial (UART) + ZMQ (Client)

### Motion Control

-   Arduino (C++)\
-   ควบคุม servo + handshake\
-   Serial @115200

------------------------------------------------------------------------

## 🔁 Handshake Protocol

### 1️⃣ Trigger Phase

เมื่อแขนกลถึง checkpoint ที่กำหนดไว้ใน firmware\
Arduino ส่งข้อความ:

    request_check

### 2️⃣ Analysis Phase

Decision Node รับ serial → ส่ง `CAPTURE` → Perception Node\
Perception Node จับภาพ → เรียก VLM ผ่าน LM Studio API

ตัวอย่างผลลัพธ์:

``` json
{
  "object_present": true,
  "confidence": 0.87
}
```

### 3️⃣ Execution Phase

หาก `object_present = true`\
และ `confidence > CONFIDENCE_THRESHOLD`

ส่ง:

    pass

หากไม่เข้าเงื่อนไข:

    stop

Arduino จะหยุดและ reset กลับตำแหน่ง Home

------------------------------------------------------------------------

## 🚀 Deployment Workflow

1.  อัปโหลด `low_level_wait.ino` ไปยัง Arduino\
2.  เปิด LM Studio และโหลดโมเดล `qwen/qwen3-vl-4b`\
3.  Start Local Server ที่ Port 1234\
4.  รัน `1perception_VLM.py`\
5.  รัน `1decision_node.py`\
6.  เลือก COM Port และ Connect Serial

------------------------------------------------------------------------

## ⚙️ Customization

### 🔹 Confidence Threshold

ปรับค่า `CONFIDENCE_THRESHOLD` ในไฟล์ `1decision_node.py`\
ค่าเริ่มต้น = 80

### 🔹 Keyframe Checkpoint

สามารถแก้ไข checkpoint ใน `low_level_wait.ino` ภายในฟังก์ชัน `loop()`\
ปัจจุบันใช้ Step 2, 3, 4, 5

------------------------------------------------------------------------

## 🧠 Design Philosophy

ระบบนี้ตั้งอยู่บนสมมติฐานว่า\
Vision model สามารถทำหน้าที่แทน tactile sensing ได้บางบริบท

การประมวลผลแบบ event-driven มีประสิทธิภาพกว่า\
real-time continuous streaming

System integration สำคัญเทียบเท่าขนาดโมเดล

------------------------------------------------------------------------

## ⚠️ Safety Notes

-   หาก confidence แกว่ง ควรลดความเร็วแขนกล\
-   ตรวจสอบ latency ก่อนใช้งานจริง\
-   หลีกเลี่ยงวัตถุหนักหรือมีความเสี่ยงโดยไม่มี stop mechanism สำรอง
