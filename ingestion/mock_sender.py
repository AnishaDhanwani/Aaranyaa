import time
import requests
import random

API_TELEMETRY = "http://127.0.0.1:8000/api/telemetry"
API_MODE = "http://127.0.0.1:8000/api/simulation/mode"

print("[AegisNet Simulator Engine] Online and polling scenario state...")

mode_duration_counter = 0
last_mode = "NORMAL"

while True:
    try:
        # Check active mode from backend
        res = requests.get(API_MODE, timeout=1)
        current_mode = res.json().get("active_mode", "NORMAL")
    except Exception:
        current_mode = "NORMAL"

    if current_mode != last_mode:
        mode_duration_counter = 0
        last_mode = current_mode
        print(f"\n[Mode Switched] -> Active Scenario: {current_mode}")

    mode_duration_counter += 1

    # Case 1: NORMAL Condition
    if current_mode == "NORMAL":
        smoke = round(random.uniform(910.0, 940.0), 2)
        co = round(random.uniform(390.0, 410.0), 2)
        flame = 1  # Safe
        temp = round(random.uniform(27.5, 29.0), 2)
        humidity = round(random.uniform(55.0, 60.0), 2)

    # Case 2: FAKE ALARM (Less than 3 intervals / < 30 sec burst, single sensor anomaly)
    elif current_mode == "FAKE_ALARM":
        if mode_duration_counter <= 2:  # 2 iterations (< 3 intervals)
            # Gas sensor transient noise / lighter puff without sustained heat or IR flame
            smoke = round(random.uniform(200.0, 280.0), 2)
            co = round(random.uniform(430.0, 460.0), 2)
            flame = 1  # No flame
            temp = round(random.uniform(28.5, 29.5), 2)  # No heat slope
            humidity = round(random.uniform(52.0, 56.0), 2)
        else:
            # Auto-recovery to normal after short spike
            smoke = round(random.uniform(880.0, 920.0), 2)
            co = round(random.uniform(395.0, 410.0), 2)
            flame = 1
            temp = round(random.uniform(28.0, 29.0), 2)
            humidity = round(random.uniform(55.0, 58.0), 2)

    # Case 3: REAL ALARM (Sustained > 3 intervals / > 30 sec, multi-sensor corroborated)
    elif current_mode == "REAL_ALARM":
        # Progressive heat buildup + drop in smoke resistance + flame trigger
        smoke = round(max(60.0, 300.0 - (mode_duration_counter * 18)), 2)
        co = round(min(900.0, 500.0 + (mode_duration_counter * 35)), 2)
        flame = 0 if mode_duration_counter >= 2 else 1
        temp = round(32.0 + (mode_duration_counter * 2.8), 2)
        humidity = round(max(25.0, 50.0 - mode_duration_counter * 2), 2)

    payload = {
        "node_id": "Node 01",
        "smoke": smoke,
        "co": co,
        "flame": flame,
        "temp": temp,
        "humidity": humidity
    }

    try:
        r = requests.post(API_TELEMETRY, json=payload, timeout=1)
        resp_data = r.json()
        analysis = resp_data.get("analysis", {})
        print(f"[{current_mode} - Iter {mode_duration_counter}] Smoke: {smoke} | Temp: {temp}C | Flame: {flame} | Conf: {analysis.get('threat_confidence')}% -> {analysis.get('status')}")
    except Exception as e:
        print(f"[Error transmitting telemetry]: {e}")

    # Telemetry sampling interval
    time.sleep(1)