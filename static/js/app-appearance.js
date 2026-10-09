(function () {
    'use strict';
    const root = document.documentElement;
    const VALID_MODES = ['light', 'graphite', 'dark', 'system'];
    const QUICK_MODE_CYCLE = ['light', 'graphite', 'dark'];
    // The quick switch names and shows the theme that is on now; its accessible
    // name starts with that visible label and then says what a tap does.
    const MODE_META = {
        light: { icon: 'fa-sun', name: 'Light' },
        graphite: { icon: 'fa-circle-half-stroke', name: 'Graphite Dark' },
        dark: { icon: 'fa-moon', name: 'AMOLED Black' },
    };
    const initial = window.__initialAppearance || { mode: 'light', accent: 'classic', userId: null };
    const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    let state = { mode: normalizeMode(initial.mode), accent: initial.accent || 'classic', pending: !!initial.pending };
    let quickToggleBusy = false;
    const scopedKey = initial.userId ? `medical_appearance_user_${initial.userId}` : null;
    const lastKey = 'medical_appearance_last';

    function normalizeMode(mode) { return VALID_MODES.includes(mode) ? mode : 'light'; }
    function effective(mode) {
        const normalized = normalizeMode(mode);
        if (normalized === 'system') return media && media.matches ? 'dark' : 'light';
        return normalized === 'graphite' ? 'dark' : normalized;
    }
    function paletteFor(mode) {
        const normalized = normalizeMode(mode);
        if (normalized === 'graphite') return 'graphite';
        return effective(normalized) === 'dark' ? 'amoled' : 'light';
    }
    function nextQuickMode(mode) {
        const normalized = normalizeMode(mode);
        const current = normalized === 'system' ? effective(normalized) : normalized;
        const index = QUICK_MODE_CYCLE.indexOf(current);
        return QUICK_MODE_CYCLE[(index + 1) % QUICK_MODE_CYCLE.length];
    }
    function browserThemeColor(mode) {
        const palette = paletteFor(mode);
        return palette === 'graphite' ? '#202124' : (palette === 'amoled' ? '#000000' : '#2c3e50');
    }
    function csrf() { const tag = document.querySelector('meta[name="csrf-token"]'); return tag ? tag.content : ''; }
    function cache(next, pending) {
        const stored = { mode: next.mode, accent: next.accent, pending: !!pending, savedAt: new Date().toISOString() };
        try { localStorage.setItem(lastKey, JSON.stringify(stored)); if (scopedKey) localStorage.setItem(scopedKey, JSON.stringify(stored)); } catch (_) {}
    }
    function refreshButtons() {
        const normalized = normalizeMode(state.mode);
        const current = normalized === 'system' ? (effective(normalized) === 'dark' ? 'dark' : 'light') : normalized;
        const meta = MODE_META[current] || MODE_META.light;
        const next = MODE_META[nextQuickMode(state.mode)] || MODE_META.light;
        const label = `Theme: ${meta.name}`;
        document.querySelectorAll('.appearance-header-icon').forEach(icon => {
            icon.className = `appearance-header-icon fa-solid ${meta.icon}`;
        });
        document.querySelectorAll('.appearance-header-button').forEach(button => {
            button.title = `${label}, switch to ${next.name}`;
            button.setAttribute('aria-label', button.title);
            const text = button.querySelector('.appearance-header-label');
            if (text) text.textContent = label;
            // Offline the choice stays pending until it can be saved; the button
            // keeps working meanwhile (only a save in flight blocks it).
            button.disabled = quickToggleBusy;
            button.setAttribute('aria-busy', quickToggleBusy ? 'true' : 'false');
        });
    }
    function apply(mode, accent, options) {
        state = { mode: normalizeMode(mode), accent: accent || 'classic', pending: !!(options && options.pending) };
        const resolved = effective(state.mode);
        root.dataset.appTheme = resolved;
        root.dataset.bsTheme = resolved;
        root.dataset.appPalette = paletteFor(state.mode);
        root.dataset.accentTheme = state.accent;
        const themeMeta = document.querySelector('meta[name="theme-color"]');
        if (themeMeta) themeMeta.content = browserThemeColor(state.mode);
        cache(state, state.pending);
        refreshButtons();
        window.dispatchEvent(new CustomEvent('app-theme-changed', { detail: { ...state, effectiveMode: resolved } }));
        return state;
    }
    async function save(mode, accent) {
        apply(mode, accent, { pending: true });
        if (!initial.userId || !navigator.onLine) return { success: false, offline: true };
        try {
            const response = await fetch('/api/preferences/appearance', {
                method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify({ mode, accent }), credentials: 'same-origin'
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Unable to save appearance.');
            apply(data.mode, data.accent, { pending: false });
            return data;
        } catch (error) {
            apply(mode, accent, { pending: true });
            return { success: false, error: error.message, offline: !navigator.onLine };
        }
    }
    async function sync() {
        if (!initial.userId || !navigator.onLine) return;
        let cached = null;
        try { cached = scopedKey ? JSON.parse(localStorage.getItem(scopedKey) || 'null') : null; } catch (_) {}
        if (cached && cached.pending) { await save(cached.mode, cached.accent); return; }
        try {
            const response = await fetch('/api/preferences/appearance', { credentials: 'same-origin', cache: 'no-store' });
            const data = await response.json();
            if (response.ok && data.success) apply(data.mode, data.accent, { pending: false });
        } catch (_) {}
    }
    const MODE_NAMES = { light: 'Light', graphite: 'Graphite Dark', dark: 'AMOLED Black', system: 'System' };
    let noticeTimer = null;
    // One tap changes and saves the theme, so say what happened and offer Undo
    // (shell critique 2026-10-08, point 6). The notice stays while it is hovered
    // or focused, so Undo can be reached by mouse and keyboard.
    function noticeElement() {
        let notice = document.getElementById('appearance-notice');
        if (notice) return notice;
        notice = document.createElement('div');
        notice.id = 'appearance-notice';
        notice.className = 'appearance-notice no-print';
        const text = document.createElement('span');
        text.setAttribute('role', 'status');
        text.setAttribute('aria-live', 'polite');
        const undo = document.createElement('button');
        undo.type = 'button';
        undo.className = 'appearance-notice-undo';
        undo.textContent = 'Undo';
        notice.append(text, undo);
        const hold = () => clearTimeout(noticeTimer);
        const release = () => { clearTimeout(noticeTimer); noticeTimer = setTimeout(() => notice.classList.remove('is-visible'), 4000); };
        notice.addEventListener('mouseenter', hold);
        notice.addEventListener('focusin', hold);
        notice.addEventListener('mouseleave', release);
        notice.addEventListener('focusout', release);
        notice.text = text;
        notice.undo = undo;
        document.body.appendChild(notice);
        return notice;
    }
    function showNotice(message, undoTo) {
        const notice = noticeElement();
        notice.text.textContent = message;
        notice.undo.hidden = !undoTo;
        notice.undo.onclick = undoTo ? async () => {
            notice.undo.hidden = true;
            await save(undoTo.mode, undoTo.accent);
            showNotice(`Back to ${MODE_NAMES[normalizeMode(undoTo.mode)]} theme.`, null);
        } : null;
        notice.classList.add('is-visible');
        clearTimeout(noticeTimer);
        noticeTimer = setTimeout(() => notice.classList.remove('is-visible'), undoTo ? 6000 : 3000);
    }
    async function toggleQuick() {
        if (quickToggleBusy) return { success: false, busy: true };
        quickToggleBusy = true;
        refreshButtons();
        const previous = { mode: state.mode, accent: state.accent };
        const mode = nextQuickMode(state.mode);
        try {
            const result = await save(mode, state.accent);
            // Leaving System is said out loud (Undo returns to it), and a choice that
            // could not be saved yet says where it is kept.
            const leftSystem = normalizeMode(previous.mode) === 'system' ? 'System theme off. ' : '';
            const pending = result && result.success === false ? ' Saved on this device; it syncs when you are back online.' : '';
            showNotice(`${leftSystem}${MODE_NAMES[mode]} theme on.${pending}`, previous);
            return result;
        } finally {
            quickToggleBusy = false;
            refreshButtons();
        }
    }

    window.appAppearance = { apply, save, sync, toggleQuick, getState: () => ({ ...state, effectiveMode: effective(state.mode) }) };
    document.addEventListener('DOMContentLoaded', function () { apply(state.mode, state.accent, { pending: state.pending }); sync(); });
    window.addEventListener('online', sync);
    if (media) media.addEventListener('change', function () { if (state.mode === 'system') apply(state.mode, state.accent, { pending: state.pending }); });
})();
