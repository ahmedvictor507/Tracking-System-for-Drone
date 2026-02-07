import cv2
import numpy as np
from collections import deque
import serial
import time

# --- CONFIGURATION ---
USE_WEBCAM = True
USE_SERVO = True        
SERIAL_PORT = 'COM13'   # <--- Updated to match your last successful port
BAUD_RATE = 9600

# --- CONNECT TO ARDUINO ---
ser = None
if USE_SERVO:
    try:
        print(f"Attempting to connect to Arduino on {SERIAL_PORT}...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, write_timeout=0.1) # Added timeout prevents freezing
        time.sleep(2) 
        print("SUCCESS: Servo System Connected!")
    except Exception as e:
        print(f"\nWARNING: Arduino connection failed. Running in VISION ONLY mode.")
        print(f"Reason: {e}\n")
        USE_SERVO = False

# --- ROBUST TRACKER SETUP ---
def create_tracker():
    """
    Tries to load the best available tracker (CSRT or KCF).
    Checks both modern and legacy OpenCV paths.
    """
    tracker_types = [
        # Try CSRT first (Most Accurate)
        ('CSRT (Legacy)', lambda: cv2.legacy.TrackerCSRT_create()),
        ('CSRT (Main)',   lambda: cv2.TrackerCSRT_create()),
        
        # Try KCF second (Fastest)
        ('KCF (Legacy)',  lambda: cv2.legacy.TrackerKCF_create()),
        ('KCF (Main)',    lambda: cv2.TrackerKCF_create()),
        
        # Fallback
        ('MIL (Main)',    lambda: cv2.TrackerMIL_create()),
    ]

    for name, builder in tracker_types:
        try:
            tracker = builder()
            print(f"SUCCESS: Loaded {name} Tracker")
            return tracker
        except AttributeError:
            continue
            
    print("ERROR: No suitable tracker found. Please install opencv-contrib-python.")
    return None

# --- INITIALIZATION ---
video = cv2.VideoCapture(0) if USE_WEBCAM else cv2.VideoCapture("video.mp4")
tracker = create_tracker()
pts = deque(maxlen=64)

tracking_active = False
initBB = None

# --- MOUSE CALLBACK ---
def mouse_handler(event, x, y, flags, param):
    global initBB, tracking_active, tracker, pts
    if event == cv2.EVENT_LBUTTONDOWN:
        tracker = create_tracker()
        initBB = (x-30, y-30, 60, 60)
        tracker.init(frame, initBB)
        tracking_active = True
        pts.clear()
        print(f"TARGET LOCKED AT: {x}, {y}")

cv2.namedWindow("Targeting System")
cv2.setMouseCallback("Targeting System", mouse_handler)

print("\n--- SYSTEM READY ---")
print("1. Point camera at object.")
print("2. Click to LOCK.")
print("3. Press 'q' to QUIT.\n")

# --- MAIN LOOP ---
while True:
    ret, frame = video.read()
    if not ret: break
    
    if USE_WEBCAM: frame = cv2.flip(frame, 1)
    rows, cols, _ = frame.shape

    if tracking_active:
        (success, box) = tracker.update(frame)
        
        if success:
            (x, y, w, h) = [int(v) for v in box]
            center_x = int(x + w/2)
            center_y = int(y + h/2)
            pts.appendleft((center_x, center_y))

            # DRAW VISUALS
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)

            # --- SERVO CONTROL (CRASH PROOF) ---
            if USE_SERVO and ser is not None:
                # Calculate Angles
                pan_angle = int(np.interp(center_x, [0, cols], [180, 0]))
                tilt_angle = int(np.interp(center_y, [0, rows], [180, 0]))
                
                # Send Command Safe Block
                try:
                    if ser.is_open:
                        ser.write(f"{pan_angle},{tilt_angle}\n".encode())
                except Exception as e:
                    # If Arduino disconnects (Brownout), print error but DON'T CRASH
                    print(f"ARDUINO ERROR: {e}")
                    pass 

                # On-Screen Telemetry
                cv2.putText(frame, f"SERVO X: {pan_angle}", (10, rows-40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                cv2.putText(frame, f"SERVO Y: {tilt_angle}", (10, rows-20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            # Draw Tail
            for i in range(1, len(pts)):
                if pts[i-1] is None or pts[i] is None: continue
                cv2.line(frame, pts[i-1], pts[i], (0, 0, 255), 2)
        else:
            cv2.putText(frame, "TARGET LOST", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    else:
        cv2.putText(frame, "CLICK TO LOCK", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    cv2.imshow("Targeting System", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

# --- CLEANUP ---
if ser is not None and ser.is_open:
    ser.close()
video.release()
cv2.destroyAllWindows()
