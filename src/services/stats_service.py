import numpy as np

def calculate_dashboard_stats(current_features, history=None):
    """
    Menghitung statistik performa ketikan untuk tampilan dashboard.
    Sekarang menyertakan perbandingan dengan riwayat untuk stabilitas yang lebih akurat.
    """
    stats = {
        'avg_dwell': 0,
        'avg_flight': 0,
        'wpm': 0,
        'stability': 0
    }
    
    if not current_features or not current_features.get('dwell'):
        return stats

    dwell = current_features['dwell']
    flight = current_features.get('flight', [])
    
    cnt_d = len(dwell)
    sum_d = sum(dwell)
    sum_f = sum(flight)
    
    # 1. Average Dwell (detik)
    stats['avg_dwell'] = sum_d / cnt_d
    
    # 2. Average Flight (detik)
    if flight:
        stats['avg_flight'] = sum_f / len(flight)
    
    # 3. WPM (Words Per Minute)
    total_time_seconds = sum_d + sum_f
    if total_time_seconds > 0:
        stats['wpm'] = (cnt_d / 5) / (total_time_seconds / 60)
    
    # 4. Stability (Biometric Consistency)
    # Jika ada riwayat, kita hitung korelasi dengan rata-rata riwayat.
    # Jika tidak, gunakan standard deviation internal (onboarding).
    if history and len(history) > 1:
        # Ambil maksimal 10 sampel terakhir untuk baseline
        baseline_samples = history[1:11] 
        base_dwells = [np.array(s.get('dwell', []), dtype=float) for s in baseline_samples if s.get('dwell')]
        
        if base_dwells:
            # Cari panjang minimum untuk perbandingan
            min_len = min(len(dwell), min(len(d) for d in base_dwells))
            if min_len >= 3:
                # Rata-rata dwell dari riwayat
                avg_base = np.mean([d[:min_len] for d in base_dwells], axis=0)
                current_d = np.array(dwell[:min_len], dtype=float)
                
                # Korelasi (0 sampai 1)
                correlation = np.corrcoef(current_d, avg_base)[0, 1]
                if np.isnan(correlation): correlation = 0.5
                
                # Kita ubah korelasi (1.0 = sempurna) menjadi metric "stability"
                # Template mengharapkan nilai kecil untuk "Sangat Stabil" jika menggunakan std.
                # Jadi kita balik: stability = (1.0 - correlation) * 100 (dalam ms "virtual")
                # Semakin kecil nilainya, semakin mendekati pola riwayat.
                stats['stability'] = max(0.01, (1.0 - max(0, correlation)) * 0.15) # Skala disesuaikan
            else:
                stats['stability'] = np.std(dwell)
        else:
            stats['stability'] = np.std(dwell)
    else:
        # Internal variance untuk akun baru
        stats['stability'] = np.std(dwell)
    
    return stats

