const runTutorial = () => {
    // 1. Cek storage
// Check if user has already seen the tutorial
    const hasSeenTutorial = localStorage.getItem('keystroke_tutorial_done');

    // Log untuk memastikan fungsi terpanggil
    console.log("Memeriksa tutorial... Status di storage:", hasSeenTutorial);

    if (hasSeenTutorial === 'true') {
        return;
    }

    // 2. Inisialisasi Driver.js (Library untuk Panduan Interaktif)
    // Menggunakan cara yang lebih aman untuk versi IIFE
    const driver = window.driver.js.driver;

    const driverObj = driver({
        showProgress: true,
        allowClose: false,
        overlayColor: 'rgba(0,0,0,0.75)',

        nextBtnText: 'Next',
        prevBtnText: 'Previous',
        doneBtnText: 'Done',

        onDestroyed: () => {
            localStorage.setItem('keystroke_tutorial_done', 'true');
            console.log("Tutorial selesai, storage diupdate.");
        },
        steps: [
            {
                popover: {
                    title: 'Selamat Datang!',
                    description: 'Sistem Login ini menggunakan <b>Keystroke Dynamics</b> untuk mengenali Kamu melalui cara Kamu mengetik.'
                }
            },
            {
                element: '#username',
                popover: {
                    title: 'Kolom Username',
                    description: 'Masukkan username Kamu. <br><br><b>Tips:</b> Tekan tombol <b>Enter</b> untuk pindah ke kolom password secara instan.',
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '#password',
                popover: {
                    title: 'Kolom Password',
                    description: 'Ketik kata sandi Kamu seperti biasa. <br><br>Sistem akan mengenali <b>"Gaya Unik Mengetikmu"</b>, yaitu seberapa lama Kamu menekan tombol dan seberapa cepat jemarimu berpindah antar tombol. <br><br><b>Tips:</b> Ketik password Kamu dalam satu aliran. Sebisa mungkin hindari menghapus (<b>Backspace</b>) agar pola ketikanmu terekam sempurna.',
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                popover: {
                    title: 'Penting!',
                    description: 'Gunakan kebiasaan mengetik yang sama saat <b>Register</b> dan <b>Login</b> demi akurasi verifikasi.'
                }
            },
        ]
    });

    // 3. Jalankan
    driverObj.drive();
};

// Pastikan dipanggil setelah semua elemen HTML siap
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runTutorial);
} else {
    runTutorial();
}