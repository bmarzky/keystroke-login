import sys
import json
import numpy as np
import warnings

warnings.filterwarnings('ignore')

N_FEATURES = 8

def extract_features(data: dict) -> list:
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
    features = [float(f) if np.isfinite(f) else 0.0 for f in features]
    return features

def calculate_mahalanobis(json_path: str) -> dict:
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        input_data = data.get('input', {})
        history    = data.get('history', [])

        if len(history) < 1:
            return {
                "status": False, "distance": 0.0, "score": 0.0, "threshold": 0.55,
                "reason": "Tidak ada riwayat ketikan (enroll dulu)"
            }

        n_history = len(history)
        # Threshold diperketat lagi (Titanium Hardened)
        # 0.63 untuk tahap awal agar teman/imposter tidak mudah tembus
        threshold = 0.63 if n_history < 5 else 0.70 

        in_dwell_raw = np.array(input_data.get('dwell', []), dtype=float)
        in_flight_raw = np.array(input_data.get('flight', []), dtype=float)
        input_speed = float(input_data.get('speed', 0))

        if np.sum(in_dwell_raw) < 0.01 or np.sum(in_flight_raw) < 0.01:
            return {
                "status": False, "distance": 0.0, "score": 0.0, "threshold": threshold,
                "reason": "Data tidak valid / terlalu kecil"
            }

        # 🔹 HARD VETO GUARD (Mencegah bot / gaya ngetik ekstrim beda)
        primary_base = history[0]
        pb_speed = float(primary_base.get('speed', 0))
        pb_speed_dev = abs(input_speed - pb_speed) / max(pb_speed, 1.0)
        
        if pb_speed_dev > 0.40: # Perketat dari 60% ke 40%
             return {
                "status": False, "distance": 0.0, "score": 0.0, "threshold": threshold,
                "reason": f"Sistem Gate: Kecepatan Tidak Wajar (Deviasi {pb_speed_dev:.1%})"
            }

        # 🔹 SCORING SYSTEM (MULTI-BASELINE FUSION)
        # Bobot TITANIUM: Korelasi (30%), Ritme (20%), Speed (10%), Rasio (10%), Stabilitas (15%), Flow (15%)
        w_rhythm, w_corr, w_speed, w_ratio, w_stability, w_flow = 0.20, 0.30, 0.10, 0.10, 0.15, 0.15
        baselines = history[:5]
        all_scores = []

        for baseline in baselines:
            # Load Full Spectrum (4 Tipe Data)
            b_data = {
                'dwell': np.array(baseline.get('dwell', []), dtype=float),
                'flight': np.array(baseline.get('flight', []), dtype=float),
                'd2d': np.array(baseline.get('d2d', []), dtype=float),
                'u2u': np.array(baseline.get('u2u', []), dtype=float)
            }
            baseline_speed = float(baseline.get('speed', 0))

            # Sinkronisasi Panjang Array (Auto-Align)
            # Kita bandingkan 4 tipe sekaligus
            scores_r = []
            scores_c = []
            
            for key in ['dwell', 'flight', 'd2d', 'u2u']:
                in_arr = np.array(input_data.get(key, []), dtype=float)
                base_arr = b_data[key]
                
                # Truncate (abaikan Enter jika ada)
                mlen = min(len(in_arr), len(base_arr)) - 1
                if mlen < 3: continue
                
                in_v = in_arr[:mlen]
                bs_v = base_arr[:mlen]

                # B. Rhythm Score (Euclidean) per tipe
                # Gunakan absolut untuk normalisasi agar mendukung Overlap (angka negatif)
                norm_in = in_v / max(np.sum(np.abs(in_v)), 0.001)
                norm_bs = bs_v / max(np.sum(np.abs(bs_v)), 0.001)
                dist = np.sqrt(np.sum((norm_in - norm_bs) ** 2))
                # Mapping: Jarak 0.18 dianggap skor 0 (Lebih Sensitif)
                scores_r.append(max(0.0, 1.0 - (dist / 0.18)))

                # C. Correlation Score (Pearson)
                if len(in_v) > 2 and np.std(in_v) > 0 and np.std(bs_v) > 0:
                    c_val = np.corrcoef(in_v, bs_v)[0, 1]
                    correlation_score = max(0.0, c_val) if np.isfinite(c_val) else 0.5
                else:
                    correlation_score = 0.5
                scores_c.append(correlation_score)

            if not scores_r: continue

            # Rata-rata skor dari semua komponen yang tersedia
            rhythm_score = np.mean(scores_r)
            correlation_score = np.mean(scores_c)

            # A. Speed Score (Global)
            speed_dev = abs(input_speed - baseline_speed) / max(baseline_speed, 1.0)
            speed_score = max(0.0, 1.0 - (speed_dev / 0.50))

            # D. Ratio Score (Anatomi Jari - Tetap menggunakan Dwell vs Flight)
            in_ratio = np.sum(input_data.get('dwell', [])) / max(np.sum(input_data.get('flight', [])), 0.01)
            base_ratio = np.sum(baseline.get('dwell', [])) / max(np.sum(baseline.get('flight', [])), 0.01)
            ratio_dev = abs(in_ratio - base_ratio) / max(base_ratio, 0.01)
            ratio_score = max(0.0, 1.0 - (ratio_dev / 0.40)) # Perketat ke 40%

            # E. Stability Score (Consistency - BARU)
            # Menghitung apakah tingkat "gugup/jitter" sama dengan baseline
            in_jitter = np.std(in_dwell_raw) / max(np.mean(in_dwell_raw), 0.01)
            base_dwell = np.array(baseline.get('dwell', []), dtype=float)
            base_jitter = np.std(base_dwell) / max(np.mean(base_dwell), 0.01)
            jitter_dev = abs(in_jitter - base_jitter)
            stability_score = max(0.0, 1.0 - (jitter_dev / 0.30))

            # F. Flow Score (Transitional Acceleration - BARU)
            # Mengukur percepatan/perlambatan antar tombol (np.diff)
            in_flight = np.array(input_data.get('flight', []), dtype=float)
            base_flight = np.array(baseline.get('flight', []), dtype=float)
            flen = min(len(in_flight), len(base_flight))
            if flen > 3:
                in_acc = np.diff(in_flight[:flen])
                bs_acc = np.diff(base_flight[:flen])
                if np.std(in_acc) > 0 and np.std(bs_acc) > 0:
                    c_acc = np.corrcoef(in_acc, bs_acc)[0, 1]
                    flow_score = max(0.0, c_acc) if np.isfinite(c_acc) else 0.5
                else:
                    flow_score = 0.5
            else:
                flow_score = 0.5

            # FUSION SCORE
            final_b_score = (w_rhythm * rhythm_score) + \
                            (w_corr * correlation_score) + \
                            (w_speed * speed_score) + \
                            (w_ratio * ratio_score) + \
                            (w_stability * stability_score) + \
                            (w_flow * flow_score)
            
            all_scores.append(final_b_score)

        if not all_scores:
            return {
                "status": False, "distance": 0.0, "score": 0.0, "threshold": threshold,
                "reason": "Data Ketikan Terlalu Pendek atau Tidak Valid"
            }

        # 🔹 LOGIKA ADAPTIF: Ambil Rata-rata dari 2 gaya ngetik terbaikmu!
        # Manusia tidak konsisten. Jika 2 history cocok, biarkan masuk!
        all_scores.sort(reverse=True)
        top_k = all_scores[:2] if all_scores else [0.0]
        final_score = float(np.mean(top_k))
        
        # Penjaga: Pastikan tidak NaN agar JSON tidak crash
        if not np.isfinite(final_score):
            final_score = 0.0

        # 🔹 HYBRID LAYER: MAHALANOBIS (Aktif jika data >= 5)
        if len(history) >= 5:
            try:
                X = np.array([extract_features(h) for h in history])
                mu = np.mean(X, axis=0)
                cov = np.cov(X, rowvar=False) + np.eye(N_FEATURES) * 1e-3
                inv_cov = np.linalg.inv(cov)
                
                x_input = np.array(extract_features(input_data))
                diff = x_input - mu
                mahal_dist = np.sqrt(max(0, diff.T @ inv_cov @ diff))
                
                # Konversi jarak Mahalanobis ke Skor 0-1 yang ramah
                mahal_score = max(0.0, 1.0 - (mahal_dist / 10.0)) 
                
                # Blend: 80% Heuristic Fusion + 20% Mahalanobis AI
                final_score = (0.8 * final_score) + (0.2 * mahal_score)
            except:
                pass 

        # 🔹 ANTI-POISONING GUARD: 
        # Jangan update history jika skor "pas-pasan" (mencegah data imposter masuk)
        should_update = (final_score > 0.75) or (final_score > threshold and n_history < 3)

        return {
            "status": final_score >= threshold,
            "score": round(final_score, 4),
            "threshold": threshold,
            "should_update_history": should_update, 
            "reason": f"Score Fusion: {final_score:.2f} | Status: {'ACCEPT' if final_score >= threshold else 'REJECT'}",
            "n_features": 8,
            "n_samples": n_history
        }

    except Exception as e:
        return {
            "status": False, "distance": 0.0, "score": 0.0, "threshold": 0.0,
            "reason": f"Python Exception: {str(e)}"
        }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"status": False, "reason": "No input file provided"}))
        sys.exit(1)
    result = calculate_mahalanobis(sys.argv[1])
    print(json.dumps(result))