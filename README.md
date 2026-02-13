# 🛠️ Virtual Proprioception: VLM-Grip Integration

โปรเจกต์นี้คือการพัฒนาระบบ "Virtual Sensor" โดยการนำ Vision-Language Model (VLM) มาทำ System Integration ร่วมกับหุ่นยนต์แขนกลเพื่อตรวจจับการหยิบพลาด (Slippage) แบบ Real-time.

---

## 🏗️ System Architecture
ระบบใช้โครงสร้างแบบ Node-based เพื่อจัดการกับ Latency และการประมวลผล.

| Node | Language / Framework | Primary Function | Communication |
| :--- | :--- | :--- | :--- |
| **Perception Node** | Python + OpenCV + PyZMQ | จับภาพจากกล้องและ Query ข้อมูลจาก VLM ผ่าน LM Studio API. | ZMQ (Server - REP) |
| **Decision Node** | Python + Tkinter + PyZMQ | ควบคุม Workflow หลัก, ตรวจสอบ Confidence Threshold และส่งคำสั่งควบคุมหุ่นยนต์. | Serial (UART) & ZMQ (Client) |
| **Motion Control** | C++ (Arduino) | จัดการท่าทางหุ่นยนต์ตาม Motion Table และรอสัญญาณ Pass/Stop ที่จุด Checkpoint. | Serial @ 115200 Baud |

---

## 🚀 Getting Started

### 1. Prerequisites
* **AI Engine**: [LM Studio](https://lmstudio.ai/) รันโมเดล `qwen/qwen3-vl-4b` (OpenAI-compatible API).
* **Python Environment**: Python 3.9+ พร้อมติดตั้ง Libraries ใน `requirements.txt`.
* **Hardware**: Arduino Uno, 4-DOF Robotic Arm, Generic RGB Web-camera.

### 2. Installation
```bash
cd VLM-Grip

# Install dependencies
pip install -r requirements.txt

## 📂 Repository Modules

| File Name | Role | Description |
| :--- | :--- | :--- |
| `1perception_VLM.py` | **Core Perception** | [cite_start]เชื่อมต่อ VLM เพื่อยืนยันการมีอยู่ของวัตถุในก้ามปู (Object Presence)[cite: 105, 107]. |
| `1decision_node.py` | **Master Control** | [cite_start]GUI สำหรับเชื่อมต่อ Serial และตัดสินใจ Logic ตามค่าความเชื่อมั่น[cite: 102, 120]. |
| `low_level_wait.ino` | **Robot Firmware** | ควบคุม Servo และระบบ Handshake แบบ Blocking. |
| `mock_perception.py` | **Simulator** | จำลองข้อมูล AI สำหรับทดสอบระบบ Logic โดยไม่ต้องใช้กล้อง/VLM. |
| `mock_decision.py` | **Simulator** | จำลอง Decision Node สำหรับทดสอบการตอบสนองของ Arduino. |

---

## ⚙️ Deployment Workflow (ขั้นตอนการใช้งาน)

กรุณาทำตามลำดับดังนี้เพื่อให้ระบบ Handshake ทำงานได้ถูกต้อง:

1.  **Firmware**: อัปโหลด `low_level_wait.ino` ลงใน Arduino .
2.  [cite_start]**AI Server**: เปิด LM Studio, Load Model (`qwen/qwen3-vl-4b`) และ Start Local Server ที่ Port 1234[cite: 100, 105].
3.  **Perception**: รัน `1perception_VLM.py` เพื่อสแตนด์บายระบบรับภาพและรอคำสั่งวิเคราะห์ .
4.  **Decision**: รัน `1decision_node.py` เลือก COM Port ให้ถูกต้องแล้วกด **Connect Serial** .

---

## 🤖 Logic & Handshake Protocol

[cite_start]ระบบใช้กลยุทธ์ **Discrete Keyframe Monitoring** เพื่อประหยัดทรัพยากรประมวลผล[cite: 66, 111, 112]:

1.  **Trigger**: เมื่อหุ่นยนต์เคลื่อนที่ถึงจุด Checkpoint (Kinematic Singularities) Arduino จะส่งข้อความ `request_check` ผ่าน Serial.
2.  **Analysis**: Decision Node จะรับสัญญาณและสั่ง `CAPTURE` ไปยัง Perception Node เพื่อขอผลลัพธ์การวิเคราะห์จาก VLM .
3.  **Execution**:
    * **PASS**: หาก AI ยืนยันว่าเจอวัตถุ (`object_present: true`) และความมั่นใจ > 80% หุ่นยนต์จะได้รับคำสั่ง `pass` เพื่อทำงานต่อ.
    * **STOP**: หากไม่เจอวัตถุหรือความมั่นใจต่ำกว่าเกณฑ์ ระบบจะส่ง `stop` เพื่อหยุดการทำงานและ Reset หุ่นยนต์กลับท่า Home ทันที.

---

## 🛠️ Customization

* [cite_start]**Threshold**: ปรับค่า `CONFIDENCE_THRESHOLD` ในไฟล์ Python (`1decision_node.py`) ได้ตามความเหมาะสม (ค่าเริ่มต้นคือ 80)[cite: 121].
* **Keyframes**: สามารถเพิ่มหรือลดจุด Checkpoint ใน Arduino Code ได้ในฟังก์ชัน `loop()` โดยระบุลำดับ Step ที่ต้องการ (ปัจจุบันตั้งไว้ที่ Step 2, 3, 4, 5).
