let dwellTimes = [];
let flightTimes = [];
let d2dTimes = [];
let u2uTimes = [];
let keySequence = []; // 🔹 BARU: Menyimpan urutan tombol yang diketik
let pendingKeyDowns = {};
let lastKeyDownTime = null;
let lastKeyUpTime = null;
let startTime = null;

window.getKeystrokeData = function () {
    const passwordInput = document.getElementById('password');
    const totalChar = passwordInput ? passwordInput.value.length : 0;

    let speedCPM = 0;
    if (startTime && lastKeyUpTime) {
        let totalTimeSec = (lastKeyUpTime - startTime) / 1000;
        speedCPM = totalTimeSec > 0 ? (totalChar / totalTimeSec) * 60 : 0;
    }

    return JSON.stringify({
        dwell: dwellTimes,
        flight: flightTimes,
        d2d: d2dTimes,
        u2u: u2uTimes,
        keys: keySequence, // 🔹 BARU: Kirim urutan tombol
        speed: parseFloat(speedCPM.toFixed(2))
    });
};

document.addEventListener("DOMContentLoaded", () => {
    const passwordInput = document.getElementById('password');
    const jsErrorDisplay = document.getElementById("js-error-msg");

    const resetData = () => {
        dwellTimes = [];
        flightTimes = [];
        d2dTimes = [];
        u2uTimes = [];
        keySequence = []; // 🔹 Reset urutan
        pendingKeyDowns = {};
        lastKeyDownTime = null;
        lastKeyUpTime = null;
        startTime = null;
    };

    // Fungsi untuk menampilkan pesan error di halaman (pengganti alert)
    const showNotice = (msg) => {
        if (jsErrorDisplay) {
            jsErrorDisplay.innerText = msg;
            // Hilangkan pesan otomatis setelah 3 detik
            setTimeout(() => { jsErrorDisplay.innerText = ""; }, 3000);
        }
    };

    if (passwordInput) {
        // --- PROTEKSI COPY-PASTE & DROP ---
        const blockAction = (e) => {
            e.preventDefault();
            e.stopPropagation();
            passwordInput.value = ""; // Kosongkan input
            resetData();
            showNotice("Copy-paste dilarang!");
        };

        passwordInput.addEventListener("paste", blockAction);
        passwordInput.addEventListener("drop", blockAction);

        // Blokir klik kanan dengan pesan
        passwordInput.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            showNotice("Klik kanan dimatikan pada kolom password.");
        });

        // Monitor input ilegal (autofill/bypass) & Reset saat kosong
        passwordInput.addEventListener("input", (e) => {
            // Penguatan: Jika user menghapus semua teks, reset rekaman biometrik
            if (passwordInput.value === "") {
                resetData();
            }

            if (e.inputType === "insertFromPaste" || e.inputType === "insertFromDrop") {
                passwordInput.value = "";
                resetData();
                showNotice("Input otomatis ditolak!");
            }
        });

        passwordInput.addEventListener("focus", resetData);

        // --- EVENT KEYDOWN ---
        passwordInput.addEventListener("keydown", (e) => {
            if (e.repeat || e.key === "Process") return;
            // Abaikan backspace, Enter, dan Tab agar tidak merusak ritme
            if (e.key === "Backspace" || e.key === "Enter" || e.key === "Tab") return; 

            let now = performance.now();
            if (startTime === null) startTime = now;

            // --- ANTI-VANDALISM (SMASHING DETECTION) ---
            // Jika ada > 5 tombol tertahan secara bersamaan, kemungkinan 'keyboard smashing'
            if (Object.keys(pendingKeyDowns).length > 5) {
                resetData();
                showNotice("Input tidak wajar terdeteksi!");
                return;
            }

            pendingKeyDowns[e.key] = now;
            keySequence.push(e.key); 

            if (lastKeyDownTime !== null) {
                let diff = (now - lastKeyDownTime) / 1000;
                // Anti-Bot: Kecepatan ketik tidak mungkin < 5ms secara konsisten
                if (diff < 0.005 && d2dTimes.length > 5) {
                    resetData();
                    showNotice("Terlalu cepat! Gunakan cara manual.");
                    return;
                }
                d2dTimes.push(diff);
            }
            
            // 🔹 LOGIKA OVERLAP (ROLLOVER):
            // Jika lastKeyUpTime belum ada atau lebih besar dari sekarang (dalam kasus tertentu),
            // tetap hitung selisihnya. Nilai negatif = Overlap.
            if (lastKeyUpTime !== null) {
                flightTimes.push((now - lastKeyUpTime) / 1000);
            } else if (startTime !== now) {
                // Kasus tombol pertama belum dilepas tapi tombol kedua sudah masuk
                flightTimes.push(0); // Inisialisasi awal jika perlu
            }
            
            lastKeyDownTime = now;
        });

        // --- EVENT KEYUP ---
        passwordInput.addEventListener("keyup", (e) => {
            if (e.key === "Backspace" || e.key === "Enter" || e.key === "Tab") return;
            let now = performance.now();
            if (pendingKeyDowns[e.key] !== undefined) {
                let dTime = pendingKeyDowns[e.key];
                dwellTimes.push((now - dTime) / 1000);
                delete pendingKeyDowns[e.key];
            }
            if (lastKeyUpTime !== null) u2uTimes.push((now - lastKeyUpTime) / 1000);
            lastKeyUpTime = now;
        });
    }
});