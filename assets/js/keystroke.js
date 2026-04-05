let dwellTimes = [];
let flightTimes = [];
let keyDownTime = {};
let lastKeyUpTime = null;

window.getKeystrokeData = function() {
    console.log("DATA FINAL DIKIRIM (DETIK):", { dwell: dwellTimes, flight: flightTimes });
    return JSON.stringify({
        dwell: dwellTimes,
        flight: flightTimes
    });
};

document.addEventListener("DOMContentLoaded", () => {
    const passwordInput = document.getElementById('password'); 

    if (passwordInput) {
        passwordInput.addEventListener("focus", () => {
            dwellTimes = [];
            flightTimes = [];
            keyDownTime = {};
            lastKeyUpTime = null; 
            console.log("Data Reset (Fokus pada Password)");
        });

        passwordInput.addEventListener("keydown", (e) => {
            if (e.repeat) return; 

            let now = Date.now();
            keyDownTime[e.key] = now;

            if (lastKeyUpTime !== null && dwellTimes.length > 0) {
                // --- UBAH DI SINI: Bagi 1000 agar jadi detik ---
                let flight = (now - lastKeyUpTime) / 1000; 
                flightTimes.push(flight);
                
                console.log(`Flight [${e.key}]: ${flight} detik`);
            }
        });

        passwordInput.addEventListener("keyup", (e) => {
            let now = Date.now();

            if (keyDownTime[e.key]) {
                // --- UBAH DI SINI: Bagi 1000 agar jadi detik ---
                let dwell = (now - keyDownTime[e.key]) / 1000;
                dwellTimes.push(dwell);
                
                console.log(`Dwell [${e.key}]: ${dwell} detik`);
                
                delete keyDownTime[e.key];
            }
            lastKeyUpTime = now;
        });
    }
});