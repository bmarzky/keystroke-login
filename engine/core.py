import sys
import json
import numpy as np
import warnings

warnings.filterwarnings('ignore')


class BiometricCore:

    def __init__(self, n_features=8):
        self.n_features = n_features

    # ─────────────────────────────────────────────────────
    # Feature Extraction (8-dim statistical vector)
    # ─────────────────────────────────────────────────────
    def extract(self, data):
        features = []
        for key in ['dwell', 'flight', 'd2d', 'u2u']:
            arr = np.array(data.get(key, []), dtype=float)
            if len(arr) >= 2:
                features.append(float(np.mean(arr)))
                features.append(float(np.std(arr, ddof=1)))
            elif len(arr) == 1:
                features.append(float(arr[0]))
                features.append(0.0)
            else:
                features.append(0.0)
                features.append(0.0)
        return [float(f) if np.isfinite(f) else 0.0 for f in features]

    # ─────────────────────────────────────────────────────
    # Warm-Start Progressive Adaptive Gate Computation
    # ─────────────────────────────────────────────────────
    def _compute_adaptive_gates(self, history, hist_mahal_dists=None):
        """
        Menghitung gate adaptif berbasis statistik history user.

        Fase 0 (n=1, register): Inferensi dari Coefficient of Variation (CV)
          internal satu sesi ketikan, untuk menentukan karakter typist.
        Fase 1 (n=2-4): Blending linier antara gate register dan gate history.
        Fase 2 (n>=5) : Full adaptive dari distribusi history.
        """
        n = len(history)

        # --- Fase 0: Inferensi dari sample pertama (register) ---
        first_dwell = np.array(history[0].get('dwell', [0.1]), dtype=float)
        mean_dwell  = max(float(np.mean(first_dwell)), 0.001)
        std_dwell   = float(np.std(first_dwell)) if len(first_dwell) > 1 else mean_dwell * 0.2
        cv          = std_dwell / mean_dwell  # Coefficient of Variation

        # CV → karakter typist → inisialisasi gate awal
        # cv < 0.20: presisi | 0.20–0.40: normal | > 0.40: variabel
        cv_clamped      = float(np.clip(cv, 0.10, 0.60))
        base_speed_gate = 0.20 + cv_clamped * 0.50   # 0.25 – 0.50
        base_mahal_gate = 1.50 + cv_clamped * 6.0    # 2.10 – 5.10
        base_threshold  = 0.65 - cv_clamped * 0.15   # 0.56 – 0.63

        if n == 1:
            return {
                "speed_gate": float(round(base_speed_gate, 4)),
                "mahal_gate": float(round(base_mahal_gate, 4)),
                "threshold":  float(round(base_threshold,  4)),
                "phase": "Adaptive-Init (CV={:.2f})".format(cv),
            }

        # --- Fase 1 & 2: Hitung dari history yang sudah ada ---
        hist_speeds = [float(h.get('speed', 0)) for h in history]
        avg_speed   = float(np.mean(hist_speeds))
        hist_devs   = [abs(s - avg_speed) / max(avg_speed, 1.0) for s in hist_speeds]

        hist_mean_dev = float(np.mean(hist_devs))
        hist_std_dev  = float(np.std(hist_devs)) if len(hist_devs) > 1 else hist_mean_dev * 0.3
        hist_speed_gate = hist_mean_dev + 3.0 * hist_std_dev

        # Mahalanobis gate dari distribusi jarak user sendiri
        if hist_mahal_dists and len(hist_mahal_dists) >= 2:
            m_mean = float(np.mean(hist_mahal_dists))
            m_std  = float(np.std(hist_mahal_dists))
            hist_mahal_gate = m_mean + 3.0 * m_std
            
            # --- ADAPTIVE THRESHOLD SCALING ---
            # Jika rata-rata jarak Mahal kecil, artinya user sangat konsisten.
            # Tingkatkan threshold secara proporsional dari 0.74 ke maksimal 0.84
            # (m_mean 0.0 -> threshold 0.84, m_mean > 1.5 -> threshold 0.74)
            consistency_factor = max(0.0, 1.0 - (m_mean / 1.5))
            hist_threshold = 0.74 + (consistency_factor * 0.10)

        else:
            hist_mahal_gate = base_mahal_gate
            hist_threshold = 0.74 if n >= 5 else 0.65

        # --- Blending (Fase 1: 2-4 sample) ---
        if n < 5:
            alpha = (n - 1) / 4.0  # 0.25 → 0.75
            speed_gate = (1 - alpha) * base_speed_gate + alpha * hist_speed_gate
            mahal_gate = (1 - alpha) * base_mahal_gate + alpha * hist_mahal_gate
            threshold  = (1 - alpha) * base_threshold  + alpha * hist_threshold
            phase = "Adaptive-Blend (n={}, α={:.2f})".format(n, alpha)
        else:
            # Fase 2: Full adaptive
            speed_gate = hist_speed_gate
            mahal_gate = hist_mahal_gate
            threshold  = hist_threshold
            phase = "Mahalanobis+Adaptive-Full (n={})".format(n)

        # Clamp ke batas keamanan minimum
        speed_gate = float(np.clip(speed_gate, 0.10, 0.50))
        mahal_gate = float(np.clip(mahal_gate, 1.20, 6.00))
        threshold  = float(np.clip(threshold,  0.60, 0.86))

        return {
            "speed_gate": round(speed_gate, 4),
            "mahal_gate": round(mahal_gate, 4),
            "threshold":  round(threshold,  4),
            "phase": phase,
        }

    # ─────────────────────────────────────────────────────
    # Main Analysis
    # ─────────────────────────────────────────────────────
    def analyze(self, json_path):
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            input_data = data.get('input', {})
            history    = data.get('history', [])

            if not history:
                return {"status": False, "score": 0.0, "reason": "Enroll dulu"}

            n_history = len(history)

            in_dwell    = np.array(input_data.get('dwell', []), dtype=float)
            in_flight   = np.array(input_data.get('flight', []), dtype=float)
            input_speed = float(input_data.get('speed', 0))

            if np.sum(in_dwell) < 0.01 or np.sum(in_flight) < 0.01:
                return {"status": False, "score": 0.0, "reason": "Data tidak valid"}

            # ── Hitung Mahalanobis dist history terlebih dahulu (untuk gate adaptif) ──
            hist_mahal_dists = []
            if n_history >= 5:
                try:
                    X    = np.array([self.extract(h) for h in history])
                    mu   = np.mean(X, axis=0)
                    cov  = np.cov(X, rowvar=False) + np.eye(self.n_features) * 1e-3
                    cinv = np.linalg.inv(cov)
                    for row in X:
                        d = row - mu
                        hist_mahal_dists.append(float(np.sqrt(max(0, d.T @ cinv @ d))))
                except Exception:
                    pass

            # ── Adaptive Gate Computation ──
            gates      = self._compute_adaptive_gates(history, hist_mahal_dists)
            threshold  = gates["threshold"]
            speed_gate = gates["speed_gate"]
            mahal_gate = gates["mahal_gate"]
            adapt_phase = gates["phase"]

            # ── Speed Gate (Adaptive) ──
            history_speeds = [float(h.get('speed', 0)) for h in history]
            avg_speed  = float(np.mean(history_speeds))
            speed_dev  = abs(input_speed - avg_speed) / max(avg_speed, 1.0)

            if speed_dev > speed_gate:
                return {
                    "status": False, "score": 0.0,
                    "threshold": threshold, "should_update_history": False,
                    "reason": f"Gate: Speed Anomali (dev={speed_dev:.1%} > gate={speed_gate:.1%})",
                    "method": adapt_phase, "n_features": self.n_features,
                    "n_samples": n_history, "mahal_dist": None,
                    "speed_dev": float(round(speed_dev, 4)), 
                    "adaptive_gates": {
                        "speed_gate": speed_gate,
                        "mahal_gate": mahal_gate,
                        "threshold":  threshold,
                    },
                    "components": {},
                }

            # ── Soft Scoring ──
            baselines = history if n_history <= 5 else history[:2] + history[-3:]
            w_rhythm, w_corr, w_speed, w_ratio, w_stability, w_flow = 0.50, 0.20, 0.15, 0.00, 0.00, 0.15
            all_scores = []
            comp_rhythm, comp_corr, comp_speed, comp_ratio, comp_stability, comp_flow = [], [], [], [], [], []
            mahal_error = None

            for baseline in baselines:
                b_data = {k: np.array(baseline.get(k, []), dtype=float) for k in ['dwell', 'flight', 'd2d', 'u2u']}

                scores_r, scores_c = [], []
                for key in ['dwell', 'flight', 'd2d', 'u2u']:
                    in_v  = np.array(input_data.get(key, []), dtype=float)
                    bs_v  = b_data[key]
                    mlen  = min(len(in_v), len(bs_v)) - 1
                    if mlen < 3: continue

                    v1, v2 = in_v[:mlen], bs_v[:mlen]
                    # Rhythm (Euclidean)
                    n1, n2 = v1 / max(np.sum(np.abs(v1)), 0.001), v2 / max(np.sum(np.abs(v2)), 0.001)
                    dist   = np.sqrt(np.sum((n1 - n2) ** 2))
                    scores_r.append(max(0.0, 1.0 - (dist / 0.18)))
                    # Correlation (Pearson)
                    c = np.corrcoef(v1, v2)[0, 1] if np.std(v1) > 0 and np.std(v2) > 0 else 0.5
                    scores_c.append(max(0.0, c) if np.isfinite(c) else 0.5)

                if not scores_r: continue
                r_score, c_score = np.mean(scores_r), np.mean(scores_c)

                # Speed
                s_score  = max(0.0, 1.0 - (abs(input_speed - float(baseline.get('speed', 0))) / max(float(baseline.get('speed', 1)), 1.0) / 0.50))
                # Ratio (Dwell/Flight)
                r_in  = np.sum(input_data.get('dwell', [])) / max(np.sum(input_data.get('flight', [])), 0.01)
                r_bs  = np.sum(baseline.get('dwell', [])) / max(np.sum(baseline.get('flight', [])), 0.01)
                ra_score = max(0.0, 1.0 - (abs(r_in - r_bs) / max(r_bs, 0.01) / 0.40))
                if n_history == 1:
                    ra_score = max(ra_score, 0.50)  # Toleransi khusus n=1 (pendaftaran)
                # Stability (Jitter)
                j_in  = np.std(in_dwell) / max(np.mean(in_dwell), 0.01)
                j_bs  = np.std(b_data['dwell']) / max(np.mean(b_data['dwell']), 0.01)
                st_score = max(0.0, 1.0 - (abs(j_in - j_bs) / 0.30))
                # Flow (Acceleration)
                f_in, f_bs = np.diff(in_flight), np.diff(b_data['flight'])
                flen = min(len(f_in), len(f_bs))
                if flen > 3:
                    f1, f2   = f_in[:flen], f_bs[:flen]
                    c_f      = np.corrcoef(f1, f2)[0, 1] if np.std(f1) > 0 and np.std(f2) > 0 else 0.5
                    fl_score = max(0.0, c_f) if np.isfinite(c_f) else 0.5
                    # Flow/Akselerasi sangat rentan terhadap 1 slip jari (outlier), 
                    # beri batas minimum 0.35 agar tidak langsung 0%
                    fl_score = max(fl_score, 0.35)
                else:
                    fl_score = 0.5

                comp_rhythm.append(r_score)
                comp_corr.append(c_score)
                comp_speed.append(s_score)
                comp_ratio.append(ra_score)
                comp_stability.append(st_score)
                comp_flow.append(fl_score)
                all_scores.append(
                    w_rhythm*r_score + w_corr*c_score + w_speed*s_score +
                    w_ratio*ra_score + w_stability*st_score + w_flow*fl_score
                )

            if not all_scores:
                return {"status": False, "score": 0.0, "reason": "Data tidak cukup"}

            best_idx  = np.argmax(all_scores)
            best_score = float(all_scores[best_idx])
            
            # Gunakan skor KECOCOKAN TERBAIK (Best Match) bukan Rata-Rata.
            # Ini memungkinkan "Drift" (ketika user lelah, mereka akan cocok dengan template
            # terbaru saat mulai lelah, dan tidak diseret turun oleh template lama yang fresh).
            final_score = best_score
            
            # Komponen log ambil dari yang terbaik
            components = {
                "rhythm": float(comp_rhythm[best_idx]),
                "correlation": float(comp_corr[best_idx]),
                "speed": float(comp_speed[best_idx]),
                "ratio": float(comp_ratio[best_idx]),
                "stability": float(comp_stability[best_idx]),
                "flow": float(comp_flow[best_idx]),
            }

            # ── Mahalanobis (Adaptive Gate) ──
            method    = adapt_phase
            m_dist_val = None
            if n_history >= 5:
                method = "Mahalanobis+" + adapt_phase
                try:
                    X    = np.array([self.extract(h) for h in history])
                    mu   = np.mean(X, axis=0)
                    cov  = np.cov(X, rowvar=False) + np.eye(self.n_features) * 1e-3
                    diff = np.array(self.extract(input_data)) - mu
                    m_dist_val = float(round(np.sqrt(max(0, diff.T @ np.linalg.inv(cov) @ diff)), 4))

                    # Hard Gate Adaptif
                    if m_dist_val > mahal_gate:
                        return {
                            "status": False, "score": 0.0,
                            "threshold": threshold, "should_update_history": False,
                            "reason": f"Gate: Mahalanobis Anomali (dist={m_dist_val:.4f} > gate={mahal_gate:.4f})",
                            "method": method, "n_features": self.n_features,
                            "n_samples": n_history, "mahal_dist": m_dist_val,
                            "speed_dev": float(round(speed_dev, 4)),
                            "adaptive_gates": {
                                "speed_gate": speed_gate,
                                "mahal_gate": mahal_gate,
                                "threshold":  threshold,
                            },
                            "components": {},
                        }
                    
                    # Kita TIDAK LAGI memotong final_score dengan m_score.
                    # Mahalanobis murni berfungsi sebagai Hard Gate. Jika lolos gate, 
                    # user berhak dinilai murni menggunakan Titanium Fusion.
                    
                except Exception as e:
                    mahal_error = str(e)
                    method = "Mahalanobis+" + adapt_phase + " (error)"

            is_match  = bool(final_score >= threshold)
            should_up = bool((final_score > 0.75) or (final_score > threshold and n_history < 3))
            reason    = f"Score: {final_score:.2f} | {'ACCEPT' if is_match else 'REJECT'}"
            if mahal_error: reason += f" | Math Error: {mahal_error}"

            return {
                "status":               is_match,
                "score":                float(round(final_score, 4)),
                "threshold":            float(threshold),
                "should_update_history": should_up,
                "reason":               reason,
                "method":               method,
                "n_features":           self.n_features,
                "n_samples":            n_history,
                "mahal_dist":           m_dist_val,
                "speed_dev":            float(round(speed_dev, 4)),
                "adaptive_gates": {
                    "speed_gate": gates["speed_gate"],
                    "mahal_gate": gates["mahal_gate"],
                    "threshold":  gates["threshold"],
                },
                "components": {
                    "rhythm":    float(round(components["rhythm"],    4)) if components else None,
                    "corr":      float(round(components["correlation"], 4)) if components else None,
                    "speed":     float(round(components["speed"],     4)) if components else None,
                    "ratio":     float(round(components["ratio"],     4)) if components else None,
                    "stability": float(round(components["stability"], 4)) if components else None,
                    "flow":      float(round(components["flow"],      4)) if components else None,
                },
            }

        except Exception as e:
            return {"status": False, "score": 0.0, "reason": f"Core Error: {str(e)}"}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        core = BiometricCore()
        print(json.dumps(core.analyze(sys.argv[1])))