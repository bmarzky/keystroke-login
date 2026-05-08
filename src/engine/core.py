import sys
import json
import warnings
import os
import numpy as np
from src.engine.ml.ai_engine import AIEngine

# Abaikan peringatan library (seperti peringatan konvergensi sklearn)
warnings.filterwarnings('ignore')

class BiometricCore:
    """
    Titanium Fusion Biometric Engine
    Logika inti untuk analisis dinamika ketikan, gerbang statistik, dan fusi AI.
    """
    
    # --- KONFIGURASI SISTEM ---
    CLEAN_THRESHOLD = 0.25      # Batas durasi dwell normal (0.25 detik)
    MAX_MAHAL_DIST = 15.0       # Batas maksimal jarak statistik

    def __init__(self, n_features: int = 24):
        self.n_features = n_features
        self.ai = AIEngine()

    # API PUBLIK (Fungsi Utama)

    def analyze(self, input_data: dict, history: list, user_id: str = None) -> dict:
        """
        Titik masuk utama untuk analisis autentikasi.
        Mengikuti alur Titanium Fusion: Struktural -> Statistik -> Fusi AI.
        """
        try:
            # Jika belum ada riwayat ketikan (database kosong)
            if not history:
                return {**self._get_response_template(), "reason": "Enroll dulu"}

            # 1. Inisialisasi & Normalisasi Data
            res = self._get_response_template(len(history))
            inp = self._ensure_vectors(input_data)
            in_d = np.array(inp.get('dwell', []), dtype=float)
            
            # 2. Validasi Struktural & Pemulihan Typo (DTW)
            struct_check = self._check_structural_integrity(inp, history[0])
            if not struct_check["ok"]:
                return {**res, "reason": struct_check["reason"]}

            # 3. Setup Gerbang Statistik & Lingkungan
            mahal_history = self._get_mahal_history(history)
            gates = self._calculate_gates(len(history), history, mahal_history)
            
            # Tentukan Nama Metode (Deteksi jika model OCSVM aktif)
            uid = user_id or input_data.get('user_id', 'unknown')
            method = self._get_method_name(uid, gates["phase"])
            res.update({"threshold": gates["threshold"], "adaptive_gates": gates, "method": method})

            # 4. Analisis Kecepatan & Konsistensi
            in_speed, s_dev = self._calculate_speed_metrics(inp, history, gates)
            res["speed_dev"] = round(s_dev, 4)
            # Kita tidak lagi langsung return di sini. 
            # Kita simpan statusnya untuk diputuskan di akhir (Finalize).
            res["is_speed_anomaly"] = s_dev > gates["speed_gate"]

            # 5. Skor Titanium Fusion (Perbandingan dengan Riwayat)
            fusion_data = self._compute_fusion_scores(inp, history, in_speed)
            f_score = fusion_data["best_score"]
            res.update({
                "score": round(f_score, 4),
                "components": fusion_data["components"],
                "weights": fusion_data.get("weights", [])
            })

            # 6. Diagnostik Lanjutan (Mahalanobis & AI)
            m_dist = self._calculate_current_mahalanobis(inp, history)
            res["mahal_dist"] = round(m_dist, 4) if m_dist else None
            
            # Prediksi AI (OCSVM)
            ai_status, ai_score, n_train, raw_score = self.ai.predict(uid, self.extract(inp, history))
            if ai_status is not None:
                res.update({"ai_score": round(float(ai_score), 4), "n_train": n_train, "ai_raw_dist": round(raw_score, 4)})
                f_score, gates["threshold"] = self._apply_ai_smart_guard(ai_score, f_score, gates["threshold"], res)
            
            # 7. Pengerasan Konsistensi (Penalti jika ada komponen yang sangat buruk)
            f_score = self._apply_consistency_penalty(res["components"], f_score, res)

            # 8. Cek Gerbang Statistik Akhir (Mahalanobis)
            if m_dist is not None:
                if m_dist > gates["mahal_gate"]:
                    return {**res, "status": False, "reason": f"Gerbang Statistik ({m_dist:.2f})"}
                if m_dist < 1.5: # Bonus jika sangat konsisten secara statistik
                    f_score = min(1.0, f_score + 0.05)

            # 9. Pengambilan Keputusan Akhir
            return self._finalize_decision(res, f_score, gates, fusion_data["max_out"], len(in_d), m_dist, fusion_data["all_scores"])

        except Exception as e:
            return {"status": False, "score": 0.0, "reason": f"Core Error: {str(e)}"}

    # EKSTRAKSI FITUR (Feature Extraction)

    def extract(self, data: dict, history=None) -> list:
        """Ekstraksi vektor fitur 24-dimensi menggunakan operasi vektor NumPy."""
        data = self._ensure_vectors(data)
        features = []
        
        # Pembersihan Data Adaptif (Cleaning Outliers)
        limit = self.CLEAN_THRESHOLD
        if history:
            all_d = [d for h in history for d in h.get('dwell', [])]
            if all_d: limit = max(0.25, np.median(all_d) * 2.5)
        
        for key in ['dwell', 'flight', 'd2d', 'u2u']:
            arr = np.array(data.get(key, []), dtype=float)
            clean = arr[arr < limit] # Hanya ambil data yang masuk akal
            
            if len(clean) >= 2:
                # Statistik Dasar (Median & Standar Deviasi)
                features.extend([float(np.median(clean)), float(np.std(clean, ddof=1))])
                # Rasio Ritme (Keajegan antarkunci)
                r = clean[:-1] / (clean[1:] + 0.001) if len(clean) >= 3 else [1.0, 0.1]
                features.extend([float(np.median(r)), float(np.std(r, ddof=1)) if len(r)>1 else 0.1])
                # Tanda Tangan Frekuensi (FFT)
                fft = np.abs(np.fft.fft(clean)) if len(clean) >= 4 else [0, 0, 0]
                features.extend([float(fft[1]) if len(fft)>1 else 0.0, float(fft[2]) if len(fft)>2 else 0.0])
            else:
                # Data cadangan jika ketikan terlalu pendek/buruk
                features.extend([float(min(np.median(arr), 0.20)) if len(arr)>0 else 0.0, 0.01, 1.0, 0.1, 0.0, 0.0])
                
        # Pastikan tidak ada nilai NaN atau tak terhingga
        return [float(f) if np.isfinite(f) else 0.0 for f in features]

    # HELPER INTERNAL (Blok Logika)

    def _check_structural_integrity(self, inp: dict, h0: dict) -> dict:
        """Validasi panjang ketikan dan pemulihan typo ringan menggunakan DTW."""
        in_d, in_f = np.array(inp['dwell']), np.array(inp['flight'])
        ref_d, ref_f = np.array(h0['dwell']), np.array(h0['flight'])
        
        # Jika panjang sama, langsung lulus
        if len(in_d) == len(ref_d):
            return {"ok": True}
            
        # Jika selisih panjang <= 3 karakter, coba gunakan DTW (Dynamic Time Warping)
        if abs(len(in_d) - len(ref_d)) <= 3:
            d_dist = self._dtw_distance(in_d, ref_d)
            f_dist = self._dtw_distance(in_f, ref_f)
            # Jika secara pola masih sangat mirip, izinkan (toleransi typo)
            if d_dist < 0.05 and f_dist < 0.07:
                return {"ok": True, "typo_recovered": True}
            return {"ok": False, "reason": f"REJECT | DTW fail (d={d_dist:.3f})"}
            
        return {"ok": False, "reason": "REJECT | Length Mismatch"}

    def _compute_fusion_scores(self, inp: dict, history: list, in_speed: float) -> dict:
        """Menjalankan loop Titanium Fusion membandingkan input dengan riwayat terbaik."""
        n_h = len(history)
        c_limit = self._get_clean_limit(history)
        # Batas outlier terpisah untuk flight/d2d/u2u:
        # Flight alami bisa 3-5x lebih panjang dari dwell, jadi
        # menggunakan c_limit dwell untuk flight akan menghasilkan false-positive.
        f_limit = self._get_flight_clean_limit(history)
        
        # Jika riwayat sudah cukup (n >= 15), hitung bobot berdasarkan stabilitas profil
        if n_h >= 15:
            # Kita hitung variansi internal dari riwayat (3 sampel awal + 7 terbaru)
            audit_samples = history[:3] + history[-7:]
            stabilities = []
            
            # Ekstrak fitur stabilitas untuk setiap komponen
            for comp_idx in range(6):
                # Ambil skor komponen dari audit_samples (dibandingkan dengan sampel pertama)
                scores = []
                ref = self._ensure_vectors(audit_samples[0])
                for s in audit_samples[1:]:
                    s = self._ensure_vectors(s)
                    # Simulasi skor sederhana untuk audit stabilitas
                    if comp_idx == 0: # Rhythm
                        n1, n2 = np.array(ref['dwell'])/max(sum(ref['dwell']),0.001), np.array(s['dwell'])/max(sum(s['dwell']),0.001)
                        ml = min(len(n1), len(n2))
                        scores.append(float(max(0, 1.0 - (np.sqrt(np.sum((n1[:ml]-n2[:ml])**2))/0.25))))
                    elif comp_idx == 1: # Corr
                        c = np.corrcoef(ref['dwell'][:min(len(ref['dwell']), len(s['dwell']))], s['dwell'][:min(len(ref['dwell']), len(s['dwell']))])[0,1]
                        scores.append(max(0, c) if np.isfinite(c) else 0.5)
                    elif comp_idx == 2: # Speed
                        scores.append(max(0, 1.0 - (abs(ref.get('speed',350) - s.get('speed',350))/350 / 0.5)))
                    else: # Lainnya (Flow, Ratio, Stability) - Gunakan nilai default stabilitas moderat
                        scores.append(0.7)
                
                # Hitung Stabilitas (1 / Standar Deviasi). Semakin kecil std, semakin besar stabilitas.
                std = np.std(scores) if len(scores) > 1 else 0.1
                stabilities.append(1.0 / (std + 0.05)) # +0.05 sebagai smoothing

            # Normalisasi bobot agar total = 1.0
            # Kita batasi bobot per komponen (min 0.08, max 0.40) agar tidak ada fitur yang mati total
            raw_w = np.array(stabilities)
            w = raw_w / sum(raw_w)
            w = np.clip(w, 0.08, 0.40)
            w = w / sum(w) # Re-normalisasi setelah clip
        else:
            # Bobot Statis untuk User Baru (Fase Pembangunan Profil)
            # CATATAN KEAMANAN: Corr (Pearson) adalah diskriminator terkuat per-karakter.
            # Jangan turunkan bobotnya drastis di fase n=5-14 karena akan memudahkan penyusup.
            if n_h < 5:  w = [0.30, 0.40, 0.15, 0.15, 0.00, 0.00]
            elif n_h < 15: w = [0.27, 0.37, 0.15, 0.15, 0.03, 0.03]  # Corr tetap dominan
            else: w = [0.30, 0.15, 0.15, 0.15, 0.15, 0.10]
        
        # Pilih sampel acuan (3 awal + 7 terbaru)
        baselines = history[:3] + history[-7:] if n_h > 10 else history
        all_scores, comp_logs, max_out = [], [], 0
        
        for b in baselines:
            b = self._ensure_vectors(b)
            s_r, s_c, out = [], [], 0
            
            for k in ['dwell', 'flight', 'd2d', 'u2u']:
                v1, v2 = np.array(inp.get(k,[]), dtype=float), np.array(b.get(k,[]), dtype=float)
                ml = min(len(v1), len(v2))
                v1, v2 = v1[:ml], v2[:ml]
                
                # Deteksi Outlier Sesaat — gunakan batas yang sesuai jenis array.
                # flight/d2d/u2u secara alami lebih panjang dari dwell,
                # sehingga perlu batas yang berbeda.
                arr_limit = c_limit if k == 'dwell' else f_limit
                mask = (v1 > arr_limit)
                out += int(np.sum(mask))
                v1c, v2c = v1[~mask], v2[~mask]
                if len(v1c) < 3: v1c, v2c = v1, v2
                
                # Ritme (Jarak Normalisasi)
                n1, n2 = v1c/max(sum(v1c),0.001), v2c/max(sum(v2c),0.001)
                s_r.append(float(max(0, 1.0 - (np.sqrt(np.sum((n1-n2)**2))/0.25))))
                
                # Korelasi (Pearson)
                c = float(np.corrcoef(v1c, v2c)[0,1]) if np.std(v1c)>0 and np.std(v2c)>0 else 0.5
                s_c.append(max(0, c) if np.isfinite(c) else 0.5)
            
            # Metrik Gabungan
            r_s, c_s = float(np.mean(s_r)), float(np.mean(s_c))
            # Skor Kecepatan
            # Untuk user baru (n < 5), beri lantai minimum 0.30 agar kecepatan
            # yang sangat berbeda dari referensi 1 sampel tidak menghancurkan skor.
            raw_s_s = float(max(0, 1.0 - (abs(in_speed - b.get('speed',350))/max(b.get('speed',350),1) / 0.5)))
            s_s = float(max(0.30, raw_s_s)) if n_h < 5 else raw_s_s
            
            # Flow (Korelasi Flight Jitter)
            fl_in, fl_bs = np.diff(inp['flight']), np.diff(np.array(b['flight']))
            ml_f = min(len(fl_in), len(fl_bs))
            if ml_f > 3 and np.std(fl_in[:ml_f]) > 1e-6 and np.std(fl_bs[:ml_f]) > 1e-6:
                raw_fl = float(np.corrcoef(fl_in[:ml_f], fl_bs[:ml_f])[0,1])
                # Untuk user baru (n < 5), korelasi jitter flight tidak bisa diandalkan
                # dengan hanya 1-2 sampel — naikkan lantai dari 0.35 ke 0.45.
                fl_floor = 0.45 if n_h < 5 else 0.35
                fl_s = float(max(fl_floor, raw_fl))
            else:
                fl_s = 0.55 # Default lebih ramah jika sangat konsisten (zero jitter)
            
            # Perbandingan Fitur Lanjutan (Ratio & Stability)
            f_in, f_bs = np.array(self.extract(inp, history)), np.array(self.extract(b, history))
            rat_s = float(max(0, 1.0 - np.mean(np.abs(f_in[[2,3,6,7,10,11,14,15]]-f_bs[[2,3,6,7,10,11,14,15]])/(f_bs[[2,3,6,7,10,11,14,15]]+0.1))))
            sta_s = float(max(0, 1.0 - np.mean(np.abs(f_in[[1,3,5,7,9,11,13,15]]-f_bs[[1,3,5,7,9,11,13,15]])/(f_bs[[1,3,5,7,9,11,13,15]]+0.05))))
            
            # Total Fusi (Menggunakan Bobot w yang mungkin dinamis)
            score = w[0]*r_s + w[1]*c_s + w[2]*s_s + w[3]*fl_s + w[4]*rat_s + w[5]*sta_s
            all_scores.append(score)
            comp_logs.append([r_s, c_s, s_s, fl_s, rat_s, sta_s])
            max_out = max(max_out, out)

        best_idx = int(np.argmax(all_scores))
        res_fusion = {
            "best_score": float(np.max(all_scores)),
            "all_scores": all_scores,
            "components": {k: round(float(v), 4) for k, v in zip(["rhythm", "corr", "speed", "flow", "ratio", "stability"], comp_logs[best_idx])},
            "weights": [round(float(val), 3) for val in w], # Pastikan w selalu ada
            "max_out": max_out
        }
        return res_fusion

    def _apply_ai_smart_guard(self, ai_score: float, f_score: float, threshold: float, res: dict) -> tuple:
        """Menyesuaikan skor dan ambang batas berdasarkan tingkat kepercayaan OCSVM."""
        if ai_score > 0.60:
            res["ai_status"] = "Normal (High Trust)"
            if ai_score > 0.90:
                # Jalur Hijau: Sangat yakin, berikan sedikit bonus
                threshold = float(max(threshold, 0.68))
                f_score = min(1.0, f_score + 0.03)
            elif ai_score > 0.85:
                threshold = float(max(threshold, 0.72))
                f_score = min(1.0, f_score + 0.01)
        elif ai_score >= 0.25:
            # Jalur Kuning: Ragu, naikkan standar keamanan secara gradual (bukan lonjakan tajam)
            res["ai_status"] = "Caution (Manual Review Pattern)"
            # Gradual increase: 0.65 -> 0.78 based on how low the AI score is
            boost = (0.60 - ai_score) * 0.35 # Max boost ~0.12
            threshold = float(max(threshold, min(0.78, threshold + boost)))
        else:
            # Jalur Merah: Terdeteksi anomali (Penyusup), berikan penalti skor & naikkan threshold
            penalty = 0.60 if ai_score < 0.15 else 0.75
            f_score *= penalty
            threshold = float(max(threshold, 0.82))
            res["ai_status"] = f"Anomalous (Standard Raised to 0.82)"
            
        return f_score, threshold

    def _apply_consistency_penalty(self, comp: dict, f_score: float, res: dict) -> float:
        """Memberikan penalti jika ada satu komponen biometrik yang sangat buruk."""
        if not comp: return f_score
        
        n = res.get("n_samples", 0)

        # Untuk user sangat baru (n < 3), tidak ada cukup data untuk baseline yang
        # stabil — menonaktifkan penalti sepenuhnya mencegah penghukuman tidak adil.
        if n < 3: return f_score

        # Untuk user baru (n < 10):
        # - Jangan masukkan 'speed' (fluktuatif alami di fase awal)
        # - Jangan masukkan 'flow' (korelasi jitter tidak andal dengan < 5 sampel)
        exclude = set()
        if n < 10: exclude.add('speed')
        if n < 10: exclude.add('flow')
        check_components = {k: v for k, v in comp.items() if k not in exclude}
        
        if not check_components: return f_score
        
        critical_min = min(check_components.values())
        if critical_min < 0.45: # Dilonggarkan dari 0.50 ke 0.45
            # Penalti lebih ringan untuk user transisi (n < 40)
            if n < 40:
                penalty = 0.96 if critical_min < 0.35 else 0.98
            else:
                penalty = 0.88 if critical_min < 0.40 else 0.94
                
            f_score *= penalty
            res["reason_debug"] = f"Consistency Penalty ({critical_min:.2f})"
        return f_score

    def _finalize_decision(self, res: dict, f_score: float, gates: dict, max_out: int, in_len: int, m_dist: float, all_scores: list) -> dict:
        """Logika pemungutan suara akhir dan agregasi hasil."""
        n = res.get("n_samples", 0)

        # 1. Penghalusan skor untuk profil yang sudah mapan (n >= 10)
        if n >= 10 and all_scores:
            f_score = (0.85 * f_score) + (0.15 * float(np.mean(all_scores)))

        # 1b. Corr Security Guard (aktif setelah profil mulai terbentuk, n >= 5)
        # Pearson Correlation adalah sidik jari paling sensitif terhadap pergantian pengetik.
        # Penyusup cenderung memiliki Corr rendah meski fitur lain (Speed, Flow) tinggi.
        # Penalti proporsional: corr=0.65 -> 0% | corr=0.53 -> ~12% | corr=0.40 -> ~25%
        if n >= 5:
            corr_score = res.get("components", {}).get("corr", 1.0)
            if corr_score < 0.65:
                drop = min(0.25, 0.65 - corr_score)  # Dibatasi max 25% drop
                f_score *= (1.0 - drop)
                res.setdefault("reason_debug", f"Corr Guard ({corr_score:.1%})")

        # 2. Adaptive Speed Forgiver
        # Jika ada anomali kecepatan tapi polanya (Correlation) sangat identik (> 0.90)
        is_speed_anomaly = res.get("is_speed_anomaly", False)
        pattern_corr = res.get("components", {}).get("corr", 0.0)
        
        if is_speed_anomaly:
            if pattern_corr > 0.90:
                # Berikan toleransi: Kurangi skor sedikit (penalti 5%) tapi jangan blokir
                f_score *= 0.95
                res["reason_debug"] = f"Speed Anomali Forgiven (Corr: {pattern_corr:.2f})"
                is_speed_anomaly = False # Matikan flag anomali karena sudah dimaafkan
            else:
                # Jika pola juga buruk, tetap anggap anomali
                f_score *= 0.80

        # 3. Cek Ambang Batas Akhir
        out_p = float(max_out / (in_len * 4) if in_len > 0 else 0)

        # Toleransi outlier lebih longgar untuk user baru (n < 10):
        # Baseline (c_limit) belum stabil dengan 1-2 sampel, sehingga keystroke
        # yang sedikit lebih lambat/cepat dari biasa bisa terkena false-positive.
        out_p_limit = 0.40 if n < 10 else 0.25

        is_match = bool(f_score >= gates["threshold"] and out_p <= out_p_limit and not is_speed_anomaly)
        
        # 4. Penentuan Alasan yang informatif
        if is_match:
            reason = f"Score: {f_score:.2f} | ACCEPT"
        elif is_speed_anomaly:
            reason = f"Gate: Speed Anomali ({res.get('speed_dev', 0):.1%})"
        elif out_p > out_p_limit:
            reason = f"Outlier Rate Tinggi ({out_p*100:.1f}% > {out_p_limit*100:.0f}%)"
        else:
            reason = f"Skor Fusion Rendah ({f_score:.2f})"

        # should_update_history:
        # - n < 5  : selalu update (fase pembangunan profil awal)
        # - n < 20 : update jika m_dist < 7.0 ATAU m_dist tidak tersedia (None)
        # - n >= 20: update hanya jika m_dist < 7.0 (ketat, model sudah matang)
        # Catatan: batas dinaikkan dari 5.0 ke 7.0 agar profil user terus berkembang
        # dan model AI mendapat cukup data untuk retrain di n=40, 60, dst.
        _m_ok = (m_dist is None and n < 20) or (m_dist is not None and m_dist < 7.0)
        res.update({
            "status": is_match,
            "score": round(f_score, 4),
            "threshold": gates["threshold"],
            "reason": reason,
            "should_update_history": bool(is_match and (n < 5 or _m_ok) and out_p < 0.20)
        })
        return res

    # UTILITIES (Fungsi Pembantu)

    def _calculate_speed_metrics(self, inp: dict, history: list, gates: dict) -> tuple:
        """Menghitung metrik kecepatan ketikan dibandingkan rata-rata riwayat."""
        in_v, in_fv = np.array(inp['dwell']), np.array(inp['flight'])
        c_limit = self._get_clean_limit(history)
        v_clean = in_v[in_v < c_limit]
        fv_clean = in_fv[in_fv < c_limit]
        
        in_speed = float(60.0/(np.mean(v_clean)+np.mean(fv_clean))) if len(v_clean)>=3 else float(inp.get('speed', 0))
        avg_s = float(np.median([h.get('speed', 0) for h in history]))
        s_dev = abs(in_speed - avg_s) / max(avg_s, 1.0)
        
        return in_speed, s_dev

    def _calculate_gates(self, n, history, mahal_dists):
        """Menghitung gerbang adaptif (threshold, speed_gate, mahal_gate) berdasarkan jam terbang."""
        # 1. Heuristik Dasar (Awal Enrollment)
        h0_d = np.array(history[0].get('dwell', [0.1]), dtype=float)
        cv = float(np.clip(np.std(h0_d)/max(np.mean(h0_d),0.001), 0.1, 0.6))
        g = {"s": 0.2 + cv*0.5, "m": 1.5 + cv*6.0, "t": 0.65 - cv*0.1}

        # 2. Logika Adaptif Berdasarkan Riwayat
        if n > 1:
            speeds = [float(h.get('speed', 0)) for h in history]
            g["s"] = float(max(0.35, (3.0 * np.std(speeds) / max(np.mean(speeds), 1.0))))
            if mahal_dists and len(mahal_dists) >= 3:
                m_avg, m_std = float(np.mean(mahal_dists)), float(np.std(mahal_dists))
                # Transisi Linear dari Longgar (n=5) ke Ketat (n=50)
                # multiplier: 2.8 -> 1.8 | buffer: 4.0 -> 1.5
                progress = np.clip((n - 5) / 45.0, 0.0, 1.0)
                multiplier = 2.8 - (progress * 1.0)
                buffer = 4.0 - (progress * 2.5)
                
                g["m"] = m_avg + multiplier * m_std + buffer
                base_t = 0.65 if n >= 30 else 0.62
                g["t"] = float(min(base_t, base_t - 0.05 + (n-5)*0.01) + (max(0.0, 1.0 - m_avg/3.0)*0.08))

        # 3. Blending (Pencampuran fase transisi)
        alpha = float(1.0 if n >= 5 else min(1.0, (n-1)/4.0))
        s_final = g["s"] 
        m_final = (1-alpha)*(1.5 + cv*6.0) + alpha*g["m"]
        t_final = (1-alpha)*(0.68 - cv*0.1) + alpha*g["t"]

        # Batas Pengerasan Fase (Tighter Boundaries) - Diperketat untuk mencegah FAR
        # n < 5: Longgar | n < 20: Transisi | n < 50: Ketat | n >= 100: Sangat Ketat
        # Format: (speed_limit, mahal_limit, threshold_upper_limit)
        limits = [(0.85, 12.0, 0.72), (0.75, 10.0, 0.75), (0.50, 4.5, 0.78), (0.40, 3.2, 0.82)]
        s_h, m_l, t_h = limits[min(3, 0 if n<5 else 1 if n<20 else 2 if n<100 else 3)]
        
        # S_MIN & T_MIN: Pengetatan mulai dari n=20
        s_min = 0.75 if n < 5 else 0.60 if n < 20 else 0.35
        s_res = float(np.clip(s_final, s_min, s_h))
        m_res = float(np.clip(m_final, m_l, self.MAX_MAHAL_DIST))
        
        # Hardening Threshold Dasar
        t_min = 0.75 if n > 100 else 0.72 if n > 50 else 0.70 if n > 20 else 0.66
        t_res = float(np.clip(t_final, t_min, t_h))

        # Penalti untuk Password Pendek
        if len(h0_d) < 7:
            t_res = float(np.clip(t_res + (7-len(h0_d))*0.02, 0.72, 0.90))
            s_res, m_res = s_res*1.20, m_res*0.85

        return {"speed_gate": round(s_res,4), "mahal_gate": round(m_res,4), 
                "threshold": round(t_res,4), "phase": f"Phase {n}" if n<5 else f"Mahalanobis Mode (n={n})"}

    def _calculate_current_mahalanobis(self, inp: dict, history: list) -> float:
        """Menghitung jarak Mahalanobis input saat ini terhadap sebaran riwayat."""
        if len(history) < 5: return None
        try:
            X = np.array([self.extract(h, history) for h in history])
            mu, cov = np.mean(X,0), np.cov(X, rowvar=False) + np.eye(self.n_features)*0.01
            diff = np.array(self.extract(inp, history)) - mu
            return float(np.sqrt(max(0, diff.T @ np.linalg.inv(cov) @ diff)))
        except: return None

    def _get_mahal_history(self, history: list) -> list:
        """Menghitung riwayat jarak Mahalanobis (Internal Baseline)."""
        if len(history) < 5: return []
        try:
            X = np.array([self.extract(h, history) for h in history])
            mu, cov = np.mean(X, 0), np.cov(X, rowvar=False) + np.eye(self.n_features)*1e-3
            cinv = np.linalg.inv(cov)
            return [float(np.sqrt(max(0, (r-mu).T @ cinv @ (r-mu)))) for r in X]
        except: return []

    def _ensure_vectors(self, data: dict) -> dict:
        """Memastikan data memiliki vektor D2D (Down-to-Down) dan U2U (Up-to-Up)."""
        d, f = data.get('dwell', []), data.get('flight', [])
        if not data.get('d2d'): data['d2d'] = [float(d[i] + f[i]) for i in range(min(len(d), len(f)))]
        if not data.get('u2u'): data['u2u'] = [float(f[i] + d[i+1]) for i in range(min(len(d)-1, len(f)))]
        return data

    def _get_clean_limit(self, history: list) -> float:
        """Mendapatkan batas pembersihan data berdasarkan median dwell ketikan user."""
        if not history: return self.CLEAN_THRESHOLD
        all_d = [d for h in history for d in h.get('dwell', [])]
        return max(0.25, np.median(all_d) * 2.5) if all_d else self.CLEAN_THRESHOLD

    def _get_flight_clean_limit(self, history: list) -> float:
        """Mendapatkan batas pembersihan khusus untuk array flight/d2d/u2u.
        Flight time secara alami 3-5x lebih panjang dari dwell (jeda antar-tombol),
        sehingga membutuhkan batas yang jauh lebih longgar dari c_limit berbasis dwell.
        """
        if not history: return 0.80
        all_f = [f for h in history for f in h.get('flight', [])]
        # Gunakan 3.5x median flight, dengan lantai keras 0.80 detik.
        # Ini memastikan jeda alami seperti 0.58 detik tidak terhitung sebagai outlier.
        return max(0.80, np.median(all_f) * 3.5) if all_f else 0.80

    def _get_method_name(self, uid: str, phase: str) -> str:
        """Menentukan nama metode yang ditampilkan di log."""
        if os.path.exists(self.ai._get_model_path(uid)):
            return "Mahalanobis + OCSVM"
        return phase

    def _dtw_distance(self, s1, s2) -> float:
        """Algoritma Dynamic Time Warping untuk menghitung kemiripan deret waktu."""
        n, m = len(s1), len(s2)
        if n == 0 or m == 0: return 1.0
        dtw = np.full((n + 1, m + 1), np.inf); dtw[0, 0] = 0
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                dtw[i, j] = abs(s1[i-1] - s2[j-1]) + min(dtw[i-1, j], dtw[i, j-1], dtw[i-1, j-1])
        return float(dtw[n, m] / max(n, m))

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