import tkinter as tk
from tkinter import scrolledtext
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

# --- CONFIGURATION ---
# 1. LM Studio Settings
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_ID = "qwen/qwen3-vl-4b"  # Model VLM

# 2. Camera Settings
CAMERA_INDEX = 1
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# 3. File Path Settings
SAVE_DIR = r"D:\project_VLM\capture_img"

# 4. ZMQ Settings (Publisher)
ZMQ_PORT = 5555

# --- SYSTEM SETUP ---
# Ensure Save Directory Exists
if not os.path.exists(SAVE_DIR):
    try:
        os.makedirs(SAVE_DIR)
        print(f"Created directory: {SAVE_DIR}")
    except OSError as e:
        print(f"Error creating directory: {e}")

# Setup ZMQ Publisher
context = zmq.Context()
socket = context.socket(zmq.PUB)
try:
    socket.bind(f"tcp://*:{ZMQ_PORT}")
except zmq.ZMQError as e:
    print(f"ZMQ Bind Error: {e}")

# --- HELPER FUNCTIONS ---

def log(message):
    """Adds a timestamped message to the GUI log area."""
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    print(full_msg)  # Print to console
    
    # Update GUI safely
    log_area.config(state='normal')
    log_area.insert(tk.END, full_msg + "\n")
    log_area.see(tk.END) # Auto-scroll to bottom
    log_area.config(state='disabled')

def encode_image_to_base64(image_path):
    """Encodes an image file to a base64 string for the API."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_json_from_text(text):
    """
    Robustly extracts JSON object from LLM response.
    Handles cases where LLM wraps code in markdown ```json ... ```
    """
    try:
        # Try finding JSON within markdown blocks first
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # If no markdown, try finding the first '{' and last '}'
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
            
        # If clean, try loading directly
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def analyze_image_thread(image_path):
    """
    Worker function to send image to LM Studio. 
    Runs in a separate thread to prevent GUI freezing.
    """
    try:
        log(f"Encoding image...")
        base64_image = encode_image_to_base64(image_path)
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Prompt specified by user
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
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.1, # Keep it deterministic
            "max_tokens": 1000
        }

        log("Sending to AI Model (Waiting for response)...")
        
        # --- API REQUEST ---
        response = requests.post(LM_STUDIO_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            log(f"AI Raw Response: {content}")
            
            # Clean and Parse JSON
            json_data = extract_json_from_text(content)
            
            if json_data:
                # --- SEND TO DECISION NODE ---
                socket.send_json(json_data)
                log(f"SUCCESS: Sent to Decision Node -> {json_data}")
                
                # Visual Feedback on GUI
                status_var.set(f"Last Result: Present={json_data.get('object_present')}, Conf={json_data.get('confidence')}%")
                if json_data.get('confidence', 0) > 80 and json_data.get('object_present'):
                    status_label.config(fg="red") # Highlight danger/stop
                else:
                    status_label.config(fg="green")

            else:
                log("ERROR: AI response was not valid JSON.")
        else:
            log(f"API Error: {response.status_code} - {response.text}")

    except requests.exceptions.ConnectionError:
        log("ERROR: Could not connect to LM Studio. Is it running?")
    except Exception as e:
        log(f"ERROR in analysis: {e}")
    finally:
        # Re-enable button
        capture_btn.config(state="normal", text="Capture & Analyze")

def capture_action():
    """Triggered by button click."""
    # 1. Disable button to prevent spamming
    capture_btn.config(state="disabled", text="Processing...")
    
    # 2. Get current frame
    ret, frame = cap.read()
    if ret:
        # 3. Generate filename with timestamp
        filename = f"capture_{int(time.time())}.jpg"
        filepath = os.path.join(SAVE_DIR, filename)
        
        # 4. Save Image
        try:
            cv2.imwrite(filepath, frame)
            log(f"Image saved: {filepath}")
            
            # 5. Start Analysis Thread
            # We use threading so the video stream doesn't freeze while waiting for AI
            threading.Thread(target=analyze_image_thread, args=(filepath,), daemon=True).start()
            
        except Exception as e:
            log(f"Save Failed: {e}")
            capture_btn.config(state="normal", text="Capture & Analyze")
    else:
        log("Error: Could not read camera frame.")
        capture_btn.config(state="normal", text="Capture & Analyze")

# --- GUI MAIN LOOP ---
def update_frame():
    """Reads camera and updates Tkinter label."""
    ret, frame = cap.read()
    if ret:
        # Convert Color (OpenCV BGR -> RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Convert to PIL Image
        img = Image.fromarray(frame_rgb)
        # Convert to ImageTk
        imgtk = ImageTk.PhotoImage(image=img)
        
        video_label.imgtk = imgtk
        video_label.configure(image=imgtk)
    
    # Repeat every 10ms
    root.after(10, update_frame)

def on_closing():
    """Cleanup when closing window."""
    log("Closing system...")
    cap.release()
    root.destroy()

# --- GUI CONSTRUCTION ---
root = tk.Tk()
root.title("Perception Node: VLM Integration")
root.geometry("900x700")

# 1. Video Frame
video_frame = tk.Frame(root, bg="black", width=640, height=480)
video_frame.pack(pady=10)
video_label = tk.Label(video_frame)
video_label.pack()

# 2. Control Area
control_frame = tk.Frame(root)
control_frame.pack(pady=5, fill=tk.X, padx=20)

capture_btn = tk.Button(control_frame, text="Capture & Analyze", command=capture_action, 
                        bg="#007bff", fg="white", font=("Arial", 14, "bold"), height=2)
capture_btn.pack(fill=tk.X)

status_var = tk.StringVar()
status_var.set("Ready to Capture")
status_label = tk.Label(root, textvariable=status_var, font=("Arial", 12, "bold"), fg="blue")
status_label.pack(pady=5)

# 3. Log Area
log_frame = tk.Frame(root)
log_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)

tk.Label(log_frame, text="System Log:", anchor="w").pack(fill=tk.X)
log_area = scrolledtext.ScrolledText(log_frame, height=10, state='disabled', font=("Consolas", 9))
log_area.pack(fill=tk.BOTH, expand=True)

# --- INITIALIZATION ---
# Open Camera
cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(3, FRAME_WIDTH)
cap.set(4, FRAME_HEIGHT)

if not cap.isOpened():
    log("ERROR: Could not open camera. Check index.")
else:
    log(f"Camera opened. Resolution: {FRAME_WIDTH}x{FRAME_HEIGHT}")
    log(f"Saving images to: {SAVE_DIR}")
    log(f"Connecting to VLM at: {LM_STUDIO_URL}")

root.protocol("WM_DELETE_WINDOW", on_closing)
update_frame() # Start video loop
root.mainloop()