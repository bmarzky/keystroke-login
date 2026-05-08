import numpy as np
from src.engine.extractors.features import FeatureExtractor

class StatisticalGates:
    """Modul untuk perhitungan gerbang statistik seperti batas outlier dan Mahalanobis."""
    
    MAX_MAHAL_DIST = 15.0

    def __init__(self, feature_extractor: FeatureExtractor):
        self.extractor = feature_extractor
        self.n_features = 24

    def get_clean_limit(self, history: list) -> float:
        """Menggunakan Tukey's IQR Method (Statistik Robust) untuk Filter Outlier Dwell."""
        if not history: return self.extractor.CLEAN_THRESHOLD
        all_d = [d for h in history for d in h.get('dwell', [])]
        if len(all_d) < 4: return self.extractor.CLEAN_THRESHOLD
        
        Q1, Q3 = np.percentile(all_d, 25), np.percentile(all_d, 75)
        limit = Q3 + 1.5 * (Q3 - Q1)
        return float(max(0.25, limit))

    def get_flight_clean_limit(self, history: list) -> float:
        """Menggunakan Tukey's IQR untuk flight time yang biasanya lebih panjang."""
        if not history: return 0.80
        all_f = [f for h in history for f in h.get('flight', [])]
        if len(all_f) < 4: return 0.80
        
        Q1, Q3 = np.percentile(all_f, 25), np.percentile(all_f, 75)
        limit = Q3 + 1.5 * (Q3 - Q1)
        return float(max(0.80, limit))

    def calculate_current_mahalanobis(self, inp: dict, history: list) -> float:
        """Menggunakan Tikhonov Regularization & Pseudo-Inverse (pinv) untuk jaminan Anti-Crash."""
        if len(history) < 5: return None
        try:
            X = np.array([self.extractor.extract(h, history) for h in history])
            mu = np.mean(X, axis=0)
            
            # Tikhonov Regularization (Shrinkage covariance) - 0.01 mencegah ledakan nilai pada eigen-vector kosong
            cov = np.cov(X, rowvar=False) + np.eye(self.n_features) * 0.01
            
            # Pseudo-Inverse menanggulangi Singular Matrix
            pinv_cov = np.linalg.pinv(cov)
            
            diff = np.array(self.extractor.extract(inp, history)) - mu
            return float(np.sqrt(max(0, diff.T @ pinv_cov @ diff)))
        except: return None

    def get_mahal_history(self, history: list) -> list:
        """Menghitung riwayat jarak Mahalanobis menggunakan pendekatan shrinkage."""
        if len(history) < 5: return []
        try:
            X = np.array([self.extractor.extract(h, history) for h in history])
            mu = np.mean(X, axis=0)
            cov = np.cov(X, rowvar=False) + np.eye(self.n_features) * 0.01
            pinv_cov = np.linalg.pinv(cov)
            return [float(np.sqrt(max(0, (r-mu).T @ pinv_cov @ (r-mu)))) for r in X]
        except: return []

    def calculate_speed_metrics(self, inp: dict, history: list) -> tuple:
        in_v, in_fv = np.array(inp['dwell']), np.array(inp['flight'])
        c_limit = self.get_clean_limit(history)
        v_clean = in_v[in_v < c_limit]
        fv_clean = in_fv[in_fv < c_limit]
        
        in_speed = float(60.0/(np.mean(v_clean)+np.mean(fv_clean))) if len(v_clean)>=3 else float(inp.get('speed', 0))
        avg_s = float(np.median([h.get('speed', 0) for h in history]))
        s_dev = abs(in_speed - avg_s) / max(avg_s, 1.0)
        
        return in_speed, s_dev

    def calculate_gates(self, n: int, history: list, mahal_dists: list) -> dict:
        h0_d = np.array(history[0].get('dwell', [0.1]), dtype=float)
        cv = float(np.clip(np.std(h0_d)/max(np.mean(h0_d),0.001), 0.1, 0.6))
        g = {"s": 0.2 + cv*0.5, "m": 1.5 + cv*6.0, "t": 0.65 - cv*0.1}

        if n > 1:
            speeds = [float(h.get('speed', 0)) for h in history]
            g["s"] = float(max(0.35, (3.0 * np.std(speeds) / max(np.mean(speeds), 1.0))))
            if mahal_dists and len(mahal_dists) >= 3:
                m_avg, m_std = float(np.mean(mahal_dists)), float(np.std(mahal_dists))
                progress = np.clip((n - 5) / 45.0, 0.0, 1.0)
                multiplier = 2.8 - (progress * 1.0)
                buffer = 4.0 - (progress * 2.5)
                g["m"] = m_avg + multiplier * m_std + buffer
                base_t = 0.65 if n >= 30 else 0.62
                g["t"] = float(min(base_t, base_t - 0.05 + (n-5)*0.01) + (max(0.0, 1.0 - m_avg/3.0)*0.08))

        alpha = float(1.0 if n >= 5 else min(1.0, (n-1)/4.0))
        s_final = g["s"] 
        m_final = (1-alpha)*(1.5 + cv*6.0) + alpha*g["m"]
        t_final = (1-alpha)*(0.68 - cv*0.1) + alpha*g["t"]

        limits = [(0.85, 12.0, 0.72), (0.75, 10.0, 0.75), (0.50, 4.5, 0.78), (0.40, 3.2, 0.82)]
        s_h, m_l, t_h = limits[min(3, 0 if n<5 else 1 if n<20 else 2 if n<100 else 3)]
        
        s_min = 0.75 if n < 5 else 0.60 if n < 20 else 0.35
        s_res = float(np.clip(s_final, s_min, s_h))
        m_res = float(np.clip(m_final, m_l, self.MAX_MAHAL_DIST))
        
        t_min = 0.75 if n > 100 else 0.72 if n > 50 else 0.70 if n > 20 else 0.66
        t_res = float(np.clip(t_final, t_min, t_h))

        if len(h0_d) < 7:
            t_res = float(np.clip(t_res + (7-len(h0_d))*0.02, 0.72, 0.90))
            s_res, m_res = s_res*1.20, m_res*0.85

        return {"speed_gate": round(s_res,4), "mahal_gate": round(m_res,4), 
                "threshold": round(t_res,4), "phase": f"Phase {n}" if n<5 else f"Mahalanobis Mode (n={n})"}
