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

---



