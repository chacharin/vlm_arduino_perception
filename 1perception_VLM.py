import tkinter as tk
from tkinter import scrolledtext, ttk
from PIL import Image, ImageTk
import cv2
import zmq
import json
import base64
import requests
import os
import time
import threading
import re
import copy

# --- CONFIGURATION ---
# 1. LM Studio Settings
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_ID = "qwen/qwen3-vl-4b" 

# 2. Camera Settings (CAPTURE Resolution - High Quality for AI)
CAMERA_INDEX = 1
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# 3. GUI Display Settings (Small size for monitoring)
DISPLAY_WIDTH = 320
DISPLAY_HEIGHT = 240

# 4. File Path Settings
SAVE_DIR = r"D:\project_VLM\capture_img"

# 5. ZMQ Settings (Server / Reply Mode)
ZMQ_PORT = 5555

# --- GLOBAL VARIABLES ---
latest_frame = None  # Stores the most recent frame (Original Size)
frame_lock = threading.Lock() 

# --- SYSTEM SETUP ---
if not os.path.exists(SAVE_DIR):
    try:
        os.makedirs(SAVE_DIR)
        print(f"Created directory: {SAVE_DIR}")
    except OSError as e:
        print(f"Error creating directory: {e}")

# Setup ZMQ Server (REP)
context = zmq.Context()
socket = context.socket(zmq.REP)
try:
    socket.bind(f"tcp://*:{ZMQ_PORT}")
    print(f"ZMQ Server listening on tcp://*:{ZMQ_PORT}")
except zmq.ZMQError as e:
    print(f"ZMQ Bind Error: {e}")

# --- HELPER FUNCTIONS ---

def log(message):
    """Adds a timestamped message to the GUI log area."""
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    print(full_msg)
    
    # Update GUI safely
    try:
        log_area.config(state='normal')
        log_area.insert(tk.END, full_msg + "\n")
        log_area.see(tk.END)
        log_area.config(state='disabled')
    except:
        pass 

