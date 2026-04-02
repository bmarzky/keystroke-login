let dwellTimes = [];
let flightTimes = [];
let keyDownTime = {};
let lastKeyUpTime = null;

// Gunakan window. agar bisa dipanggil dari file HTML
window.getKeystrokeData = function() {
    return JSON.stringify({
        dwell: dwellTimes,
        flight: flightTimes
    });
};

document.addEventListener("DOMContentLoaded", () => {
    const passwordInput = document.getElementById('password'); 

    if (passwordInput) {
        // --- PERBAIKAN UTAMA: Reset saat fokus ---
        passwordInput.addEventListener("focus", () => {
            // Kosongkan data lama agar tidak tercampur jika user mengetik ulang
            dwellTimes = [];
            flightTimes = [];
            keyDownTime = {};
            // Paksa jadi null agar tidak menghitung jeda dari kolom username
            lastKeyUpTime = null; 
        });

        passwordInput.addEventListener("keydown", (e) => {
            // Abaikan jika tombol ditahan (auto-repeat)
            if (e.repeat) return; 

            let now = Date.now();
            keyDownTime[e.key] = now;

            /**
             * Syarat: lastKeyUpTime tidak null DAN sudah ada karakter yang tersimpan.
             * Ini menjamin karakter PERTAMA password tidak menghitung flight time 
             * dari penekanan tombol terakhir di luar kolom password.
             */
            if (lastKeyUpTime !== null && dwellTimes.length > 0) {
                let flight = now - lastKeyUpTime;
                flightTimes.push(flight);
            }
        });

        passwordInput.addEventListener("keyup", (e) => {
            let now = Date.now();

            if (keyDownTime[e.key]) {
                let dwell = now - keyDownTime[e.key];
                dwellTimes.push(dwell);
                delete keyDownTime[e.key];
            }

            // Simpan waktu terakhir tombol dilepas untuk perhitungan flight time berikutnya
            lastKeyUpTime = now;
        });
    }
});