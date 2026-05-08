import numpy as np

def calculate_dashboard_stats(current_features):
    """
    Menghitung statistik performa ketikan untuk tampilan dashboard.
    Memindahkan logika dari app.py agar kode lebih bersih.
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
    # Rumus standar: (Jumlah karakter / 5) / (Total waktu dalam menit)
    total_time_seconds = sum_d + sum_f
    if total_time_seconds > 0:
        stats['wpm'] = (cnt_d / 5) / (total_time_seconds / 60)
    
    # 4. Stability (Standard Deviation dari Dwell)
    # Semakin kecil nilainya, semakin stabil ritme ketikannya.
    stats['stability'] = np.std(dwell)
    
    return stats
