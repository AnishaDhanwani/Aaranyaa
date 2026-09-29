import os
import sys
import time
from collections import deque
import cv2
import numpy as np
from fastapi import FastAPI, Body
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

# Add root folder to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from processing.feature_engine import node1_engine
from processing.model import ml_classifier

app = FastAPI(title="AegisNet 2.0 Central Engine")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ----------------- TELEMETRY & SYSTEM STATE -----------------
class TelemetryData(BaseModel):
    node_id: str = "Node 01"
    smoke: float
    co: float = 400.0
    flame: int = 1
    temp: float
    humidity: float

latest_reading = {
    "node_id": "Node 01",
    "smoke": 0.0,
    "co": 0.0,
    "flame": 1,
    "temp": 0.0,
    "humidity": 0.0,
    "last_updated": 0,
    "is_online": False,
    "analysis": {
        "threat_confidence": 0.0,
        "temp_rate_of_rise": 0.0,
        "status": "NODE DISCONNECTED",
        "detected_patterns": ["No Hardware Telemetry"],
        "camera_detected": False,
        "relays": {
            "sprinkler": False,
            "exhaust_fan": False
        }
    }
}

VALID_MODES = {"NORMAL", "FAKE_ALARM", "REAL_ALARM"}
simulation_state = {"active_mode": "NORMAL"}

# Active main navigation context: "fire", "flood", "pollution", "industry"
current_active_hazard = "fire"
camera_fire_confirmed = False

# ----------------- OPENCV DUAL-SPACE FLICKER FIRE DETECTOR -----------------
def color_mask(frame):
    """Pixels matching fire spectrum in both HSV and YCrCb colour spaces."""
    blur = cv2.GaussianBlur(frame, (7, 7), 0)
    hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
    m_hsv = cv2.inRange(hsv, (0, 120, 180), (35, 255, 255))

    y, cr, cb = [c.astype(np.int16) for c in cv2.split(cv2.cvtColor(blur, cv2.COLOR_BGR2YCrCb))]
    rule = (
        (y > cb) & (cr > cb)
        & (y > y.mean()) & (cr > cr.mean()) & (cb < cb.mean())
        & (np.abs(cb - cr) > 40)
    )
    m_ycc = rule.astype(np.uint8) * 255
    mask = cv2.bitwise_and(m_hsv, m_ycc)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    return mask

def classical_detect(frame, mask, motion, min_area_frac=0.0003):
    """Returns bounding boxes passing color, size, motion flicker, and hull tests."""
    h, w = frame.shape[:2]
    min_area = min_area_frac * h * w
    boxes = []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, bw, bh = cv2.boundingRect(c)

        # Flame Flicker Check
        roi_motion = motion[y:y + bh, x:x + bw]
        if np.count_nonzero(roi_motion) / float(bw * bh) < 0.04:
            continue

        # Flame Shape Irregularity Check
        hull_area = cv2.contourArea(cv2.convexHull(c))
        if hull_area > 0 and area / hull_area > 0.93:
            continue

        boxes.append((x, y, x + bw, y + bh))
    return boxes

def generate_camera_frames():
    global camera_fire_confirmed
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return

    bg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=25, detectShadows=False)
    history = deque(maxlen=10)

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.resize(frame, (640, 480))

        # Check main panel mode
        if current_active_hazard == "fire":
            # Fire mode -> Full Optical Feature Detection Active
            motion = bg.apply(frame)
            motion = cv2.dilate(motion, None, iterations=2)
            boxes = classical_detect(frame, color_mask(frame), motion)
            history.append(bool(boxes))
            confirmed = sum(history) >= 5
            camera_fire_confirmed = confirmed

            if confirmed:
                for (x1, y1, x2, y2) in boxes:
                    # Mark detected fire on square
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(frame, "FIRE HAZARD", (x1, max(y1 - 8, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.putText(frame, "OPTICAL ALERT: FIRE DETECTED", (15, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                cv2.putText(frame, "MONITORING // NO OPTICAL FLAME", (15, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
        else:
            # Flood, Pollution, Industry -> Clean Standard Surveillance Camera
            camera_fire_confirmed = False
            history.clear()
            cv2.putText(frame, f"SURVEILLANCE MODE: {current_active_hazard.upper()} (OPTICAL ONLY)", (15, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap.release()

@app.get("/api/camera/stream")
def get_camera_stream():
    return StreamingResponse(
        generate_camera_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/api/camera/context")
def set_camera_context(payload: dict = Body(...)):
    """Receives active panel tab from frontend: fire, flood, pollution, industry."""
    global current_active_hazard
    current_active_hazard = payload.get("hazard", "fire").lower()
    return {"status": "ok", "active_context": current_active_hazard}

# ----------------- TELEMETRY INGESTION & FUSION -----------------
@app.get("/")
def root():
    return {"system": "AegisNet 2.0", "node": "Node 01"}

@app.get("/api/simulation/mode")
def get_simulation_mode():
    return simulation_state

@app.post("/api/simulation/mode")
def set_simulation_mode(payload: dict = Body(...)):
    mode = payload.get("mode", "NORMAL")
    if mode not in VALID_MODES:
        return {"status": "error", "message": f"Invalid mode: {mode}"}
    simulation_state["active_mode"] = mode
    return simulation_state

@app.post("/api/telemetry")
def receive_telemetry(data: TelemetryData):
    global latest_reading
    node1_engine.update(data.temp, data.smoke)
    ror = node1_engine.calculate_ror()

    # Real ML Inference
    ml_out = ml_classifier.predict_risk(
        humidity=data.humidity,
        temp=data.temp,
        sensor_reading=data.smoke
    )

    threat_conf = ml_out["confidence"]

    # Multi-Modal Fusion: Camera confirmation boosts confidence and triggers alert
    if camera_fire_confirmed:
        threat_conf = max(threat_conf, 85.0)

    is_danger = threat_conf >= 70.0
    status = "CRITICAL FIRE ALERT" if is_danger else ("ELEVATED RISK" if threat_conf >= 40.0 else "NOMINAL (SAFE)")

    pattern = []
    if ml_out["is_fire"]:
        pattern.append("XGBoost Confirmed Threat")
    if ror > 0.6:
        pattern.append("Thermal RoR Rise")
    if camera_fire_confirmed:
        pattern.append("Optical Flame Confirmed")
    if not pattern:
        pattern.append("Ambient Background")

    latest_reading = {
        "node_id": data.node_id,
        "smoke": data.smoke,
        "co": data.co,
        "flame": data.flame,
        "temp": data.temp,
        "humidity": data.humidity,
        "last_updated": time.time(),
        "is_online": True,
        "analysis": {
            "threat_confidence": threat_conf,
            "temp_rate_of_rise": ror,
            "status": status,
            "detected_patterns": pattern,
            "camera_detected": camera_fire_confirmed,
            "relays": {
                "sprinkler": threat_conf >= 70.0,
                "exhaust_fan": threat_conf >= 40.0 or data.smoke > 1000
            }
        }
    }
    return latest_reading

@app.get("/api/dashboard/live")
def get_live():
    if time.time() - latest_reading.get("last_updated", 0) > 4.0:
        latest_reading["is_online"] = False
        latest_reading["analysis"]["status"] = "NODE OFFLINE (NO SIGNAL)"
    else:
        latest_reading["is_online"] = True
    
    # Keep camera flag synced even during idle polling
    latest_reading["analysis"]["camera_detected"] = camera_fire_confirmed
    return latest_reading

@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    path = os.path.join(BASE_DIR, "dashboard.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()