import os
import joblib
import pandas as pd
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), "smoke_detector_xgb.joblib")

class XGBFireClassifier:
    def __init__(self):
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                print("[ML Engine] XGBoost model loaded successfully.")
            except Exception as e:
                self.model = None
                print(f"[ML Engine Error] Failed to load joblib: {e}")
        else:
            self.model = None
            print(f"[ML Engine Warning] File not found at {MODEL_PATH}")

    def predict_risk(self, humidity: float, temp: float, sensor_reading: float) -> dict:
        """
        NOTE: The model was trained to PREDICT Smoke_Detect (fire / not fire) from
        Humidity, Temperature, and Sensor_Reading. Smoke_Detect is the label, not
        an input feature — it must never be passed into the DataFrame below, or
        XGBoost will raise a feature-name mismatch and this will silently fall
        back to the heuristic in the except block.
        """
        if self.model is None:
            conf = 88.0 if sensor_reading > 1100 else 4.0
            return {"confidence": conf, "is_fire": conf >= 65.0}

        df = pd.DataFrame([{
            "Humidity": humidity,
            "Temperature": temp,
            "Sensor_Reading": sensor_reading
        }])

        try:
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(df)[0]
                confidence = round(float(proba[1] * 100), 1)  # P(Smoke_Detect == 1)
            else:
                pred = self.model.predict(df)[0]
                confidence = 96.0 if pred == 1 else 4.0
        except Exception as e:
            print(f"[ML Inference Error] {e}")
            confidence = 85.0 if sensor_reading > 1100 else 6.0

        return {
            "confidence": confidence,
            "is_fire": confidence >= 65.0
        }

ml_classifier = XGBFireClassifier()