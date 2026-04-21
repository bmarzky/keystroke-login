import sys
import json
import numpy as np
from sklearn.covariance import LedoitWolf

# ============================================================
# FEATURE EXTRACTION: Per-keystroke arrays → 8-dim summary
# ============================================================
# Sebelumnya: dwell(n) + flight(n-1) + d2d(n-1) + u2u(n-1)
#             = 25–45 dimensi tergantung panjang password → FATAL
#
# Sekarang: mean + std per tipe = 8 dimensi TETAP
#   [mean_dwell, std_dwell, mean_flight, std_flight,
#    mean_d2d,   std_d2d,   mean_u2u,   std_u2u]
#
# Keuntungan:
#   1. Dimensi TETAP → tidak sensitif panjang vector / typo
#   2. 8 << 3 samples → rasio sehat untuk Mahalanobis
#   3. Hard length-filter tidak lagi dibutuhkan
# ============================================================

N_FEATURES = 8  # Selalu 8 dimensi, tidak pernah berubah

def extract_features(data: dict) -> list:
    """
    Mengkompres raw keystroke arrays menjadi 8 statistical features.
    Aman untuk array kosong atau panjang berbeda.
    """
    features = []
    for key in ['dwell', 'flight', 'd2d', 'u2u']:
        arr = np.array(data.get(key, []), dtype=float)
        if len(arr) >= 2:
            features.append(float(np.mean(arr)))
            features.append(float(np.std(arr, ddof=1)))
        elif len(arr) == 1:
            features.append(float(arr[0]))
            features.append(0.0)   # std = 0 jika hanya 1 data poin
        else:
            features.append(0.0)   # Tidak ada data → impute nol
            features.append(0.0)
    return features  # Panjang selalu N_FEATURES = 8

def extract_relative_rhythm(data: dict) -> tuple:
    """
    Mengekstrak raw array untuk dwell dan flight, 
    lalu menormalisasinya (membaginya dengan total waktu)
    sehingga membentuk 'Relative Rhythm' persentase.
    Juga mengembalikan total waktu absolut sebagai Speed Anchor.
    """
    dwell = np.array(data.get('dwell', []), dtype=float)
    flight = np.array(data.get('flight', []), dtype=float)
    
    if len(dwell) == 0 or len(flight) == 0:
        return None, None, None
        
    s_dwell = np.sum(dwell) if np.sum(dwell) > 0 else 1.0
    s_flight = np.sum(flight) if np.sum(flight) > 0 else 1.0
    
    return dwell / s_dwell, flight / s_flight, (s_dwell + s_flight)

