import numpy as np

class FeatureExtractor:
    """Modul untuk ekstraksi fitur dan pemrosesan awal (preprocessing) dari ketikan."""
    
    CLEAN_THRESHOLD = 0.25

    def ensure_vectors(self, data: dict) -> dict:
        """Memastikan data memiliki vektor D2D, U2U, dan Trigraph."""
        d, f = data.get('dwell', []), data.get('flight', [])
        
        # Calculate D2D and U2U if missing
        if not data.get('d2d'): 
            data['d2d'] = [float(d[i] + f[i]) for i in range(min(len(d), len(f)))]
        if not data.get('u2u'): 
            data['u2u'] = [float(f[i] + d[i+1]) for i in range(min(len(d)-1, len(f)))]
            
        # Calculate Trigraph (n to n+2) if missing - based on D2D sum
        if not data.get('trigraph'):
            d2d = data.get('d2d', [])
            if len(d2d) >= 2:
                data['trigraph'] = [float(d2d[i] + d2d[i+1]) for i in range(len(d2d)-1)]
            else:
                data['trigraph'] = []
                
        return data

    def extract(self, data: dict, history=None) -> list:
        """Ekstraksi vektor fitur 16-dimensi (Refined) menggunakan operasi vektor NumPy."""
        data = self.ensure_vectors(data)
        features = []
        
        # Pembersihan Data Adaptif (Tukey's IQR)
        limit = self.CLEAN_THRESHOLD
        if history:
            all_d = [d for h in history for d in h.get('dwell', [])]
            if len(all_d) >= 4:
                Q1, Q3 = np.percentile(all_d, 25), np.percentile(all_d, 75)
                limit = float(max(0.25, Q3 + 1.5 * (Q3 - Q1)))
        
        # 1. Base Features (Dwell, Flight, D2D, U2U) - 12 features
        for key in ['dwell', 'flight', 'd2d', 'u2u']:
            arr = np.array(data.get(key, []), dtype=float)
            clean = arr[arr < limit]
            
            if len(clean) >= 2:
                features.extend([float(np.median(clean)), float(np.std(clean, ddof=1))])
                # Rasio Ritme
                r = clean[:-1] / (clean[1:] + 0.001) if len(clean) >= 3 else [1.0]
                features.append(float(np.median(r)))
            else:
                features.extend([float(min(np.median(arr), 0.20)) if len(arr)>0 else 0.05, 0.01, 1.0])

        # 2. Tri-graph Features (Baru) - 2 features
        tri = np.array(data.get('trigraph', []), dtype=float)
        if len(tri) >= 2:
            features.extend([float(np.median(tri)), float(np.std(tri, ddof=1))])
        else:
            features.extend([0.4, 0.05])

        # 3. Jitter Feature (Baru) - 1 feature
        features.append(float(data.get('jitter', 0.0)))

        # 4. Speed (CPM) - 1 feature
        features.append(float(data.get('speed', 0.0)) / 600.0) # Normalize
                
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
