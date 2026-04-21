import sys
import json
import numpy as np
from sklearn.covariance import LedoitWolf

def calculate_mahalanobis(json_path):
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        input_data = data.get('input', {})
        history = data.get('history', [])
        
        # 1. Validasi Keberadaan Data
        if len(history) < 1:
            return {"status": False, "distance": 9996.0, "threshold": 0.0, "reason": "No training data"}
            
        # 2. Gabungkan array fitur mikro menjadi input_vector tunggal secara dinamis
        # CATATAN PENTING: Variabel 'speed' sengaja dicabut (tidak dimasukkan ke Matriks Kovarians)!
        # 'Speed' memiliki besaran (magnitude) berupa ratusan (~400 CPM).
        # Sementara 'dwell/flight' memiliki besaran desimal mikrosekon (~0.05 s).
        # Membenamkan 'speed' memicu Ledoit-Wolf Shrinkage untuk "buta/menghiraukan" deviasi mikroskopis 
        # jari dan hanya fokus pada kecepatan global, menyebabkan REJECTION gagal jika imposter ngetik lambat.
        input_vector = []
        for k in ['dwell', 'flight', 'd2d', 'u2u']:
            if k not in input_data:
                continue
            input_vector.extend(input_data[k])
        
        expected_length = len(input_vector)
        
        # 3. Ekstrak data historis dengan panjang vektor yang sama
        samples = []
        for hist in history:
            vec = []
            try:
                for k in ['dwell', 'flight', 'd2d', 'u2u']:
                    if k not in hist:
                        continue
                    vec.extend(hist[k])
                
                # Filter typo (panjang tidak sama)
                if len(vec) == expected_length:
                    samples.append(vec)
            except:
                continue
                
        if len(samples) < 1:
            return {"status": False, "distance": 9998.0, "threshold": 0.0, "reason": "Sampel tidak cukup atau perbedaan panjang ketikan"}

        samples = np.array(samples)
        input_vector = np.array(input_vector)
        
        distance = 0.0
        final_threshold = 0.0
        calculated_threshold = 0.0
        
        if len(samples) > 1:
            # Solusi Paling Tangguh Untuk "Low Sample vs High Dimension": Ledoit-Wolf Shrinkage
            lw = LedoitWolf()
            lw.fit(samples)
            
            mean_vector = lw.location_
            inv_cov_matrix = lw.precision_  # Inverse covariance yg sudah di-regulasi dengan cerdas
            
            # Kalkulasi Jarak Mahalanobis
            diff = input_vector - mean_vector
            distance = np.sqrt(np.clip(np.dot(np.dot(diff, inv_cov_matrix), diff.T), 0, None))
            
            # Menghitung variasi historis untuk Baseline otomatis
            hist_distances = []
            for s in samples:
                d_diff = s - mean_vector
                d = np.sqrt(np.clip(np.dot(np.dot(d_diff, inv_cov_matrix), d_diff.T), 0, None))
                hist_distances.append(d)
                
            mean_dist = np.mean(hist_distances)
            std_dist = np.std(hist_distances, ddof=1) if len(hist_distances) > 1 else 0
            
            # Threshold kelonggaran Z=3.0 (99.7% confidence interval dr histori user)
            calculated_threshold = mean_dist + (3.0 * std_dist)
            
        else:
            mean_vector = np.mean(samples, axis=0)
            diff = input_vector - mean_vector
            distance = np.sqrt(np.sum(diff ** 2))
            calculated_threshold = 0.0
            
        # 4. Dynamic Baseline Threshold (Floor)
        num_samples = len(samples)
        if num_samples < 3:
            floor_multiplier = 2.0  # Sangat pemaaf bagi pemula
        elif num_samples < 6:
            floor_multiplier = 1.5 
        elif num_samples < 10:
            floor_multiplier = 1.2
        else:
            floor_multiplier = 1.0  # Stabil 
            
        dynamic_min_threshold = np.sqrt(expected_length) * floor_multiplier
        
        final_threshold = float(max(calculated_threshold, dynamic_min_threshold))
        is_match = bool(distance <= final_threshold)
        
        return {
            "status": is_match,
            "distance": float(distance),
            "threshold": final_threshold,
            "reason": "Pola Cocok (Ledoit-Wolf Mahalanobis)" if is_match else "Pola Tidak Cocok (Terlalu Menyimpang)"
        }
    
    except Exception as e:
        return {"status": False, "distance": 9999.0, "threshold": 0.0, "reason": f"Python Exception: {str(e)}"}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"status": False, "distance": 9999.0, "threshold": 0.0, "reason": "No input file provided"}))
        sys.exit(1)
        
    result = calculate_mahalanobis(sys.argv[1])
    print(json.dumps(result))
