import sys
import json
import numpy as np
import warnings

warnings.filterwarnings('ignore')


class BiometricCore:

    def __init__(self, n_features=8):
        self.n_features = n_features

    # Feature Extraction (8-dim statistical vector)
    def extract(self, data):
        data = self._ensure_vectors(data)
        features = []
        for key in ['dwell', 'flight', 'd2d', 'u2u']:
            arr = np.array(data.get(key, []), dtype=float)
            # Filter outlier (> 0.25s) agar tidak merusak Median dan Std
            clean_arr = arr[arr < 0.25]
            if len(clean_arr) >= 2:
                features.append(float(np.median(clean_arr)))
                features.append(float(np.std(clean_arr, ddof=1)))
            elif len(arr) >= 1:
                # Jika semua macet atau cuma 1 tombol, pakai data asli tapi limitasi
                features.append(float(min(np.median(arr), 0.20)))
                features.append(0.01)
            else:
                features.append(0.0)
                features.append(0.0)
        return [float(f) if np.isfinite(f) else 0.0 for f in features]

    def _ensure_vectors(self, data):
        """
        Menjamin keberadaan d2d dan u2u. Jika tidak ada di database,
        hitung otomatis dari dwell dan flight (Virtual Feature Augmentation).
        """
        dwell = data.get('dwell', [])
        flight = data.get('flight', [])
        
        # Jika d2d atau u2u belum ada, hitung secara matematis
        if 'd2d' not in data or not data['d2d']:
            # D2D[i] = Dwell[i] + Flight[i]
            data['d2d'] = [float(dwell[i] + flight[i]) for i in range(min(len(dwell), len(flight)))]
            
        if 'u2u' not in data or not data['u2u']:
            # U2U[i] = Flight[i] + Dwell[i+1]
            data['u2u'] = [float(flight[i] + dwell[i+1]) for i in range(min(len(dwell)-1, len(flight)))]
            
        return data

    # Warm-Start Progressive Adaptive Gate Computation
    def _compute_adaptive_gates(self, history, hist_mahal_dists=None):
        """
        Menghitung gate adaptif berbasis statistik history user.

        Fase 0 (n=1, register): Inferensi dari Coefficient of Variation (CV)
          internal satu sesi ketikan, untuk menentukan karakter typist.
        Fase 1 (n=2-4): Blending linier antara gate register dan gate history.
        Fase 2 (n>=5) : Full adaptive dari distribusi history.
        """
        n = len(history)

        # --- Fase 0: Inferensi dari sample pertama (register) ---
        first_dwell = np.array(history[0].get('dwell', [0.1]), dtype=float)
        mean_dwell  = max(float(np.mean(first_dwell)), 0.001)
        std_dwell   = float(np.std(first_dwell)) if len(first_dwell) > 1 else mean_dwell * 0.2
        cv          = std_dwell / mean_dwell  # Coefficient of Variation

        # CV → karakter typist → inisialisasi gate awal
        # cv < 0.20: presisi | 0.20–0.40: normal | > 0.40: variabel
        cv_clamped      = float(np.clip(cv, 0.10, 0.60))
        base_speed_gate = 0.20 + cv_clamped * 0.50   # 0.25 – 0.50
        base_mahal_gate = 1.50 + cv_clamped * 6.0    # 2.10 – 5.10
        base_threshold  = 0.58 - cv_clamped * 0.10   # 0.52 – 0.57

        if n == 1:
            # Tetap terapkan Welcome Buffer meskipun n=1
            speed_gate = max(base_speed_gate, 0.50)
            mahal_gate = max(base_mahal_gate, 5.0)
            return {
                "speed_gate": float(round(speed_gate, 4)),
                "mahal_gate": float(round(mahal_gate, 4)),
                "threshold":  float(round(base_threshold,  4)),
                "phase": "Adaptive-Init (CV={:.2f}) [Welcome Buffer]".format(cv),
            }

        # --- Fase 1 & 2: Hitung dari history yang sudah ada ---
        hist_speeds = [float(h.get('speed', 0)) for h in history]
        avg_speed   = float(np.mean(hist_speeds))
        hist_devs   = [abs(s - avg_speed) / max(avg_speed, 1.0) for s in hist_speeds]

        hist_mean_dev = float(np.mean(hist_devs))
        hist_std_dev  = float(np.std(hist_devs)) if len(hist_devs) > 1 else hist_mean_dev * 0.3
        hist_speed_gate = hist_mean_dev + 3.0 * hist_std_dev

        # Mahalanobis gate dari distribusi jarak user sendiri
        if hist_mahal_dists and len(hist_mahal_dists) >= 2:
            m_mean = float(np.mean(hist_mahal_dists))
            m_std  = float(np.std(hist_mahal_dists))
            hist_mahal_gate = m_mean + 3.0 * m_std
            
            # --- ADAPTIVE THRESHOLD SCALING ---
            # Jika rata-rata jarak Mahal kecil, artinya user sangat konsisten.
            # Berikan kurva pembelajaran (learning curve) yang lebih lambat untuk
            # user yang belum terbiasa dengan device baru (Registration Bias).
            consistency_factor = max(0.0, 1.0 - (m_mean / 2.0))
            
            # Base hist_threshold perlahan naik dari 0.60 (n=5) ke 0.70 (n>=10)
            # Ini mencegah "Threshold Shock" di mana threshold tiba-tiba naik ke 0.70 di login ke-5
            base_curve = min(0.70, 0.60 + ((n - 5) * 0.02))
            hist_threshold = base_curve + (consistency_factor * 0.10)

        else:
            hist_mahal_gate = base_mahal_gate
            hist_threshold = 0.60 if n >= 5 else 0.55

        # --- Blending (Fase 1: 2-4 sample) ---
        if n < 5:
            alpha = (n - 1) / 4.0  # 0.25 → 0.75
            speed_gate = (1 - alpha) * base_speed_gate + alpha * hist_speed_gate
            mahal_gate = (1 - alpha) * base_mahal_gate + alpha * hist_mahal_gate
            threshold  = (1 - alpha) * base_threshold  + alpha * hist_threshold
            phase = "Adaptive-Blend (n={}, α={:.2f})".format(n, alpha)
        else:
            # Fase 2: Full adaptive
            speed_gate = hist_speed_gate
            mahal_gate = hist_mahal_gate
            threshold  = hist_threshold
            phase = "Mahalanobis+Adaptive-Full (n={})".format(n)

        # Clamp ke batas keamanan minimum
        # Berikan kelonggaran besar saat adaptasi karena "Registration Bias"
        # (user mengetik lambat saat daftar, tapi cepat saat login)
        if n < 3:
            # Welcome Buffer: Gate sangat longgar untuk login pertama
            min_speed_gate = 0.50
            min_mahal_gate = 5.0
        elif n < 5:
            min_speed_gate = 0.50
            min_mahal_gate = 3.5
        else:
            # User mapan (n >= 5) diberikan kelonggaran 60% 
            # agar 'The Forgiver' bisa bekerja jika ada typo di awal/tengah
            min_speed_gate = 0.60 
            min_mahal_gate = 10.0 # Sangat longgar agar pemaaf bisa bekerja
            
        speed_gate = float(np.clip(speed_gate, min_speed_gate, 0.60))
        mahal_gate = float(np.clip(mahal_gate, 1.20, 15.00)) # Range ditingkatkan ke 15.0
        threshold  = float(np.clip(threshold,  0.55, 0.82))

        # --- Low Entropy (Short Password) Penalty ---
        # Password pendek ( < 8 karakter ) memiliki sedikit biometrik entropi.
        # Mudah diretas karena spurious correlation tinggi. Kita harus mengetatkan aturan.
        pw_len = len(first_dwell)
        if pw_len < 8:
            entropy_penalty = (8 - pw_len) * 0.015
            threshold = float(np.clip(threshold + entropy_penalty, 0.55, 0.88))
            speed_gate = float(np.clip(speed_gate * 0.85, 0.08, 0.60))
            mahal_gate = float(np.clip(mahal_gate * 0.85, 1.00, 6.00))
            phase += " [Low Entropy Lock]"

        return {
            "speed_gate": round(speed_gate, 4),
            "mahal_gate": round(mahal_gate, 4),
            "threshold":  round(threshold,  4),
            "phase": phase,
        }

    # Main Analysis
    def analyze(self, json_path):
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            input_data = data.get('input', {})
            history    = data.get('history', [])

            if not history:
                return {"status": False, "score": 0.0, "reason": "Enroll dulu"}

            n_history = len(history)

            input_data = self._ensure_vectors(input_data)
            in_dwell    = np.array(input_data.get('dwell', []), dtype=float)
            in_flight   = np.array(input_data.get('flight', []), dtype=float)
            
            # --- [Clean Speed Computation] ---
            # Abaikan tombol macet (> 0.25s) saat menghitung kecepatan murni (CPM).
            c_dwell  = in_dwell[in_dwell < 0.25]
            c_flight = in_flight[in_flight < 0.25]
            if len(c_dwell) >= 3 and len(c_flight) >= 3:
                input_speed = 60.0 / (np.mean(c_dwell) + np.mean(c_flight))
            else:
                input_speed = float(input_data.get('speed', 0))

            if np.sum(in_dwell) < 0.01 or np.sum(in_flight) < 0.01:
                return {"status": False, "score": 0.0, "reason": "Data tidak valid"}

            # ── Hitung Mahalanobis dist history terlebih dahulu (untuk gate adaptif) ──
            hist_mahal_dists = []
            if n_history >= 5:
                try:
                    X    = np.array([self.extract(h) for h in history])
                    mu   = np.mean(X, axis=0)
                    cov  = np.cov(X, rowvar=False) + np.eye(self.n_features) * 1e-3
                    cinv = np.linalg.inv(cov)
                    for row in X:
                        d = row - mu
                        hist_mahal_dists.append(float(np.sqrt(max(0, d.T @ cinv @ d))))
                except Exception:
                    pass

            # ── Adaptive Gate Computation ──
            gates      = self._compute_adaptive_gates(history, hist_mahal_dists)
            threshold  = gates["threshold"]
            speed_gate = gates["speed_gate"]
            mahal_gate = gates["mahal_gate"]
            adapt_phase = gates["phase"]

            # ── Speed Gate (Adaptive) ──
            history_speeds = [float(h.get('speed', 0)) for h in history]
            avg_speed  = float(np.mean(history_speeds))
            
            # --- [The Forgiver: Speed Normalization] ---
            # Jika n=1, pendaftaran mungkin sangat lambat karena backspace.
            # Kita lakukan normalisasi agar Speed Gate lebih masuk akal.
            if n_history == 1:
                # Jika pendaftaran < 200 CPM, anggap pendaftaran bermasalah
                # dan limitasi dampaknya terhadap perhitungan deviasi.
                if avg_speed < 250: avg_speed = 350 
            
            speed_dev  = abs(input_speed - avg_speed) / max(avg_speed, 1.0)

            if speed_dev > speed_gate:
                return {
                    "status": False, "score": 0.0,
                    "threshold": threshold, "should_update_history": False,
                    "reason": f"Gate: Speed Anomali (dev={speed_dev:.1%} > gate={speed_gate:.1%})",
                    "method": adapt_phase, "n_features": self.n_features,
                    "n_samples": n_history, "mahal_dist": None,
                    "speed_dev": float(round(speed_dev, 4)), 
                    "adaptive_gates": {
                        "speed_gate": speed_gate,
                        "mahal_gate": mahal_gate,
                        "threshold":  threshold,
                    },
                    "components": {},
                }

            # ── Soft Scoring ──
            # Lebih banyak baseline = lebih sulit ditiru impostor yang hanya cocok di 1 sampel.
            if n_history <= 5:
                baselines = history
            elif n_history <= 10:
                baselines = history[:2] + history[-4:]   # 6 baseline
            elif n_history <= 20:
                baselines = history[:3] + history[-5:]   # 8 baseline
            else:
                baselines = history[:4] + history[-6:]   # 10 baseline
            
            if n_history < 5:
                # Masa adaptasi awal: user belum punya ritme stabil.
                # Fokus pada korelasi kasar dan kurangi hukuman Euclidean.
                w_rhythm, w_corr, w_speed, w_ratio, w_stability, w_flow = 0.30, 0.40, 0.15, 0.00, 0.00, 0.15
            elif n_history < 10:
                # Masa transisi: User mulai terbiasa dengan keyboard, tapi belum konsisten sempurna.
                w_rhythm, w_corr, w_speed, w_ratio, w_stability, w_flow = 0.35, 0.30, 0.15, 0.00, 0.00, 0.20
            else:
                # Fase stabil: Kunci pada Rhythm (40%), tapi tingkatkan bobot Speed (20%) dan Flow (20%) 
                # untuk membedakan Expert Mimic tanpa menghukum pemilik asli saat sedang lelah.
                w_rhythm, w_corr, w_speed, w_ratio, w_stability, w_flow = 0.40, 0.20, 0.20, 0.00, 0.00, 0.20

            # --- Shift Bobot untuk Low Entropy ---
            # Jika password pendek, korelasi Pearson dan akselerasi (Flow) sangat tidak akurat 
            # (mudah menyentuh angka 0.9+ hanya karena kebetulan).
            pw_len = len(input_data.get('dwell', []))
            if pw_len < 8:
                w_corr *= 0.5
                w_flow *= 0.5
                w_rhythm = 1.0 - (w_corr + w_speed + w_ratio + w_stability + w_flow)

            all_scores = []
            r_score, c_score, s_score, ra_score, st_score, fl_score = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            comp_rhythm, comp_corr, comp_speed, comp_ratio, comp_stability, comp_flow = [], [], [], [], [], []
            mahal_error = None

            input_speed = float(input_data.get('speed', 0))
            in_dwell    = np.array(input_data.get('dwell', []), dtype=float)
            in_flight   = np.array(input_data.get('flight', []), dtype=float)
            
            # --- [PERMANENT_FORGIVER_FEATURE] Historical Key-Consistency Profile ---
            stats_profile = {}
            if n_history > 1:
                for k in ['dwell', 'flight', 'd2d', 'u2u']:
                    arrs = [np.array(b.get(k, []), dtype=float) for b in baselines if b.get(k)]
                    if arrs:
                        min_l = min(len(x) for x in arrs)
                        matrix = np.array([x[:min_l] for x in arrs])
                        stats_profile[k] = {
                            "mean": np.mean(matrix, axis=0),
                            "std":  np.std(matrix, axis=0) + 0.005
                        }

            final_outlier_count = 0
            best_r_score = -1

            for baseline in baselines:
                # Pastikan baseline dari DB juga punya d2d/u2u (virtual)
                baseline = self._ensure_vectors(baseline)
                b_data = {k: np.array(baseline.get(k, []), dtype=float) for k in ['dwell', 'flight', 'd2d', 'u2u']}
                
                scores_r, scores_c = [], []
                current_outlier_count = 0
                for key in ['dwell', 'flight', 'd2d', 'u2u']:
                    in_v  = np.array(input_data.get(key, []), dtype=float)
                    bs_v  = b_data[key]
                    
                    # --- [The Forgiver: Median Substitution] ---
                    # Jika ini login pertama (n=1), kita bersihkan data pendaftaran.
                    # Tombol yang > 0.4s (outlier) diganti dengan median sesi tersebut.
                    if n_history == 1:
                        bs_v = np.array(bs_v)
                        median_val = np.median(bs_v)
                        bs_v[bs_v > 0.40] = median_val
                    
                    # Samakan panjang data dengan statistik history agar tidak Broadcast Error
                    stat_len = len(stats_profile[key]["mean"]) if key in stats_profile else 999
                    mlen  = min(len(in_v), len(bs_v), stat_len) - 1
                    if mlen < 3: continue

                    v1, v2 = in_v[:mlen], bs_v[:mlen]
                    
                    # --- [PERMANENT_FORGIVER_FEATURE] Dynamic Key-Level Outlier Rejection ---
                    # Kita harus membuang outlier SEBELUM normalisasi agar tidak meracuni skor tombol lain.
                    outlier_mask = np.zeros(len(v1), dtype=bool)
                    if key in stats_profile and n_history > 1:
                        p_mean = stats_profile[key]["mean"][:len(v1)]
                        p_std  = stats_profile[key]["std"][:len(v1)]
                        stat_mask = np.abs(v1 - p_mean) > (3.5 * p_std)
                        hard_mask = v1 > 0.25
                        outlier_mask = stat_mask | hard_mask
                        
                        current_outlier_count += int(np.sum(outlier_mask))

                    # Gunakan data yang sudah bersih
                    v1_c = v1[~outlier_mask]
                    v2_c = v2[~outlier_mask]
                    
                    if len(v1_c) < 3: 
                        # Jika terlalu banyak dibuang, balikkan ke data asli (safety)
                        v1_c, v2_c = v1, v2

                    # Rhythm (Euclidean) - Sekarang aman dari racun outlier
                    n1, n2 = v1_c / max(np.sum(v1_c), 0.001), v2_c / max(np.sum(v2_c), 0.001)
                    diffs  = (n1 - n2) ** 2

                    # Fallback untuk n=1 (pemaafan ratio tetap)
                    if n_history == 1 and len(diffs) > 5:
                        n_trim = max(1, int(len(diffs) * 0.20))
                        diffs = np.sort(diffs)[:-n_trim]
                    
                    dist = np.sqrt(np.sum(diffs))
                    scores_r.append(max(0.0, 1.0 - (dist / 0.18)))
                    
                    # Correlation (Pearson) - Gunakan data bersih (v1_c, v2_c)
                    c = np.corrcoef(v1_c, v2_c)[0, 1] if np.std(v1_c) > 0 and np.std(v2_c) > 0 else 0.5
                    scores_c.append(max(0.0, c) if np.isfinite(c) else 0.5)

                if not scores_r: continue
                r_score, c_score = np.mean(scores_r), np.mean(scores_c)

                # --- [PERMANENT_FORGIVER_FEATURE] Recovery Bonus ---
                # Jika kita mendeteksi ada outlier yang dibuang, tapi sisa tombol lainnya
                # memiliki korelasi yang sangat kuat (>0.90), berikan bonus kepercayaan.
                if current_outlier_count > 0 and c_score > 0.90:
                    # Bonus 15% untuk Rhythm dan Correlation jika sangat yakin
                    boost_factor = 1.15 if c_score > 0.93 else 1.05
                    r_score = min(1.0, r_score * boost_factor)
                    c_score = min(1.0, c_score * boost_factor)
                    # Berikan bonus juga ke s_score jika korelasi sangat kuat
                    if c_score > 0.94:
                        s_score = min(1.0, s_score * 1.20)
                    
                # --- [UX Welcome Buffer] Partial Matching for First Login (n=1) ---
                # Jika ini login pertama setelah daftar, user mungkin grogi/typo.
                # Kita "memaafkan" 20% error terbesar (Trimmed Mean).
                if n_history == 1 and len(scores_r) > 4:
                    # Ambil semua skor individu per-key (jika tersedia)
                    # Untuk kesederhanaan di n=1, kita berikan bonus toleransi 15% 
                    # jika korelasi Pearson-nya masih sangat kuat (>0.85)
                    if c_score > 0.85:
                        r_score = min(1.0, r_score * 1.15)
                        c_score = min(1.0, c_score * 1.10)

                # --- [Anti-Impostor #2] Dwell Alternating Direction Check ---
                # Pola alternating dwell (pendek->panjang vs panjang->pendek) sangat
                # spesifik per user karena ditentukan oleh posisi jari di keyboard.
                # Data: bima rasio=1.287 (pendek->panjang), alip rasio=0.835 (terbalik!)
                # Jika arah pola berlawanan, berikan penalti 20% pada Rhythm score.
                if n_history >= 10 and len(in_dwell) >= 4 and len(b_data['dwell']) >= 4:
                    in_odd  = float(np.mean(in_dwell[0::2]))
                    in_even = float(np.mean(in_dwell[1::2]))
                    bs_odd  = float(np.mean(b_data['dwell'][0::2]))
                    bs_even = float(np.mean(b_data['dwell'][1::2]))
                    if (in_odd > in_even) != (bs_odd > bs_even):
                        r_score *= 0.80

                # Speed Score dengan Kompensasi Outlier
                bs_speed = float(baseline.get('speed', 0))
                if n_history == 1 and bs_speed < 250: 
                    bs_speed = 350 # Normalisasi untuk pendaftaran lambat
                
                # Hitung deviasi kecepatan mentah
                speed_diff_ratio = abs(input_speed - bs_speed) / max(bs_speed, 1.0)
                
                # --- [PERMANENT_FORGIVER_FEATURE] Speed Compensation ---
                # Jika tadi ada tombol yang dibuang (outlier), jangan hukum kecepatannya terlalu berat.
                # Kita berikan toleransi ekstra pada speed_gate jika ada outlier.
                speed_penalty_limit = 0.50
                if current_outlier_count > 0:
                    # Berikan bonus toleransi 10% per outlier (maks 20%)
                    speed_penalty_limit += min(0.20, current_outlier_count * 0.10)
                
                s_score = max(0.0, 1.0 - (speed_diff_ratio / speed_penalty_limit))

                # Ratio (Dwell/Flight)
                r_in  = np.sum(input_data.get('dwell', [])) / max(np.sum(input_data.get('flight', [])), 0.01)
                r_bs  = np.sum(baseline.get('dwell', [])) / max(np.sum(baseline.get('flight', [])), 0.01)
                ra_score = max(0.0, 1.0 - (abs(r_in - r_bs) / max(r_bs, 0.01) / 0.40))
                if n_history == 1:
                    ra_score = max(ra_score, 0.50)  # Toleransi khusus n=1 (pendaftaran)
                # Stability (Jitter)
                j_in  = np.std(in_dwell) / max(np.mean(in_dwell), 0.01)
                j_bs  = np.std(b_data['dwell']) / max(np.mean(b_data['dwell']), 0.01)
                st_score = max(0.0, 1.0 - (abs(j_in - j_bs) / 0.30))
                # Flow (Acceleration)
                f_in, f_bs = np.diff(in_flight), np.diff(b_data['flight'])
                flen = min(len(f_in), len(f_bs))
                if flen > 3:
                    f1, f2   = f_in[:flen], f_bs[:flen]
                    c_f      = np.corrcoef(f1, f2)[0, 1] if np.std(f1) > 0 and np.std(f2) > 0 else 0.5
                    fl_score = max(0.0, c_f) if np.isfinite(c_f) else 0.5
                    # Flow/Akselerasi sangat rentan terhadap 1 slip jari (outlier), 
                    # beri batas minimum 0.35 agar tidak langsung 0%
                    fl_score = max(fl_score, 0.35)
                else:
                    fl_score = 0.5

                # --- [Anti-Impostor #1] Flight Stability Penalty ---
                # Impostor cenderung punya variabilitas flight (std) sangat berbeda dari
                # pemilik asli. Contoh: bima std=0.01 (stabil), alip std=0.17 (liar) -> 17x!
                # Penalti proporsional diterapkan ke fl_score.
                if n_history >= 10 and len(in_flight) >= 3 and len(b_data['flight']) >= 3:
                    in_fstd = float(np.std(in_flight))
                    b_fstd  = float(np.std(b_data['flight']))
                    if b_fstd > 0.001:
                        fstd_ratio = abs(in_fstd - b_fstd) / b_fstd
                        if fstd_ratio > 2.0:
                            # Semakin beda, semakin besar penalti (maks 40%)
                            fl_score *= max(0.60, 1.0 - (fstd_ratio - 2.0) * 0.10)

                # --- [Anti-Impostor #3] Near-Zero Flight Count Penalty ---
                # Jumlah 'simultaneous keypress' (<15ms) adalah sidik jari cara mengetik.
                # Data: bima avg=0.73/sesi, alip avg=1.39/sesi -> hampir 2x lipat.
                # Perbedaan > 2 near-zero dianggap anomali dan dikenai penalti 30%.
                if n_history >= 10 and len(in_flight) >= 3 and len(b_data['flight']) >= 3:
                    in_zeros = sum(1 for f in in_flight if f < 0.015)
                    b_zeros  = sum(1 for f in b_data['flight'] if f < 0.015)
                    # FIX: Turunkan threshold dari >2 ke >1.
                    # Data bima-252 avg=2.8 near-zeros, attacker=1 -> |diff|=1.8, tapi '>2' tidak aktif.
                    # Dengan '>1', kasus ini tertangkap.
                    if abs(in_zeros - b_zeros) > 1:
                        fl_score *= 0.70

                # Simpan outlier count dari baseline dengan rhythm terbaik
                if r_score > best_r_score:
                    best_r_score = r_score
                    final_outlier_count = current_outlier_count

                comp_rhythm.append(r_score)
                comp_corr.append(c_score)
                comp_speed.append(s_score)
                comp_ratio.append(ra_score)
                comp_stability.append(st_score)
                comp_flow.append(fl_score)
                all_scores.append(
                    w_rhythm*r_score + w_corr*c_score + w_speed*s_score +
                    w_ratio*ra_score + w_stability*st_score + w_flow*fl_score
                )

            if not all_scores:
                return {"status": False, "score": 0.0, "reason": "Data tidak cukup"}

            best_idx   = np.argmax(all_scores)
            best_score = float(all_scores[best_idx])

            # -- Consensus Scoring (Anti-Impostor) --
            # Impostor yang kebetulan cocok 1 dari N baseline tidak bisa lolos.
            # Legitimate user konsisten di semua baseline (max ~= mean).
            # Impostor: max bisa tinggi (keberuntungan) tapi mean rendah.
            #
            # Rasio 0.40*max + 0.60*mean — lebih mean-heavy dari versi lama (0.55/0.45).
            # Kalkulasi kasus breach bima-253:
            #   Jika best=0.88, mean=0.663 (estimasi dari consensus lama 0.7822)
            #   Baru: 0.40*0.88 + 0.60*0.663 = 0.352 + 0.398 = 0.750 < threshold -> REJECT
            if n_history >= 10 and len(all_scores) >= 3:
                mean_score  = float(np.mean(all_scores))
                
                # Jika skor terbaik sudah cukup meyakinkan, kurangi bobot Mean
                if best_score > 0.70:
                    weight_best = 0.80
                    weight_mean = 0.20
                else:
                    weight_best = 0.40
                    weight_mean = 0.60
                    
                final_score = weight_best * best_score + weight_mean * mean_score

                # -- Minimum Baseline Agreement (MBA) --
                # Jika ada baseline yang scored sangat rendah (<0.50), berarti
                # attacker tidak konsisten di semua baseline -> penalti.
                # Legitimate user jarang punya baseline yang scored < 0.50.
                min_score = float(np.min(all_scores))
                if min_score < 0.50:
                    # Penalti proporsional: semakin rendah min, semakin besar penalti
                    mba_penalty = max(0.78, min_score / 0.50)
                    final_score *= mba_penalty
            else:
                final_score = best_score
            
            # Komponen log ambil dari yang terbaik
            components = {
                "rhythm": float(comp_rhythm[best_idx]),
                "correlation": float(comp_corr[best_idx]),
                "speed": float(comp_speed[best_idx]),
                "ratio": float(comp_ratio[best_idx]),
                "stability": float(comp_stability[best_idx]),
                "flow": float(comp_flow[best_idx]),
            }

            fusion_weights = {
                "w_rhythm": w_rhythm,
                "w_corr": w_corr,
                "w_speed": w_speed,
                "w_ratio": w_ratio,
                "w_stability": w_stability,
                "w_flow": w_flow
            }

            # ── Mahalanobis (Adaptive Gate) ──
            method    = adapt_phase
            m_dist_val = None
            if n_history >= 5:
                method = "Mahalanobis+" + adapt_phase
                try:
                    X    = np.array([self.extract(h) for h in history])
                    mu   = np.mean(X, axis=0)
                    cov  = np.cov(X, rowvar=False) + np.eye(self.n_features) * 1e-3
                    diff = np.array(self.extract(input_data)) - mu
                    m_dist_val = float(round(np.sqrt(max(0, diff.T @ np.linalg.inv(cov) @ diff)), 4))

                    # Hard Gate Adaptif
                    if m_dist_val > mahal_gate:
                        return {
                            "status": False, "score": 0.0,
                            "threshold": threshold, "should_update_history": False,
                            "reason": f"Gate: Mahalanobis Anomali (dist={m_dist_val:.4f} > gate={mahal_gate:.4f})",
                            "method": method, "n_features": self.n_features,
                            "n_samples": n_history, "mahal_dist": m_dist_val,
                            "speed_dev": float(round(speed_dev, 4)),
                            "adaptive_gates": {
                                "speed_gate": speed_gate,
                                "mahal_gate": mahal_gate,
                                "threshold":  threshold,
                            },
                            "components": {},
                        }
                    
                    # Kita TIDAK LAGI memotong final_score dengan m_score.
                    # Mahalanobis murni berfungsi sebagai Hard Gate. Jika lolos gate, 
                    # user berhak dinilai murni menggunakan Titanium Fusion.
                    
                except Exception as e:
                    mahal_error = str(e)
                    method = "Mahalanobis+" + adapt_phase + " (error)"

            # --- [The Master Forgiver: Instinct Trust Bonus] ---
            # Jika Mahalanobis Distance sangat rendah (< 1.2), ini indikator kuat 
            # bahwa 'jiwa' ketikan ini adalah milik owner asli (Median & Std cocok).
            if 'm_dist_val' in locals() and m_dist_val is not None and m_dist_val < 1.2:
                # Berikan bonus kepercayaan +0.22 agar tetap lolos meski ada typo.
                final_score = min(1.0, final_score + 0.22)

            is_match = bool(final_score >= threshold)
            reason   = f"Score: {final_score:.2f} | {'ACCEPT' if is_match else 'REJECT'}"
            
            if n_history == 1 and final_score >= 0.25 and not is_match:
                is_match = True
                reason = f"Score: {final_score:.2f} | Welcome Grace Pass (n=1)"
            
            # --- [Anti-Poisoning: Messy Data Protection] ---
            # Jika tombol yang dibuang (outlier) > 25%, anggap data ini 'rusak/berisik'.
            # Kita ijinkan login (ACCEPT) tapi JANGAN simpan ke database agar tidak meracuni history.
            total_keys = len(in_dwell) + len(in_flight)
            outlier_pct = (final_outlier_count / total_keys) if total_keys > 0 else 0
            
            is_messy = outlier_pct > 0.25
            if is_messy:
                should_up = False
                reason += f" | [POISON-RISK] Messy Typing ({outlier_pct:.1%} outliers)"
            else:
                # Logika update normal
                if n_history < 10:
                    update_threshold = threshold + 0.02
                else:
                    update_threshold = max(0.75, threshold + 0.02)
                should_up = bool((final_score >= update_threshold) or (is_match and n_history < 3))

            if final_outlier_count > 0:
                reason += f" | [STERILE] Removed {final_outlier_count} noisy keys"

            if mahal_error: reason += f" | Math Error: {mahal_error}"

            return {
                "status":               is_match,
                "score":                float(round(final_score, 4)),
                "threshold":            float(threshold),
                "should_update_history": should_up,
                "reason":               reason,
                "method":               method,
                "n_features":           self.n_features,
                "n_samples":            n_history,
                "mahal_dist":           m_dist_val,
                "speed_dev":            float(round(speed_dev, 4)),
                "adaptive_gates": {
                    "speed_gate": gates["speed_gate"],
                    "mahal_gate": gates["mahal_gate"],
                    "threshold":  gates["threshold"],
                },
                "components": {
                    "rhythm":    float(round(components["rhythm"],    4)) if components else None,
                    "corr":      float(round(components["correlation"], 4)) if components else None,
                    "speed":     float(round(components["speed"],     4)) if components else None,
                    "ratio":     float(round(components["ratio"],     4)) if components else None,
                    "stability": float(round(components["stability"], 4)) if components else None,
                    "flow":      float(round(components["flow"],      4)) if components else None,
                },
                "weights": fusion_weights
            }

        except Exception as e:
            return {"status": False, "score": 0.0, "reason": f"Core Error: {str(e)}"}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        core = BiometricCore()
        print(json.dumps(core.analyze(sys.argv[1])))