(function () {
    'use strict';
    const root = document.documentElement;
    const VALID_MODES = ['light', 'graphite', 'dark', 'system'];
    const QUICK_MODE_CYCLE = ['light', 'graphite', 'dark'];
    const NEXT_MODE_META = {
        light: { icon: 'fa-circle-half-stroke', label: 'Switch to Graphite Dark' },
        graphite: { icon: 'fa-moon', label: 'Switch to AMOLED Black' },
        dark: { icon: 'fa-sun', label: 'Switch to Light' },
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
        const current = normalizeMode(state.mode) === 'system' ? effective(state.mode) : normalizeMode(state.mode);
        const next = NEXT_MODE_META[current] || NEXT_MODE_META.light;
        document.querySelectorAll('.appearance-header-icon').forEach(icon => {
            icon.className = `appearance-header-icon fa-solid ${next.icon}`;
        });
        document.querySelectorAll('.appearance-header-button').forEach(button => {
            button.title = next.label;
            button.setAttribute('aria-label', button.title);
            button.disabled = quickToggleBusy || state.pending;
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
    async function toggleQuick() {
        if (quickToggleBusy || state.pending) return { success: false, busy: true };
        quickToggleBusy = true;
        refreshButtons();
        try {
            return await save(nextQuickMode(state.mode), state.accent);
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
