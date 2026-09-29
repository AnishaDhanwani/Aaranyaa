import time
import requests

FIREBASE_GET_URL = "https://sih26-538ab-default-rtdb.firebaseio.com/aegisnet/sensor_stream.json"
LOCAL_BACKEND_URL = "http://127.0.0.1:8000/api/telemetry"

print("[AegisNet] Listening to Cloud Firebase for friend's sensor readings...")

while True:
    try:
        # Firebase se dost ka live data fetch karo
        res = requests.get(FIREBASE_GET_URL, timeout=2)
        if res.status_code == 200 and res.json():
            data = res.json()
            
            # Local backend ko bhejo jahan XGBoost model chal raha hai
            payload = {
                "node_id": "Node 01",
                "smoke": data.get("sensor_reading", 500.0),
                "co": 400.0,
                "flame": data.get("smoke_detect", 1),
                "temp": data.get("temp", 28.0),
                "humidity": data.get("humidity", 70.0)
            }
            
            r = requests.post(LOCAL_BACKEND_URL, json=payload, timeout=1)
            analysis = r.json().get("analysis", {})
            print(f"[Model Evaluated] Threat: {analysis.get('threat_confidence')}% | Status: {analysis.get('status')}")

    except Exception as e:
        print("Sync wait...", e)

    time.sleep(1)