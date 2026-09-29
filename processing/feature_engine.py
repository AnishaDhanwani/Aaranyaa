import numpy as np
from collections import deque

class SingleNodeDecisionEngine:
    def __init__(self, window_size=10):
        self.temp_history = deque(maxlen=window_size)
        self.smoke_history = deque(maxlen=window_size)

    def update(self, temp: float, smoke: float):
        self.temp_history.append(temp)
        self.smoke_history.append(smoke)

    def calculate_ror(self) -> float:
        if len(self.temp_history) < 3:
            return 0.0
        x = np.arange(len(self.temp_history))
        y = np.array(self.temp_history)
        slope, _ = np.polyfit(x, y, 1)
        return round(float(slope), 2)

node1_engine = SingleNodeDecisionEngine()