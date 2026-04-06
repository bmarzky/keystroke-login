let dwellTimes = [];
let flightTimes = [];
let d2dTimes = [];
let u2uTimes = [];
let pendingKeyDowns = {}; // Menggunakan objek untuk mapping key -> time
let lastKeyDownTime = null;
let lastKeyUpTime = null;
let startTime = null;

window.getKeystrokeData = function() {
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
        speed: parseFloat(speedCPM.toFixed(2))
    });
};

document.addEventListener("DOMContentLoaded", () => {
    const passwordInput = document.getElementById('password');

    const resetData = () => {
        dwellTimes = []; flightTimes = []; d2dTimes = []; u2uTimes = [];
        pendingKeyDowns = {}; lastKeyDownTime = null; lastKeyUpTime = null;
        startTime = null;
        console.log("Data Keystroke Reset.");
    };

    if (passwordInput) {
        passwordInput.addEventListener("focus", resetData);
        
        passwordInput.addEventListener("keydown", (e) => {
            if (e.repeat || e.key === "Process") return;
            if (e.key === "Backspace") { resetData(); return; }

            let now = Date.now();
            if (startTime === null) startTime = now;

            // Simpan waktu tekan dengan ID unik (key + timestamp) 
            // agar tidak bentrok jika ada huruf ganda
            let keyId = e.key + "_" + now;
            pendingKeyDowns[e.key] = now; 

            // Hitung D2D (Down-to-Down)
            if (lastKeyDownTime !== null) {
                d2dTimes.push((now - lastKeyDownTime) / 1000);
            }

            // Hitung Flight (Up-to-Down)
            if (lastKeyUpTime !== null) {
                flightTimes.push((now - lastKeyUpTime) / 1000);
            }

            lastKeyDownTime = now;
        });

        passwordInput.addEventListener("keyup", (e) => {
            if (e.key === "Backspace") return;
            let now = Date.now();

            // Ambil waktu pasangannya dari pendingKeyDowns
            if (pendingKeyDowns[e.key]) {
                let dTime = pendingKeyDowns[e.key];
                dwellTimes.push((now - dTime) / 1000);
                delete pendingKeyDowns[e.key]; // Hapus setelah dihitung
            }

            // Hitung U2U (Up-to-Up)
            if (lastKeyUpTime !== null) {
                u2uTimes.push((now - lastKeyUpTime) / 1000);
            }

            lastKeyUpTime = now;
        });
    }
});