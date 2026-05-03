import sys, json, warnings, os
import numpy as np

# Fix pathing agar bisa menemukan folder 'ml' saat dijalankan via PHP
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path: sys.path.append(root)

try:
    from ml.ai_engine import AIEngine
except ImportError:
    # Fallback jika dijalankan dari root langsung
    if os.path.exists('ml/ai_engine.py'):
        from ml.ai_engine import AIEngine
    else:
        raise

warnings.filterwarnings('ignore')

class BiometricCore:
    # --- CONFIGURATION ---
    CLEAN_THRESHOLD, DEFAULT_SPEED, MIN_SAMPLES = 0.25, 350.0, 5
    MAX_MAHAL_DIST, ANOMALY_LIMIT = 15.0, 0.25
    
    def __init__(self, n_features=24):
        self.n_features = n_features
        self.ai = AIEngine()

    def extract(self, data: dict, history=None) -> list:
        """Extracts 24-dim statistical feature vector using vectorized operations."""
        data = self._ensure_vectors(data)
        features = []
        
        # Adaptive Cleaning
        limit = self.CLEAN_THRESHOLD
        if history:
            all_d = [d for h in history for d in h.get('dwell', [])]
            if all_d: limit = max(0.25, np.median(all_d) * 2.5)
        
        for key in ['dwell', 'flight', 'd2d', 'u2u']:
            arr = np.array(data.get(key, []), dtype=float)
            clean = arr[arr < limit]
            
            if len(clean) >= 2:
                features.extend([float(np.median(clean)), float(np.std(clean, ddof=1))])
                # Rhythm Ratios
                r = clean[:-1] / (clean[1:] + 0.001) if len(clean) >= 3 else [1.0, 0.1]
                features.extend([float(np.median(r)), float(np.std(r, ddof=1)) if len(r)>1 else 0.1])
                # FFT Signature
                fft = np.abs(np.fft.fft(clean)) if len(clean) >= 4 else [0, 0, 0]
                features.extend([float(fft[1]) if len(fft)>1 else 0.0, float(fft[2]) if len(fft)>2 else 0.0])
            else:
                features.extend([float(min(np.median(arr), 0.20)) if len(arr)>0 else 0.0, 0.01, 1.0, 0.1, 0.0, 0.0])
                
        return [float(f) if np.isfinite(f) else 0.0 for f in features]

    def _ensure_vectors(self, data: dict) -> dict:
        d, f = data.get('dwell', []), data.get('flight', [])
        if not data.get('d2d'): data['d2d'] = [float(d[i] + f[i]) for i in range(min(len(d), len(f)))]
        if not data.get('u2u'): data['u2u'] = [float(f[i] + d[i+1]) for i in range(min(len(d)-1, len(f)))]
        return data

    def _dtw_distance(self, s1, s2) -> float:
        n, m = len(s1), len(s2)
        if n == 0 or m == 0: return 1.0
        dtw = np.full((n + 1, m + 1), np.inf); dtw[0, 0] = 0
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                dtw[i, j] = abs(s1[i-1] - s2[j-1]) + min(dtw[i-1, j], dtw[i, j-1], dtw[i-1, j-1])
        return float(dtw[n, m] / max(n, m))

    def _calculate_gates(self, n, history, mahal_dists):
        # 1. Base Logic (Intra-Sample Heuristic)
        h0_d = np.array(history[0].get('dwell', [0.1]), dtype=float)
        cv = float(np.clip(np.std(h0_d)/max(np.mean(h0_d),0.001), 0.1, 0.6))
        g = {"s": 0.2 + cv*0.5, "m": 1.5 + cv*6.0, "t": 0.65 - cv*0.1}

        # 2. Adaptive Logic (History Driven)
        if n > 1:
            speeds = [float(h.get('speed', 0)) for h in history]
            g["s"] = float(max(0.35, (3.0 * np.std(speeds) / max(np.mean(speeds), 1.0))))
            if mahal_dists and len(mahal_dists) >= 3:
                m_avg, m_std = float(np.mean(mahal_dists)), float(np.std(mahal_dists))
                # SMART GUARD: Keseimbangan antara keamanan dan kenyamanan (n >= 20)
                multiplier = 1.8 if n >= 20 else 2.8
                buffer = 1.5 if n >= 20 else 4.0
                g["m"] = m_avg + multiplier * m_std + buffer
                # Hardening: Base threshold disesuaikan agar lebih seimbang (0.68)
                base_t = 0.68 if n >= 20 else 0.65
                g["t"] = float(min(base_t, base_t - 0.05 + (n-5)*0.01) + (max(0.0, 1.0 - m_avg/3.0)*0.08))

        # 3. Blending & Hardening
        alpha = float(1.0 if n >= 5 else min(1.0, (n-1)/4.0))
        s_final = (1-alpha)*g["s"] + alpha*g["s"] 
        m_final = (1-alpha)*(1.5 + cv*6.0) + alpha*g["m"]
        t_final = (1-alpha)*(0.68 - cv*0.1) + alpha*g["t"]

        # Phase Hardening Boundaries (Tighter)
        limits = [(0.75, 10.0, 0.74), (0.65, 8.0, 0.78), (0.45, 3.5, 0.82), (0.40, 3.5, 0.80)]
        s_h, m_l, t_h = limits[min(3, 0 if n<3 else 1 if n<5 else 2 if n<10 else 3)]
        
        s_res = float(np.clip(s_final, 0.40, s_h))
        m_res = float(np.clip(m_final, m_l, 12.0))
        t_min = 0.68 if n > 50 else 0.65
        t_res = float(np.clip(t_final, t_min, t_h))

        # Short Password Penalty
        if len(h0_d) < 7:
            t_res = float(np.clip(t_res + (7-len(h0_d))*0.015, 0.70, 0.88))
            s_res, m_res = s_res*1.15, m_res*0.90

        phase = f"Enrollment Phase (n={n})" if n < 5 else f"Mahalanobis Mode (n={n})"
        return {"speed_gate": round(s_res,4), "mahal_gate": round(m_res,4), 
                "threshold": round(t_res,4), "phase": phase}

    def _get_response_template(self, n=0):
        return {"status": False, "score": 0.0, "threshold": 0.70, "reason": "Unknown", "method": "Titanium Fusion + OCSVM",
                "n_samples": n, "speed_dev": 0.0, "mahal_dist": None, "ai_score": None, "ai_status": "Standby (Collecting Data)",
                "should_update_history": False, "adaptive_gates": {}, "components": {}, "weights": {}}

    def analyze(self, input_data, history, user_id=None):
        """Analyzes input keystrokes against user history using Titanium Fusion logic."""
        try:
            input_raw = input_data
            if not history: return {**self._get_response_template(), "reason": "Enroll dulu"}
            
            res = self._get_response_template(len(history))
            inp = self._ensure_vectors(input_raw)
            in_d, in_f = np.array(inp.get('dwell', []), dtype=float), np.array(inp.get('flight', []), dtype=float)
            
            # 1. Structural & DTW Typo Recovery
            h0 = history[0]
            d_dist, f_dist, is_typo = None, None, False
            if len(in_d) != len(h0['dwell']):
                if abs(len(in_d) - len(h0['dwell'])) <= 3:
                    d_dist, f_dist = self._dtw_distance(in_d, h0['dwell']), self._dtw_distance(in_f, h0['flight'])
                    if d_dist < 0.05 and f_dist < 0.07: is_typo = True
                    else: return {**res, "reason": f"REJECT | DTW fail (d={d_dist:.3f})"}
                else: return {**res, "reason": "REJECT | Length Mismatch"}

            # 2. Feature Extraction & Speed Check
            c_limit = self.CLEAN_THRESHOLD
            if len(history)>1: c_limit = max(0.25, np.median([d for h in history for d in h.get('dwell',[])]) * 2.5)
            
            in_v = in_d[in_d < c_limit]; in_fv = in_f[in_f < c_limit]
            in_speed = float(60.0/(np.mean(in_v)+np.mean(in_fv))) if len(in_v)>=3 else float(inp.get('speed', 0))
            
            # Mahalanobis Internal History Calculation
            hist_m = []
            if len(history) >= 5:
                try:
                    X_h = np.array([self.extract(h, history) for h in history])
                    mu_h, cov_h = np.mean(X_h, 0), np.cov(X_h, rowvar=False) + np.eye(self.n_features)*1e-3
                    cinv_h = np.linalg.inv(cov_h)
                    for r in X_h: hist_m.append(float(np.sqrt(max(0, (r-mu_h).T @ cinv_h @ (r-mu_h)))))
                except: pass

            gates = self._calculate_gates(len(history), history, hist_m)
            
            # Tentukan Nama Method (Tampilkan OCSVM jika aktif)
            user_id = user_id if user_id else input_raw.get('user_id', 'unknown')
            method_name = gates["phase"]
            if os.path.exists(self.ai._get_model_path(user_id)):
                method_name = "Mahalanobis + OCSVM"
                
            res.update({"threshold": gates["threshold"], "adaptive_gates": gates, "method": method_name})
            
            avg_s = float(np.median([h.get('speed', 0) for h in history]))
            s_dev = abs(in_speed - avg_s) / max(avg_s, 1.0)
            res["speed_dev"] = round(s_dev, 4)
            if s_dev > gates["speed_gate"]: return {**res, "reason": f"Gate: Speed Anomali ({s_dev:.1%})"}

            # 3. Titanium Fusion Scoring
            n_h = len(history)
            w = [0.3, 0.4, 0.15, 0.15, 0, 0] if n_h<5 else [0.35, 0.25, 0.15, 0.15, 0.05, 0.05] if n_h<10 else [0.3, 0.15, 0.15, 0.15, 0.15, 0.1]
            res["weights"] = {k: v for k, v in zip(["w_rhythm", "w_corr", "w_speed", "w_flow", "w_ratio", "w_stability"], w)}
            
            # Profile & Scoring Loop
            baselines = history[:3] + history[-7:] if n_h > 10 else history
            all_s, comp_logs, max_out = [], [], 0
            
            for b in baselines:
                b = self._ensure_vectors(b); s_r, s_c, out = [], [], 0
                for k in ['dwell', 'flight', 'd2d', 'u2u']:
                    v1, v2 = np.array(inp.get(k,[]), dtype=float), np.array(b.get(k,[]), dtype=float)
                    ml = min(len(v1), len(v2)); v1, v2 = v1[:ml], v2[:ml]
                    mask = (v1 > c_limit); out += int(np.sum(mask))
                    v1c, v2c = v1[~mask], v2[~mask]
                    if len(v1c) < 3: v1c, v2c = v1, v2
                    n1, n2 = v1c/max(sum(v1c),0.001), v2c/max(sum(v2c),0.001)
                    # Longgarkan toleransi ritme (0.18 -> 0.25)
                    s_r.append(float(max(0, 1.0 - (np.sqrt(np.sum((n1-n2)**2))/0.25))))
                    c = float(np.corrcoef(v1c, v2c)[0,1]) if np.std(v1c)>0 and np.std(v2c)>0 else 0.5
                    s_c.append(max(0, c) if np.isfinite(c) else 0.5)
                
                # Composite
                r_s, c_s = float(np.mean(s_r)), float(np.mean(s_c))
                s_s = float(max(0, 1.0 - (abs(in_speed - b.get('speed',350))/max(b.get('speed',350),1) / 0.5)))
                fl_in, fl_bs = np.diff(in_f), np.diff(np.array(b['flight']))
                ml_f = min(len(fl_in), len(fl_bs))
                fl_s = float(max(0.35, np.corrcoef(fl_in[:ml_f], fl_bs[:ml_f])[0,1])) if ml_f>3 else 0.5
                
                f_in, f_bs = np.array(self.extract(inp, history)), np.array(self.extract(b, history))
                rat_s = float(max(0, 1.0 - np.mean(np.abs(f_in[[2,3,6,7,10,11,14,15]]-f_bs[[2,3,6,7,10,11,14,15]])/(f_bs[[2,3,6,7,10,11,14,15]]+0.1))))
                sta_s = float(max(0, 1.0 - np.mean(np.abs(f_in[[1,3,5,7,9,11,13,15]]-f_bs[[1,3,5,7,9,11,13,15]])/(f_bs[[1,3,5,7,9,11,13,15]]+0.05))))
                
                all_s.append(w[0]*r_s + w[1]*c_s + w[2]*s_s + w[3]*fl_s + w[4]*rat_s + w[5]*sta_s)
                comp_logs.append([r_s, c_s, s_s, fl_s, rat_s, sta_s]); max_out = max(max_out, out)

            # 4. Final Scoring & Decision Engine
            f_score = float(np.max(all_s)) if all_s else 0.0
            best = int(np.argmax(all_s)) if all_s else 0
            
            # Populasi Data Dasar untuk Log
            res.update({
                "score": round(f_score, 4),
                "components": {k: round(float(v), 4) for k, v in zip(["rhythm", "corr", "speed", "flow", "ratio", "stability"], comp_logs[best])},
            })

            # 5. Diagnostic Metrics Calculation (Mahalanobis & AI)
            m_dist = None
            if n_h >= 5:
                try:
                    X = np.array([self.extract(h, history) for h in history])
                    mu, cov = np.mean(X,0), np.cov(X, rowvar=False) + np.eye(self.n_features)*0.01
                    diff = np.array(self.extract(inp, history)) - mu
                    m_dist = float(np.sqrt(max(0, diff.T @ np.linalg.inv(cov) @ diff)))
                    res["mahal_dist"] = round(m_dist, 4)
                except: pass

            ai_dec, ai_score = self.ai.predict(user_id, self.extract(inp, history))
            if ai_dec is not None:
                res["ai_score"] = round(float(ai_score), 4)
            else:
                res["ai_score"] = None
                res["ai_status"] = "Standby (Collecting Data)"
            
            # 6. Security Gates Logic (Refined Smart Guard)
            if ai_dec is not None:
                # Kepercayaan Tinggi (User Asli)
                if ai_score > 0.60:
                    res["ai_status"] = "Normal (High Trust)"
                    # Jalur Hijau: Mode Aman (Threshold 0.70)
                    if ai_score > 0.90:
                        gates["threshold"] = float(max(gates["threshold"], 0.70))
                        f_score = min(1.0, f_score + 0.03) # Bonus dikurangi
                    elif ai_score > 0.85:
                        gates["threshold"] = float(max(gates["threshold"], 0.74))
                        f_score = min(1.0, f_score + 0.01)
                
                # Area Abu-abu
                elif ai_score >= 0.30:
                    res["ai_status"] = "Caution (Manual Review Pattern)"
                    gates["threshold"] = float(max(gates["threshold"], 0.78))
                
                # Terdeteksi Asing (Penyusup)
                else:
                    penalty = float(0.60 if ai_score < 0.15 else 0.75)
                    f_score *= penalty
                    gates["threshold"] = float(max(gates["threshold"], 0.82))
                    res["ai_status"] = f"Anomalous (Standard Raised to 0.82)"

            # 6.5 Consistency Check (Komponen Tunggal yang Sangat Rendah)
            # Jika ada satu komponen utama < 50%, berikan penalti tambahan
            comp = res.get("components", {})
            critical_min = min(comp.values()) if comp else 1.0
            if critical_min < 0.55:
                penalty = 0.85 if critical_min < 0.40 else 0.92
                f_score *= penalty
                res["reason_debug"] = f"Low Consistency Penalty ({critical_min:.2f})"

            # Gate B: Mahalanobis (Statistical Outlier)
            if m_dist is not None:
                if m_dist > gates["mahal_gate"]:
                    res.update({"status": False, "reason": f"Gerbang Statistik ({m_dist:.2f})"})
                    return res
                # Bonus for statistical consistency
                if m_dist < 1.5: f_score = min(1.0, f_score + 0.05)

            # 7. Final Matching Logic
            out_p = float(max_out / (len(in_d)*4) if len(in_d)>0 else 0)
            # Final f_score calculation (Weighted best + mean)
            if n_h >= 10:
                f_score = (0.85 * f_score) + (0.15 * float(np.mean(all_s)))
            
            is_match = bool(f_score >= gates["threshold"] and out_p <= 0.25)
            
            # Tentukan alasan spesifik jika gagal di tahap akhir
            reason = f"Score: {f_score:.2f} | ACCEPT" if is_match else "REJECT"
            if not is_match:
                if out_p > 0.25:
                    reason = f"Gerbang Kecepatan ({out_p*100:.1f}%)"
                else:
                    reason = f"Skor Fusion Rendah ({f_score:.2f})"

            res.update({
                "status": is_match,
                "score": round(f_score, 4),
                "n_samples": n_h,
                "reason": reason,
                "should_update_history": bool(is_match and (n_h < 5 or (m_dist and m_dist < 5.0)) and out_p < 0.20)
            })
            return res

        except Exception as e: return {"status": False, "score": 0.0, "reason": f"Core Error: {str(e)}"}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r') as f:
                data = json.load(f)
            print(json.dumps(BiometricCore().analyze(data.get('input', {}), data.get('history', []))))
        except Exception as e:
            print(json.dumps({"status": False, "score": 0.0, "reason": f"CLI Error: {str(e)}"}))