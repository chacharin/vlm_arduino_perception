import tkinter as tk
import zmq
import json
import time

# --- ZMQ CONFIGURATION ---
# This node behaves as a PUBLISHER (Server side of ZMQ)
# It binds to port 5555 so the decision_node can connect to it.
ZMQ_PORT = 5555
zmq_context = zmq.Context()
zmq_socket = zmq_context.socket(zmq.PUB)
try:
    # Bind to all network interfaces on this machine
    zmq_socket.bind(f"tcp://*:{ZMQ_PORT}")
    print(f"Mock Perception Publisher bound to tcp://*:{ZMQ_PORT}")
except Exception as e:
    print(f"Error binding ZMQ: {e}")
    exit()

# --- GUI FUNCTIONS ---
def send_perception_packet():
    """
    Reads the GUI widgets, creates the JSON packet, and publishes it via ZMQ.
    """
    # 1. Get values from GUI widgets
    confidence_val = confidence_scale.get()
    # Tkinter Checkbutton uses 1 for True, 0 for False. Convert to boolean.
    is_present_bool = True if object_present_var.get() == 1 else False

    # 2. Create the dictionary payload based on your requirement
    payload = {
        "object_present": is_present_bool,
        "confidence": confidence_val
    }

    try:
        # 3. Send directly as JSON (ZMQ handles serialization)
        zmq_socket.send_json(payload)
        
        # Update feedback label with timestamp
        timestamp = time.strftime("%H:%M:%S")
        feedback_label.config(text=f"Last Sent [{timestamp}]:\n{json.dumps(payload)}", fg="blue")
        print(f"Sent: {payload}")
        
    except Exception as e:
        feedback_label.config(text=f"Error sending: {e}", fg="red")

# --- GUI SETUP ---
root = tk.Tk()
root.title("Mock Perception Simulator (ZMQ PUB)")
root.geometry("400x300")

# Title Label
tk.Label(root, text="Adjust values and click 'Send' to simulate AI detection", 
         wraplength=380, pady=10, font=("Arial", 10, "bold")).pack()

# --- Confidence Slider ---
scale_frame = tk.Frame(root, pady=10, highlightbackground="gray", highlightthickness=1)
scale_frame.pack(fill=tk.X, padx=20)
tk.Label(scale_frame, text="Confidence Level (0-100):").pack()
# Scale widget for easy slider input
confidence_scale = tk.Scale(scale_frame, from_=0, to=100, orient=tk.HORIZONTAL, length=300)
confidence_scale.set(50) # Set default value
confidence_scale.pack()

# --- Object Present Checkbox ---
check_frame = tk.Frame(root, pady=10)
check_frame.pack()
object_present_var = tk.IntVar() # Variable to store checkbox state (0 or 1)
# Checkbutton widget
obj_check = tk.Checkbutton(check_frame, text="Object Present (True/False)", 
                           variable=object_present_var, font=("Arial", 11))
obj_check.select() # Default to checked (True)
obj_check.pack()

# --- Send Button ---
send_btn = tk.Button(root, text="SEND JSON PACKET NOW", 
                     command=send_perception_packet, height=2, width=25, 
                     bg="#d0f0c0", font=("Arial", 10, "bold"))
send_btn.pack(pady=15)

# --- Feedback Label ---
feedback_label = tk.Label(root, text="Waiting to send...", fg="gray", pady=5, wraplength=380)
feedback_label.pack()

# Start GUI loop
root.mainloop()