import numpy as np
from src.engine.extractors.features import FeatureExtractor

class StatisticalGates:
    """Modul untuk perhitungan gerbang statistik seperti batas outlier dan Mahalanobis."""
    
    MAX_MAHAL_DIST = 15.0

    def __init__(self, feature_extractor: FeatureExtractor):
        self.extractor = feature_extractor
        self.n_features = 16

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
        """
        Optimized: Adaptive Hybrid Behavioral Gates (Production-Grade).
        Menerapkan pembobotan dinamis antara Anchor (Long-term Memory) 
        dan Rolling (Short-term Adaptation).
        """
        # 1. Hitung CV Dasar
        h0_d = np.array(history[0].get('dwell', [0.1]), dtype=float)
        anchor_cv = float(np.clip(np.std(h0_d)/max(np.mean(h0_d), 0.001), 0.1, 0.6))
        
        recent_history = history[-10:] if n > 10 else history
        all_dwells = [d for h in recent_history for d in h.get('dwell', [])]
        rolling_cv = float(np.clip(np.std(all_dwells)/max(np.mean(all_dwells), 0.001), 0.08, 0.55)) if len(all_dwells) > 5 else anchor_cv

        # 2. ADAPTIVE HYBRID WEIGHTING (Mekanisme Recovery & Trust)
        # Menghitung bobot anchor secara dinamis
        if n < 10:
            anchor_w = 0.80  # User baru: Percaya penuh pada data awal
        elif n < 50:
            anchor_w = 0.70  # User transisi
        else:
            anchor_w = 0.60  # User senior: Berikan ruang adaptasi lebih besar
            
        # Emergency Recovery: Jika Rolling CV tiba-tiba berantakan (Anomali), tarik bobot ke Anchor
        if rolling_cv > anchor_cv * 1.5:
            anchor_w = min(0.90, anchor_w + 0.20)
            
        cv = (anchor_cv * anchor_w) + (rolling_cv * (1.0 - anchor_w))

        # 3. Base Gates Calculation
        g = {
            "s": 0.2 + cv * 0.4,
            "m": 1.5 + cv * 5.0,
            "t": 0.68 - cv * 0.08
        }

        # 4. Dynamic Refinement & Stability Bonus
        stability_bonus = 0.0
        if n >= 5:
            speeds = [float(h.get('speed', 0)) for h in history]
            g["s"] = float(np.clip(3.0 * np.std(speeds) / max(np.mean(speeds), 1.0), 0.35, 0.75))
            
            if mahal_dists and len(mahal_dists) >= 3:
                m_avg, m_std = float(np.mean(mahal_dists)), float(np.std(mahal_dists))
                progress = np.clip((n - 5) / 45.0, 0.0, 1.0)
                
                multiplier = 3.0 - (progress * 1.2) 
                g["m"] = m_avg + (multiplier * m_std) + (2.0 * (1.0 - progress))
                
                stability_bonus = max(0.0, (3.0 - m_avg) * 0.025)
                base_t = 0.68 + (progress * 0.10)
                g["t"] = base_t + stability_bonus - (cv * 0.05)

        # 5. HARD CAPPING (Safety Belt)
        T_FLOOR, T_CEILING = 0.68, 0.85
        t_res = float(np.clip(g["t"], T_FLOOR, T_CEILING))
        s_res = float(np.clip(g["s"], 0.35, 0.75))
        m_res = float(np.clip(g["m"], 3.0, self.MAX_MAHAL_DIST))

        return {
            "speed_gate": round(s_res, 4), 
            "mahal_gate": round(m_res, 4), 
            "threshold": round(t_res, 4), 
            "cv_hybrid": round(cv, 4),
            "anchor_weight": round(anchor_w, 2),
            "stability_bonus": round(stability_bonus, 4),
            "phase": f"Hybrid Adaptive (n={n})"
        }



