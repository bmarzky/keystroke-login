/*
 * Auth form behavior for login and register pages.
 * Menangani validasi biometrik, auto-hide pesan, dan navigasi keyboard.
 */

const AuthForm = (() => {
    const MESSAGE_TTL = 3000;

    const getElement = (selector) => document.querySelector(selector);

    const hideAfterDelay = (element) => {
        if (!element) return;
        setTimeout(() => {
            element.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => {
                element.remove();
            }, 300);
        }, MESSAGE_TTL);
    };

    const createToast = (message, type = 'error') => {
        const container = getElement('#toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type === 'error' ? 'error-box' : 'success-box'}`;
        toast.textContent = message;
        container.appendChild(toast);
        hideAfterDelay(toast);
    };

    const showError = (message) => {
        createToast(message, 'error');
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
            const container = getElement('#toast-container');
            if (container) {
                // Opsional: hapus toast lama saat fokus
                // container.innerHTML = ''; 
            }
        });
    };

    const initShowPassword = () => {
        const toggleBtn = getElement('#toggle-password');
        const passwordInput = getElement('#password');

        if (toggleBtn && passwordInput) {
            toggleBtn.addEventListener('click', () => {
                const isPassword = passwordInput.type === 'password';
                passwordInput.type = isPassword ? 'text' : 'password';
                
                // Ganti icon SVG
                toggleBtn.innerHTML = isPassword 
                    ? '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="eye-off-icon"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" y1="2" x2="22" y2="22"/></svg>'
                    : '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="eye-icon"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>';
            });
        }
    };

    const initAutoHide = () => {
        const statusMsg = getElement('#status-msg');
        if (statusMsg && statusMsg.textContent.trim() !== '') {
            hideAfterDelay(statusMsg);
        }
    };

    const init = () => {
        const form = getElement('#loginForm') || getElement('#registerForm');
        if (form) {
            form.addEventListener('submit', handleFormSubmit);
        }

        initKeyboardNavigation();
        initBiometricProtection();
        initShowPassword();
        initAutoHide();
    };

    return { init };
})();

window.addEventListener('DOMContentLoaded', AuthForm.init);
