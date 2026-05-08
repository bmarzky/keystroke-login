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
    Titanium Fusion Biometric Engine (Core Orchestrator)
    Menggabungkan fitur struktural, gerbang statistik, dan model ML (OCSVM).
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

            # 7. Cek Gerbang Statistik Akhir
            if m_dist is not None:
                if m_dist > gates_info["mahal_gate"]:
                    return {**res, "status": False, "reason": f"Gerbang Statistik ({m_dist:.2f})"}
                if m_dist < 1.5:
                    f_score = min(1.0, f_score + 0.05)

            # 8. Pengambilan Keputusan Akhir
            return self._finalize_decision(res, f_score, gates_info, fusion_data["max_out"], len(in_d), m_dist, fusion_data["all_scores"])

        except Exception as e:
            return {"status": False, "score": 0.0, "reason": f"Core Error: {str(e)}"}

    def _compute_fusion_scores(self, inp: dict, history: list, in_speed: float) -> dict:
        n_h = len(history)
        c_limit = self.gates.get_clean_limit(history)
        f_limit = self.gates.get_flight_clean_limit(history)
        
        if n_h >= 15:
            audit_samples = history[:3] + history[-7:]
            stabilities = []
            for comp_idx in range(6):
                scores = []
                ref = self.extractor.ensure_vectors(audit_samples[0])
                for s in audit_samples[1:]:
                    s = self.extractor.ensure_vectors(s)
                    if comp_idx == 0:
                        n1, n2 = np.array(ref['dwell'])/max(sum(ref['dwell']),0.001), np.array(s['dwell'])/max(sum(s['dwell']),0.001)
                        ml = min(len(n1), len(n2))
                        scores.append(float(max(0, 1.0 - (np.sqrt(np.sum((n1[:ml]-n2[:ml])**2))/0.25))))
                    elif comp_idx == 1:
                        c = np.corrcoef(ref['dwell'][:min(len(ref['dwell']), len(s['dwell']))], s['dwell'][:min(len(ref['dwell']), len(s['dwell']))])[0,1]
                        scores.append(max(0, c) if np.isfinite(c) else 0.5)
                    elif comp_idx == 2:
                        scores.append(max(0, 1.0 - (abs(ref.get('speed',350) - s.get('speed',350))/350 / 0.5)))
                    else:
                        scores.append(0.7)
                
                std = np.std(scores) if len(scores) > 1 else 0.1
                stabilities.append(1.0 / (std + 0.05))

            raw_w = np.array(stabilities)
            w = raw_w / sum(raw_w)
            w = np.clip(w, 0.08, 0.40)
            w = w / sum(w)
        else:
            if n_h < 5:  w = [0.30, 0.40, 0.15, 0.15, 0.00, 0.00]
            elif n_h < 15: w = [0.27, 0.37, 0.15, 0.15, 0.03, 0.03]
            else: w = [0.30, 0.15, 0.15, 0.15, 0.15, 0.10]
        
        baselines = history[:3] + history[-7:] if n_h > 10 else history
        all_scores, comp_logs, max_out = [], [], 0
        
        for b in baselines:
            b = self.extractor.ensure_vectors(b)
            s_r, s_c, out = [], [], 0
            
            for k in ['dwell', 'flight', 'd2d', 'u2u']:
                v1, v2 = np.array(inp.get(k,[]), dtype=float), np.array(b.get(k,[]), dtype=float)
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
            raw_s_s = float(max(0, 1.0 - (abs(in_speed - b.get('speed',350))/max(b.get('speed',350),1) / 0.5)))
            s_s = float(max(0.30, raw_s_s)) if n_h < 5 else raw_s_s
            
            fl_in, fl_bs = np.diff(inp['flight']), np.diff(np.array(b['flight']))
            ml_f = min(len(fl_in), len(fl_bs))
            if ml_f > 3 and np.std(fl_in[:ml_f]) > 1e-6 and np.std(fl_bs[:ml_f]) > 1e-6:
                raw_fl = float(np.corrcoef(fl_in[:ml_f], fl_bs[:ml_f])[0,1])
                fl_floor = 0.45 if n_h < 5 else 0.35
                fl_s = float(max(fl_floor, raw_fl))
            else:
                fl_s = 0.55
            
            f_in, f_bs = np.array(self.extractor.extract(inp, history)), np.array(self.extractor.extract(b, history))
            rat_s = float(max(0, 1.0 - np.mean(np.abs(f_in[[2,3,6,7,10,11,14,15]]-f_bs[[2,3,6,7,10,11,14,15]])/(f_bs[[2,3,6,7,10,11,14,15]]+0.1))))
            sta_s = float(max(0, 1.0 - np.mean(np.abs(f_in[[1,3,5,7,9,11,13,15]]-f_bs[[1,3,5,7,9,11,13,15]])/(f_bs[[1,3,5,7,9,11,13,15]]+0.05))))
            
            score = w[0]*r_s + w[1]*c_s + w[2]*s_s + w[3]*fl_s + w[4]*rat_s + w[5]*sta_s
            all_scores.append(score)
            comp_logs.append([r_s, c_s, s_s, fl_s, rat_s, sta_s])
            max_out = max(max_out, out)

        best_idx = int(np.argmax(all_scores))
        return {
            "best_score": float(np.max(all_scores)),
            "all_scores": all_scores,
            "components": {k: round(float(v), 4) for k, v in zip(["rhythm", "corr", "speed", "flow", "ratio", "stability"], comp_logs[best_idx])},
            "weights": [round(float(val), 3) for val in w],
            "max_out": max_out
        }

    def _apply_ai_smart_guard(self, ai_score: float, f_score: float, threshold: float, res: dict) -> tuple:
        if ai_score > 0.60:
            res["ai_status"] = "Normal (High Trust)"
            if ai_score > 0.90:
                threshold = float(max(threshold, 0.68))
                f_score = min(1.0, f_score + 0.03)
            elif ai_score > 0.85:
                threshold = float(max(threshold, 0.72))
                f_score = min(1.0, f_score + 0.01)
        elif ai_score >= 0.25:
            res["ai_status"] = "Caution (Manual Review Pattern)"
            boost = (0.60 - ai_score) * 0.35
            threshold = float(max(threshold, min(0.78, threshold + boost)))
        else:
            penalty = 0.60 if ai_score < 0.15 else 0.75
            f_score *= penalty
            threshold = float(max(threshold, 0.82))
            res["ai_status"] = f"Anomalous (Standard Raised to 0.82)"
            
        return f_score, threshold

    def _apply_consistency_penalty(self, comp: dict, f_score: float, res: dict) -> float:
        if not comp: return f_score
        n = res.get("n_samples", 0)
        if n < 3: return f_score

        exclude = set()
        if n < 10: exclude.add('speed'); exclude.add('flow')
        check_components = {k: v for k, v in comp.items() if k not in exclude}
        if not check_components: return f_score
        
        critical_min = min(check_components.values())
        if critical_min < 0.45:
            penalty = 0.96 if critical_min < 0.35 else 0.98 if n < 40 else 0.88 if critical_min < 0.40 else 0.94
            f_score *= penalty
            res["reason_debug"] = f"Consistency Penalty ({critical_min:.2f})"
        return f_score

    def _finalize_decision(self, res: dict, f_score: float, gates: dict, max_out: int, in_len: int, m_dist: float, all_scores: list) -> dict:
        n = res.get("n_samples", 0)

        if n >= 10 and all_scores:
            f_score = (0.85 * f_score) + (0.15 * float(np.mean(all_scores)))

        if n >= 5:
            corr_score = res.get("components", {}).get("corr", 1.0)
            if corr_score < 0.65:
                drop = min(0.25, 0.65 - corr_score)
                f_score *= (1.0 - drop)
                res.setdefault("reason_debug", f"Corr Guard ({corr_score:.1%})")

        is_speed_anomaly = res.get("is_speed_anomaly", False)
        pattern_corr = res.get("components", {}).get("corr", 0.0)
        
        if is_speed_anomaly:
            if pattern_corr > 0.90:
                f_score *= 0.95
                res["reason_debug"] = f"Speed Anomali Forgiven (Corr: {pattern_corr:.2f})"
                is_speed_anomaly = False
            else:
                f_score *= 0.80

        out_p = float(max_out / (in_len * 4) if in_len > 0 else 0)
        out_p_limit = 0.40 if n < 10 else 0.25

        is_match = bool(f_score >= gates["threshold"] and out_p <= out_p_limit and not is_speed_anomaly)
        
        if is_match: reason = f"Score: {f_score:.2f} | ACCEPT"
        elif is_speed_anomaly: reason = f"Gate: Speed Anomali ({res.get('speed_dev', 0):.1%})"
        elif out_p > out_p_limit: reason = f"Outlier Rate Tinggi ({out_p*100:.1f}% > {out_p_limit*100:.0f}%)"
        else: reason = f"Skor Fusion Rendah ({f_score:.2f})"

        _m_ok = (m_dist is None and n < 20) or (m_dist is not None and m_dist < 7.0)
        res.update({
            "status": is_match,
            "score": round(f_score, 4),
            "threshold": gates["threshold"],
            "reason": reason,
            "should_update_history": bool(is_match and (n < 5 or _m_ok) and out_p < 0.20)
        })
        return res

    def _get_method_name(self, uid: str, phase: str) -> str:
        if self.ai._get_latest_model_path(uid) is not None:
            return "Mahalanobis + OCSVM"
        return phase

    def _get_response_template(self, n=0):
        return {"status": False, "score": 0.0, "threshold": 0.70, "reason": "Unknown", "method": "Titanium Fusion",
                "n_samples": n, "speed_dev": 0.0, "mahal_dist": None, "ai_score": None, "ai_status": "Standby",
                "should_update_history": False, "adaptive_gates": {}, "components": {}}

# Blok eksekusi CLI (untuk pengujian lewat terminal)
if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r') as f:
                data = json.load(f)
            print(json.dumps(BiometricCore().analyze(data.get('input', {}), data.get('history', []))))
        except Exception as e:
            print(json.dumps({"status": False, "score": 0.0, "reason": f"CLI Error: {str(e)}"}))