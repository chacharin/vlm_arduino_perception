import tkinter as tk
from tkinter import scrolledtext
import serial
import zmq
import json
import time
import threading

# --- CONFIGURATION ---
# Serial (Arduino)
PORT = "COM10"           # CHANGE THIS to your actual port
BAUD = 115200

# ZMQ (Perception Node)
ZMQ_HOST = "tcp://localhost:5555"
CONFIDENCE_THRESHOLD = 80

# --- GLOBAL VARIABLES ---
ser = None
running = True  # Flag to control the background thread

# --- ZMQ SETUP (Client Mode) ---
context = zmq.Context()
# We use REQ because we REQUEST a capture and wait for a REPLY
zmq_socket = context.socket(zmq.REQ)
try:
    zmq_socket.connect(ZMQ_HOST)
    print(f"ZMQ Client connected to {ZMQ_HOST}")
except Exception as e:
    print(f"ZMQ Connect Error: {e}")

# --- HELPER FUNCTIONS ---
def log(message):
    """Updates the GUI log in a thread-safe way."""
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    print(full_msg)
    
    try:
        log_area.config(state='normal')
        log_area.insert(tk.END, full_msg + "\n")
        log_area.see(tk.END)
        log_area.config(state='disabled')
    except:
        pass

def connect_serial():
    global ser
    try:
        if ser and ser.is_open:
            ser.close()
        
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
        time.sleep(2) # Allow Arduino reset
        status_label.config(text=f"Connected: {PORT}", fg="green")
        log(f"Serial connected on {PORT}")
        
    except Exception as e:
        status_label.config(text="Serial Failed", fg="red")
        log(f"Serial Error: {e}")
        ser = None

def send_to_arduino(command_str):
    """Sends a command to Arduino (pass/stop)."""
    if ser and ser.is_open:
        try:
            cmd = command_str + "\n"
            ser.write(cmd.encode('utf-8'))
            log(f"Sent to Arduino: {command_str}")
        except Exception as e:
            log(f"Write Error: {e}")
    else:
        log(f"Cannot send '{command_str}': Serial not connected")

def emergency_stop():
    """Manual Stop Button - works immediately."""
    log("!!! EMERGENCY STOP TRIGGERED !!!")
    send_to_arduino("stop")
    status_label.config(text="EMERGENCY STOP SENT", fg="red")

# --- CORE LOGIC THREAD ---
def serial_worker():
    global ser
    log("Worker Thread Started. Waiting for Arduino...")
    
    while running:
        if ser and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8').strip()
                    
                    if not line:
                        continue
                        
                    # --- THE HANDSHAKE LOGIC ---
                    if line == "request_check":
                        log(">>> Arduino requests check. Asking Perception...")
                        
                        try:
                            # 1. Request Perception
                            zmq_socket.send_string("CAPTURE")
                            
                            # 2. Wait for Reply
                            if zmq_socket.poll(timeout=5000): 
                                response = zmq_socket.recv_json()
                                log(f"Perception Reply: {response}")
                                
                                # 3. Analyze Logic (แก้ไขใหม่ตรงนี้ครับ)
                                obj_present = response.get("object_present", False)
                                confidence = response.get("confidence", 0)
                                
                                # เงื่อนไขใหม่: ต้อง "เจอวัตถุ" และ "มั่นใจ > 80" ถึงจะให้ "PASS"
                                if obj_present and confidence > CONFIDENCE_THRESHOLD:
                                    log(f"DECISION: PASS (Object Found, Conf {confidence}%)")
                                    status_label.config(text="PASS SENT (Ready)", fg="green")
                                    send_to_arduino("pass")  # อนุญาตให้ไปต่อ
                                else:
                                    # ถ้าไม่เจอ หรือ ไม่มั่นใจ ให้ STOP
                                    log(f"DECISION: STOP (Object Missing/Low Conf {confidence}%)")
                                    status_label.config(text="STOP SENT (Not Ready)", fg="red")
                                    send_to_arduino("stop")  # สั่งหยุด/Reset
                                    
                            else:
                                log("ERROR: Perception Node Timeout (No Reply)")
                                send_to_arduino("stop") 
                                
                        except zmq.ZMQError as e:
                            log(f"ZMQ Error: {e}")

            except Exception as e:
                log(f"Serial Read Error: {e}")
        
        time.sleep(0.01)

# --- GUI SETUP ---
root = tk.Tk()
root.title("Decision Node: Master Controller")
root.geometry("500x400")

# Header
header = tk.Frame(root, pady=10)
header.pack()

status_label = tk.Label(header, text="Not Connected", font=("Arial", 14, "bold"), fg="gray")
status_label.pack()

# Controls
btn_frame = tk.Frame(root, pady=10)
btn_frame.pack()

connect_btn = tk.Button(btn_frame, text="Connect Serial", command=connect_serial, 
                        bg="#dddddd", width=15, height=2)
connect_btn.grid(row=0, column=0, padx=5)

stop_btn = tk.Button(btn_frame, text="EMERGENCY STOP", command=emergency_stop, 
                     bg="#ff4444", fg="white", font=("Arial", 10, "bold"), width=15, height=2)
stop_btn.grid(row=0, column=1, padx=5)

# Log Area
tk.Label(root, text="System Activity Log:", anchor="w").pack(fill=tk.X, padx=10)
log_area = scrolledtext.ScrolledText(root, height=15, state='disabled', font=("Consolas", 9))
log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

# --- STARTUP ---
# Start the background thread
t = threading.Thread(target=serial_worker, daemon=True)
t.start()

def on_closing():
    global running
    running = False
    if ser and ser.is_open:
        ser.close()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()