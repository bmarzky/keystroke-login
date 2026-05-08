import numpy as np

class FeatureExtractor:
    """Modul untuk ekstraksi fitur dan pemrosesan awal (preprocessing) dari ketikan."""
    
    CLEAN_THRESHOLD = 0.25

    def ensure_vectors(self, data: dict) -> dict:
        """Memastikan data memiliki vektor D2D (Down-to-Down) dan U2U (Up-to-Up)."""
        d, f = data.get('dwell', []), data.get('flight', [])
        if not data.get('d2d'): data['d2d'] = [float(d[i] + f[i]) for i in range(min(len(d), len(f)))]
        if not data.get('u2u'): data['u2u'] = [float(f[i] + d[i+1]) for i in range(min(len(d)-1, len(f)))]
        return data

    def extract(self, data: dict, history=None) -> list:
        """Ekstraksi vektor fitur 24-dimensi menggunakan operasi vektor NumPy."""
        data = self.ensure_vectors(data)
        features = []
        
        # Pembersihan Data Adaptif (Tukey's IQR)
        limit = self.CLEAN_THRESHOLD
        if history:
            all_d = [d for h in history for d in h.get('dwell', [])]
            if len(all_d) >= 4:
                Q1, Q3 = np.percentile(all_d, 25), np.percentile(all_d, 75)
                limit = float(max(0.25, Q3 + 1.5 * (Q3 - Q1)))
        
        for key in ['dwell', 'flight', 'd2d', 'u2u']:
            arr = np.array(data.get(key, []), dtype=float)
            clean = arr[arr < limit] # Hanya ambil data yang masuk akal
            
            if len(clean) >= 2:
                features.extend([float(np.median(clean)), float(np.std(clean, ddof=1))])
                # Rasio Ritme
                r = clean[:-1] / (clean[1:] + 0.001) if len(clean) >= 3 else [1.0, 0.1]
                features.extend([float(np.median(r)), float(np.std(r, ddof=1)) if len(r)>1 else 0.1])
                # Tanda Tangan Frekuensi (FFT)
                fft = np.abs(np.fft.fft(clean)) if len(clean) >= 4 else [0, 0, 0]
                features.extend([float(fft[1]) if len(fft)>1 else 0.0, float(fft[2]) if len(fft)>2 else 0.0])
            else:
                features.extend([float(min(np.median(arr), 0.20)) if len(arr)>0 else 0.0, 0.01, 1.0, 0.1, 0.0, 0.0])
                
        return [float(f) if np.isfinite(f) else 0.0 for f in features]

    def check_structural_integrity(self, inp: dict, h0: dict) -> dict:
        """Validasi panjang ketikan dan pemulihan typo ringan menggunakan DTW."""
        in_d, in_f = np.array(inp['dwell']), np.array(inp['flight'])
        ref_d, ref_f = np.array(h0['dwell']), np.array(h0['flight'])
        
        if len(in_d) == len(ref_d):
            return {"ok": True}
            
        if abs(len(in_d) - len(ref_d)) <= 3:
            d_dist = self.dtw_distance(in_d, ref_d)
            f_dist = self.dtw_distance(in_f, ref_f)
            if d_dist < 0.05 and f_dist < 0.07:
                return {"ok": True, "typo_recovered": True}
            return {"ok": False, "reason": f"REJECT | DTW fail (d={d_dist:.3f})"}
            
        return {"ok": False, "reason": "REJECT | Length Mismatch"}

    def dtw_distance(self, s1, s2) -> float:
        """Algoritma Dynamic Time Warping."""
        n, m = len(s1), len(s2)
        if n == 0 or m == 0: return 1.0
        dtw = np.full((n + 1, m + 1), np.inf); dtw[0, 0] = 0
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                dtw[i, j] = abs(s1[i-1] - s2[j-1]) + min(dtw[i-1, j], dtw[i, j-1], dtw[i-1, j-1])
        return float(dtw[n, m] / max(n, m))
