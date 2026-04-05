import numpy as np

class KESCalculator:
    """
    KES (Kutup Eğilim Skoru) Hesaplayıcı
    
    Formüller:
    --------
    V_iç = α*G + β*O - (γ*E + λ*B)
    V_iç_score = (V_iç + 100) / 2  (0-100 arasına normalize)
    
    KES (varsayılan) = (V_iç_score * V_dış) / 100
    KES (geometrik) = V_iç_score * sqrt(V_dış) / 10
    KES (min) = min(V_iç_score, V_dış)
    
    Parametreler:
    -----------
    α (alpha) : Gini katsayısının ağırlığı (patlayıcı kuvvet)
    β (beta)  : Otomasyonun ağırlığı (patlayıcı kuvvet)
    γ (gamma) : Evcilleştirme kapasitesinin ağırlığı (dengeleyici)
    λ (lambd) : Toplumsal bilincin ağırlığı (dengeleyici)
    
    Değişkenler:
    -----------
    G (gini)          : Gelir eşitsizliği (0-100)
    O (otomasyon)     : Robot yoğunluğu / otomasyon seviyesi (0-100)
    E (evcillestirme) : Devletin sermayeyi kontrol kapasitesi (0-100)
    B (bilinc)        : Toplumsal bilinç ve örgütlülük (0-100)
    V_dış (dis_direnc): Dış direnç / emperyalizme karşı koyma kapasitesi (0-100)
    
    Yorum:
    ------
    KES < 33  : Sermayeci Kutup (kapitalist eğilim baskın)
    KES 34-66 : Karma / Geçiş dönemi
    KES > 66  : Kamucu Kutup (sosyalist eğilim baskın)
    """
    
    def __init__(self, alpha=0.5, beta=0.5, gamma=0.5, lambd=0.5,
                 geometric=False, use_min=False):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.lambd = lambd
        self.geometric = geometric
        self.use_min = use_min

    def calculate_v_ic(self, gini, otomasyon, evcillestirme, bilinc):
        """
        İç çelişki vektörü V_iç'yi hesaplar.
        Pozitif değerler patlayıcı kuvvetlerin (eşitsizlik+otomasyon) 
        dengeleyici kuvvetlerden (evcilleştirme+bilinç) daha güçlü olduğunu gösterir.
        """
        P = self.alpha * gini + self.beta * otomasyon
        D = self.gamma * evcillestirme + self.lambd * bilinc
        V_ic_raw = P - D
        # -100 ile +100 arasındaki değeri 0-100 arasına normalize et
        V_ic_score = (V_ic_raw + 100) / 2
        return np.clip(V_ic_score, 0, 100)

    def calculate_kes(self, v_ic_score, v_dis):
        """
        KES (Kutup Eğilim Skoru) hesaplar.
        Yüksek değer kamucu (sosyalist) kutba yakınlığı, düşük değer sermayeci kutba yakınlığı gösterir.
        """
        if self.use_min:
            # Her iki değerin minimumu - en kötümser senaryo
            return np.minimum(v_ic_score, v_dis)
        elif self.geometric:
            # Geometrik ortalama benzeri - dış direncin etkisini azaltır
            return v_ic_score * np.sqrt(v_dis) / 10
        else:
            # Varsayılan: aritmetik çarpım (0-100 arası)
            return (v_ic_score * v_dis) / 100
