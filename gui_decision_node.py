import tkinter as tk
import serial
import time
import zmq
import json

# --- CONFIGURATION ---
# Serial Config
PORT = "COM10"          # Check your Device Manager
BAUD = 115200

# ZMQ Config (Perception Node Communication)
ZMQ_HOST = "tcp://localhost:5555"
CONFIDENCE_THRESHOLD = 80

# Global Serial Object
ser = None

# --- ZMQ SETUP ---
context = zmq.Context()
socket = context.socket(zmq.SUB)
# Assuming perception_node binds to 5555, we connect. 
# If perception_node connects, change this to socket.bind()
try:
    socket.connect(ZMQ_HOST)
    socket.setsockopt_string(zmq.SUBSCRIBE, "") # Subscribe to all topics
    print(f"ZMQ Listener started on {ZMQ_HOST}")
except Exception as e:
    print(f"Error starting ZMQ: {e}")

# --- SERIAL FUNCTIONS ---
def connect_serial():
    global ser
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)  # Arduino reset time
        status_label.config(text=f"Connected: {PORT} @ {BAUD}", fg="green")
        
        # Start the ZMQ polling loop only after we attempt connection
        # (Or you can run it immediately if you want logic to run without serial)
    except Exception as e:
        status_label.config(text=f"Serial connect failed: {e}", fg="red")
        ser = None

def send_stop():
    """
    Sends the stop command to Arduino.
    Used by both the GUI Button and the ZMQ Decision Logic.
    """
    if ser is None or not ser.is_open:
        status_label.config(text="Not connected. Check PORT.", fg="orange")
        return
    try:
        # The specific byte sequence you requested
        ser.write(b"stop\n")
        status_label.config(text="Sent: stop (Emergency/Decision)", fg="red")
        print("Command sent: stop")
    except Exception as e:
        status_label.config(text=f"Send failed: {e}", fg="red")

# --- ZMQ DECISION LOOP ---
def check_perception_messages():
    """
    Check for ZMQ messages without blocking the GUI.
    """
    try:
        # NON-BLOCKING receive. If no message, it raises zmq.Again
        message = socket.recv_json(flags=zmq.NOBLOCK)
        
        # --- DECISION LOGIC ---
        # Expected format: {"object_present": true, "confidence": 95}
        obj_present = message.get("object_present", False)
        confidence = message.get("confidence", 0)

        # Print for debugging (optional)
        # print(f"Perception: {obj_present}, Conf: {confidence}")

        if obj_present == False and confidence > CONFIDENCE_THRESHOLD:
            print(f"Decision Triggered: Confidence {confidence}% > {CONFIDENCE_THRESHOLD}%")
            send_stop()
            
    except zmq.Again:
        pass # No message received, do nothing
    except json.JSONDecodeError:
        print("Received invalid JSON data")
    except Exception as e:
        print(f"ZMQ Error: {e}")

    # Schedule this function to run again in 50ms
    root.after(50, check_perception_messages)

# --- GUI SETUP ---
root = tk.Tk()
root.title("Decision Node: Robot Arm Controller")
root.geometry("350x200")

# Label
status_label = tk.Label(root, text="System Ready - Not Connected", pady=10, font=("Arial", 10))
status_label.pack()

# Connect Button
connect_btn = tk.Button(root, text="Connect Serial", command=connect_serial, height=2, width=20, bg="#dddddd")
connect_btn.pack(pady=5)

# Manual Stop Button
stop_btn = tk.Button(root, text="STOP (Manual)", command=send_stop, height=2, width=20, bg="#ffcccc", fg="red")
stop_btn.pack(pady=5)

# Start the ZMQ polling loop immediately so we don't miss messages 
# (even if Serial isn't connected yet, we can monitor the stream)
root.after(100, check_perception_messages)

# Start GUI
root.mainloop()