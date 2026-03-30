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

// Tunggu DOM selesai dimuat agar getElementById tidak null
document.addEventListener("DOMContentLoaded", () => {
    const passwordInput = document.getElementById('password'); 

    if (passwordInput) {
        passwordInput.addEventListener("keydown", (e) => {
            if (e.repeat) return; 

            keyDownTime[e.key] = Date.now();

            if (lastKeyUpTime !== null) {
                let flight = Date.now() - lastKeyUpTime;
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

            lastKeyUpTime = now;
        });
    }
});