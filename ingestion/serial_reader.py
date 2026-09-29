import serial
import serial.tools.list_ports
import time
import requests
import re

API_URL = "http://127.0.0.1:8000/api/telemetry"
BAUD = 115200

def get_port():
    ports = [p.device for p in serial.tools.list_ports.comports() if "COM" in p.device]
    return ports[0] if ports else None

def parse_line(line: str):
    pattern = r"Humidity:([\d\.]+),Temperature:([\d\.]+),Smoke detect:(\d+),Sensor reading:(\d+)"
    match = re.search(pattern, line, re.IGNORECASE)
    if match:
        return {
            "node_id": "Node 01",
            "smoke": float(match.group(4)),      # Sensor_Reading
            "co": 400.0,
            "flame": int(match.group(3)),         # Smoke_Detect
            "temp": float(match.group(2)),        # Temperature
            "humidity": float(match.group(1))     # Humidity
        }
    return None

def main():
    port = get_port()
    if not port:
        print("[Error] No ESP32 USB device found. Reconnect cable and try again.")
        return

    print(f"[AegisNet] Connecting directly via USB to {port}...")

    try:
        ser = serial.Serial(port, BAUD, timeout=1)
        time.sleep(2)
        print(f"[AegisNet] USB Link Active on {port}. Forwarding data to ML model...")

        while True:
            raw = ser.readline().decode("utf-8", errors="ignore").strip()
            if not raw:
                continue

            payload = parse_line(raw)
            if payload:
                try:
                    res = requests.post(API_URL, json=payload, timeout=0.5)
                    data = res.json()
                    analysis = data.get("analysis", {})
                    status = analysis.get("status", "NOMINAL")
                    conf = analysis.get("threat_confidence", 0.0)
                    print(f"[{status} | Threat: {conf}%] Sensor: {payload['smoke']} | Temp: {payload['temp']}C")
                except requests.exceptions.RequestException:
                    print("[Waiting] FastAPI server is offline.")
            else:
                print(f"[Raw Serial] {raw}")

    except serial.SerialException as e:
        print(f"[Serial Error] {e}")
    except KeyboardInterrupt:
        print("\n[Stopped]")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()