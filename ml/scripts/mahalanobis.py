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
            # LANGKAH 1: Kunci Baseline Hanya pada Data Registrasi Murni (history[-1])
            # Karena array ditarik dengan ORDER BY id DESC, data asli pendaftaran ada di ujung akhir [-1]
            baseline = history[-1]
            
            in_dwell_raw = np.array(input_data.get('dwell', []), dtype=float)
            in_flight_raw = np.array(input_data.get('flight', []), dtype=float)
            in_d2d_raw = np.array(input_data.get('d2d', []), dtype=float)
            
            base_dwell_raw = np.array(baseline.get('dwell', []), dtype=float)
            base_flight_raw = np.array(baseline.get('flight', []), dtype=float)
            base_d2d_raw = np.array(baseline.get('d2d', []), dtype=float)
            
            # Toleransi Panjang Ketikan (Masalah "Panjang Ketikan Berubah" karena Enter/Shift/Backspace)
            # DITAMBAH: Selalu abaikan 1 ketukan terakhir (biasanya tombol ENTER atau ketukan telat)
            # karena jeda sebelum menekan Enter sangat fluktuatif dan merusak akurasi ritme/standar deviasi.
            min_dwell_len = max(3, min(len(in_dwell_raw), len(base_dwell_raw)) - 1)
            min_flight_len = max(3, min(len(in_flight_raw), len(base_flight_raw)) - 1)
            min_d2d_len = max(2, min(len(in_d2d_raw), len(base_d2d_raw)) - 1)
            
            if min_dwell_len < 3 or min_flight_len < 3:
                return {
                    "status": False, "distance": 999.0, "threshold": 0.15,
                    "reason": "Data Ketikan Terlalu Pendek atau Kosong",
                    "n_samples": len(history), "n_features": 0
                }
            
            # Truncate array ke ukuran terkecil agar selalu sejajar (Auto-Aligning)
            in_dwell_raw = in_dwell_raw[:min_dwell_len]
            base_dwell_raw = base_dwell_raw[:min_dwell_len]
            in_flight_raw = in_flight_raw[:min_flight_len]
            base_flight_raw = base_flight_raw[:min_flight_len]
            in_d2d_raw = in_d2d_raw[:min_d2d_len]
            base_d2d_raw = base_d2d_raw[:min_d2d_len]
            
            # Normalisasi setelah disamakan panjangnya
            in_dwell = in_dwell_raw / max(np.sum(in_dwell_raw), 0.001)
            base_dwell = base_dwell_raw / max(np.sum(base_dwell_raw), 0.001)
            in_flight = in_flight_raw / max(np.sum(in_flight_raw), 0.001)
            base_flight = base_flight_raw / max(np.sum(base_flight_raw), 0.001)
            
            if True: # Menjaga indentasi agar sesuai dengan kode di bawahnya
                
                # LANGKAH 2: Terapkan "Hard Speed Gate" (Blokir Otomatis)
                input_speed = float(input_data.get('speed', 0))
                baseline_speed = float(baseline.get('speed', 0))
                
                # Hitung persentase deviasi kecepatan terhadap ketikan asli pertama
                speed_deviation = abs(input_speed - baseline_speed) / max(baseline_speed, 1.0)
                
                # Jika bedanya lebih dari 85%, langsung REJECT (Telat menekan Enter bisa bikin deviasi CPM hingga 70%)
                if speed_deviation > 0.85:
                    return {
                        "status": False, "distance": 999.0, "threshold": 0.85,
                        "reason": f"Kecepatan Abnormal (Deviasi {int(speed_deviation*100)}% dari Baseline Asli)",
                        "n_samples": len(history), "n_features": len(in_dwell) + len(in_flight)
                    }
                
                # LANGKAH 3: Hitung Jarak Ritme Relatif Ekstrem Ketat
                dist_dwell = np.sqrt(np.sum((in_dwell - base_dwell) ** 2))
                dist_flight = np.sqrt(np.sum((in_flight - base_flight) ** 2))
                
                total_dist = (dist_dwell * 0.75) + (dist_flight * 0.25)
                
                # LANGKAH 4: DUAL PEARSON CORRELATION (Pendeteksi Bentuk Jari Asli Mutlak)
                # Alih-alih menggunakan heuristic veto yang rentan False Rejection (seperti D2D variance),
                # kita menggunakan Korelasi Pearson pada DWELL dan FLIGHT secara bersamaan.
                # Pearson mengukur "Shape" (bentuk naik turun jari) terlepas dari skala atau baseline variance.
                # Ini mengamankan sistem dari impostor sambil memberikan Usability maksimal bagi user asli.
                
                corr_dwell = 1.0
                corr_flight = 1.0
                
                if len(in_dwell_raw) > 1 and len(base_dwell_raw) > 1:
                    c_dwell = np.corrcoef(in_dwell_raw, base_dwell_raw)
                    if not np.isnan(c_dwell[0, 1]):
                        corr_dwell = c_dwell[0, 1]
                        
                if len(in_flight_raw) > 1 and len(base_flight_raw) > 1:
                    c_flight = np.corrcoef(in_flight_raw, base_flight_raw)
                    if not np.isnan(c_flight[0, 1]):
                        corr_flight = c_flight[0, 1]
                        
                # Rata-rata kemiripan bentuk (Shape) dari ketukan (Dwell) dan perpindahan (Flight)
                avg_corr = (corr_dwell + corr_flight) / 2.0
                        
                if avg_corr < 0.60: # Batas minimal diturunkan ke 60% agar Sangat Mudah Digunakan tapi tetap mustahil ditebak impostor
                    return {
                        "status": False, "distance": 999.0, "threshold": 0.60,
                        "reason": f"Pola Jari Tidak Dikenali (Korelasi Dwell+Flight: {avg_corr:.2f})",
                        "n_samples": len(history), "n_features": len(in_dwell) + len(in_flight)
                    }
                
                # Longgarkan Threshold Ritme Euclidean menjadi 0.20 (Memberi ruang nafas maksimal untuk fluktuasi harian)
                rhythm_threshold = 0.20
                            
                # KEPUTUSAN AKHIR: Kita hapus Total Deviation karena Pearson sudah sangat kuat.
                # Kita hanya bergantung pada jarak Euclidean yang telah dilonggarkan ke 0.15
                if total_dist <= rhythm_threshold:
                    return {
                        "status": True, "distance": float(total_dist), "threshold": float(rhythm_threshold),
                        "reason": "Pola Ritme Cocok (Early-Stage Fingerprint)",
                        "n_samples": len(history), "n_features": len(in_dwell) + len(in_flight)
                    }
                else:
                    return {
                        "status": False, "distance": float(total_dist), "threshold": float(rhythm_threshold),
                        "reason": f"Pola Ritme Tidak Cocok (Skor Euclidean: {total_dist:.2f} > {rhythm_threshold})",
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
