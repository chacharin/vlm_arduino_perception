import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import serial
import serial.tools.list_ports
import zmq
import time
import threading

# --- CONFIGURATION ---
BAUD = 115200

# ZMQ (Perception Node)
ZMQ_HOST = "tcp://localhost:5555"
CONFIDENCE_THRESHOLD = 80

# --- GLOBAL VARIABLES ---
ser = None
running = True  # Flag to control the background thread
is_connected = False # Flag to track connection state

# --- ZMQ SETUP (Client Mode) ---
context = zmq.Context()
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

def update_status_indicator(text, color, text_color="white"):
    """Updates the big status box safely."""
    try:
        main_status_var.set(text)
        main_status_label.config(bg=color, fg=text_color)
    except:
        pass

def get_available_ports():
    """Scans for available COM ports."""
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def refresh_ports():
    """Refreshes the dropdown list."""
    ports = get_available_ports()
    port_combo['values'] = ports
    if ports:
        port_combo.current(0)
    else:
        port_combo.set('')

def toggle_connection():
    """Handles Connect/Disconnect logic."""
    global ser, is_connected
    
    if not is_connected:
        # --- CONNECT LOGIC ---
        selected_port = port_combo.get()
        if not selected_port:
            messagebox.showwarning("Warning", "Please select a COM Port first.")
            return

        try:
            ser = serial.Serial(selected_port, BAUD, timeout=0.1)
            time.sleep(2) # Allow Arduino reset
            
            is_connected = True
            connect_btn.config(text="DISCONNECT", bg="#FFF0F0", fg="#D32F2F", relief=tk.SUNKEN)
            port_combo.config(state="disabled") # Lock dropdown
            refresh_btn.config(state="disabled")
            
            update_status_indicator("SYSTEM READY", "#E0F2F1", "#00695C") # Soft Teal
            log(f"Connected to {selected_port} @ {BAUD}")
            
        except Exception as e:
            update_status_indicator("CONNECTION FAILED", "#FFEBEE", "#C62828")
            log(f"Serial Error: {e}")
            ser = None
            is_connected = False
    else:
        # --- DISCONNECT LOGIC ---
        if ser and ser.is_open:
            ser.close()
        
        ser = None
        is_connected = False
        connect_btn.config(text="CONNECT SERIAL", bg="#E3F2FD", fg="#1565C0", relief=tk.RAISED)
        port_combo.config(state="normal") # Unlock dropdown
        refresh_btn.config(state="normal")
        
        update_status_indicator("DISCONNECTED", "#ECEFF1", "#546E7A") # Grey
        log("Serial Disconnected")

def send_to_arduino(command_str):
    """Sends a command to Arduino."""
    if ser and ser.is_open:
        try:
            cmd = command_str + "\n"
            ser.write(cmd.encode('utf-8'))
            log(f"Sent to Arduino: {command_str}")
        except Exception as e:
            log(f"Write Error: {e}")
    else:
        log(f"Cannot send '{command_str}': Not connected")

def emergency_stop():
    """Manual Stop Button."""
    log("!!! EMERGENCY STOP TRIGGERED !!!")
    send_to_arduino("stop")
    update_status_indicator("EMERGENCY STOP", "#FFEBEE", "#D32F2F") # Red bg, Dark Red text
    log("Sent STOP command")

# --- CORE LOGIC THREAD ---
def serial_worker():
    global ser
    log("Worker Thread Started.")
    
    while running:
        if is_connected and ser and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8').strip()
                    
                    if not line:
                        continue
                        
                    # --- HANDSHAKE LOGIC ---
                    if line == "request_check":
                        log(">>> Arduino requests check. Asking Perception...")
                        update_status_indicator("CHECKING...", "#FFF8E1", "#F57F17") # Amber
                        
                        try:
                            # 1. Request Perception
                            zmq_socket.send_string("CAPTURE")
                            
                            # 2. Wait for Reply
                            if zmq_socket.poll(timeout=5000): 
                                response = zmq_socket.recv_json()
                                log(f"Perception Reply: {response}")
                                
                                # 3. Analyze Logic
                                obj_present = response.get("object_present", False)
                                confidence = response.get("confidence", 0)
                                
                                if obj_present and confidence > CONFIDENCE_THRESHOLD:
                                    log(f"DECISION: PASS (Conf {confidence}%)")
                                    update_status_indicator("PASS ALLOWED", "#E8F5E9", "#2E7D32") # Green
                                    send_to_arduino("pass")
                                else:
                                    log(f"DECISION: STOP (Conf {confidence}%)")
                                    update_status_indicator("STOP (NOT READY)", "#FFEBEE", "#C62828") # Red
                                    send_to_arduino("stop")
                                    
                            else:
                                log("ERROR: Perception Timeout")
                                update_status_indicator("TIMEOUT ERROR", "#FFEBEE", "#C62828")
                                send_to_arduino("stop") 
                                
                        except zmq.ZMQError as e:
                            log(f"ZMQ Error: {e}")

            except Exception as e:
                log(f"Serial Read Error: {e}")
                # Optional: Auto-disconnect on error
                # toggle_connection() 
        
        time.sleep(0.01)

