import os
import time
import requests
import firebase_admin
from firebase_admin import credentials, db

CRED_PATH = os.path.join(os.path.dirname(__file__), "..", "serviceAccountKey.json")
DATABASE_URL = "https://sih26-538ab-default-rtdb.firebaseio.com/"
BACKEND_API_URL = "http://127.0.0.1:8000/api/dashboard/live"

def init_firebase():
    if not os.path.exists(CRED_PATH):
        print(f"[Firebase Error] '{CRED_PATH}' nahi mili. 'serviceAccountKey.json' ko SIH26 root folder me rakhein.")
        return False

    if not firebase_admin._apps:
        cred = credentials.Certificate(CRED_PATH)
        firebase_admin.initialize_app(cred, {
            'databaseURL': DATABASE_URL
        })
        print("[Firebase] Connected to Cloud Realtime Database.")
    return True

def start_sync():
    if not init_firebase():
        return

    live_ref = db.reference("aegisnet/live_telemetry")
    incident_ref = db.reference("aegisnet/incidents")

    print("[Firebase Sync] Live sync worker running...")

    while True:
        try:
            res = requests.get(BACKEND_API_URL, timeout=1.5)
            if res.status_code == 200:
                data = res.json()
                data["cloud_synced_at"] = int(time.time())

                # Live Node Update
                live_ref.set(data)

                threat = data.get("analysis", {}).get("threat_confidence", 0.0)
                status = data.get("analysis", {}).get("status", "NORMAL")

                if threat >= 65.0 or "FIRE" in status:
                    incident_ref.push({
                        "timestamp": data["cloud_synced_at"],
                        "node_id": data.get("node_id", "Node 01"),
                        "threat_confidence": threat,
                        "status": status,
                        "smoke": data.get("smoke"),
                        "temp": data.get("temp")
                    })
                    print(f"[ALERT LOGGED] Threat: {threat}% -> Synced to Firebase")

                print(f"[Firebase Synced] Threat: {threat}% | Temp: {data.get('temp')}C")
        except requests.exceptions.ConnectionError:
            print("[Waiting] FastAPI server offline hai.")
        except Exception as e:
            print(f"[Sync Error] {e}")

        time.sleep(1.5)

if __name__ == "__main__":
    start_sync()
    
#   python ingestion/firebase_sync.py