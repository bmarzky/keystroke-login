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
        # 2. Ekstrak fitur input → 8-dim vector
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
            std_dist  = float(np.std(hist_dists, ddof=1)) if len(hist_dists) > 1 else mean_dist * 0.5

            # Z=2.5 – lebih gentle dari 3.0 karena dim sudah kecil & sehat
            calculated_threshold = mean_dist + (2.5 * std_dist)

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
        # ----------------------------------------------------------
        if n_samples < 3:
            floor_multiplier = 3.5   # Sangat pemaaf (1 atau 2 sampel)
        elif n_samples < 6:
            floor_multiplier = 2.5   # Pemaaf menengah
        elif n_samples < 10:
            floor_multiplier = 1.8   # Mulai ketat
        else:
            floor_multiplier = 1.2   # Stabil + akurat

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