# --- GUI CONSTRUCTION (BENTO STYLE) ---
def on_closing():
    global running
    running = False
    if ser and ser.is_open:
        ser.close()
    root.destroy()

# Root Window Setup
root = tk.Tk()
root.title("Decision Node: Master Controller")
root.geometry("800x500")
root.configure(bg="#F3F4F6") # Light Grey Background for Bento feel

# Styles
STYLE_CARD_BG = "#FFFFFF"
STYLE_FONT_HEAD = ("Segoe UI", 11, "bold")
STYLE_FONT_BODY = ("Segoe UI", 10)
STYLE_FONT_MONO = ("Consolas", 9)

# === BENTO LAYOUT (Grid) ===
# We use grid to create the bento boxes
root.columnconfigure(0, weight=1) # Left Col (Controls)
root.columnconfigure(1, weight=2) # Right Col (Logs)
root.rowconfigure(0, weight=1) # Main Row

# --- LEFT COLUMN (CONTROLS) ---
left_container = tk.Frame(root, bg="#F3F4F6")
left_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

# Bento Box 1: Connection Settings
conn_card = tk.Frame(left_container, bg=STYLE_CARD_BG, padx=15, pady=15)
conn_card.pack(fill=tk.X, pady=(0, 10)) # Spacing between cards

tk.Label(conn_card, text="CONNECTION", bg=STYLE_CARD_BG, fg="#374151", font=STYLE_FONT_HEAD, anchor="w").pack(fill=tk.X, pady=(0, 10))

# Port Selection Row
port_frame = tk.Frame(conn_card, bg=STYLE_CARD_BG)
port_frame.pack(fill=tk.X, pady=5)

tk.Label(port_frame, text="COM Port:", bg=STYLE_CARD_BG, font=STYLE_FONT_BODY).pack(side=tk.LEFT)

# Dropdown
port_combo = ttk.Combobox(port_frame, width=10, state="readonly")
port_combo.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

# Refresh Button (Small)
refresh_btn = tk.Button(port_frame, text="⟳", command=refresh_ports, width=3, bg="#E0E0E0", relief=tk.FLAT)
refresh_btn.pack(side=tk.LEFT)

# Connect/Disconnect Toggle Button
connect_btn = tk.Button(conn_card, text="CONNECT SERIAL", command=toggle_connection,
                        bg="#E3F2FD", fg="#1565C0", font=("Segoe UI", 10, "bold"),
                        height=2, relief=tk.RAISED, bd=0)
connect_btn.pack(fill=tk.X, pady=(10, 0))


# Bento Box 2: Status Dashboard
status_card = tk.Frame(left_container, bg=STYLE_CARD_BG, padx=15, pady=15)
status_card.pack(fill=tk.X, pady=(0, 10))

tk.Label(status_card, text="SYSTEM STATUS", bg=STYLE_CARD_BG, fg="#374151", font=STYLE_FONT_HEAD, anchor="w").pack(fill=tk.X, pady=(0, 10))

main_status_var = tk.StringVar(value="DISCONNECTED")
main_status_label = tk.Label(status_card, textvariable=main_status_var,
                             bg="#ECEFF1", fg="#546E7A", font=("Segoe UI", 14, "bold"),
                             pady=20, width=15) # Fixed width prevents jitter
main_status_label.pack(fill=tk.X)


# Bento Box 3: Safety Control
safety_card = tk.Frame(left_container, bg=STYLE_CARD_BG, padx=15, pady=15)
safety_card.pack(fill=tk.X, pady=(0, 10))

tk.Label(safety_card, text="SAFETY OVERRIDE", bg=STYLE_CARD_BG, fg="#374151", font=STYLE_FONT_HEAD, anchor="w").pack(fill=tk.X, pady=(0, 10))

stop_btn = tk.Button(safety_card, text="STOP / RESET", command=emergency_stop,
                     bg="#FFEBEE", fg="#C62828", font=("Segoe UI", 11, "bold"),
                     height=2, relief=tk.FLAT, bd=0, activebackground="#FFCDD2")
stop_btn.pack(fill=tk.X)


# --- RIGHT COLUMN (LOGS) ---
# Bento Box 4: Logs (Takes full height)
log_card = tk.Frame(root, bg=STYLE_CARD_BG, padx=15, pady=15)
log_card.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)

tk.Label(log_card, text="ACTIVITY LOG", bg=STYLE_CARD_BG, fg="#374151", font=STYLE_FONT_HEAD, anchor="w").pack(fill=tk.X, pady=(0, 10))

# Scrollbar and Text
log_area = scrolledtext.ScrolledText(log_card, state='disabled',
                                     font=STYLE_FONT_MONO, bg="#F9FAFB", fg="#1F2937",
                                     bd=0, highlightthickness=1, highlightbackground="#E5E7EB")
log_area.pack(fill=tk.BOTH, expand=True)


# --- INITIALIZATION ---
# Initial port scan
refresh_ports()

# Start background thread
t = threading.Thread(target=serial_worker, daemon=True)
t.start()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()