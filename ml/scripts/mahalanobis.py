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
    """
    dwell = np.array(data.get('dwell', []), dtype=float)
    flight = np.array(data.get('flight', []), dtype=float)
    
    if len(dwell) == 0 or len(flight) == 0:
        return None, None
        
    s_dwell = np.sum(dwell)
    s_dwell = s_dwell if s_dwell > 0 else 1.0
    
    s_flight = np.sum(flight)
    s_flight = s_flight if s_flight > 0 else 1.0
    
    return dwell / s_dwell, flight / s_flight

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
        # 2. EARLY STAGE FINGERPRINT (Sekarang digunakan untuk SEMUA tahap)
        # ----------------------------------------------------------
        if len(history) >= 1:
            in_dwell, in_flight = extract_relative_rhythm(input_data)
            
            # LANGKAH 1: Kunci Baseline Hanya pada Data Registrasi Murni (history[-1])
            # Karena array ditarik dengan ORDER BY id DESC, data asli pendaftaran ada di ujung akhir [-1]
            baseline = history[-1]
            base_dwell, base_flight = extract_relative_rhythm(baseline)
            
            if in_dwell is not None and base_dwell is not None:
                # Syarat telak: jumlah ketukan harus konsisten
                if len(in_dwell) != len(base_dwell) or len(in_flight) != len(base_flight):
                    return {
                        "status": False, "distance": 999.0, "threshold": 0.15,
                        "reason": "Pola Ritme Tidak Cocok (Panjang Ketikan Berubah)",
                        "n_samples": len(history), "n_features": 0
                    }
                
                # LANGKAH 2: Terapkan "Hard Speed Gate" (Blokir Otomatis)
                input_speed = float(input_data.get('speed', 0))
                baseline_speed = float(baseline.get('speed', 0))
                
                # Hitung persentase deviasi kecepatan terhadap ketikan asli pertama
                speed_deviation = abs(input_speed - baseline_speed) / max(baseline_speed, 1.0)
                
                # Jika bedanya lebih dari 15%, langsung REJECT seketika!
                if speed_deviation > 0.15:
                    return {
                        "status": False, "distance": 999.0, "threshold": 0.15,
                        "reason": f"Kecepatan Abnormal (Deviasi {int(speed_deviation*100)}% dari Baseline Asli)",
                        "n_samples": len(history), "n_features": len(in_dwell) + len(in_flight)
                    }
                
                # LANGKAH 3: Hitung Jarak Ritme Relatif Ekstrem Ketat
                dist_dwell = np.sqrt(np.sum((in_dwell - base_dwell) ** 2))
                dist_flight = np.sqrt(np.sum((in_flight - base_flight) ** 2))
                
                total_dist = (dist_dwell * 0.75) + (dist_flight * 0.25)
                
                # LANGKAH 4: Pertahanan Anti Brute-Force (Kombinasi Edge-Case)
                # Jika imposter mencoba berbagai kecepatan 
                # dan tidak sengaja masuk jendela 15%, kita periksa TOTAL deviasi.
                total_deviation = total_dist + speed_deviation
                
                # 1. Turunkan Threshold Ritme Mahalanobis menjadi 0.12 (Maksimal deviasi bentuk 12%)
                rhythm_threshold = 0.12
                
                # LANGKAH 5 (BARU): Ratio Dwell-to-Flight & D2D Consistency Veto
                # Penjelasan Matematis: mean(D2D) adalah kebalikan dari Speed. Jika Speed cocok, mean(D2D) pasti cocok.
                # Untuk mendeteksi peniru yang menyamakan Speed, kita WAJIB mengecek:
                # 1. Rasio mutlak antara waktu menekan tombol (Dwell) vs waktu pindah jari (Flight).
                # 2. Konsistensi / Standar Deviasi dari D2D (Peniru biasanya ritmenya berantakan).
                
                # 5a. Dwell-to-Flight Ratio Veto
                in_dwell_raw = np.array(input_data.get('dwell', []), dtype=float)
                in_flight_raw = np.array(input_data.get('flight', []), dtype=float)
                base_dwell_raw = np.array(baseline.get('dwell', []), dtype=float)
                base_flight_raw = np.array(baseline.get('flight', []), dtype=float)
                
                if len(in_dwell_raw) > 0 and len(base_dwell_raw) > 0:
                    in_ratio = np.sum(in_dwell_raw) / max(np.sum(in_flight_raw), 0.001)
                    base_ratio = np.sum(base_dwell_raw) / max(np.sum(base_flight_raw), 0.001)
                    ratio_dev = abs(in_ratio - base_ratio) / max(base_ratio, 0.001)
                    
                    if ratio_dev > 0.25: # Toleransi rasio 25%
                        return {
                            "status": False, "distance": 999.0, "threshold": 0.20,
                            "reason": f"Rasio Dwell/Flight Anomali (Deviasi {int(ratio_dev*100)}%)",
                            "n_samples": len(history), "n_features": len(in_dwell) + len(in_flight)
                        }

                # 5b. D2D Consistency Veto (Standard Deviation)
                in_d2d_raw = np.array(input_data.get('d2d', []), dtype=float)
                base_d2d_raw = np.array(baseline.get('d2d', []), dtype=float)
                if len(in_d2d_raw) > 1 and len(base_d2d_raw) > 1:
                    in_d2d_std = np.std(in_d2d_raw, ddof=1)
                    base_d2d_std = np.std(base_d2d_raw, ddof=1)
                    
                    std_dev = abs(in_d2d_std - base_d2d_std) / max(base_d2d_std, 0.001)
                    if std_dev > 0.40: # Toleransi variance 40% (karena std dev fluktuatif)
                        return {
                            "status": False, "distance": 999.0, "threshold": 0.20,
                            "reason": f"D2D Consistency Anomali (Deviasi Varians {int(std_dev*100)}%)",
                            "n_samples": len(history), "n_features": len(in_dwell) + len(in_flight)
                        }

                # LANGKAH 6 (BARU): Key Overlap Veto (Deteksi Ketikan Tumpang Tindih)
                in_flight_raw = np.array(input_data.get('flight', []), dtype=float)
                base_flight_raw = np.array(baseline.get('flight', []), dtype=float)
                if len(in_flight_raw) > 0 and len(base_flight_raw) > 0:
                    base_has_overlap = np.any(base_flight_raw < 0)
                    in_has_overlap = np.any(in_flight_raw < 0)
                    # Jika baseline menggelinding (ada overlap), tapi input kaku (tidak ada overlap sama sekali)
                    if base_has_overlap and not in_has_overlap:
                        return {
                            "status": False, "distance": 999.0, "threshold": 0.15,
                            "reason": "Key Overlap Veto (Gaya mengetik kaku, tidak menggelinding)",
                            "n_samples": len(history), "n_features": len(in_dwell) + len(in_flight)
                        }
                
                # KEPUTUSAN AKHIR: Batas Gesekan Total menjadi 0.18
                # Artinya: Jika ritme pas-pasan di 0.11, maka kecepatan hanya boleh meleset 7%
                if total_dist <= rhythm_threshold and total_deviation <= 0.18:
                    return {
                        "status": True, "distance": float(total_dist), "threshold": float(rhythm_threshold),
                        "reason": "Pola Ritme Cocok (Early-Stage Fingerprint)",
                        "n_samples": len(history), "n_features": len(in_dwell) + len(in_flight)
                    }
                else:
                    return {
                        "status": False, "distance": float(total_dist), "threshold": float(rhythm_threshold),
                        "reason": f"Pola Ritme Tidak Cocok (Gesekan Total: {total_deviation:.2f})",
                        "n_samples": len(history), "n_features": len(in_dwell) + len(in_flight)
                    }
            else:
                return {
                    "status": False, "distance": 999.0, "threshold": 0.15,
                    "reason": "Data Input Tidak Valid", "n_samples": len(history), "n_features": 0
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