def calculate_mahalanobis(json_path: str) -> dict:
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        input_data = data.get('input', {})
        history    = data.get('history', [])

        # ----------------------------------------------------------
        # 1. Tidak ada riwayat sama sekali
        # ----------------------------------------------------------
        if len(history) < 1:
            return {
                "status": False, "distance": 9996.0, "threshold": 0.0,
                "reason": "Tidak ada riwayat ketikan (enroll dulu)"
            }

        # ----------------------------------------------------------
        # 2. EARLY STAGE FINGERPRINT (Relative Rhythm + Speed Anchor)
        # ----------------------------------------------------------
        if 1 <= len(history) < 5:
            in_dwell, in_flight, in_time = extract_relative_rhythm(input_data)
            if in_dwell is not None:
                distances = []
                
                for hist in history:
                    h_dwell, h_flight, h_time = extract_relative_rhythm(hist)
                    # Syarat telak: jumlah ketukan (panjang array) harus sama persis
                    if h_dwell is None or len(in_dwell) != len(h_dwell) or len(in_flight) != len(h_flight):
                        distances.append(999.0)
                        continue
                        
                    # Euclidean Jarak Ritme (Persentase)
                    dist_dwell = np.sqrt(np.sum((in_dwell - h_dwell) ** 2))
                    dist_flight = np.sqrt(np.sum((in_flight - h_flight) ** 2))
                    
                    # Absolute Speed Anchor: Penalti jika kecepatan mutlak (detik) beda
                    time_ratio = min(in_time, h_time) / max(in_time, h_time)
                    time_penalty = 1.0 - time_ratio 
                    
                    # PERBAIKAN STRIKE: 
                    # Penalti jauh lebih agresif (1.5x) untuk Absolute Speed.
                    # Jika speed beda 15%, skor eror langsung +0.22, pasti terhempas.
                    rhythm_dist = (dist_dwell * 0.75) + (dist_flight * 0.25)
                    total_dist = rhythm_dist + (time_penalty * 1.5)
                    distances.append(total_dist)
                
                if not distances:
                    best_distance = 9999.0
                else:
                    # PERBAIKAN POISONING: 
                    # Jangan gunakan nilai MIN(), karena jika penyusup lolos 1x saja,
                    # dia akan cocok dengan sidik jarinya sendiri (0.00).
                    # Gunakan MEAN() sehingga input selalu diadu juga terhadap anchor asli
                    best_distance = float(np.mean(distances))
                
                # Threshold dinaikkan ke 0.18 karena ada tambahan Absolute Speed Penalty
                rhythm_threshold = 0.18
                
                if best_distance <= rhythm_threshold:
                    return {
                        "status": True,
                        "distance": float(best_distance),
                        "threshold": float(rhythm_threshold),
                        "reason": "Pola Ritme Cocok (Early-Stage Fingerprint)",
                        "n_samples": len(history),
                        "n_features": len(in_dwell) + len(in_flight)
                    }
                else:
                    return {
                        "status": False,
                        "distance": float(best_distance) if best_distance != 9999.0 else 0.0,
                        "threshold": float(rhythm_threshold),
                        "reason": "Pola Ritme Tidak Cocok (Early-Stage Fingerprint)",
                        "n_samples": len(history),
                        "n_features": len(in_dwell) + len(in_flight) if in_dwell is not None else 0
                    }

        # ----------------------------------------------------------
        # 3. Ekstrak fitur input → 8-dim vector (Gunakan untuk > 4 data)
        # ----------------------------------------------------------
        input_vector = np.array(extract_features(input_data), dtype=float)

        # ----------------------------------------------------------
        # 3. Ekstrak fitur historis
        #    TIDAK ADA hard-length filter!
        #    extract_features() sudah handle panjang berbeda dengan aman.
        # ----------------------------------------------------------
        samples = []
        for hist in history:
            try:
                vec = extract_features(hist)
                samples.append(vec)
            except Exception:
                continue

        n_samples = len(samples)
        if n_samples < 1:
            return {
                "status": False, "distance": 9998.0, "threshold": 0.0,
                "reason": "Tidak ada sampel historis yang valid"
            }

        samples = np.array(samples, dtype=float)  # shape: (n, 8)

        distance           = 0.0
        calculated_threshold = 0.0

        # ----------------------------------------------------------
        # 4. Kalkulasi jarak berdasarkan jumlah sampel
        # ----------------------------------------------------------
        if n_samples >= 3:
            # Ledoit-Wolf sangat stabil untuk 8 dim + ≥3 sampel
            lw = LedoitWolf(assume_centered=False)
            lw.fit(samples)
            mean_vector = lw.location_
            inv_cov     = lw.precision_

            diff     = input_vector - mean_vector
            distance = float(np.sqrt(np.clip(diff @ inv_cov @ diff, 0.0, None)))

            # Threshold adaptif dari distribusi jarak historis
            hist_dists = []
            for s in samples:
                d = s - mean_vector
                hist_dists.append(float(np.sqrt(np.clip(d @ inv_cov @ d, 0.0, None))))

            mean_dist = float(np.mean(hist_dists))
            # ddof=1 agar std tidak biased; jika hanya 1 nilai, fallback 50% mean
            std_raw   = float(np.std(hist_dists, ddof=1)) if len(hist_dists) > 1 else mean_dist * 0.5

            # Minimum variability guard:
            # Enrollment awal sering dilakukan dgn hati-hati → std_raw sangat kecil.
            # Tanpa guard ini, threshold kolaps ke ~mean saja → ketikan natural REJECT.
            # Guard: std minimal 35% dari mean (slack relatif, bukan absolut).
            min_std  = mean_dist * 0.35
            std_dist = max(std_raw, min_std)

            # Z=3.0 (99.7% confidence interval) – lebih gentle dari 2.5
            calculated_threshold = mean_dist + (3.0 * std_dist)

        elif n_samples == 2:
            # Belum cukup untuk kovarians: pakai Euclidean + inter-sample distance
            mean_vector = np.mean(samples, axis=0)
            diff        = input_vector - mean_vector
            distance    = float(np.sqrt(np.sum(diff ** 2)))

            inter_dist           = float(np.sqrt(np.sum((samples[0] - samples[1]) ** 2)))
            calculated_threshold = max(inter_dist * 2.0, 1.5)

        else:  # n_samples == 1 – single reference
            mean_vector = samples[0]
            diff        = input_vector - mean_vector
            distance    = float(np.sqrt(np.sum(diff ** 2)))
            # Threshold murni dari floor, calculated = 0
            calculated_threshold = 0.0

        # ----------------------------------------------------------
        # 5. Dynamic floor threshold (memaafkan saat data masih sedikit)
        #    Floor = sqrt(N_FEATURES) × multiplier
        #          = sqrt(8)          × multiplier
        #          ≈ 2.83             × multiplier
        #
        # CATATAN: floor_multiplier sengaja TIDAK turun terlalu agresif.
        # Mahalanobis 8-dim cukup diskriminatif; threshold rendah bukan
        # tanda akurasi, tapi tanda model overfit ke enrollment awal.
        # ----------------------------------------------------------
        if n_samples < 3:
            floor_multiplier = 3.5   # Sangat pemaaf (1 atau 2 sampel)
        elif n_samples < 6:
            floor_multiplier = 2.5   # Pemaaf menengah
        elif n_samples < 10:
            floor_multiplier = 2.0   # Mulai ketat
        else:
            floor_multiplier = 1.8   # Stabil – TIDAK turun ke 1.2 (terlalu ketat)

        dynamic_floor    = float(np.sqrt(N_FEATURES)) * floor_multiplier
        final_threshold  = float(max(calculated_threshold, dynamic_floor))
        is_match         = bool(distance <= final_threshold)

        return {
            "status":    is_match,
            "distance":  float(distance),
            "threshold": final_threshold,
            "reason":    (
                "Pola Cocok (Stat-Mahalanobis 8-dim)"
                if is_match else
                "Pola Tidak Cocok (Terlalu Menyimpang)"
            ),
            "n_samples":  n_samples,
            "n_features": N_FEATURES
        }

    except Exception as e:
        return {
            "status": False, "distance": 9999.0, "threshold": 0.0,
            "reason": f"Python Exception: {str(e)}"
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": False, "distance": 9999.0, "threshold": 0.0,
            "reason": "No input file provided"
        }))
        sys.exit(1)

    result = calculate_mahalanobis(sys.argv[1])
    print(json.dumps(result))
