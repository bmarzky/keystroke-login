import sys
import json
import warnings
import os
import numpy as np

from src.engine.extractors.features import FeatureExtractor
from src.engine.gates.statistics import StatisticalGates
from src.engine.ml.ai_engine import AIEngine

# Abaikan peringatan library
warnings.filterwarnings('ignore')

class BiometricCore:
    """
    Sequential Mahalanobis-SVM Biometric Engine (Core Orchestrator)
    Menggabungkan fitur struktural, gerbang statistik (Mahalanobis), dan model ML (One-Class SVM).
    """
    
    def __init__(self):
        self.extractor = FeatureExtractor()
        self.gates = StatisticalGates(self.extractor)
        self.ai = AIEngine()

    def analyze(self, input_data: dict, history: list, user_id: str = None) -> dict:
        try:
            if not history:
                return {**self._get_response_template(), "reason": "Enroll dulu"}

            res = self._get_response_template(len(history))
            inp = self.extractor.ensure_vectors(input_data)
            in_d = np.array(inp.get('dwell', []), dtype=float)
            
            # 1. Validasi Struktural
            struct_check = self.extractor.check_structural_integrity(inp, history[0])
            if not struct_check["ok"]:
                return {**res, "reason": struct_check["reason"]}

            # 2. Setup Gerbang Statistik
            mahal_history = self.gates.get_mahal_history(history)
            gates_info = self.gates.calculate_gates(len(history), history, mahal_history)
            
            uid = user_id or input_data.get('user_id', 'unknown')
            method = self._get_method_name(uid, gates_info["phase"])
            res.update({"threshold": gates_info["threshold"], "adaptive_gates": gates_info, "method": method})

            # 3. Analisis Kecepatan
            in_speed, s_dev = self.gates.calculate_speed_metrics(inp, history)
            res["speed_dev"] = round(s_dev, 4)
            res["is_speed_anomaly"] = s_dev > gates_info["speed_gate"]

            # 4. Skor Fusion (Perbandingan dengan Riwayat)
            fusion_data = self._compute_fusion_scores(inp, history, in_speed)
            f_score = fusion_data["best_score"]
            res.update({
                "score": round(f_score, 4),
                "components": fusion_data["components"],
                "weights": fusion_data.get("weights", [])
            })

            # 5. Mahalanobis & AI
            m_dist = self.gates.calculate_current_mahalanobis(inp, history)
            res["mahal_dist"] = round(m_dist, 4) if m_dist else None
            
            ai_status, ai_score, n_train, raw_score = self.ai.predict(uid, self.extractor.extract(inp, history))
            if ai_status is not None:
                res.update({"ai_score": round(float(ai_score), 4), "n_train": n_train, "ai_raw_dist": round(raw_score, 4)})
                f_score, gates_info["threshold"] = self._apply_ai_smart_guard(ai_score, f_score, gates_info["threshold"], res)
            
            # 6. Pengerasan Konsistensi
            f_score = self._apply_consistency_penalty(res["components"], f_score, res)

            # 7. Cek Gerbang Statistik Akhir (Adaptive Buffer)
            if m_dist is not None:
                # Jika jarak mahalanobis tinggi tapi skor fusi sangat bagus, berikan toleransi kecil (Buffer Zone)
                # Kita perkecil dari 1.5 ke 1.2 untuk mencegah impersonation.
                mahal_buffer = gates_info["mahal_gate"] * 1.2
                
                if m_dist > mahal_buffer:
                    return {**res, "status": False, "reason": f"Gerbang Statistik (Anomali Berat: {m_dist:.2f})"}
                elif m_dist > gates_info["mahal_gate"] and f_score < 0.88:
                    # Tolak jika di atas gate utama DAN skor fusi tidak sangat kuat (>0.88)
                    return {**res, "status": False, "reason": f"Gerbang Statistik (Outlier: {m_dist:.2f})"}
                
                if m_dist < 1.5:
                    f_score = min(1.0, f_score + 0.05)

            # 8. Pengambilan Keputusan Akhir
            return self._finalize_decision(inp, res, f_score, gates_info, fusion_data["max_out"], len(in_d), m_dist, fusion_data["all_scores"], history)

        except Exception as e:
            return {"status": False, "score": 0.0, "reason": f"Core Error: {str(e)}"}

    def _compute_fusion_scores(self, inp: dict, history: list, in_speed: float) -> dict:
        n_h = len(history)
        c_limit = self.gates.get_clean_limit(history)
        f_limit = self.gates.get_flight_clean_limit(history)
        
        # Penentuan bobot berdasarkan kematangan user (Phase 1: Paranoid Mode n < 5)
        # Rhythm & Correlation mengambil alih 80% keputusan.
        if n_h < 5:
            w = [0.45, 0.35, 0.10, 0.05, 0.025, 0.025]
        elif n_h < 15:
            # Phase 2: Early Maturity. Rhythm tetap dominan (65%) untuk mencegah collision.
            w = [0.35, 0.30, 0.15, 0.10, 0.05, 0.05]
        else:
            w = [0.30, 0.15, 0.15, 0.15, 0.15, 0.10]
        
        # Batasan Penelitian: Maksimal 50 sampel untuk merepresentasikan Cold-Start
        history = history[-50:]
        baselines = history[:3] + history[-7:] if n_h > 10 else history
        all_scores, comp_logs, max_out = [], [], 0
        
        for b in baselines:
            b = self.extractor.ensure_vectors(b)
            s_r, s_c, out = [], [], 0
            
            aligned_f1, aligned_f2 = np.array(inp['flight']), np.array(b['flight'])
            for k in ['dwell', 'flight', 'd2d', 'u2u']:
                v1, v2 = np.array(inp.get(k,[]), dtype=float), np.array(b.get(k,[]), dtype=float)
                
                # Handling Missing Vector Intervals
                if abs(len(v1) - len(v2)) == 1 and len(v1) >= 5 and len(v2) >= 5:
                    if len(v1) > len(v2):
                        c1 = float(np.corrcoef(v1[:-1], v2)[0,1]) if np.std(v1[:-1])>0 else 0
                        c2 = float(np.corrcoef(v1[1:], v2)[0,1]) if np.std(v1[1:])>0 else 0
                        if c1 > c2: v1 = v1[:-1]
                        else: v1 = v1[1:]
                    else:
                        c1 = float(np.corrcoef(v1, v2[:-1])[0,1]) if np.std(v2[:-1])>0 else 0
                        c2 = float(np.corrcoef(v1, v2[1:])[0,1]) if np.std(v2[1:])>0 else 0
                        if c1 > c2: v2 = v2[:-1]
                        else: v2 = v2[1:]

                if k == 'flight':
                    aligned_f1, aligned_f2 = v1, v2

                ml = min(len(v1), len(v2))
                v1, v2 = v1[:ml], v2[:ml]
                
                arr_limit = c_limit if k == 'dwell' else f_limit
                mask = (v1 > arr_limit)
                out += int(np.sum(mask))
                v1c, v2c = v1[~mask], v2[~mask]
                if len(v1c) < 3: v1c, v2c = v1, v2
                
                n1, n2 = v1c/max(sum(v1c),0.001), v2c/max(sum(v2c),0.001)
                s_r.append(float(max(0, 1.0 - (np.sqrt(np.sum((n1-n2)**2))/0.25))))
                
                c = float(np.corrcoef(v1c, v2c)[0,1]) if np.std(v1c)>0 and np.std(v2c)>0 else 0.5
                s_c.append(max(0, c) if np.isfinite(c) else 0.5)
            
            r_s, c_s = float(np.mean(s_r)), float(np.mean(s_c))
            
            # --- GAUSSIAN SPEED SCORE (Smooth Tolerance) ---
            cpm_in = float(in_speed)
            cpm_ref = float(b.get('speed', 350))
            diff = abs(cpm_in - cpm_ref)
            # Std Dev ~ 25% dari ref memberikan toleransi yang manusiawi
            s_s = float(np.exp(-(diff**2) / (2 * (0.25 * cpm_ref + 1e-9)**2)))
            
            # Flow Score
            fl_in, fl_bs = np.diff(aligned_f1), np.diff(aligned_f2)
            ml_f = min(len(fl_in), len(fl_bs))
            if ml_f >= 3 and np.std(fl_in[:ml_f]) > 1e-6 and np.std(fl_bs[:ml_f]) > 1e-6:
                fl_s = max(0, float(np.corrcoef(fl_in[:ml_f], fl_bs[:ml_f])[0,1]))
            else:
                fl_s = 0.60
            
            f_in, f_bs = np.array(self.extractor.extract(inp, history)), np.array(self.extractor.extract(b, history))
            rat_idx, sta_idx = [2, 5, 8, 11], [1, 4, 7, 10]
            
            rat_s = float(max(0, 1.0 - np.mean(np.abs(f_in[rat_idx]-f_bs[rat_idx])/(f_bs[rat_idx]+0.1))))
            sta_s = float(max(0, 1.0 - np.mean(np.abs(f_in[sta_idx]-f_bs[sta_idx])/(f_bs[sta_idx]+0.05))))
            
            # Tri-graph consistency
            t_in, t_bs = np.array(inp.get('trigraph', []), dtype=float), np.array(b.get('trigraph', []), dtype=float)
            ml_t = min(len(t_in), len(t_bs))
            tri_s = float(max(0, 1.0 - (np.linalg.norm(t_in[:ml_t] - t_bs[:ml_t]) / 0.5))) if ml_t >= 2 else 0.6
            
            score = w[0]*r_s + w[1]*c_s + w[2]*s_s + w[3]*fl_s + (w[4]*0.7*rat_s + w[4]*0.3*tri_s) + w[5]*sta_s
            all_scores.append(score)
            comp_logs.append([r_s, c_s, s_s, fl_s, (0.7*rat_s + 0.3*tri_s), sta_s])
            max_out = max(max_out, out)

        best_idx = int(np.argmax(all_scores))
        best_score = float(np.max(all_scores))
        
        if n_h < 5 and n_h > 1:
            if all_scores[0] < 0.70: best_score *= 0.85 

        return {
            "best_score": best_score,
            "all_scores": all_scores,
            "components": {k: round(float(v), 4) for k, v in zip(["rhythm", "corr", "speed", "flow", "ratio", "stability"], comp_logs[best_idx])},
            "weights": [round(float(val), 3) for val in w],
            "max_out": max_out
        }

    def _apply_ai_smart_guard(self, ai_score: float, f_score: float, threshold: float, res: dict) -> tuple:
        n_samples = res.get("n_samples", 0)
        stability = res.get("components", {}).get("stability", 0.0)
        
        # Turbo Protection: Jika stabilitas tinggi (>90%), kurangi kecurigaan AI
        is_turbo_consistent = stability > 0.90
        
        if ai_score > 0.60:
            res["ai_status"] = "Normal (High Trust)"
            offset = -0.04 if ai_score > 0.90 else (-0.02 if ai_score > 0.85 else 0.0)
            threshold += offset
            if ai_score > 0.90: f_score = min(1.0, f_score + 0.03)
        elif ai_score >= 0.25:
            res["ai_status"] = "Caution (Manual Review Pattern)"
            multiplier = 0.5 if is_turbo_consistent else 1.0
            offset = (0.60 - ai_score) * (0.06 if n_samples < 50 else 0.12) * multiplier
            threshold += offset
        else:
            res["ai_status"] = "Anomalous (Security Raised)"
            # Dampen AI Anomaly jika user sangat konsisten (mencegah false rejection pada fast typing)
            if is_turbo_consistent and n_samples < 50:
                penalty = 0.96 # Lebih ringan (sebelumnya 0.92)
                offset = 0.04  # Lebih ringan (sebelumnya 0.08)
            else:
                penalty = 0.92 if n_samples < 50 else 0.82
                offset = 0.08 if n_samples < 50 else 0.15
                
            f_score *= penalty
            threshold += offset
            
        if "audit" not in res: res["audit"] = {}
        res["audit"]["ai_offset"] = round(float(threshold - res.get("threshold", threshold)), 4)
        return f_score, threshold

    def _apply_consistency_penalty(self, comp: dict, f_score: float, res: dict) -> float:
        if not comp: return f_score
        n = res.get("n_samples", 0)
        if n < 4: return f_score
        
        critical_min = min(comp.values())
        if critical_min < 0.45:
            penalty = 0.98 if n < 40 else (0.90 if critical_min < 0.25 else 0.95)
            f_score *= penalty
            res["reason_debug"] = f"Consistency Penalty ({critical_min:.2f})"
        return f_score

    def _finalize_decision(self, inp: dict, res: dict, f_score: float, gates: dict, max_out: int, in_len: int, m_dist: float, all_scores: list, history: list) -> dict:
        n = res.get("n_samples", 0)
        audit = {
            "Layer_A_Raw": {"jitter": round(float(inp.get('jitter', 0)), 6), "typing_speed": round(float(res.get('speed_dev', 0)), 4)},
            "Layer_B_Stats": {"mahalanobis_dist": round(float(m_dist), 4) if m_dist else None, "base_threshold": round(float(gates["threshold"]), 4)},
            "Layer_C_AI": {"ai_confidence": res.get("ai_score"), "ai_status": res.get("ai_status", "Standby")},
            "Layer_D_Decision": {"final_score": round(f_score, 4), "final_threshold": round(float(gates["threshold"]), 4), 
                                 "outlier_rate": round(float(max_out / (in_len * 4) if in_len > 0 else 0), 3), "is_replay": False}
        }

        # RETRAINING / MOVING AVERAGE
        if n >= 10 and all_scores:
            f_score = (0.85 * f_score) + (0.15 * float(np.mean(all_scores)))

        # REPLAY GUARD
        in_jitter = float(inp.get('jitter', 0.1))
        historical_jitters = [float(h.get('jitter', 0.1)) for h in history[-10:]]
        baseline_jitter = float(np.median(historical_jitters)) if historical_jitters else 0.05
        if in_jitter < 0.0001 or (n >= 5 and in_jitter < baseline_jitter * 0.1):
            audit["Layer_D_Decision"]["is_replay"] = True
            f_score *= 0.4

        # DECISION
        out_p = audit["Layer_D_Decision"]["outlier_rate"]
        out_p_limit = 0.45 if n < 10 else 0.30 # Slightly relaxed
        is_replay = audit["Layer_D_Decision"]["is_replay"]
        is_speed_anomaly = res.get("is_speed_anomaly", False)
        
        # Soft Speed Anomaly: Jangan langsung blokir jika user sangat konsisten
        # Konversi is_speed_anomaly dari hard-block ke score penalty (0.90x) untuk user dengan CPM > 380
        curr_cpm = float(inp.get('speed', 0))
        if is_speed_anomaly and curr_cpm > 380 and res.get("components", {}).get("stability", 0) > 0.85:
            f_score *= 0.92
            is_speed_anomaly = False
            res["reason_debug"] = (res.get("reason_debug", "") + " | Soft Speed Penalty").strip(" | ")

        is_match = bool(f_score >= gates["threshold"] and out_p <= out_p_limit and not is_speed_anomaly and not is_replay)
        
        if is_match: reason = f"ACCEPT | Match Score {f_score:.2f} (Target {gates['threshold']:.2f})"
        elif is_replay: reason = f"REJECT | SECURITY: Replay Attack Detected"
        elif is_speed_anomaly: reason = f"REJECT | Gate: Speed Anomaly"
        elif out_p > out_p_limit: reason = f"REJECT | Outlier Rate ({out_p*100:.1f}%)"
        else: reason = f"REJECT | Fusion Score Rendah ({f_score:.2f})"

        # LEARNING LOGIC (MASTER KEY)
        ai_status = res.get("ai_status", "")
        ai_suspicious = "Anomalous" in ai_status or "Caution" in ai_status
        m_trust = (m_dist is not None and m_dist < 2.0)
        
        if n < 30:
            if (m_trust and f_score > 0.72) or ("Caution" in ai_status and f_score > 0.72) or ("Anomalous" in ai_status and f_score > 0.80):
                ai_suspicious = False
        else:
            if (m_trust and f_score > 0.82) or ("Caution" in ai_status and f_score > 0.85):
                ai_suspicious = False
        
        early_trust = (n >= 5 or f_score > 0.75)
        # _m_ok: Jarak mahalanobis boleh sedikit lebih tinggi untuk user turbo selama skor fusi tinggi
        _m_ok = (m_dist is None and n < 20) or (m_dist is not None and m_dist < 10.0)

        res.update({
            "status": is_match, "score": round(f_score, 4), "threshold": gates["threshold"],
            "reason": reason, "audit": audit,
            "should_update_history": bool(is_match and early_trust and (n < 5 or _m_ok) and out_p <= out_p_limit and not ai_suspicious)
        })
        return res

    def _get_method_name(self, uid: str, phase: str) -> str:
        if self.ai._get_latest_model_path(uid) is not None: return "Mahalanobis + OCSVM"
        return phase

    def _get_response_template(self, n=0):
        return {"status": False, "score": 0.0, "threshold": 0.70, "reason": "Unknown", "method": "Sequential Mahalanobis-SVM",
                "n_samples": n, "speed_dev": 0.0, "mahal_dist": None, "ai_score": None, "ai_status": "Standby",
                "should_update_history": False, "adaptive_gates": {}, "components": {}, "audit": {}}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r') as f:
                data = json.load(f)
            print(json.dumps(BiometricCore().analyze(data.get('input', {}), data.get('history', []))))
        except Exception as e:
            print(json.dumps({"status": False, "score": 0.0, "reason": f"CLI Error: {str(e)}"}))