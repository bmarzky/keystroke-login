import logging
import numpy as np
from src.engine.extractors.features import FeatureExtractor

_logger = logging.getLogger(__name__)

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
        limit = Q3 + 2.0 * (Q3 - Q1) # Increased multiplier from 1.5 to 2.0
        return float(max(0.30, limit))

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
        except np.linalg.LinAlgError:
            # Matrix singular meski sudah di-regularisasi — kondisi numerik yang diketahui dan dapat ditoleransi.
            # Kembalikan None agar caller jatuh kembali ke mode tanpa Mahalanobis gate.
            return None
        except (ValueError, TypeError) as exc:
            # Data fitur rusak atau memiliki dimensi yang tidak konsisten.
            _logger.warning("calculate_current_mahalanobis: data error — %s", exc)
            return None
        except Exception as exc:
            # Exception tak terduga (bukan numerik). Di-log sebagai ERROR agar terdeteksi.
            _logger.error("calculate_current_mahalanobis: unexpected error — %s", exc, exc_info=True)
            return None

    def get_mahal_history(self, history: list) -> list:
        """Menghitung riwayat jarak Mahalanobis menggunakan pendekatan shrinkage."""
        if len(history) < 5: return []
        try:
            X = np.array([self.extractor.extract(h, history) for h in history])
            mu = np.mean(X, axis=0)
            cov = np.cov(X, rowvar=False) + np.eye(self.n_features) * 0.01
            pinv_cov = np.linalg.pinv(cov)
            return [float(np.sqrt(max(0, (r-mu).T @ pinv_cov @ (r-mu)))) for r in X]
        except np.linalg.LinAlgError:
            # Matrix singular — kondisi yang diketahui; kembalikan list kosong agar
            # calculate_gates tetap berjalan tanpa riwayat Mahalanobis.
            return []
        except (ValueError, TypeError) as exc:
            # Data fitur tidak konsisten antar sampel riwayat.
            _logger.warning("get_mahal_history: data error — %s", exc)
            return []
        except Exception as exc:
            # Exception tak terduga di-log sebagai ERROR untuk memudahkan investigasi.
            _logger.error("get_mahal_history: unexpected error — %s", exc, exc_info=True)
            return []

    def calculate_speed_metrics(self, inp: dict, history: list) -> tuple:
        # Gunakan .get() dengan fallback [] agar tidak KeyError jika key tidak ada di payload
        in_v  = np.array(inp.get('dwell',  []), dtype=float)
        in_fv = np.array(inp.get('flight', []), dtype=float)

        c_limit = self.get_clean_limit(history)
        # Gunakan flight-specific limit — dwell limit TIDAK tepat untuk flight time
        # karena distribusi flight time bisa jauh lebih besar dari dwell time.
        f_limit = self.get_flight_clean_limit(history)

        v_clean  = in_v[in_v   < c_limit] if len(in_v)  > 0 else in_v
        fv_clean = in_fv[in_fv < f_limit] if len(in_fv) > 0 else in_fv

        # Guard: jika outlier filter mengosongkan array, np.mean([]) = nan.
        # nan dalam pembagi menyebabkan in_speed = nan → s_dev = nan →
        # is_speed_anomaly selalu False (nan > gate == False), sehingga
        # anomali kecepatan ekstrem lolos tanpa terdeteksi.
        # Fall-back: gunakan speed dari payload jika data bersih tidak cukup.
        has_clean_dwell  = len(v_clean)  >= 3
        has_clean_flight = len(fv_clean) >= 1
        if has_clean_dwell and has_clean_flight:
            mean_sum = float(np.mean(v_clean) + np.mean(fv_clean))
            # Extra guard: denominator nol seharusnya tidak mungkin karena
            # nilai dwell/flight selalu positif, tapi dijaga untuk keamanan.
            in_speed = float(60.0 / mean_sum) if mean_sum > 1e-9 else float(inp.get('speed', 0))
        else:
            # Array bersih terlalu kecil — gunakan speed yang dilaporkan frontend.
            # Ini adalah degradasi yang disengaja: lebih baik pakai speed kasar
            # daripada menghasilkan nan yang merusak deteksi anomali.
            _logger.debug(
                "calculate_speed_metrics: clean arrays too small "
                "(dwell=%d, flight=%d) — falling back to payload speed",
                len(v_clean), len(fv_clean)
            )
            in_speed = float(inp.get('speed', 0))

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
        # Menghitung bobot anchor secara dinamis (Optimasi Cold-Start < 50)
        if n < 5:
            anchor_w = 0.95  # Fase Inisiasi (Sangat Terikat Data Registrasi)
        elif n < 20:
            anchor_w = 0.80  # Fase Observasi (Mulai Mengikuti Variansi)
        elif n < 50:
            anchor_w = 0.65  # Fase Konsolidasi (Menjelang Matang)
        else:
            anchor_w = 0.60  # Batas Akhir Penelitian (Mature Window)
            
        # Emergency Recovery: Jika Rolling CV tiba-tiba berantakan (Anomali), tarik bobot ke Anchor
        if rolling_cv > anchor_cv * 1.5:
            anchor_w = min(0.90, anchor_w + 0.20)
            
        cv = (anchor_cv * anchor_w) + (rolling_cv * (1.0 - anchor_w))

        # 3. Base Gates Calculation - Relaxed Start
        g = {
            "s": 0.2 + cv * 0.4,
            "m": 1.5 + cv * 5.0,
            "t": 0.65 - cv * 0.05  # Sedikit lebih tinggi dari sebelumnya
        }

        # 4. Dynamic Refinement & Stability Bonus
        stability_bonus = 0.0
        if n >= 5:
            speeds = [float(h.get('speed', 0)) for h in history]
            g["s"] = float(np.clip(3.0 * np.std(speeds) / max(np.mean(speeds), 1.0), 0.35, 0.75))
            
            if mahal_dists and len(mahal_dists) >= 3:
                # Mekanisme Adaptif Murni: Menghitung stabilitas perilaku
                m_avg = float(np.mean(mahal_dists))
                progress = np.clip((n - 5) / 45.0, 0.0, 1.0)
                
                # Bonus Stabilitas: Dikurangi agar tidak terlalu memberatkan user (0.01 instead of 0.03)
                stability_bonus = max(0.0, (4.0 - m_avg) * 0.01)
                
                # Penyesuaian bertahap (progress) dikurangi (0.05 instead of 0.12)
                progress_inc = progress * 0.05
                
                # Threshold Akhir = Dasar (0.65) + Kematangan Data + Bonus Konsistensi - Penalti Variansi
                g["t"] = 0.65 + progress_inc + stability_bonus - (cv * 0.08)

        # 5. HARD CAPPING (Safety Belt)
        # Cold Start Calibration: Transisi dibuat lebih halus untuk riset < 50 sampel.
        if n == 1: T_FLOOR = 0.80
        elif n < 5: T_FLOOR = 0.82
        elif n < 10: T_FLOOR = 0.78 
        elif n < 30: T_FLOOR = 0.74 
        elif n < 50: T_FLOOR = 0.70 # Batas bawah diperketat agar riset lebih menantang
        else: T_FLOOR = 0.68        # Threshold minimal standar final        
        T_CEILING = 0.78
        
        # Turbo Scaling: Jika CPM tinggi, berikan ruang nafas lebih pada gerbang
        avg_speed = np.median([h.get('speed', 350) for h in history]) if history else 350
        turbo_factor = 1.2 if avg_speed > 400 else 1.0
        
        # Batas minimum (Floor) naik ke 5.0 jika pengetikan cepat
        m_floor = 5.0 if turbo_factor > 1.0 else 4.5

        t_res = float(np.clip(g["t"], T_FLOOR, T_CEILING))
        s_res = float(np.clip(g["s"], 0.25 if n < 5 else 0.40, 0.75)) # Lebih ketat di awal (25%)
        m_res = float(np.clip(g["m"] * turbo_factor, m_floor, self.MAX_MAHAL_DIST))

        return {
            "speed_gate": round(s_res, 4), 
            "mahal_gate": round(m_res, 4), 
            "threshold": round(t_res, 4), 
            "cv_hybrid": round(cv, 4),
            "anchor_weight": round(anchor_w, 2),
            "stability_bonus": round(stability_bonus, 4),
            "phase": f"Cold-Start Analysis Mode (n={n}/50)"
        }