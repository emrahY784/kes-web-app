import numpy as np

class KESCalculator:
    def __init__(self, alpha=0.5, beta=0.5, gamma=0.5, lambd=0.5,
                 geometric=False, use_min=False):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.lambd = lambd
        self.geometric = geometric
        self.use_min = use_min

    def calculate_v_ic(self, gini, otomasyon, evcillestirme, bilinc):
        P = self.alpha * gini + self.beta * otomasyon
        D = self.gamma * evcillestirme + self.lambd * bilinc
        V_ic_raw = P - D
        V_ic_score = (V_ic_raw + 100) / 2
        return np.clip(V_ic_score, 0, 100)

    def calculate_kes(self, v_ic_score, v_dis):
        if self.use_min:
            return np.minimum(v_ic_score, v_dis)
        elif self.geometric:
            return v_ic_score * np.sqrt(v_dis) / 10
        else:
            return (v_ic_score * v_dis) / 100
