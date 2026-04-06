let dwellTimes = [];
let flightTimes = [];
let keyDownTime = [];
let lastKeyUpTime = null;
let keyIndex = 0;

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
            keyDownTime = [];
            lastKeyUpTime = null;
            keyIndex = 0;

            console.log("Data Reset (Fokus Password)");
        });

        passwordInput.addEventListener("keydown", (e) => {
            if (e.repeat) return;

            // 🔴 HANDLE BACKSPACE (WAJIB)
            if (e.key === "Backspace") {
                dwellTimes = [];
                flightTimes = [];
                keyDownTime = [];
                lastKeyUpTime = null;
                keyIndex = 0;

                console.log("RESET karena Backspace");
                return;
            }

            let now = Date.now();

            // Simpan berdasarkan urutan ketikan
            keyDownTime[keyIndex] = now;

            if (lastKeyUpTime !== null && dwellTimes.length > 0) {
                let flight = (now - lastKeyUpTime) / 1000;
                flightTimes.push(flight);

                console.log(`Flight index-${keyIndex}: ${flight}`);
            }

            keyIndex++;
        });

        passwordInput.addEventListener("keyup", (e) => {
            let now = Date.now();

            let index = keyIndex - 1;

            if (keyDownTime[index]) {
                let dwell = (now - keyDownTime[index]) / 1000;
                dwellTimes.push(dwell);

                console.log(`Dwell index-${index}: ${dwell}`);

                delete keyDownTime[index];
            }

            lastKeyUpTime = now;
        });
    }
});