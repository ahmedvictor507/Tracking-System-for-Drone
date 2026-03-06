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
# --- SERVO TRACKING SETTINGS ---
pan_angle = 90       # Starting X angle
tilt_angle = 90      # Starting Y angle
DEADZONE = 40        # Pixels from center before it starts moving (Increase to make it hold still more)
STEP_SIZE = 2        # Speed of movement (Degrees per frame)
INVERT_PAN = False   # Change to True if X-axis is backward
INVERT_TILT = True  # Change to True if Y-axis is backward

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
video = cv2.VideoCapture(1) if USE_WEBCAM else cv2.VideoCapture("video.mp4")
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

            # --- SERVO CONTROL (CRASH PROOF & DEADZONE) ---
            if USE_SERVO and ser is not None:
                # Calculate how far the object is from the exact center
                error_x = center_x - (cols // 2)
                error_y = center_y - (rows // 2)

                # --- X-AXIS (PAN) LOGIC ---
                if abs(error_x) > DEADZONE:
                    direction_x = 1 if error_x > 0 else -1
                    if INVERT_PAN: direction_x *= -1
                    pan_angle += (direction_x * STEP_SIZE)

                # --- Y-AXIS (TILT) LOGIC ---
                if abs(error_y) > DEADZONE:
                    direction_y = 1 if error_y > 0 else -1
                    if INVERT_TILT: direction_y *= -1
                    tilt_angle += (direction_y * STEP_SIZE)

                # Keep angles strictly between 0 and 180 to protect servos
                pan_angle = max(0, min(180, pan_angle))
                tilt_angle = max(0, min(180, tilt_angle))
                
                # Send Command Safe Block
                try:
                    if ser.is_open:
                        ser.write(f"{int(pan_angle)},{int(tilt_angle)}\n".encode())
                except Exception as e:
                    print(f"ARDUINO ERROR: {e}")
                    pass
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
