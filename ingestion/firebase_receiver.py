import time
import requests

FIREBASE_URL = "https://sensor-reading-3bea0-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
LOCAL_BACKEND_URL = "http://127.0.0.1:8000/api/telemetry"

print("[AegisNet Bridge] Firebase se connect kar rahe hain...")
print(f"[AegisNet Bridge] Target Endpoint: {FIREBASE_URL}")

last_hash = None

def parse_firebase_payload(data):
    if not isinstance(data, dict):
        return None

    esp = data.get("ESP32", {})
    if not esp:
        return None

    # Exact key extraction from your Firebase tree
    temp = esp.get("temperature", 28.0)
    hum = esp.get("humidity", 65.0)

    mq2 = esp.get("MQ2", {})
    smoke_analog = (mq2.get("analog", 0.0))/1
    smoke_digital = mq2.get("digital", 0)

    mq135 = esp.get("MQ135", {})
    co_analog = mq135.get("analog", 400.0)

    return {
        "node_id": "Node 01",
        "smoke": float(smoke_analog),
        "co": float(co_analog),
        "flame": int(smoke_digital),
        "temp": float(temp),
        "humidity": float(hum)
    }

while True:
    try:
        res = requests.get(FIREBASE_URL, timeout=2.5)
        if res.status_code == 200:
            raw_json = res.json()
            if raw_json is not None:
                payload = parse_firebase_payload(raw_json)
                if payload:
                    current_hash = (payload["smoke"], payload["temp"], payload["humidity"], payload["flame"], payload["co"])

                    if current_hash != last_hash:
                        last_hash = current_hash
                        # Local FastAPI backend ko send karega (ML Model + Dashboard update)
                        backend_res = requests.post(LOCAL_BACKEND_URL, json=payload, timeout=1.5)
                        if backend_res.status_code == 200:
                            eval_data = backend_res.json().get("analysis", {})
                            status = eval_data.get("status", "NOMINAL")
                            conf = eval_data.get("threat_confidence", 0.0)
                            print(f"[{status} | Threat: {conf}%] MQ2: {payload['smoke']} | Temp: {payload['temp']}°C | Hum: {payload['humidity']}% | MQ135: {payload['co']}")
                        else:
                            print(f"[Backend Error] Code: {backend_res.status_code}")
            else:
                print("[Waiting] Firebase database khali hai...")
        else:
            print(f"[Firebase Error] HTTP {res.status_code}")

    except requests.exceptions.ConnectionError as e:
        if "8000" in str(e):
            print("[Backend Offline] Terminal 1 me backend uvicorn nahi chal raha hai!")
        else:
            print("[Network Delay] Reconnecting...")
    except Exception as e:
        print(f"[Sync Error] {e}")

    time.sleep(1)