def update_status_display(text, confidence_val, is_pass):
    """Updates the Bento Status Card safely."""
    try:
        status_var.set(text)
        conf_var.set(f"CONFIDENCE: {confidence_val}%")
        
        if is_pass:
            # Green Scheme
            status_indicator.config(bg="#E8F5E9", fg="#2E7D32")
        else:
            # Red Scheme
            status_indicator.config(bg="#FFEBEE", fg="#C62828")
    except:
        pass

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_json_from_text(text):
    """Robustly extracts JSON object from LLM response."""
    try:
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match: return json.loads(match.group(1))
        
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match: return json.loads(match.group(1))
            
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def perform_analysis_logic(save_path):
    """The core logic: Encode -> Send to API -> Parse JSON -> Return Dict"""
    try:
        log(f"Analyzing: {os.path.basename(save_path)}")
        base64_image = encode_image_to_base64(save_path)
        
        headers = {"Content-Type": "application/json"}
        
        system_prompt = (
            "Analyze the gripper camera image. Focus on the gap between the jaws. "
            "Is the object physically present? "
            "Return ONLY a raw JSON object without Markdown formatting. "
            "Schema: {\"object_present\": true/false, \"confidence\": number 0-100}."
        )

        payload = {
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 100
        }

        # API Request
        response = requests.post(LM_STUDIO_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            log(f"AI Raw: {content}")
            
            json_data = extract_json_from_text(content)
            
            if json_data:
                present = json_data.get('object_present')
                conf = json_data.get('confidence')
                
                # Logic for Visual Feedback
                if present and conf > 80:
                    update_status_display(f"OBJECT FOUND", conf, True)
                else:
                    status_text = "OBJECT MISSING" if not present else "LOW CONFIDENCE"
                    update_status_display(status_text, conf, False)
                
                return json_data
            else:
                log("ERROR: Invalid JSON from AI")
                return {"object_present": False, "confidence": 0, "error": "Invalid JSON"}
        else:
            log(f"API Error: {response.status_code}")
            return {"object_present": False, "confidence": 0, "error": "API Error"}

    except Exception as e:
        log(f"Exception during analysis: {e}")
        return {"object_present": False, "confidence": 0, "error": str(e)}

# --- ZMQ WORKER THREAD ---
def zmq_listener_thread():
    """Runs in background. Waits for requests."""
    log("System Ready. Listening for commands...")
    
    while True:
        try:
            message = socket.recv_string()
            
            if message == "CAPTURE":
                log(">>> COMMAND RECEIVED: CAPTURE")
                
                # Update UI to show processing
                status_var.set("ANALYZING...")
                status_indicator.config(bg="#FFF8E1", fg="#F57F17") # Amber
                
                frame_to_save = None
                with frame_lock:
                    if latest_frame is not None:
                        frame_to_save = copy.deepcopy(latest_frame)
                
                if frame_to_save is not None:
                    # Save Image (Original High Res)
                    filename = f"req_{int(time.time())}.jpg"
                    filepath = os.path.join(SAVE_DIR, filename)
                    cv2.imwrite(filepath, frame_to_save)
                    
                    # Analyze
                    result_json = perform_analysis_logic(filepath)
                    
                    # Reply
                    socket.send_json(result_json)
                    log(f"<<< REPLY SENT: {result_json}")
                else:
                    log("ERROR: No frame available.")
                    socket.send_json({"object_present": False, "confidence": 0, "error": "No Camera Frame"})
            else:
                log(f"Unknown Request: {message}")
                socket.send_string("UNKNOWN_CMD")
                
        except zmq.ZMQError as e:
            print(f"ZMQ Error: {e}")
            break
        except Exception as e:
            print(f"General Error: {e}")

# --- GUI MAIN LOOP ---
def update_frame():
    """Reads camera, updates Global Var (High Res), and updates GUI (Low Res)."""
    global latest_frame
    ret, frame = cap.read()
    if ret:
        # 1. Store High-Res Frame for AI
        with frame_lock:
            latest_frame = frame
        
        # 2. Resize for GUI Display (Make it smaller/compact)
        frame_resized = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        
        # 3. Convert for Tkinter
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        
        video_label.imgtk = imgtk
        video_label.configure(image=imgtk)
    
    root.after(10, update_frame)

def on_closing():
    log("Shutting down...")
    cap.release()
    socket.close()
    context.term()
    root.destroy()
    os._exit(0)

# --- GUI CONSTRUCTION (BENTO STYLE) ---
root = tk.Tk()
root.title("Perception Node: VLM Vision System")
root.geometry("800x500") 
root.configure(bg="#F3F4F6") # Light Grey Background

# Styles
STYLE_CARD_BG = "#FFFFFF"
STYLE_FONT_HEAD = ("Segoe UI", 11, "bold")
STYLE_FONT_BODY = ("Segoe UI", 10)
STYLE_FONT_MONO = ("Consolas", 9)

# === BENTO GRID LAYOUT ===
root.columnconfigure(0, weight=1) # Left Col (Visuals)
root.columnconfigure(1, weight=1) # Right Col (Logs)
root.rowconfigure(0, weight=1)

# --- LEFT COLUMN (VISUALS) ---
left_container = tk.Frame(root, bg="#F3F4F6")
left_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

# Bento Box 1: Live Vision
vision_card = tk.Frame(left_container, bg=STYLE_CARD_BG, padx=15, pady=15)
vision_card.pack(fill=tk.X, pady=(0, 10))

tk.Label(vision_card, text="LIVE VISION FEED", bg=STYLE_CARD_BG, fg="#374151", font=STYLE_FONT_HEAD, anchor="w").pack(fill=tk.X, pady=(0, 10))

# Camera Frame (Centered)
video_frame_container = tk.Frame(vision_card, bg="#000000") # Black border for video
video_frame_container.pack()
video_label = tk.Label(video_frame_container, bg="black")
video_label.pack()

# Bento Box 2: Analytics Result
stats_card = tk.Frame(left_container, bg=STYLE_CARD_BG, padx=15, pady=15)
stats_card.pack(fill=tk.X, pady=(0, 10))

tk.Label(stats_card, text="AI ANALYTICS", bg=STYLE_CARD_BG, fg="#374151", font=STYLE_FONT_HEAD, anchor="w").pack(fill=tk.X, pady=(0, 10))

status_var = tk.StringVar(value="WAITING FOR COMMAND")
status_indicator = tk.Label(stats_card, textvariable=status_var, 
                            bg="#ECEFF1", fg="#546E7A", font=("Segoe UI", 14, "bold"), 
                            pady=15, width=20)
status_indicator.pack(fill=tk.X)

conf_var = tk.StringVar(value="CONFIDENCE: -")
tk.Label(stats_card, textvariable=conf_var, bg=STYLE_CARD_BG, fg="#6B7280", font=STYLE_FONT_BODY).pack(pady=(5,0))

# --- RIGHT COLUMN (LOGS) ---
# Bento Box 3: System Logs
log_card = tk.Frame(root, bg=STYLE_CARD_BG, padx=15, pady=15)
log_card.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)

tk.Label(log_card, text="SYSTEM ACTIVITY LOG", bg=STYLE_CARD_BG, fg="#374151", font=STYLE_FONT_HEAD, anchor="w").pack(fill=tk.X, pady=(0, 10))

log_area = scrolledtext.ScrolledText(log_card, state='disabled', 
                                     font=STYLE_FONT_MONO, bg="#F9FAFB", fg="#1F2937",
                                     bd=0, highlightthickness=1, highlightbackground="#E5E7EB")
log_area.pack(fill=tk.BOTH, expand=True)

# Footer Info
info_text = f"Listening: Port {ZMQ_PORT} | Model: {MODEL_ID.split('/')[-1]}"
tk.Label(log_card, text=info_text, bg=STYLE_CARD_BG, fg="#9CA3AF", font=("Segoe UI", 8)).pack(side=tk.BOTTOM, anchor="e", pady=(5,0))


# --- INITIALIZATION ---
cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(3, FRAME_WIDTH)  # Capture High Res
cap.set(4, FRAME_HEIGHT)

if cap.isOpened():
    log(f"System Initialized. Camera: {FRAME_WIDTH}x{FRAME_HEIGHT}")
    log(f"Listening on Port {ZMQ_PORT}...")
    threading.Thread(target=zmq_listener_thread, daemon=True).start()
else:
    log("ERROR: Camera Connection Failed.")
    status_var.set("CAMERA ERROR")
    status_indicator.config(bg="#FFEBEE", fg="#C62828")

root.protocol("WM_DELETE_WINDOW", on_closing)
update_frame()
root.mainloop()