import sys
import json
import numpy as np
import warnings

# Menonaktifkan peringatan numpy agar output JSON tetap bersih
warnings.filterwarnings('ignore')



class BiometricCore:
    # --- CONFIGURATION CONSTANTS ---
    CLEAN_THRESHOLD = 0.25      # Detik: Tombol yang lebih lambat dari ini dianggap macet/error
    DEFAULT_SPEED   = 350.0     # CPM: Kecepatan fallback untuk user baru
    MIN_SAMPLES     = 5         # Minimal sampel untuk mulai menggunakan Mahalanobis
    MAX_MAHAL_DIST  = 15.0      # Batas maksimal jarak Mahalanobis sebelum reject mutlak
    ANOMALY_LIMIT   = 0.25      # 25% data anomali akan memicu reject identitas
    
    def __init__(self, n_features=16):
        # n_features=16 karena kita mengambil Median, Std, Ratio-Median, dan Ratio-Std dari 4 jenis data
        self.n_features = n_features



    def extract(self, data):
        # Fungsi untuk mengekstrak vektor fitur statistik 8-dimensi
        data = self._ensure_vectors(data)
        features = []
        
        for key in ['dwell', 'flight', 'd2d', 'u2u']:
            arr = np.array(data.get(key, []), dtype=float)
            # Filter tombol macet atau error (> 0.25 detik) agar tidak merusak rata-rata
            clean_arr = arr[arr < self.CLEAN_THRESHOLD]
            
            if len(clean_arr) >= 2:
                # Ambil Median untuk stabilitas dan Std Dev untuk konsistensi ritme
                features.append(float(np.median(clean_arr)))
                features.append(float(np.std(clean_arr, ddof=1)))
                
                # Tambahan fitur Rasio Antar Tombol (Rhythm Ratios) - Unik per orang
                if len(clean_arr) >= 3:
                    ratios = clean_arr[:-1] / (clean_arr[1:] + 0.001)
                    features.append(float(np.median(ratios)))
                    features.append(float(np.std(ratios, ddof=1)))
                else:
                    features.extend([1.0, 0.1])
            elif len(arr) >= 1:
                # Fallback jika data sangat sedikit
                features.append(float(min(np.median(arr), 0.20)))
                features.append(0.01)
                features.extend([1.0, 0.1])
            else:
                features.extend([0.0, 0.0, 0.0, 0.0])
                
        return [float(f) if np.isfinite(f) else 0.0 for f in features]



    def _ensure_vectors(self, data):
        # Memastikan data d2d dan u2u ada melalui perhitungan otomatis
        dwell, flight = data.get('dwell', []), data.get('flight', [])
        
        if not data.get('d2d'):
            data['d2d'] = [float(dwell[i] + flight[i]) for i in range(min(len(dwell), len(flight)))]
            
        if not data.get('u2u'):
            data['u2u'] = [float(flight[i] + dwell[i+1]) for i in range(min(len(dwell)-1, len(flight)))]
            
        return data



    def _dtw_distance(self, s1, s2):
        # Algoritma Dynamic Time Warping untuk menghitung kemiripan pola
        n, m = len(s1), len(s2)
        if n == 0 or m == 0: return 1.0
        
        dtw = np.full((n + 1, m + 1), np.inf)
        dtw[0, 0] = 0
        
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = abs(s1[i-1] - s2[j-1])
                dtw[i, j] = cost + min(dtw[i-1, j], dtw[i, j-1], dtw[i-1, j-1])
        
        return float(dtw[n, m] / max(n, m))



    def _compute_adaptive_gates(self, history, hist_mahal_dists):
        # Entry point untuk perhitungan gerbang adaptif
        n = len(history)
        
        # 1. Hitung base gates (untuk user baru atau fase awal)
        base = self._get_base_gates(history)
        if n == 1:
            return {**base, "phase": "Init [Welcome Buffer]"}

        # 2. Hitung history gates (berdasarkan performa kumulatif)
        hist = self._get_history_gates(history, hist_mahal_dists, base)
        
        # 3. Interpolasi (Blending) antara base dan history
        alpha = min(1.0, (n - 1) / 4.0) if n < 5 else 1.0
        speed_g = (1-alpha)*base["speed_gate"] + alpha*hist["speed_gate"]
        mahal_g = (1-alpha)*base["mahal_gate"] + alpha*hist["mahal_gate"]
        thresh  = (1-alpha)*base["threshold"]  + alpha*hist["threshold"]
        
        # 4. Terapkan batasan human-centric (Hardening)
        return self._apply_gate_hardening(n, speed_g, mahal_g, thresh, history[0].get('dwell', []))



    def _get_base_gates(self, history):
        first_dwell = np.array(history[0].get('dwell', [0.1]), dtype=float)
        mean_d = max(float(np.mean(first_dwell)), 0.001)
        std_d  = float(np.std(first_dwell)) if len(first_dwell) > 1 else mean_d * 0.2
        cv     = np.clip(std_d / mean_d, 0.10, 0.60)
        
        return {
            "speed_gate": 0.20 + cv * 0.5,
            "mahal_gate": 1.5 + cv * 6.0,
            "threshold": 0.65 - cv * 0.1
        }



    def _get_history_gates(self, history, hist_mahal_dists, base):
        h_speeds = [float(h.get('speed', 0)) for h in history]
        avg_s = float(np.median(h_speeds))
        h_devs = [abs(s - avg_s) / max(avg_s, 1.0) for s in h_speeds]
        
        h_speed_gate = max(float(np.max(h_devs) * 1.5) if len(h_devs) > 0 else 0.35, 0.35)
        
        if hist_mahal_dists and len(hist_mahal_dists) >= 2:
            m_mean, m_std = np.mean(hist_mahal_dists), np.std(hist_mahal_dists)
            h_mahal_gate = float(m_mean + 3.0 * m_std)
            h_thresh = float(min(0.72, 0.62 + ((len(history) - 5) * 0.02)) + (max(0.0, 1.0 - (m_mean / 2.0)) * 0.10))
        else:
            h_mahal_gate, h_thresh = base["mahal_gate"], (0.62 if len(history) >= 5 else 0.55)
            
        return {"speed_gate": h_speed_gate, "mahal_gate": h_mahal_gate, "threshold": h_thresh}



    def _apply_gate_hardening(self, n, speed_g, mahal_g, thresh, first_dwell):
        if n < 5:    s_high, m_low, t_high = 0.75, 12.0, 0.72
        elif n < 10: s_high, m_low, t_high = 0.65, 10.0, 0.78
        elif n < 20: s_high, m_low, t_high = 0.55, 8.0, 0.82
        else:        s_high, m_low, t_high = 0.45, 1.5, 0.88
        
        speed_g = float(np.clip(speed_g, 0.12, s_high))
        mahal_g = float(np.clip(mahal_g, m_low, 15.0))
        thresh  = float(np.clip(thresh, 0.62, t_high))

        if len(first_dwell) < 8:
            p = (8 - len(first_dwell)) * 0.015
            thresh = float(np.clip(thresh + p, 0.65, 0.88))
            speed_g *= 1.15 
            mahal_g *= 0.90

        return {
            "speed_gate": round(float(speed_g), 4),
            "mahal_gate": round(float(mahal_g), 4),
            "threshold": round(float(thresh), 4),
            "phase": f"Adaptive-{'Blend' if n < 5 else 'Full'} (n={n})"
        }



    def _get_default_response(self):
        return {
            "status": False, 
            "score": 0.0, 
            "threshold": 0.70, 
            "reason": "Unknown Error",
            "method": "Unknown", 
            "n_samples": 0, 
            "speed_dev": 0.0,
            "mahal_dist": None,
            "should_update_history": False,
            "adaptive_gates": {"speed_gate": 0.40, "mahal_gate": 3.0, "threshold": 0.70},
            "components": {"rhythm": 0, "corr": 0, "speed": 0, "flow": 0, "ratio": 0, "stability": 0},
            "weights": {"w_rhythm": 0.4, "w_corr": 0.2, "w_speed": 0.2, "w_flow": 0.2, "w_ratio": 0, "w_stability": 0}
        }



    def analyze(self, json_path):
        res = self._get_default_response()

        try:
            with open(json_path, 'r') as f: data = json.load(f)
            input_raw, history = data.get('input', {}), data.get('history', [])
            if not history: 
                res["reason"] = "Enroll dulu"
                return res

            res["n_samples"] = len(history)
            input_data = self._ensure_vectors(input_raw)
            in_dwell, in_flight = np.array(input_data.get('dwell', []), dtype=float), np.array(input_data.get('flight', []), dtype=float)
            threshold, is_typo_recovery, is_messy, d_dist, f_dist = 0.75, False, False, None, None
            
            exp_len, act_len = len(history[0].get('dwell', [])), len(in_dwell)
            if act_len != exp_len:
                if abs(act_len - exp_len) <= 3:
                    b_dwell, b_flight = np.array(history[0]['dwell']), np.array(history[0]['flight'])
                    d_dist, f_dist = self._dtw_distance(in_dwell, b_dwell), self._dtw_distance(in_flight, b_flight)
                    if d_dist < 0.05 and f_dist < 0.07: is_typo_recovery = True
                    else: 
                        res["reason"] = f"REJECT | DTW fail (d={d_dist:.3f}, f={f_dist:.3f})"
                        res["adaptive_gates"].update({"dtw_dwell": float(d_dist), "dtw_flight": float(f_dist)})
                        return res
                else: 
                    res["reason"] = "REJECT | Length Mismatch"
                    return res

            c_dw, c_fl = in_dwell[in_dwell < self.CLEAN_THRESHOLD], in_flight[in_flight < self.CLEAN_THRESHOLD]
            input_speed = float(60.0/(np.mean(c_dw)+np.mean(c_fl))) if (len(c_dw)>=3 and len(c_fl)>=3) else float(input_data.get('speed', 0))
            if np.sum(in_dwell) < 0.01: 
                res["reason"] = "Data tidak valid"
                return res

            hist_mahal = []
            if len(history) >= 5:
                try:
                    X = np.array([self.extract(h) for h in history])
                    mu, cov = np.mean(X, axis=0), np.cov(X, rowvar=False) + np.eye(self.n_features) * 1e-3
                    cinv = np.linalg.inv(cov)
                    for row in X:
                        d = row - mu
                        hist_mahal.append(float(np.sqrt(max(0, d.T @ cinv @ d))))
                except: pass

            gates = self._compute_adaptive_gates(history, hist_mahal)
            threshold, speed_gate, mahal_gate = float(gates["threshold"]), float(gates["speed_gate"]), float(gates["mahal_gate"])
            
            res["threshold"] = threshold
            res["adaptive_gates"] = gates
            res["method"] = gates["phase"]

            # Gunakan Median untuk menangkis polusi data awal yang salah (bias)
            avg_s = float(np.median([float(h.get('speed', 0)) for h in history]))
            if len(history) == 1 and avg_s < 250: avg_s = self.DEFAULT_SPEED
            speed_dev = float(abs(input_speed - avg_s) / max(avg_s, 1.0))
            res["speed_dev"] = round(speed_dev, 4)

            if speed_dev > speed_gate: 
                res["reason"] = f"Gate: Speed Anomali ({speed_dev:.1%})"
                res["adaptive_gates"].update({"dtw_dwell": float(d_dist) if d_dist else None, "dtw_flight": float(f_dist) if f_dist else None})
                return res

            n_h = len(history)
            if n_h < 5: 
                w = [0.30, 0.40, 0.15, 0.15, 0.00, 0.00] # Init
            elif n_h < 10: 
                w = [0.35, 0.25, 0.15, 0.15, 0.05, 0.05] # Transition
            else: 
                w = [0.30, 0.15, 0.15, 0.15, 0.15, 0.10] # Expert (Ratios matter more)
            
            if len(in_dwell) < 8: 
                w[1], w[3] = w[1]*0.5, w[3]*0.5
                rem = 1.0 - sum(w[1:])
                w[0] = max(0.1, rem)
            
            res["weights"] = {"w_rhythm": float(w[0]), "w_corr": float(w[1]), "w_speed": float(w[2]), "w_flow": float(w[3]), "w_ratio": float(w[4]), "w_stability": float(w[5])}

            stats_profile = {}
            if n_h > 1:
                for k in ['dwell', 'flight', 'd2d', 'u2u']:
                    arrs = [np.array(b.get(k, []))[:15] for b in (history[:3]+history[-7:] if n_h>10 else history)]
                    if arrs:
                        ml = min(len(x) for x in arrs)
                        mat = np.array([x[:ml] for x in arrs])
                        stats_profile[k] = {"mean": np.mean(mat, axis=0), "std": np.std(mat, axis=0) + 0.005}

            all_scores, comp_log, final_outliers = [], [], 0
            baselines = (history[:3]+history[-7:] if n_h>10 else history)
            
            for baseline in baselines:
                b_data = self._ensure_vectors(baseline)
                scores_r, scores_c, outliers = [], [], 0
                for k in ['dwell', 'flight', 'd2d', 'u2u']:
                    v1, v2 = (in_dwell if k=='dwell' else in_flight if k=='flight' else np.array(input_data[k])), np.array(b_data[k])
                    if n_h == 1: v2[v2 > 0.40] = np.median(v2)
                    ml = min(len(v1), len(v2), len(stats_profile[k]["mean"]) if k in stats_profile else 999)
                    if ml < 3: continue
                    v1, v2 = v1[:ml], v2[:ml]
                    mask = (np.abs(v1 - stats_profile[k]["mean"][:ml]) > (3.5 * stats_profile[k]["std"][:ml])) | (v1 > self.CLEAN_THRESHOLD) if (k in stats_profile and n_h>1) else (v1 > self.CLEAN_THRESHOLD)
                    outliers += int(np.sum(mask))
                    v1c, v2c = v1[~mask], v2[~mask]
                    if len(v1c) < 3: v1c, v2c = v1, v2
                    n1, n2 = v1c/max(np.sum(v1c),0.001), v2c/max(np.sum(v2c),0.001)
                    scores_r.append(float(max(0, 1.0 - (np.sqrt(np.sum((n1-n2)**2))/0.18))))
                    c = np.corrcoef(v1c, v2c)[0, 1] if np.std(v1c)>0 and np.std(v2c)>0 else 0.5
                    scores_c.append(float(max(0, c) if np.isfinite(c) else 0.5))

                if not scores_r: continue
                r_s, c_s = float(np.mean(scores_r)), float(np.mean(scores_c))
                if outliers > 0 and c_s > 0.90: r_s, c_s = min(1.0, r_s*1.05), min(1.0, c_s*1.05)
                bs_s = float(baseline.get('speed', 350 if n_h==1 else 0))
                s_s = float(max(0, 1.0 - (abs(input_speed - bs_s)/max(bs_s, 1.0) / (0.5 + min(0.2, outliers*0.1)))))
                
                f_in, f_bs = np.diff(in_flight), np.diff(np.array(b_data['flight']))
                flen = min(len(f_in), len(f_bs))
                fl_s = float(max(0.35, np.corrcoef(f_in[:flen], f_bs[:flen])[0,1])) if flen > 3 else 0.5

                # Ratio & Stability Scoring (16-Dim Logic)
                in_feat, bs_feat = np.array(self.extract(input_data)), np.array(self.extract(b_data))
                
                # Ratio Score: Bandingkan fitur index 2,3, 6,7, 10,11, 14,15 (Rhythm Ratios)
                idx_ratios = [2, 3, 6, 7, 10, 11, 14, 15]
                rat_s = float(max(0, 1.0 - np.mean(np.abs(in_feat[idx_ratios] - bs_feat[idx_ratios]) / (bs_feat[idx_ratios] + 0.1))))
                
                # Stability Score: Bandingkan Std Dev features (Index 1, 3, 5, 7, 9, 11, 13, 15)
                idx_stds = [1, 3, 5, 7, 9, 11, 13, 15]
                sta_s = float(max(0, 1.0 - np.mean(np.abs(in_feat[idx_stds] - bs_feat[idx_stds]) / (bs_feat[idx_stds] + 0.05))))

                all_scores.append(float(w[0]*r_s + w[1]*c_s + w[2]*s_s + w[3]*fl_s + w[4]*rat_s + w[5]*sta_s))
                comp_log.append([r_s, c_s, s_s, fl_s, rat_s, sta_s])
                final_outliers = max(final_outliers, outliers)

            if not all_scores:
                res["reason"] = "REJECT | Data tidak cukup untuk penilaian"
                return res

            best_idx = int(np.argmax(all_scores))
            final_score = float(all_scores[best_idx])
            if n_h >= 10:
                final_score = float((0.8 if final_score > 0.7 else 0.4)*final_score + (0.2 if final_score > 0.7 else 0.6)*np.mean(all_scores))
                if np.min(all_scores) < 0.5: final_score *= float(max(0.78, np.min(all_scores)/0.5))

            m_dist = None
            if n_h >= 5:
                try:
                    X = np.array([self.extract(h) for h in history])
                    # REGULARIZATION: Gunakan buffer lebih besar untuk user Senior agar tidak sensitif
                    reg = 0.1 if n_h < 20 else 1e-3
                    mu, cov = np.mean(X, axis=0), np.cov(X, rowvar=False) + np.eye(self.n_features) * reg
                    diff = np.array(self.extract(input_data)) - mu
                    m_dist = float(round(np.sqrt(max(0, diff.T @ np.linalg.inv(cov) @ diff)), 4))
                    res["mahal_dist"] = m_dist
                    if m_dist > mahal_gate: 
                        res["reason"] = f"Gate: Mahalanobis Anomali ({m_dist:.4f})"
                        res["method"] = "Mahalanobis+" + res["method"]
                        res["adaptive_gates"].update({"dtw_dwell": float(d_dist) if d_dist else None, "dtw_flight": float(f_dist) if f_dist else None, "outlier_count": int(final_outliers)})
                        return res
                    if m_dist < 1.2: final_score = min(1.0, final_score + 0.07)
                except: pass

            # --- SECURITY HARDENING (Anti-Impostor) ---
            # Batasi seberapa banyak data yang boleh "dibuang" (Sterile). 
            # Jika terlalu banyak anomali (>25%), identitas tidak bisa divalidasi dengan aman.
            out_p = float(final_outliers / (len(in_dwell)*4)) if len(in_dwell)>0 else 0.0
            
            # Berikan penalti skor jika ada tombol yang dibuang agar penyusup tidak mudah lolos
            if final_outliers > 0:
                # HARDENING: Penalti lebih agresif (0.5 pengali)
                penalty = min(0.25, (final_outliers / len(in_dwell)) * 0.5)
                final_score = max(0.0, final_score - penalty)

            if out_p > 0.25: 
                is_match, final_score = False, 0.0
                res["reason"] = f"REJECT | Identitas meragukan (Anomali: {out_p:.1%})"
            else:
                is_match = bool(final_score >= threshold) or (n_h == 1 and final_score >= 0.25)
                res["reason"] = f"Score: {final_score:.2f} | {'ACCEPT' if is_match else 'REJECT'}"

            res["status"] = is_match
            res["score"] = round(float(final_score), 4)
            
            # --- UPDATE HISTORY LOGIC (Anti-Poisoning) ---
            # Jangan update history jika:
            # 1. Sedang pemulihan typo (tidak representatif)
            # 2. Banyak data anomali (Sterile > 15%)
            # 3. KHUSUS USER BARU: Jangan simpan jika ada > 2 tombol Sterile (No Garbage Baseline)
            # 4. KHUSUS EXPERT: Hanya update jika data sangat meyakinkan (High Integrity)
            
            is_clean_init = True
            if n_h < 5 and final_outliers > 2:
                is_clean_init = False 

            is_high_integrity = True
            if n_h > 10:
                # Expert hanya update jika score sangat tinggi dan jarak Mahalanobis rendah
                # Ini mencegah orang yang 'mirip' (seperti Asir) meracuni database sejarah user
                if final_score < (threshold + 0.04) or (m_dist and m_dist > 0.85):
                    is_high_integrity = False

            res["should_update_history"] = bool(
                is_match and 
                is_clean_init and
                is_high_integrity and
                not (is_typo_recovery or out_p > 0.15) and 
                (final_score >= (threshold + 0.02) or n_h < 3)
            )
            
            res["adaptive_gates"].update({"dtw_dwell": float(d_dist) if d_dist else None, "dtw_flight": float(f_dist) if f_dist else None, "outlier_count": int(final_outliers), "is_typo": bool(is_typo_recovery)})
            res["components"] = {
                "rhythm": round(float(comp_log[best_idx][0]), 4), 
                "corr": round(float(comp_log[best_idx][1]), 4), 
                "speed": round(float(comp_log[best_idx][2]), 4), 
                "flow": round(float(comp_log[best_idx][3]), 4), 
                "ratio": round(float(comp_log[best_idx][4]), 4), 
                "stability": round(float(comp_log[best_idx][5]), 4)
            }
            
            return res

        except Exception as e: 
            res["reason"] = f"Core Error: {str(e)}"
            return res



if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            print(json.dumps(BiometricCore().analyze(sys.argv[1])))
        except Exception as e:
            # Fallback jika json.dumps tetap gagal karena ada tipe data non-standar
            print(json.dumps({"status": False, "score": 0.0, "reason": f"Serialization Error: {str(e)}"}))