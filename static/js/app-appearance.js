(function () {
    'use strict';
    const root = document.documentElement;
    const initial = window.__initialAppearance || { mode: 'light', accent: 'classic', userId: null };
    const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    let state = { mode: initial.mode || 'light', accent: initial.accent || 'classic', pending: !!initial.pending };
    const scopedKey = initial.userId ? `medical_appearance_user_${initial.userId}` : null;
    const lastKey = 'medical_appearance_last';

    function effective(mode) { return mode === 'system' ? (media && media.matches ? 'dark' : 'light') : mode; }
    function csrf() { const tag = document.querySelector('meta[name="csrf-token"]'); return tag ? tag.content : ''; }
    function cache(next, pending) {
        const stored = { mode: next.mode, accent: next.accent, pending: !!pending, savedAt: new Date().toISOString() };
        try { localStorage.setItem(lastKey, JSON.stringify(stored)); if (scopedKey) localStorage.setItem(scopedKey, JSON.stringify(stored)); } catch (_) {}
    }
    function refreshButtons() {
        const dark = effective(state.mode) === 'dark';
        document.querySelectorAll('.appearance-header-icon').forEach(icon => {
            icon.className = `appearance-header-icon fa-solid ${dark ? 'fa-sun' : 'fa-moon'}`;
        });
        document.querySelectorAll('.appearance-header-button').forEach(button => {
            button.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
            button.setAttribute('aria-label', button.title);
        });
    }
    function apply(mode, accent, options) {
        state = { mode: mode || 'light', accent: accent || 'classic', pending: !!(options && options.pending) };
        const resolved = effective(state.mode);
        root.dataset.appTheme = resolved;
        root.dataset.bsTheme = resolved;
        root.dataset.accentTheme = state.accent;
        const themeMeta = document.querySelector('meta[name="theme-color"]');
        if (themeMeta) themeMeta.content = resolved === 'dark' ? '#101925' : '#2c3e50';
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
    function toggleQuick() { return save(effective(state.mode) === 'dark' ? 'light' : 'dark', state.accent); }

    window.appAppearance = { apply, save, sync, toggleQuick, getState: () => ({ ...state, effectiveMode: effective(state.mode) }) };
    document.addEventListener('DOMContentLoaded', function () { apply(state.mode, state.accent, { pending: state.pending }); sync(); });
    window.addEventListener('online', sync);
    if (media) media.addEventListener('change', function () { if (state.mode === 'system') apply(state.mode, state.accent, { pending: state.pending }); });
})();
