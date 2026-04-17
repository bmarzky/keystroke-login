let dwellTimes = [];
let flightTimes = [];
let d2dTimes = [];
let u2uTimes = [];
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
        speed: parseFloat(speedCPM.toFixed(2))
    });
};

document.addEventListener("DOMContentLoaded", () => {
    const passwordInput = document.getElementById('password');
    const jsErrorDisplay = document.getElementById("js-error-msg");

    // Validasi panjang password minimal
    passwordInput.addEventListener('input', () => {
        if (passwordInput.value.length < 6 && passwordInput.value.length > 0) {
            showNotice('Password must be at least 6 characters');
        } else if (passwordInput.value.length >= 6) {
            showNotice(''); // Clear the notice
        }
    });

    const resetData = () => {
        dwellTimes = []; flightTimes = []; d2dTimes = []; u2uTimes = [];
        pendingKeyDowns = {}; lastKeyDownTime = null; lastKeyUpTime = null;
        startTime = null;
        console.log("Data Keystroke Reset.");
    };

    // Fungsi untuk menampilkan pesan error di halaman (pengganti alert)
    const showNotice = (msg) => {
        if (jsErrorDisplay) {
            jsErrorDisplay.innerText = "" + msg;
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

        // Monitor input ilegal (autofill/bypass)
        passwordInput.addEventListener("input", (e) => {
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
            // if (e.key === "Backspace") { resetData(); return; } 
            if (e.key === "Backspace") return; // Abaikan backspace tapi jangan hapus data yang sudah ada

            let now = Date.now();
            if (startTime === null) startTime = now;
            pendingKeyDowns[e.key] = now;

            if (lastKeyDownTime !== null) d2dTimes.push((now - lastKeyDownTime) / 1000);
            if (lastKeyUpTime !== null) flightTimes.push((now - lastKeyUpTime) / 1000);
            lastKeyDownTime = now;
        });

        // --- EVENT KEYUP ---
        passwordInput.addEventListener("keyup", (e) => {
            if (e.key === "Backspace") return;
            let now = Date.now();
            if (pendingKeyDowns[e.key]) {
                let dTime = pendingKeyDowns[e.key];
                dwellTimes.push((now - dTime) / 1000);
                delete pendingKeyDowns[e.key];
            }
            if (lastKeyUpTime !== null) u2uTimes.push((now - lastKeyUpTime) / 1000);
            lastKeyUpTime = now;
        });
    }
});