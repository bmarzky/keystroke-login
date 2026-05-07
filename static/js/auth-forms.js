/*
 * Auth form behavior for login and register pages.
 * Menangani validasi biometrik, auto-hide pesan, dan navigasi keyboard.
 */

const AuthForm = (() => {
    const MESSAGE_TTL = 3000;

    const getElement = (selector) => document.querySelector(selector);

    const hideAfterDelay = (element) => {
        if (!element) return;
        element.style.opacity = '1';
        setTimeout(() => {
            element.style.opacity = '0';
            setTimeout(() => {
                element.textContent = '';
                element.style.opacity = '1';
            }, 250);
        }, MESSAGE_TTL);
    };

    const showError = (message) => {
        const errorElement = getElement('#js-error-msg');
        if (!errorElement) return;
        errorElement.textContent = message;
        hideAfterDelay(errorElement);
    };

    const getKeystrokePayload = () => {
        if (typeof window.getKeystrokeData !== 'function') {
            return null;
        }

        try {
            const payload = window.getKeystrokeData();
            return JSON.parse(payload);
        } catch (error) {
            return null;
        }
    };

    const handleFormSubmit = (event) => {
        const form = event.target;
        const keystrokeInput = getElement('#keystrokeData');
        const parsed = getKeystrokePayload();
        const isRegister = form.id === 'registerForm';

        if (!parsed || !Array.isArray(parsed.dwell) || parsed.dwell.length === 0) {
            event.preventDefault();
            showError('Pola ketikan tidak terdeteksi. Silakan ketik ulang password.');
            return;
        }

        if (isRegister && parsed.dwell.length < 5) {
            event.preventDefault();
            showError('Pola ketikan terlalu pendek. Silakan ketik ulang.');
            return;
        }

        if (keystrokeInput) {
            keystrokeInput.value = JSON.stringify(parsed);
        }
    };

    const initKeyboardNavigation = () => {
        const username = getElement('#username');
        const password = getElement('#password');
        const form = getElement('#loginForm') || getElement('#registerForm');

        if (username) {
            username.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    password?.focus();
                }
            });
        }

        if (password) {
            password.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    setTimeout(() => {
                        form?.requestSubmit();
                    }, 100);
                }
            });
        }
    };

    const initBiometricProtection = () => {
        // CATATAN: Listener paste, drop, contextmenu, dan input sudah
        // ditangani sepenuhnya oleh keystroke.js agar tidak terjadi
        // double-firing event. File ini hanya menangani UX (pesan & navigasi).
        const passwordInput = getElement('#password');
        const noticeTarget = getElement('#js-error-msg');

        if (!passwordInput || !noticeTarget) return;

        // Hanya clear pesan saat user kembali fokus ke kolom password
        passwordInput.addEventListener('focus', () => {
            noticeTarget.textContent = '';
        });
    };

    const initAutoHide = () => {
        const statusMsg = getElement('#status-msg');
        const jsErrorMsg = getElement('#js-error-msg');

        if (statusMsg && statusMsg.textContent.trim() !== '') {
            hideAfterDelay(statusMsg);
        }

        if (jsErrorMsg) {
            const observer = new MutationObserver(() => {
                if (jsErrorMsg.textContent.trim() !== '') {
                    hideAfterDelay(jsErrorMsg);
                }
            });
            observer.observe(jsErrorMsg, { childList: true });
        }
    };

    const init = () => {
        const form = getElement('#loginForm') || getElement('#registerForm');
        if (form) {
            form.addEventListener('submit', handleFormSubmit);
        }

        initKeyboardNavigation();
        initBiometricProtection();
        initAutoHide();
    };

    return { init };
})();

window.addEventListener('DOMContentLoaded', AuthForm.init);
