let dwellTimes = [];
let flightTimes = [];
let d2dTimes = [];
let u2uTimes = [];
let trigraphs = []; // 🔹 BARU: Tri-graph rhythm (n1 to n3)
let keySequence = [];
let pendingKeyDowns = {};
let lastKeyDownTime = null;
let lastKeyUpTime = null;
let startTime = null;

// Keystroke Buffer untuk Tri-graph
let keyTimeBuffer = []; 

window.getKeystrokeData = function () {
    const passwordInput = document.getElementById('password');
    const totalChar = passwordInput ? passwordInput.value.length : 0;

    let speedCPM = 0;
    if (startTime && lastKeyUpTime) {
        let totalTimeSec = (lastKeyUpTime - startTime) / 1000;
        speedCPM = totalTimeSec > 0 ? (totalChar / totalTimeSec) * 60 : 0;
    }

    // Hitung Jitter (Variasi Mikro)
    let jitter = 0;
    if (dwellTimes.length > 1) {
        let diffs = [];
        for (let i = 1; i < dwellTimes.length; i++) {
            diffs.push(Math.abs(dwellTimes[i] - dwellTimes[i-1]));
        }
        jitter = diffs.reduce((a, b) => a + b, 0) / diffs.length;
    }

    return JSON.stringify({
        dwell: dwellTimes,
        flight: flightTimes,
        d2d: d2dTimes,
        u2u: u2uTimes,
        trigraph: trigraphs, // 🔹 KIRIM: Tri-graph
        jitter: parseFloat(jitter.toFixed(6)), // 🔹 KIRIM: Jitter detection
        keys: keySequence,
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
        trigraphs = [];
        keySequence = [];
        pendingKeyDowns = {};
        lastKeyDownTime = null;
        lastKeyUpTime = null;
        startTime = null;
        keyTimeBuffer = [];
    };

    const showNotice = (msg) => {
        if (jsErrorDisplay) {
            jsErrorDisplay.innerText = msg;
            setTimeout(() => { jsErrorDisplay.innerText = ""; }, 3000);
        }
    };

    if (passwordInput) {
        passwordInput.addEventListener("paste", (e) => {
            e.preventDefault();
            passwordInput.value = "";
            resetData();
            showNotice("Copy-paste dilarang!");
        });

        passwordInput.addEventListener("drop", (e) => {
            e.preventDefault();
            passwordInput.value = "";
            resetData();
            showNotice("Input otomatis dilarang!");
        });

        passwordInput.addEventListener("contextmenu", (e) => e.preventDefault());

        passwordInput.addEventListener("input", (e) => {
            if (passwordInput.value === "") resetData();
        });

        passwordInput.addEventListener("focus", resetData);

        const IGNORE_KEYS = new Set([
            "Shift", "Control", "Alt", "Meta", "CapsLock", "Tab", "Enter", "Backspace", "Escape",
            "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"
        ]);

        const MAX_DWELL = 2.0; 
        const MIN_DWELL = 0.010; // 10ms (Lebih ketat untuk noise hardware)

        passwordInput.addEventListener("keydown", (e) => {
            if (e.repeat || IGNORE_KEYS.has(e.key)) return;

            // --- NETWORK LATENCY COMPENSATION ---
            // Menggunakan performance.now() untuk akurasi sub-millisecond
            let now = performance.now();
            if (startTime === null) startTime = now;

            if (Object.keys(pendingKeyDowns).length > 8) {
                resetData();
                showNotice("Input terlalu cepat/tidak wajar!");
                return;
            }

            pendingKeyDowns[e.code] = now;
            keySequence.push(e.key);
            keyTimeBuffer.push(now);

            // Hitung Tri-graph (n to n+2)
            if (keyTimeBuffer.length >= 3) {
                let tri = (now - keyTimeBuffer[keyTimeBuffer.length - 3]) / 1000;
                trigraphs.push(parseFloat(tri.toFixed(4)));
            }

            if (lastKeyDownTime !== null) {
                let d2d = (now - lastKeyDownTime) / 1000;
                if (d2d > 0.005) d2dTimes.push(parseFloat(d2d.toFixed(4)));
            }
            
            if (lastKeyUpTime !== null) {
                let flight = (now - lastKeyUpTime) / 1000;
                flightTimes.push(parseFloat(flight.toFixed(4)));
            }
            
            lastKeyDownTime = now;
        });

        passwordInput.addEventListener("keyup", (e) => {
            if (IGNORE_KEYS.has(e.key)) return;
            
            let now = performance.now();
            if (pendingKeyDowns[e.code] !== undefined) {
                let dTime = pendingKeyDowns[e.code];
                let dwell = (now - dTime) / 1000;
                
                if (dwell > MAX_DWELL) {
                    resetData();
                    showNotice("Sensor lag terdeteksi. Ulangi.");
                    passwordInput.value = "";
                    return;
                }
                
                if (dwell >= MIN_DWELL) {
                    dwellTimes.push(parseFloat(dwell.toFixed(4)));
                    if (lastKeyUpTime !== null) {
                        let u2u = (now - lastKeyUpTime) / 1000;
                        u2uTimes.push(parseFloat(u2u.toFixed(4)));
                    }
                    lastKeyUpTime = now;
                }
                
                delete pendingKeyDowns[e.code];
            }
        });
    }
});