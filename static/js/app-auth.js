// Shared behaviour for the signed-out pages: login, forgot password, reset password.
// Each page marks its form with data-auth-form and sets its button labels as data
// attributes; every part below only runs when its elements exist on the page.
(function () {
    const form = document.querySelector('[data-auth-form]');
    if (!form) { return; }

    const submitButton = form.querySelector('[type="submit"]');
    const submitLabel = submitButton && submitButton.querySelector('[data-label]');
    const submitIcon = submitButton && submitButton.querySelector('[data-icon]');
    const note = document.getElementById('form-note');
    const offlineBanner = document.getElementById('offline-banner');
    const passwordInput = document.getElementById('password');
    const confirmInput = document.getElementById('confirm_password');
    const toggleButton = document.getElementById('toggle-password');
    const capsHint = document.getElementById('capslock-hint');
    const matchHint = document.getElementById('match-hint');
    const serverAlert = document.querySelector('.alert-login');

    const idleLabel = form.dataset.idleLabel || 'SUBMIT';
    const busyLabel = form.dataset.busyLabel || 'WORKING';
    const idleIcon = submitIcon ? submitIcon.dataset.icon : '';
    const needsOnline = form.hasAttribute('data-needs-online');
    let submitting = false;
    let timers = [];

    function setNote(text) {
        if (note) { note.textContent = text || ''; }
    }

    function setButton(label, busy) {
        if (submitLabel) { submitLabel.textContent = label; }
        if (submitIcon) {
            submitIcon.className = 'fa-solid ' + (busy ? 'fa-spinner fa-spin' : idleIcon);
        }
    }

    // Password visibility toggle.
    if (toggleButton && passwordInput) {
        const toggleIcon = toggleButton.querySelector('i');
        toggleButton.addEventListener('click', function () {
            const nowVisible = passwordInput.type === 'password';
            passwordInput.type = nowVisible ? 'text' : 'password';
            toggleButton.setAttribute('aria-pressed', nowVisible ? 'true' : 'false');
            toggleButton.setAttribute('aria-label', nowVisible ? 'Hide password' : 'Show password');
            if (toggleIcon) {
                toggleIcon.classList.toggle('fa-eye', !nowVisible);
                toggleIcon.classList.toggle('fa-eye-slash', nowVisible);
            }
            passwordInput.focus();
        });
    }

    // Caps lock warning. getModifierState is unavailable on most touch keyboards,
    // which simply leaves the hint hidden.
    if (passwordInput && capsHint) {
        const updateCapsHint = function (event) {
            if (typeof event.getModifierState !== 'function') { return; }
            capsHint.classList.toggle('is-visible', event.getModifierState('CapsLock'));
        };
        passwordInput.addEventListener('keydown', updateCapsHint);
        passwordInput.addEventListener('keyup', updateCapsHint);
        passwordInput.addEventListener('blur', function () { capsHint.classList.remove('is-visible'); });
    }

    // Inline match feedback (reset page). The server still validates on submit.
    function passwordsMismatch() {
        return Boolean(confirmInput && passwordInput && confirmInput.value && confirmInput.value !== passwordInput.value);
    }
    if (matchHint && confirmInput && passwordInput) {
        const updateMatchHint = function () { matchHint.classList.toggle('is-visible', passwordsMismatch()); };
        confirmInput.addEventListener('input', updateMatchHint);
        passwordInput.addEventListener('input', updateMatchHint);
    }

    // Connection status. The banner text is written on each change so screen readers
    // announce it; toggling display alone is often not read out.
    function updateConnectionState() {
        const online = navigator.onLine !== false;
        if (offlineBanner) {
            offlineBanner.classList.toggle('is-visible', !online);
            const text = offlineBanner.querySelector('[data-offline-text]');
            if (text) { text.textContent = online ? '' : text.dataset.offlineText; }
        }
        if (needsOnline && submitButton && !submitting) {
            submitButton.disabled = !online;
            setButton(online ? idleLabel : 'OFFLINE', false);
        }
    }
    window.addEventListener('online', updateConnectionState);
    window.addEventListener('offline', updateConnectionState);
    updateConnectionState();

    // Submit: block empty required fields, then guard against double taps. A weak
    // signal is announced instead of silently resetting the button, and the user can
    // try again after 20 seconds.
    form.addEventListener('submit', function (event) {
        if (submitting) { event.preventDefault(); return; }

        const empty = Array.prototype.filter.call(form.querySelectorAll('[required]'), function (input) {
            return !String(input.value || '').trim();
        });
        form.querySelectorAll('[required]').forEach(function (input) {
            input.setAttribute('aria-invalid', empty.indexOf(input) === -1 ? 'false' : 'true');
        });
        if (empty.length) {
            event.preventDefault();
            const label = form.querySelector('label[for="' + empty[0].id + '"]');
            setNote('Enter your ' + (label ? label.textContent.trim().toLowerCase() : 'details') + '.');
            empty[0].focus();
            return;
        }
        if (passwordsMismatch()) {
            event.preventDefault();
            setNote('Passwords do not match.');
            confirmInput.focus();
            return;
        }

        submitting = true;
        setNote('');
        if (submitButton) { submitButton.disabled = true; }
        setButton(busyLabel, true);
        timers.forEach(clearTimeout);
        timers = [
            setTimeout(function () {
                setButton('STILL CONNECTING', true);
                setNote('Slow connection. Keep this page open.');
            }, 5000),
            setTimeout(function () {
                submitting = false;
                if (submitButton) { submitButton.disabled = false; }
                updateConnectionState();
                if (!submitButton || !submitButton.disabled) { setButton('TRY AGAIN', false); }
            }, 20000)
        ];
    });

    // Focus: after a server error go straight to the password (the username is kept);
    // otherwise focus the first field on desktop only, so phones don't pop the keyboard.
    if (serverAlert && passwordInput) {
        passwordInput.focus();
    } else if (window.matchMedia && window.matchMedia('(pointer: fine)').matches) {
        const first = form.querySelector('input:not([type="hidden"])');
        if (first) { first.focus(); }
    }
})();
