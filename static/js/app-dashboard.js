/* Extracted from the inline <script> blocks in templates/dashboard.html.
   Behaviour is unchanged; only the 12 template-injected constants moved to
   window.__dashboardConfig, set inline by the template before this loads. */

    (function(){
        const dismissKey = 'medical_dashboard_whats_new_dismissed';
        function readDismissedRelease(){
            try { return localStorage.getItem(dismissKey) || ''; } catch (err) { return ''; }
        }
        function renderDashboardChangelogPrompt(data){
            const panel = document.getElementById('dashboard-whats-new');
            const latest = data?.latest_unread;
            if(!panel) return;
            if(!latest || Number(data.unread_count || 0) <= 0 || readDismissedRelease() === String(latest.id || '')){
                panel.style.display = 'none';
                return;
            }
            panel.dataset.releaseId = String(latest.id || '');
            document.getElementById('dashboard-whats-new-date').textContent = `${Number(data.unread_count || 0)} unread update${Number(data.unread_count || 0) === 1 ? '' : 's'} | ${latest.release_date || ''}`;
            document.getElementById('dashboard-whats-new-title').textContent = latest.title || "What's New";
            document.getElementById('dashboard-whats-new-summary').textContent = latest.summary || `${Number(latest.item_count || 0)} improvement(s) are ready to review.`;
            panel.style.display = '';
        }
        window.addEventListener('changelog:summary', event => renderDashboardChangelogPrompt(event.detail || {}));
        document.addEventListener('click', event => {
            if(!event.target.closest('#dashboard-whats-new-dismiss')) return;
            const panel = document.getElementById('dashboard-whats-new');
            if(!panel) return;
            try { localStorage.setItem(dismissKey, panel.dataset.releaseId || ''); } catch (err) { /* hide anyway */ }
            panel.style.display = 'none';
        });
    })();

    // --- APP INITIALIZATION ---
    // Values are injected by dashboard.html via window.__dashboardConfig so this file
    // stays free of template syntax and can be cached as a static asset.
    const __cfg = window.__dashboardConfig || {};
    const loggedInUser = __cfg.loggedInUser || '';
    const userRole = __cfg.userRole || '';
    const loggedInEngineerId = Number(__cfg.loggedInEngineerId) || null;
    const dashboardHasEngineerProfile = __cfg.hasEngineerProfile === true;
    const dashboardAdminView = __cfg.adminView === true;
    const dashboardSchedulerOnly = __cfg.schedulerOnly === true;
    const dashboardHybridView = __cfg.hybridView === true;
    const dashboardManagerView = __cfg.managerView === true;
    const dashboardSchedulerAccount = __cfg.schedulerAccount === true;
    const dashboardStaffLanding = __cfg.staffLanding === true;

    // v5.4.5: Real-time Manila Ticker and Date
    function updateClock() {
        const now = new Date();
        const clockOptions = { 
            timeZone: 'Asia/Manila', 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit', 
            hour12: true 
        };
        // The header subtitle: "Your work, Sunday, October 11".
        const dateOptions = {
            timeZone: 'Asia/Manila',
            weekday: 'long',
            month: 'long',
            day: 'numeric'
        };

        const manilaTime = new Intl.DateTimeFormat('en-US', clockOptions).format(now);
        const manilaDate = new Intl.DateTimeFormat('en-US', dateOptions).format(now);
        
        setTextIfPresent('system-clock', manilaTime);
        setTextIfPresent('current-date', manilaDate);
    }

    setInterval(updateClock, 1000);
    updateClock();
    
    // Global Dataset Context
    let allOpenTasksRaw = []; 
    let currentSortMode = 'scheduled_latest'; 
    let managerOverviewData = null;
    let managerWatchlistFilter = '';
    let schedulerCoordinationData = null;
    let schedulerDispatchData = null;
    let schedulerBranchFilter = 'ALL';
    let schedulerQueueFilter = 'all';
    let schedulerSelectedShift = null;
    let schedulerBoardView = 'today';
    let schedulerPendingLaneAssign = null;

    /**
     * MASTER DATA LOADER:
     * Dispatches concurrent fetch requests to sync dashboard metrics from server.
     */
    function setDashboardLoadState(state, message = '') {
        let alertBox = document.getElementById('dashboard-load-alert');
        const container = document.querySelector('.container.py-4') || document.querySelector('.container-fluid') || document.querySelector('.container');
        if (!container) return;

        if (!alertBox) {
            alertBox = document.createElement('div');
            alertBox.id = 'dashboard-load-alert';
            alertBox.className = 'alert d-none rounded-4 shadow-sm mb-3';
            alertBox.setAttribute('role', 'alert');
            container.prepend(alertBox);
        }

        if (state === 'loading') {
            alertBox.className = 'alert alert-info rounded-4 shadow-sm mb-3';
            alertBox.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin me-2"></i> Loading dashboard data...';
            return;
        }

        if (state === 'error') {
            alertBox.className = 'alert alert-warning rounded-4 shadow-sm mb-3 d-flex justify-content-between align-items-center gap-3 flex-wrap';
            alertBox.innerHTML = `
                <div><i class="fa-solid fa-triangle-exclamation me-2"></i>${escapeHtml(message || 'Dashboard failed to load. Please try again.')}</div>
                <button type="button" class="btn btn-sm btn-outline-dark fw-bold" onclick="loadDashboard()">Retry</button>
            `;
            return;
        }

        alertBox.className = 'alert d-none rounded-4 shadow-sm mb-3';
        alertBox.innerHTML = '';
    }

    async function fetchJsonOrThrow(url) {
        const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`${url} returned ${response.status}`);
        }
        return response.json();
    }

    function setTextIfPresent(elementId, value) {
        const el = document.getElementById(elementId);
        if (el) el.innerText = value;
    }

    function renderTeamEmpty(containerId, message) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = `
            <div class="dashboard-team-empty">
                <i class="fa-solid fa-circle-check me-2"></i>${escapeHtml(message || 'No team items to show.')}
            </div>`;
    }

    function toggleDashboardSection(sectionId, button) {
        const section = document.getElementById(sectionId);
        if (!section) return;

        const isHidden = section.classList.contains('d-none');
        section.classList.toggle('d-none', !isHidden);

        if (button) {
            button.innerHTML = isHidden
                ? '<i class="fa-solid fa-chevron-up me-1"></i>Hide'
                : '<i class="fa-solid fa-chevron-down me-1"></i>Show';
        }

        saveDashboardCollapsedState(sectionId, !isHidden);
    }

    // --- DASHBOARD PERSONALIZATION: DRAG / REORDER / SAVE ---
    const dashboardLayoutStorageKey = `medical_dashboard_layout_${loggedInUser || 'user'}`;
    const dashboardCollapsedStorageKey = `medical_dashboard_collapsed_${loggedInUser || 'user'}`;
    const dashboardHiddenStorageKey = `medical_dashboard_hidden_${loggedInUser || 'user'}`;
    let dashboardCustomizeMode = false;
    let dashboardDraggedSection = null;

    function getDashboardSections() {
        return Array.from(document.querySelectorAll('.dashboard-sortable-section[data-dashboard-section]'));
    }

    function getSavedDashboardOrder() {
        try {
            const saved = JSON.parse(localStorage.getItem(dashboardLayoutStorageKey) || '[]');
            return Array.isArray(saved) ? saved : [];
        } catch (err) {
            return [];
        }
    }

    function saveDashboardOrder() {
        const order = getDashboardSections().map(section => section.dataset.dashboardSection).filter(Boolean);
        // localStorage stays as the pre-render cache so the layout does not flash on the
        // next load; the account copy is the source of truth, same as the theme.
        localStorage.setItem(dashboardLayoutStorageKey, JSON.stringify(order));
        syncDashboardLayoutToAccount(order);
    }

    function getHiddenDashboardSections() {
        try {
            const saved = JSON.parse(localStorage.getItem(dashboardHiddenStorageKey) || '[]');
            return Array.isArray(saved) ? saved : [];
        } catch (err) {
            return [];
        }
    }

    function syncDashboardLayoutToAccount(order, hidden) {
        const body = {
            order: order || getDashboardSections().map(s => s.dataset.dashboardSection).filter(Boolean),
            hidden: hidden || getHiddenDashboardSections()
        };

        return fetch('/api/preferences/dashboard-layout', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken()},
            body: JSON.stringify(body)
        }).catch(error => {
            // A sync failure must never break the dashboard; the local copy still applies.
            console.warn('[Dashboard] Unable to sync layout to account', error);
        });
    }

    // The account copy wins over the local cache. Applied on load so a layout arranged
    // on another device carries over.
    async function loadDashboardLayoutFromAccount() {
        try {
            const response = await fetch('/api/preferences/dashboard-layout', {
                credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}
            });
            if (!response.ok) return;
            const data = await response.json();
            if (!data || !data.success) return;

            if (Array.isArray(data.order) && data.order.length) {
                localStorage.setItem(dashboardLayoutStorageKey, JSON.stringify(data.order));
            }
            localStorage.setItem(dashboardHiddenStorageKey, JSON.stringify(data.hidden || []));

            applySavedDashboardOrder();
            applyHiddenDashboardSections();
        } catch (error) {
            console.warn('[Dashboard] Unable to load account layout', error);
        }
    }

    function applyHiddenDashboardSections() {
        const hidden = new Set(getHiddenDashboardSections());
        getDashboardSections().forEach(section => {
            const key = section.dataset.dashboardSection;
            section.classList.toggle('dashboard-section-hidden', hidden.has(key));
        });
    }

    function setDashboardSectionHidden(sectionId, isHidden) {
        const hidden = new Set(getHiddenDashboardSections());
        isHidden ? hidden.add(sectionId) : hidden.delete(sectionId);
        const list = Array.from(hidden);
        localStorage.setItem(dashboardHiddenStorageKey, JSON.stringify(list));
        applyHiddenDashboardSections();
        syncDashboardLayoutToAccount(null, list);
    }
    window.setDashboardSectionHidden = setDashboardSectionHidden;

    function applySavedDashboardOrder() {
        const order = getSavedDashboardOrder();
        if (!order.length) return;

        const sections = getDashboardSections();
        const sectionMap = new Map(sections.map(section => [section.dataset.dashboardSection, section]));
        const container = document.querySelector('.container.py-4') || document.querySelector('.container');
        if (!container) return;

        // Append the saved order first, then anything it does not mention, in its
        // existing DOM order. A saved layout can legitimately be partial -- it may come
        // from a device or role that rendered fewer sections -- and appending only the
        // listed ones would silently float the unlisted sections to the top.
        const ordered = order.filter(key => sectionMap.has(key));
        const remaining = sections
            .map(section => section.dataset.dashboardSection)
            .filter(key => key && !ordered.includes(key));

        ordered.concat(remaining).forEach(key => {
            const section = sectionMap.get(key);
            if (section) container.appendChild(section);
        });
    }

    function getSavedCollapsedStates() {
        try {
            const saved = JSON.parse(localStorage.getItem(dashboardCollapsedStorageKey) || '{}');
            return saved && typeof saved === 'object' ? saved : {};
        } catch (err) {
            return {};
        }
    }

    function saveDashboardCollapsedState(sectionId, isCollapsed) {
        const states = getSavedCollapsedStates();
        states[sectionId] = Boolean(isCollapsed);
        localStorage.setItem(dashboardCollapsedStorageKey, JSON.stringify(states));
    }

    function applySavedCollapsedStates() {
        const states = getSavedCollapsedStates();
        Object.entries(states).forEach(([sectionId, isCollapsed]) => {
            const section = document.getElementById(sectionId);
            if (!section) return;
            section.classList.toggle('d-none', Boolean(isCollapsed));

            const button = document.querySelector(`[onclick*="${sectionId}"]`);
            if (button) {
                button.innerHTML = Boolean(isCollapsed)
                    ? '<i class="fa-solid fa-chevron-down me-1"></i>Show'
                    : '<i class="fa-solid fa-chevron-up me-1"></i>Hide';
            }
        });
    }

    function addDashboardDragHandles() {
        getDashboardSections().forEach(section => {
            if (section.querySelector(':scope > .dashboard-drag-handle')) return;
            const title = section.dataset.dashboardTitle || 'Dashboard Section';
            const handle = document.createElement('button');
            handle.type = 'button';
            handle.className = 'dashboard-drag-handle';
            handle.setAttribute('aria-label', `Drag ${title}`);
            handle.setAttribute('title', `Drag ${title}`);
            handle.innerHTML = '<i class="fa-solid fa-grip-vertical"></i>';
            section.prepend(handle);
        });
    }

    function setDashboardCustomizeMode(enabled) {
        dashboardCustomizeMode = Boolean(enabled);
        document.body.classList.toggle('dashboard-customize-active', dashboardCustomizeMode);

        const toggleButton = document.getElementById('dashboard-customize-toggle');
        if (toggleButton) {
            toggleButton.className = dashboardCustomizeMode
                ? 'btn btn-sm btn-primary fw-bold'
                : 'btn btn-sm btn-outline-primary fw-bold';
            toggleButton.innerHTML = dashboardCustomizeMode
                ? '<i class="fa-solid fa-check me-1"></i>Done'
                : '<i class="fa-solid fa-grip-vertical me-1"></i>Customize';
        }

        getDashboardSections().forEach(section => {
            section.setAttribute('draggable', dashboardCustomizeMode ? 'true' : 'false');
        });
    }

    function toggleDashboardCustomizeMode() {
        setDashboardCustomizeMode(!dashboardCustomizeMode);
    }

    function resetDashboardLayout() {
        if (!window.confirm('Reset the dashboard to the default section order?')) return;
        localStorage.removeItem(dashboardLayoutStorageKey);
        localStorage.removeItem(dashboardCollapsedStorageKey);
        localStorage.removeItem(dashboardHiddenStorageKey);
        // Clear the account copy too, otherwise the next load restores what was reset.
        syncDashboardLayoutToAccount([], []).finally(() => location.reload());
    }

    // A remodel renames a role's sections, so a layout saved against the old page is
    // cleared once. The template sets the version per role (data-dashboard-layout-version);
    // version 1 is a page that has not been remodelled, so it never resets. Resolves once
    // the account copy is cleared, so the account load that follows cannot restore it.
    function resetDashboardLayoutIfOutdated() {
        const root = document.querySelector('[data-dashboard-layout-version]');
        const version = root ? root.getAttribute('data-dashboard-layout-version') : '';
        const versionKey = `medical_dashboard_layout_version_${loggedInUser || 'user'}`;
        try {
            if (!version || localStorage.getItem(versionKey) === version) return Promise.resolve();
            localStorage.setItem(versionKey, version);
            if (version === '1') return Promise.resolve();
            localStorage.removeItem(dashboardLayoutStorageKey);
            localStorage.removeItem(dashboardCollapsedStorageKey);
            localStorage.removeItem(dashboardHiddenStorageKey);
        } catch (storageError) {
            return Promise.resolve();
        }
        // getCSRFToken() is defined by layout.html after this file runs, so the account
        // copy is cleared once the page has finished loading.
        const pageReady = document.readyState === 'loading'
            ? new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, {once: true}))
            : Promise.resolve();
        return pageReady
            .then(() => syncDashboardLayoutToAccount([], []))
            .catch(error => console.warn('[Dashboard] Unable to reset the saved layout', error));
    }

    function initDashboardDragAndDrop() {
        const layoutReset = resetDashboardLayoutIfOutdated();
        addDashboardDragHandles();
        applySavedDashboardOrder();
        applyHiddenDashboardSections();
        applySavedCollapsedStates();
        setDashboardCustomizeMode(false);

        // Then reconcile against the account copy, which wins. Runs after the cached
        // layout is already applied so there is no visible reflow on the common path.
        layoutReset.then(loadDashboardLayoutFromAccount);

        getDashboardSections().forEach(section => {
            section.addEventListener('dragstart', event => {
                if (!dashboardCustomizeMode) {
                    event.preventDefault();
                    return;
                }
                dashboardDraggedSection = section;
                section.classList.add('dashboard-section-dragging');
                event.dataTransfer.effectAllowed = 'move';
                event.dataTransfer.setData('text/plain', section.dataset.dashboardSection || '');
            });

            section.addEventListener('dragend', () => {
                section.classList.remove('dashboard-section-dragging');
                document.querySelectorAll('.dashboard-section-drag-over').forEach(el => el.classList.remove('dashboard-section-drag-over'));
                dashboardDraggedSection = null;
                saveDashboardOrder();
            });

            section.addEventListener('dragover', event => {
                if (!dashboardCustomizeMode || !dashboardDraggedSection || dashboardDraggedSection === section) return;
                event.preventDefault();
                section.classList.add('dashboard-section-drag-over');
            });

            section.addEventListener('dragleave', () => {
                section.classList.remove('dashboard-section-drag-over');
            });

            section.addEventListener('drop', event => {
                if (!dashboardCustomizeMode || !dashboardDraggedSection || dashboardDraggedSection === section) return;
                event.preventDefault();
                section.classList.remove('dashboard-section-drag-over');

                const container = document.querySelector('.container.py-4') || document.querySelector('.container');
                const rect = section.getBoundingClientRect();
                const placeAfter = event.clientY > rect.top + rect.height / 2;
                if (placeAfter) {
                    container.insertBefore(dashboardDraggedSection, section.nextSibling);
                } else {
                    container.insertBefore(dashboardDraggedSection, section);
                }
                saveDashboardOrder();
            });
        });
    }

    function managerUtilizationBadgeClass(level) {
        const value = String(level || '').toLowerCase();
        if (value === 'high') return 'bg-danger';
        if (value === 'watch') return 'bg-warning text-dark';
        return 'bg-success';
    }

    function renderManagerBranchOverview(rows) {
        const container = document.getElementById('manager-branch-list');
        if (!container) return;

        if (!Array.isArray(rows) || !rows.length) {
            renderTeamEmpty('manager-branch-list', 'No branch workload found.');
            return;
        }

        container.innerHTML = rows.map(row => `
            <div class="dashboard-team-row manager-branch-row">
                <div>
                    <div class="dashboard-team-row-title">${escapeHtml(row.branch || 'Unassigned')}</div>
                    <div class="dashboard-team-row-sub">${escapeHtml(row.engineers || 0)} engineer(s)</div>
                </div>
                <div class="dashboard-team-row-badges">
                    <span class="badge bg-primary">${escapeHtml(row.open_tasks || 0)} open</span>
                    ${Number(row.overdue || 0) ? `<span class="badge bg-danger">${escapeHtml(row.overdue)} overdue</span>` : ''}
                    ${Number(row.pending_tsr || 0) ? `<span class="badge bg-warning text-dark">${escapeHtml(row.pending_tsr)} TSR</span>` : ''}
                </div>
            </div>
        `).join('');
    }

    function renderManagerEngineerUtilization(rows) {
        const container = document.getElementById('manager-engineer-utilization-list');
        if (!container) return;

        if (!Array.isArray(rows) || !rows.length) {
            renderTeamEmpty('manager-engineer-utilization-list', 'No engineer utilization data found.');
            return;
        }

        container.innerHTML = rows.slice(0, 16).map(row => `
            <div class="dashboard-team-row manager-utilization-row">
                <div>
                    <div class="dashboard-team-row-title">${escapeHtml(row.name || 'Engineer')}</div>
                    <div class="dashboard-team-row-sub">${escapeHtml(row.branch || 'No branch')}</div>
                </div>
                <div class="dashboard-team-row-badges">
                    <span class="badge ${managerUtilizationBadgeClass(row.utilization_level)}">${escapeHtml(row.utilization_level || 'normal')}</span>
                    <span class="badge bg-primary">${escapeHtml(row.open_tasks || 0)} open</span>
                    <span class="badge bg-danger">${escapeHtml(row.overdue || 0)} overdue</span>
                    <span class="badge bg-warning text-dark">${escapeHtml(row.waiting_items || 0)} waiting</span>
                </div>
            </div>
        `).join('');
    }

    /**
     * The approvals block is hidden entirely unless the account is an approver.
     * is_manager_dashboard_user() also admits regional admins and the developer account,
     * and a panel of permanent zeros reads as "nothing is waiting" rather than
     * "this is not yours".
     */
    function renderManagerApprovals(data) {
        const panel = document.getElementById('manager-approvals');
        const tile = document.getElementById('manager-kpi-approvals');
        if (!panel) return;

        if (!data || data.is_approver !== true || data.workflows_enabled !== true) {
            panel.classList.add('d-none');
            if (tile) tile.classList.add('d-none');
            return;
        }
        panel.classList.remove('d-none');
        if (tile) tile.classList.remove('d-none');

        const counts = data.counts || {};
        const modules = Array.isArray(data.modules) ? data.modules : [];
        setManagerKpiValue('manager-approvals-total', counts.pending_total || 0);
        renderManagerKpiTrend('approvals', (data.trends || {}).approvals);

        const aging = document.getElementById('manager-approvals-aging');
        if (aging) {
            const agingTotal = Number(counts.aging_total || 0);
            const threshold = Number(data.aging_threshold_days || 5);
            if (agingTotal) {
                aging.textContent = `${agingTotal} waiting more than ${threshold} days — oldest ${counts.oldest_days || 0} days`;
                aging.className = 'manager-approvals-aging is-aging';
            } else if (Number(counts.pending_total || 0)) {
                aging.textContent = `Nothing older than ${threshold} days`;
                aging.className = 'manager-approvals-aging';
            } else {
                aging.textContent = 'Your approval queue is clear';
                aging.className = 'manager-approvals-aging is-clear';
            }
        }

        const grid = document.getElementById('manager-approvals-grid');
        if (!grid) return;

        const waiting = modules.filter(row => Number(row.pending || 0) > 0);
        if (!waiting.length) {
            grid.innerHTML = '<div class="manager-approvals-empty">No requests are waiting on you right now.</div>';
            return;
        }

        grid.innerHTML = waiting.map(row => `
            <a class="manager-approval-card${Number(row.aging || 0) ? ' is-aging' : ''}" href="${escapeHtml(row.href || '/approvals')}">
                <span class="manager-approval-count">${escapeHtml(row.pending || 0)}</span>
                <span class="manager-approval-label">${escapeHtml(row.label || 'Requests')}</span>
                <span class="manager-approval-age">${Number(row.oldest_days || 0)
                    ? `oldest ${escapeHtml(row.oldest_days)}d`
                    : 'just in'}</span>
            </a>
        `).join('');
    }

    async function loadManagerApprovals() {
        if (!dashboardManagerView || dashboardSchedulerOnly) return;

        try {
            renderManagerApprovals(await fetchJsonOrThrow('/get_manager_approvals'));
        } catch (approvalsError) {
            console.warn('Manager approvals could not be loaded:', approvalsError);
            ['manager-approvals', 'manager-kpi-approvals'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.classList.add('d-none');
            });
        }
    }

    function renderManagerRisk(data) {
        const box = document.getElementById('manager-risk');
        if (!box) return;
        const risk = (data || {}).risk || {};
        box.className = `manager-risk mb-3 is-${String(risk.level || 'stable')}`;
        setTextIfPresent('manager-risk-label', risk.label || 'Operations stable');
    }

    /**
     * Only flow metrics reach this renderer -- the server sends nothing else. A change
     * figure on a current-state total would be wrong: a shift that was overdue last week
     * and has since been completed has left the overdue set, so the historical figure
     * would be systematically low.
     */
    function renderManagerDirection(data) {
        const grid = document.getElementById('manager-direction-grid');
        if (!grid) return;

        const direction = (data || {}).direction || {};
        const metrics = Array.isArray(direction.metrics) ? direction.metrics : [];

        const caption = document.getElementById('manager-direction-caption');
        if (caption && direction.current_from) {
            caption.textContent = `${direction.current_from} to ${direction.current_to}, compared with ${direction.previous_from} to ${direction.previous_to}`;
        }

        if (!metrics.length) {
            grid.innerHTML = '<div class="manager-approvals-empty">No activity in this period.</div>';
            return;
        }

        grid.innerHTML = metrics.map(metric => {
            const change = Number(metric.change || 0);
            const better = metric.higher_is_better !== false;
            let tone = 'is-flat';
            let arrow = '&rarr;';
            if (change > 0) {
                tone = better ? 'is-good' : 'is-neutral';
                arrow = '&uarr;';
            } else if (change < 0) {
                tone = better ? 'is-bad' : 'is-neutral';
                arrow = '&darr;';
            }
            const unit = escapeHtml(metric.unit || '');
            const changeText = change === 0
                ? 'no change'
                : `${change > 0 ? '+' : ''}${escapeHtml(change)}${unit} vs previous`;

            return `
            <div class="manager-direction-metric">
                <span class="manager-direction-value">${escapeHtml(metric.value)}${unit}</span>
                <span class="manager-direction-label">${escapeHtml(metric.label || '')}</span>
                <span class="manager-direction-change ${tone}">
                    <span aria-hidden="true">${arrow}</span> ${changeText}
                </span>
            </div>`;
        }).join('');
    }

    // Inventory PM (Genoray, Vieworks) for the current Manila month. The label names the
    // brands so the figure is never read as covering all preventive maintenance.
    function renderManagerPmSummary(pm) {
        const box = document.getElementById('manager-pm-summary');
        const tile = document.getElementById('manager-kpi-pm-tile');
        if (!box) return;
        if (!pm || typeof pm !== 'object') {
            box.classList.add('d-none');
            if (tile) tile.classList.add('d-none');
            return;
        }
        const due = Number(pm.due_this_month || 0);
        const done = Number(pm.done_this_month || 0);
        const overdue = Number(pm.overdue || 0);
        const percent = due ? Math.round(done / due * 100) : null;
        setTextIfPresent('manager-kpi-pm', `${done} / ${due}`);
        const meter = document.getElementById('manager-kpi-pm-meter');
        if (meter) meter.style.transform = `scaleX(${due ? Math.min(done / due, 1) : 0})`;
        if (tile) tile.classList.remove('d-none');
        box.innerHTML = `
            <span class="manager-pm-label">Inventory PM (Genoray, Vieworks) this month</span>
            <span class="manager-pm-value">${escapeHtml(done)} / ${escapeHtml(due)} done${percent === null ? '' : ` (${escapeHtml(percent)}%)`}</span>
            <span class="manager-pm-overdue ${overdue ? 'is-late' : ''}">${escapeHtml(overdue)} overdue</span>`;
        box.classList.remove('d-none');
    }

    function managerWatchlistTypeLabel(type) {
        const labels = {
            severe_overdue: 'Severely overdue',
            overdue: 'Overdue',
            aged_tsr: 'TSR missing',
            waiting: 'Blocked',
            repeat_equipment: 'Repeat equipment',
            high_risk_client: 'Client at risk'
        };
        return labels[String(type || '')] || 'Attention';
    }

    // What a KPI tile's filter shows. The watchlist holds only the severe cases, so the
    // line says so rather than letting "Overdue 12" sit above a list of 3.
    function managerWatchlistFilterText(type, days) {
        const texts = {
            severe_overdue: `Overdue ${days} days or more`,
            aged_tsr: `Completed ${days} days or more ago with no TSR`,
            waiting: 'Blocked on P.O / parts'
        };
        return texts[type] || managerWatchlistTypeLabel(type);
    }

    // With no type the server's list renders as sent; a type (from a KPI tile) shows that
    // type only, from watchlist_by_type so lower-ranked types are not cut by the top 20.
    function renderManagerWatchlist(data, type) {
        const container = document.getElementById('manager-watchlist-list');
        if (!container) return;

        const filter = String(type || '');
        const payload = data || {};
        const allRows = Array.isArray(payload.watchlist) ? payload.watchlist : [];
        const byType = payload.watchlist_by_type || {};
        // 'age:<bucket>' comes from an Overdue by age bar; the bucket carries its own rows.
        const ageBucket = filter.startsWith('age:')
            ? (Array.isArray(payload.overdue_by_age) ? payload.overdue_by_age : []).find(bucket => `age:${bucket.key}` === filter)
            : null;
        let rows;
        let total;
        if (ageBucket) {
            rows = Array.isArray(ageBucket.rows) ? ageBucket.rows : [];
            total = Number(ageBucket.count || rows.length);
        } else {
            rows = filter ? (Array.isArray(byType[filter]) ? byType[filter] : allRows.filter(row => row.type === filter)) : allRows;
            total = filter
                ? Number((payload.watchlist_type_totals || {})[filter] || rows.length)
                : Number(payload.watchlist_total || rows.length);
        }
        setTextIfPresent('manager-watchlist-count', `${total} item${total === 1 ? '' : 's'}`);

        const caption = document.getElementById('manager-watchlist-caption');
        if (caption) {
            if (!caption.dataset.defaultText) caption.dataset.defaultText = caption.textContent;
            caption.textContent = total > rows.length
                ? `Showing the ${rows.length} most pressing of ${total}`
                : caption.dataset.defaultText;
        }

        const filterLine = document.getElementById('manager-watchlist-filter');
        if (filterLine) filterLine.classList.toggle('d-none', !filter);
        if (filter) {
            setTextIfPresent('manager-watchlist-filter-label',
                `Showing: ${ageBucket ? `Overdue ${ageBucket.label}` : managerWatchlistFilterText(filter, Number(payload.severe_age_days || 7))}`);
        }
        document.querySelectorAll('[data-overdue-age]').forEach(bar => {
            const active = `age:${bar.dataset.overdueAge}` === filter;
            bar.classList.toggle('is-active', active);
            bar.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        document.querySelectorAll('[data-manager-kpi]').forEach(tile => {
            const active = tile.dataset.managerKpi === filter;
            tile.classList.toggle('is-active', active);
            tile.setAttribute('aria-pressed', active ? 'true' : 'false');
        });

        if (!rows.length) {
            container.innerHTML = `
                <div class="manager-watchlist-clear">
                    <i class="fa-solid fa-circle-check" aria-hidden="true"></i>
                    <span>${filter ? 'Nothing of this kind needs management attention right now.' : 'Nothing needs management attention right now.'}</span>
                </div>`;
            return;
        }

        container.innerHTML = rows.map(row => `
            <div class="manager-watchlist-row">
                <span class="manager-watchlist-accent is-${escapeHtml(row.tone || 'watch')}" aria-hidden="true"></span>
                <span class="manager-watchlist-body">
                    <span class="manager-watchlist-title">${escapeHtml(row.title || '')}</span>
                    <span class="manager-watchlist-hint">${escapeHtml(row.subtitle || '')} • ${escapeHtml(row.detail || '')}</span>
                </span>
                <span class="manager-watchlist-tag">${escapeHtml(managerWatchlistTypeLabel(row.type))}</span>
            </div>
        `).join('');
    }

    // A KPI tile's number; a zero tile drops its alert/warn colour.
    function setManagerKpiValue(id, value) {
        const el = document.getElementById(id);
        animateDashboardNumber(el, value);
        const tile = el ? el.closest('.manager-kpi') : null;
        if (tile) tile.classList.toggle('is-zero', Number(value) === 0);
    }

    // ---- Dashboard Trends ("alive, not overloaded") ----
    const dashboardReducedMotion = window.matchMedia
        ? window.matchMedia('(prefers-reduced-motion: reduce)')
        : {matches: false};

    // Counts from the number on screen to the new one (exponential ease-out, 700 ms).
    // Non-numbers and reduced motion set the text directly.
    function animateDashboardNumber(el, value) {
        if (!el) return;
        const target = Number(value);
        const from = Number(el.textContent);
        if (!Number.isFinite(target) || !Number.isFinite(from) || from === target || dashboardReducedMotion.matches) {
            el.textContent = value;
            return;
        }
        const token = {};
        el._dashboardCount = token;
        const started = performance.now();
        const step = now => {
            if (el._dashboardCount !== token) return;
            const progress = Math.min((now - started) / 700, 1);
            const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
            el.textContent = Math.round(from + (target - from) * eased);
            if (progress < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
        // A background tab pauses requestAnimationFrame; never leave a half-counted number.
        setTimeout(() => {
            if (el._dashboardCount === token) el.textContent = value;
        }, 800);
    }

    function formatDashboardShortDate(value) {
        const date = parseDashboardDate(value);
        return date ? date.toLocaleDateString('en-US', {month: 'short', day: 'numeric'}) : '';
    }

    // One card's trend (Dashboard Style): a short corner badge and a sentence on the card's
    // line. Every trended count is lower-is-better, so a rise is the only red. Without a row
    // from a week ago the card says when the comparison starts rather than guessing one;
    // without a trend the line keeps its own description (data-default).
    function renderManagerKpiTrend(key, trend) {
        const badge = document.getElementById(`manager-trend-${key}`);
        const line = document.getElementById(`manager-trend-line-${key}`);
        if (!badge) return;
        let tone = 'is-flat';
        let short = '';
        let sentence = line ? (line.dataset.default || '') : '';
        if (trend && typeof trend === 'object') {
            const delta = trend.delta;
            if (delta === null || delta === undefined) {
                sentence = `Trend from ${formatDashboardShortDate(trend.delta_from)}`;
            } else if (Number(delta) === 0) {
                short = 'Same';
                sentence = 'Same as last week';
            } else {
                const up = Number(delta) > 0;
                const size = Math.abs(Number(delta));
                tone = up ? 'is-worse' : 'is-better';
                short = `<i class="fa-solid fa-arrow-${up ? 'up' : 'down'}" aria-hidden="true"></i> ${escapeHtml(size)}`;
                sentence = `${up ? 'Up' : 'Down'} ${size} from last week`;
            }
        }
        badge.innerHTML = short;
        badge.className = `manager-kpi-trend dash-stat-badge ${tone}`;
        if (line) line.textContent = sentence;
    }

    function renderManagerTrends(trends) {
        const data = trends || {};
        renderManagerKpiTrend('overdue', data.overdue);
        renderManagerKpiTrend('pending_tsr', data.pending_tsr);
        renderManagerKpiTrend('waiting', data.waiting);
    }

    // The one chart: overdue visits by how late they are. Bars are buttons that filter
    // What Needs Attention; lateness past the watchlist threshold deepens the red.
    function renderOverdueByAge(data) {
        const box = document.getElementById('manager-overdue-age');
        const bars = document.getElementById('manager-overdue-age-bars');
        if (!box || !bars) return;
        const buckets = Array.isArray((data || {}).overdue_by_age) ? data.overdue_by_age : null;
        if (!buckets) {
            box.classList.add('d-none');
            return;
        }
        box.classList.remove('d-none');

        const total = buckets.reduce((sum, bucket) => sum + Number(bucket.count || 0), 0);
        const severeDays = Number((data || {}).severe_age_days || 7);
        setTextIfPresent('manager-overdue-age-note', total
            ? `${total} visit${total === 1 ? '' : 's'} · the watchlist starts at ${severeDays} days`
            : 'Nothing overdue');
        bars.classList.toggle('d-none', !total);
        if (!total) {
            bars.innerHTML = '';
            return;
        }

        const max = Math.max(...buckets.map(bucket => Number(bucket.count || 0)), 1);
        bars.innerHTML = buckets.map((bucket, index) => {
            const count = Number(bucket.count || 0);
            const height = count ? Math.max(Math.round(count / max * 100), 6) : 0;
            const active = managerWatchlistFilter === `age:${bucket.key}`;
            return `
            <button type="button" class="manager-age-bar is-step-${index}${count ? '' : ' is-empty'}${active ? ' is-active' : ''}"
                    data-overdue-age="${escapeHtml(bucket.key)}" aria-pressed="${active ? 'true' : 'false'}"
                    aria-label="${escapeHtml(count)} overdue ${escapeHtml(bucket.label)}"
                    onclick="openOverdueAge('${escapeHtml(bucket.key)}')">
                <span class="manager-age-count">${escapeHtml(count)}</span>
                <span class="manager-age-track"><span class="manager-age-fill" style="height: ${height}%"></span></span>
                <span class="manager-age-label">${escapeHtml(bucket.label)}</span>
            </button>`;
        }).join('');
    }

    function openOverdueAge(key) {
        openManagerKpi(`age:${key}`);
    }

    // "Updated N min ago" beside Refresh. The dot pulses for three seconds after each load,
    // then sits still: the page reads as live without anything looping.
    let managerUpdatedAt = null;
    let managerUpdatedTimer = null;

    function renderManagerUpdatedLabel() {
        if (!managerUpdatedAt) return;
        const minutes = Math.floor((Date.now() - managerUpdatedAt) / 60000);
        setTextIfPresent('manager-updated-label',
            minutes < 1 ? 'Updated just now' : `Updated ${minutes} min ago`);
    }

    function renderManagerUpdated() {
        const box = document.getElementById('manager-updated');
        if (!box) return;
        managerUpdatedAt = Date.now();
        renderManagerUpdatedLabel();
        box.classList.remove('d-none', 'is-fresh');
        void box.offsetWidth;
        box.classList.add('is-fresh');
        if (!managerUpdatedTimer) managerUpdatedTimer = setInterval(renderManagerUpdatedLabel, 60000);
    }

    function revealManagerSection(bodyId) {
        const body = document.getElementById(bodyId);
        if (body && body.classList.contains('d-none')) {
            toggleDashboardSection(bodyId, document.querySelector(`[onclick="toggleDashboardSection('${bodyId}', this)"]`));
        }
        return body;
    }

    // KPI tiles: 'pm' opens Direction at the PM line; a watchlist type filters What Needs
    // Attention (pressing the active tile again, or '' from Show all, clears the filter).
    function openManagerKpi(type) {
        if (type === 'pm') {
            revealManagerSection('manager-direction-body');
            const pm = document.getElementById('manager-pm-summary');
            if (pm) pm.scrollIntoView({block: 'center'});
            return;
        }
        managerWatchlistFilter = type && type !== managerWatchlistFilter ? type : '';
        renderManagerWatchlist(managerOverviewData, managerWatchlistFilter);
        if (!managerWatchlistFilter) {
            // Show all hides its own button; keep focus in the list rather than losing it.
            if (!type) document.getElementById('manager-watchlist-list')?.focus({preventScroll: true});
            return;
        }
        revealManagerSection('manager-watchlist-body');
        const panel = document.querySelector('[data-dashboard-section="manager-watchlist"]');
        if (panel) panel.scrollIntoView({block: 'start'});
        document.getElementById('manager-watchlist-filter')?.focus({preventScroll: true});
    }

    async function loadManagerOverview() {
        if (!dashboardManagerView || dashboardSchedulerOnly) return;

        try {
            const data = await fetchJsonOrThrow('/get_manager_overview');
            managerOverviewData = data || {};
            const counts = managerOverviewData.counts || {};
            setTextIfPresent('manager-open-count', counts.open_schedules || 0);
            setManagerKpiValue('manager-overdue-count', counts.overdue_schedules || 0);
            setManagerKpiValue('manager-pending-tsr-count', counts.pending_tsr || 0);
            setManagerKpiValue('manager-waiting-count', counts.waiting_items || 0);

            renderManagerTrends(managerOverviewData.trends);
            renderOverdueByAge(managerOverviewData);
            renderManagerUpdated();
            renderManagerRisk(managerOverviewData);
            renderManagerDirection(managerOverviewData);
            renderManagerPmSummary(managerOverviewData.pm);
            renderManagerWatchlist(managerOverviewData, managerWatchlistFilter);
            renderManagerBranchOverview(managerOverviewData.branch_summary || []);
            renderManagerEngineerUtilization(managerOverviewData.engineer_utilization || []);
        } catch (managerError) {
            console.warn('Manager overview could not be loaded:', managerError);
            setTextIfPresent('manager-risk-label', 'Operational status could not be loaded.');
            renderTeamEmpty('manager-watchlist-list', 'Watchlist could not be loaded.');
        }
    }

    /**
     * The queue rows arrive already ordered and already tagged with a category by
     * /get_scheduler_dispatch_intelligence, so nothing here re-sorts or re-derives
     * urgency -- the server is the single source of what is most pressing.
     */
    function schedulerQueueAccent(category) {
        if (category === 'unassigned' || category === 'overdue') return 'is-danger';
        return 'is-warning';
    }

    function schedulerQueueActionLabel(row) {
        const assigned = Array.isArray(row.engineer_ids) && row.engineer_ids.length;
        return assigned ? 'Reschedule' : 'Assign';
    }

    function getSchedulerQueueRows() {
        const rows = schedulerDispatchData && Array.isArray(schedulerDispatchData.priority_queue)
            ? schedulerDispatchData.priority_queue
            : [];

        return rows.filter(row => {
            if (schedulerQueueFilter !== 'all' && String(row.category || '') !== schedulerQueueFilter) {
                return false;
            }
            if (schedulerBranchFilter === 'ALL') return true;
            return String(row.branches || '')
                .split(',')
                .map(value => value.trim())
                .includes(schedulerBranchFilter);
        });
    }

    function renderSchedulerQueue() {
        const container = document.getElementById('scheduler-dispatch-list');
        if (!container) return;

        const rows = getSchedulerQueueRows();
        const total = Number((schedulerDispatchData || {}).priority_queue_total || 0);
        const shown = rows.length;

        const caption = document.getElementById('scheduler-queue-caption');
        if (caption) {
            if (!shown) {
                caption.textContent = 'Most urgent first — select a row to assign or reschedule it';
            } else if (shown < total) {
                caption.textContent = `Showing ${shown} of ${total} — most urgent first, select a row to work on it`;
            } else {
                caption.textContent = `${shown} to work through — most urgent first, select a row`;
            }
        }

        if (!shown) {
            container.innerHTML = `
                <div class="scheduler-queue-clear">
                    <i class="fa-solid fa-circle-check" aria-hidden="true"></i>
                    <span>${escapeHtml(schedulerQueueFilter === 'all' && schedulerBranchFilter === 'ALL'
                        ? 'Nothing needs dispatch attention. The queue is clear.'
                        : 'Nothing matches this filter. Clear it to see the whole queue.')}</span>
                </div>`;
            return;
        }

        container.innerHTML = rows.map(row => {
            const selected = schedulerSelectedShift && Number(schedulerSelectedShift.id) === Number(row.id);
            const when = [row.date, row.time_start].filter(Boolean).join(' ');
            return `
            <button type="button"
                    class="scheduler-queue-row${selected ? ' is-selected' : ''}"
                    aria-pressed="${selected ? 'true' : 'false'}"
                    draggable="true"
                    ondragstart="startSchedulerQueueDrag(event, ${Number(row.id) || 0})"
                    onclick="selectSchedulerActionShift(${Number(row.id) || 0})">
                <span class="scheduler-queue-accent ${schedulerQueueAccent(row.category)}" aria-hidden="true"></span>
                <span class="scheduler-queue-body">
                    <span class="scheduler-queue-title">${escapeHtml(row.client || 'No client')} — ${escapeHtml(row.task || 'Untitled')}</span>
                    <span class="scheduler-queue-hint">${escapeHtml(row.priority_reason || '')} • ${escapeHtml(when)} • ${escapeHtml(row.engineers || 'Unassigned')}</span>
                </span>
                <span class="scheduler-queue-action">${escapeHtml(schedulerQueueActionLabel(row))} &rarr;</span>
            </button>`;
        }).join('');
    }

    function renderSchedulerRisk() {
        const box = document.getElementById('scheduler-risk');
        if (!box) return;

        const risk = (schedulerDispatchData || {}).risk || {};
        const counts = (schedulerDispatchData || {}).counts || {};
        const level = String(risk.level || 'stable');

        box.className = `scheduler-risk mb-3 is-${level}`;
        setTextIfPresent('scheduler-risk-label', risk.label || 'Dispatch queue stable');

        // Deliberately does not restate the overdue or unassigned counts: those are the
        // filter buttons directly below, and the raw bucket totals differ from the queue
        // counts wherever a schedule qualifies for two categories. Two different numbers
        // under the same word is worse than one fewer number.
        const parts = [];
        if (counts.high_load_engineers) {
            parts.push(`${counts.high_load_engineers} engineer${counts.high_load_engineers === 1 ? '' : 's'} carrying a heavy load`);
        }
        if (counts.watch_load_engineers) parts.push(`${counts.watch_load_engineers} to watch`);
        setTextIfPresent('scheduler-risk-detail', parts.join(' • '));
    }

    function renderSchedulerMetrics() {
        const counts = (schedulerDispatchData || {}).counts || {};
        // Filter buttons read queue_counts, which is counted from the de-duplicated queue,
        // so each button's number equals the rows its filter produces. counts.* holds the
        // raw bucket totals, where a schedule can appear in two buckets at once.
        const queueCounts = (schedulerDispatchData || {}).queue_counts || {};
        // setMetricValue colours a count only above zero (data-metric-tone on the card).
        setTextIfPresent('scheduler-queue-count', (schedulerDispatchData || {}).priority_queue_total || 0);
        setMetricValue('scheduler-overdue-count', queueCounts.overdue || 0);
        setMetricValue('scheduler-unassigned-count', queueCounts.unassigned || 0);
        setMetricValue('scheduler-waiting-count', queueCounts.waiting || 0);
        setMetricValue('scheduler-pending-tsr-count', queueCounts.tsr || 0);
        setTextIfPresent('scheduler-next7-count', counts.upcoming_7_days || 0);

        document.querySelectorAll('#scheduler-metric-strip [data-scheduler-filter]').forEach(button => {
            const active = button.getAttribute('data-scheduler-filter') === schedulerQueueFilter;
            button.setAttribute('aria-pressed', active ? 'true' : 'false');
            button.classList.toggle('is-active', active);
        });
    }

    function setSchedulerQueueFilter(filterName) {
        schedulerQueueFilter = filterName || 'all';
        renderSchedulerMetrics();
        renderSchedulerQueue();
    }

    async function loadSchedulerDispatchIntelligence() {
        if (!dashboardSchedulerOnly) return;

        try {
            schedulerDispatchData = await fetchJsonOrThrow('/get_scheduler_dispatch_intelligence') || {};
            renderSchedulerRisk();
            renderSchedulerMetrics();
            renderSchedulerQueue();
            // load_level comes from the same payload, so the availability chips have to be
            // re-rendered here or they would disagree with the risk line above them.
            renderSchedulerAvailabilityStrip();
        } catch (schedulerError) {
            console.warn('Scheduler dispatch intelligence could not be loaded:', schedulerError);
            setTextIfPresent('scheduler-risk-label', 'Dispatch status could not be loaded.');
            renderTeamEmpty('scheduler-dispatch-list', 'Priority queue could not be loaded.');
        }
    }

    /**
     * Workload level for one engineer, taken from the dispatch intelligence payload so the
     * chip colour and the risk line above it are computed from a single source. Falls back
     * to the coordination endpoint's own availability value until that payload arrives.
     */
    function schedulerEngineerLoadLevel(row) {
        const workload = schedulerDispatchData && Array.isArray(schedulerDispatchData.engineer_workload)
            ? schedulerDispatchData.engineer_workload
            : [];
        const match = workload.find(entry => Number(entry.engineer_id) === Number(row.engineer_id));
        if (match && match.load_level) {
            if (match.load_level === 'high') return 'busy';
            if (match.load_level === 'watch') return 'watch';
            return 'available';
        }
        return String(row.availability || 'available').toLowerCase();
    }

    function schedulerAvailabilityBadgeClass(level) {
        const value = String(level || '').toLowerCase();
        if (value === 'busy') return 'bg-danger';
        if (value === 'watch') return 'bg-warning text-dark';
        return 'bg-success';
    }

    // Label and colour are both derived from the same level, so a chip can never read
    // "Available" in red.
    function schedulerAvailabilityLabel(level) {
        const value = String(level || '').toLowerCase();
        if (value === 'busy') return 'Heavy load';
        if (value === 'watch') return 'Watch';
        return 'Available';
    }

    /**
     * Availability rows decorated with the workload level actually displayed, sorted
     * lightest-loaded first. Both the chips and the assign dropdown read from here, so a
     * chip and its matching option can never disagree, and the engineer most able to take
     * the work is offered first.
     */
    function getSchedulerFilteredAvailability() {
        const rows = schedulerCoordinationData && Array.isArray(schedulerCoordinationData.availability)
            ? schedulerCoordinationData.availability
            : [];

        const scoped = schedulerBranchFilter === 'ALL'
            ? rows.slice()
            : rows.filter(row => String(row.branch || 'Unassigned') === schedulerBranchFilter);

        const rank = {available: 0, watch: 1, busy: 2};
        return scoped
            .map(row => ({...row, loadLevel: schedulerEngineerLoadLevel(row)}))
            .sort((a, b) => (rank[a.loadLevel] ?? 9) - (rank[b.loadLevel] ?? 9)
                || String(a.branch || '').localeCompare(String(b.branch || ''))
                || String(a.name || '').localeCompare(String(b.name || '')));
    }

    function renderSchedulerBranchFilters(data) {
        const container = document.getElementById('scheduler-branch-filters');
        if (!container) return;

        const branches = Array.isArray(data.branches) ? data.branches : [];
        const branchCounts = data.branch_counts || {};
        const buttons = [
            `<button type="button" class="btn btn-sm ${schedulerBranchFilter === 'ALL' ? 'btn-success' : 'btn-outline-success'} fw-bold" data-branch="ALL" aria-pressed="${schedulerBranchFilter === 'ALL'}" onclick="setSchedulerBranchFilter('ALL')">All Branches</button>`,
            ...branches.map(branch => `
                <button type="button" class="btn btn-sm ${schedulerBranchFilter === branch ? 'btn-success' : 'btn-outline-success'} fw-bold" data-branch="${escapeHtml(branch)}" aria-pressed="${schedulerBranchFilter === branch}" onclick="setSchedulerBranchFilter('${escapeHtml(branch)}')">
                    ${escapeHtml(branch)} <span class="badge bg-light text-dark ms-1">${escapeHtml(branchCounts[branch] || 0)}</span>
                </button>
            `)
        ];

        container.innerHTML = buttons.join('');
    }

    // --- DISPATCH BOARD LANES ---
    // Today view spans 07:00-19:00; visits outside are clamped to the edge.
    const SCHEDULER_BOARD_START_HOUR = 7;
    const SCHEDULER_BOARD_END_HOUR = 19;

    function schedulerTimeToMinutes(label) {
        const value = convertTimeLabelToInputValue(label);
        if (!value) return null;
        const [hour, minute] = value.split(':').map(Number);
        return hour * 60 + minute;
    }

    // Manila "today" as the server saw it, so the board and the lanes agree on the date.
    function schedulerBoardDates() {
        const start = parseDashboardDate((schedulerCoordinationData || {}).board_start) || new Date();
        start.setHours(0, 0, 0, 0);
        return Array.from({length: 7}, (_, index) => {
            const day = new Date(start);
            day.setDate(start.getDate() + index);
            const iso = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
            return {iso, label: day.toLocaleDateString(undefined, {weekday: 'short', day: 'numeric'})};
        });
    }

    function schedulerLaneBlock(visit, extraClass, style) {
        const selected = schedulerSelectedShift && Number(schedulerSelectedShift.id) === Number(visit.id);
        const when = [visit.time_start, visit.time_end].filter(Boolean).join('–');
        const title = `${visit.client || 'No client'} • ${visit.task || ''} • ${when} • ${visit.status || 'In Progress'}`;
        return `
            <button type="button" class="scheduler-lane-block ${dashboardStatusClass(visit.status)} ${extraClass}${selected ? ' is-selected' : ''}"
                    ${style ? `style="${style}"` : ''} title="${escapeHtml(title)}"
                    aria-pressed="${selected ? 'true' : 'false'}"
                    onclick="selectSchedulerActionShift(${Number(visit.id) || 0})">
                <span class="scheduler-lane-block-time">${escapeHtml(visit.time_start || '')}</span>
                <span class="scheduler-lane-block-client">${escapeHtml(visit.client || 'No client')}</span>
            </button>`;
    }

    // Today: blocks placed by time; overlapping visits go to the next row of the lane.
    function schedulerTodayTrack(visits, todayIso) {
        const span = (SCHEDULER_BOARD_END_HOUR - SCHEDULER_BOARD_START_HOUR) * 60;
        const rowEnds = [];
        const blocks = visits
            .filter(visit => visit.date === todayIso)
            .map(visit => {
                const rawStart = schedulerTimeToMinutes(visit.time_start);
                const rawEnd = schedulerTimeToMinutes(visit.time_end);
                const start = Math.min(Math.max((rawStart ?? SCHEDULER_BOARD_START_HOUR * 60) - SCHEDULER_BOARD_START_HOUR * 60, 0), span - 30);
                const end = Math.min(Math.max((rawEnd ?? 0) - SCHEDULER_BOARD_START_HOUR * 60, start + 30), span);
                let row = rowEnds.findIndex(rowEnd => rowEnd <= start);
                if (row === -1) { row = rowEnds.length; rowEnds.push(end); } else { rowEnds[row] = end; }
                const style = `--block-start:${(start / span * 100).toFixed(2)}%;--block-span:${((end - start) / span * 100).toFixed(2)}%;--block-row:${row}`;
                return schedulerLaneBlock(visit, 'is-timed', style);
            });
        if (!blocks.length) return '<span class="scheduler-lane-free">Free today</span>';
        return `<div class="scheduler-lane-timed" style="--lane-rows:${Math.max(rowEnds.length, 1)}">${blocks.join('')}</div>`;
    }

    function schedulerWeekTrack(visits, dates) {
        return `<div class="scheduler-lane-week">${dates.map(day => {
            const dayVisits = visits.filter(visit => visit.date === day.iso);
            const shown = dayVisits.slice(0, 3).map(visit => schedulerLaneBlock(visit, 'is-compact', '')).join('');
            const more = dayVisits.length > 3 ? `<span class="scheduler-lane-more">+${dayVisits.length - 3} more</span>` : '';
            return `<div class="scheduler-lane-day"><span class="scheduler-lane-day-label">${escapeHtml(day.label)}</span>${shown}${more}</div>`;
        }).join('')}</div>`;
    }

    function schedulerBoardAxis(dates) {
        if (schedulerBoardView === 'week') return '';
        const hours = [];
        for (let hour = SCHEDULER_BOARD_START_HOUR; hour < SCHEDULER_BOARD_END_HOUR; hour += 2) {
            hours.push(`<span>${hour > 12 ? hour - 12 : hour}${hour >= 12 ? 'p' : 'a'}</span>`);
        }
        return `<div class="scheduler-lane scheduler-lane-axis" aria-hidden="true"><span class="scheduler-lane-head"></span><div class="scheduler-lane-hours">${hours.join('')}</div></div>`;
    }

    // Renders the engineer lanes. Kept under its old name because the dispatch payload
    // loader and the branch filter both call it.
    function renderSchedulerAvailabilityStrip() {
        const container = document.getElementById('scheduler-availability-strip');
        if (!container) return;

        const rows = getSchedulerFilteredAvailability();
        setTextIfPresent('scheduler-availability-count', `${rows.length} engineer${rows.length === 1 ? '' : 's'}`);

        if (!rows.length) {
            container.innerHTML = `<div class="dashboard-team-empty">No engineer availability found for this branch. Try All Branches or refresh tools.</div>`;
            return;
        }

        const dates = schedulerBoardDates();
        const canAssignHere = Boolean(schedulerSelectedShift);
        container.innerHTML = schedulerBoardAxis(dates) + rows.map(row => {
            const level = row.loadLevel;
            const engineerId = Number(row.engineer_id) || 0;
            const visits = Array.isArray(row.visits) ? row.visits : [];
            const track = schedulerBoardView === 'week' ? schedulerWeekTrack(visits, dates) : schedulerTodayTrack(visits, dates[0].iso);
            return `
            <div class="scheduler-lane" data-engineer-id="${engineerId}"
                 ondragover="allowSchedulerLaneDrop(event)" ondragleave="this.classList.remove('is-drop-target')"
                 ondrop="dropOnSchedulerLane(event, ${engineerId})">
                <div class="scheduler-lane-head">
                    <button type="button" class="scheduler-lane-name" onclick="selectSchedulerEngineerForAssign(${engineerId})" title="Select ${escapeHtml(row.name || 'engineer')} in the assign list">
                        <span class="scheduler-availability-avatar">${escapeHtml(row.initials || '?')}</span>
                        <span class="scheduler-availability-main">
                            <strong>${escapeHtml(row.name || 'Engineer')}</strong>
                            <small>${escapeHtml(row.branch || 'No branch')} • ${escapeHtml(row.today_tasks || 0)} today • ${escapeHtml(row.next_7_days || 0)} week</small>
                        </span>
                    </button>
                    <span class="badge ${schedulerAvailabilityBadgeClass(level)}">${escapeHtml(schedulerAvailabilityLabel(level))}</span>
                    ${canAssignHere ? `<button type="button" class="btn btn-sm btn-outline-success fw-bold scheduler-lane-assign" onclick="proposeSchedulerLaneAssign(${engineerId})">Assign here</button>` : ''}
                </div>
                <div class="scheduler-lane-track">${track}</div>
            </div>`;
        }).join('');
    }

    function setSchedulerBoardView(view) {
        schedulerBoardView = view === 'week' ? 'week' : 'today';
        document.querySelectorAll('#scheduler-board-view [data-board-view]').forEach(button => {
            const active = button.getAttribute('data-board-view') === schedulerBoardView;
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        renderSchedulerAvailabilityStrip();
    }

    function startSchedulerQueueDrag(event, shiftId) {
        if (!event.dataTransfer) return;
        event.dataTransfer.setData('text/plain', String(shiftId));
        event.dataTransfer.effectAllowed = 'move';
    }

    function allowSchedulerLaneDrop(event) {
        event.preventDefault();
        event.currentTarget.classList.add('is-drop-target');
    }

    function dropOnSchedulerLane(event, engineerId) {
        event.preventDefault();
        event.currentTarget.classList.remove('is-drop-target');
        const shiftId = Number(event.dataTransfer ? event.dataTransfer.getData('text/plain') : 0);
        if (!shiftId) return;
        selectSchedulerActionShift(shiftId);
        proposeSchedulerLaneAssign(engineerId);
    }

    // A drop (or "Assign here") only proposes; Confirm sends it. The assign route replaces
    // the engineer list, so the engineers already on the schedule are sent along too.
    function proposeSchedulerLaneAssign(engineerId) {
        const shift = schedulerSelectedShift;
        const engineer = ((schedulerCoordinationData || {}).availability || [])
            .find(row => Number(row.engineer_id) === Number(engineerId));
        if (!shift || !engineer) return;

        const current = (Array.isArray(shift.engineer_ids) ? shift.engineer_ids : []).map(Number);
        if (current.includes(Number(engineerId))) {
            setSchedulerActionStatus(`${escapeHtml(engineer.name)} is already assigned to this schedule.`, 'info');
            return;
        }

        schedulerPendingLaneAssign = {shiftId: Number(shift.id), engineerIds: [...current, Number(engineerId)]};
        const verb = current.length ? 'Add' : 'Assign';
        setTextIfPresent('scheduler-drop-confirm-text', `${verb} ${engineer.name} to ${shift.client || 'this schedule'}, ${shift.date || ''}?`);
        const box = document.getElementById('scheduler-drop-confirm');
        if (box) {
            box.classList.remove('d-none');
            const confirmButton = box.querySelector('button');
            if (confirmButton) confirmButton.focus();
        }
    }

    function cancelSchedulerLaneAssign() {
        schedulerPendingLaneAssign = null;
        const box = document.getElementById('scheduler-drop-confirm');
        if (box) box.classList.add('d-none');
    }

    async function confirmSchedulerLaneAssign() {
        const pending = schedulerPendingLaneAssign;
        cancelSchedulerLaneAssign();
        if (!pending) return;
        await submitSchedulerAction('/scheduler_quick_assign_shift', {
            shift_id: pending.shiftId,
            engineer_ids: pending.engineerIds
        }, 'Assignment updated. Dashboard refreshed.');
    }

    function renderSchedulerAssignableEngineers() {
        const select = document.getElementById('scheduler-assign-engineers');
        if (!select) return;

        // Same source as the chips above, so an option can never label an engineer
        // differently from the chip the scheduler just clicked.
        const filteredRows = getSchedulerFilteredAvailability();

        select.innerHTML = filteredRows.map(row => `
            <option value="${Number(row.engineer_id) || 0}">
                ${escapeHtml(row.name || 'Engineer')} — ${escapeHtml(row.branch || 'No branch')} — ${escapeHtml(schedulerAvailabilityLabel(row.loadLevel))}
            </option>
        `).join('');

        if (schedulerSelectedShift && Array.isArray(schedulerSelectedShift.engineer_ids)) {
            const selectedIds = new Set(schedulerSelectedShift.engineer_ids.map(Number));
            Array.from(select.options).forEach(option => {
                option.selected = selectedIds.has(Number(option.value));
            });
        }
    }

    function renderSchedulerCoordinationTools(data) {
        schedulerCoordinationData = data || {};
        renderSchedulerBranchFilters(schedulerCoordinationData);
        renderSchedulerAvailabilityStrip();
        renderSchedulerAssignableEngineers();
    }

    async function loadSchedulerCoordinationTools() {
        if (!dashboardSchedulerOnly) return;

        try {
            const data = await fetchJsonOrThrow('/get_scheduler_coordination_tools');
            renderSchedulerCoordinationTools(data || {});
        } catch (coordinationError) {
            console.warn('Scheduler coordination tools could not be loaded:', coordinationError);
            renderTeamEmpty('scheduler-availability-strip', 'Scheduler coordination tools could not be loaded.');
        }
    }

    function setSchedulerBranchFilter(branchName) {
        schedulerBranchFilter = branchName || 'ALL';
        schedulerSelectedShift = null;
        cancelSchedulerLaneAssign();
        const hidden = document.getElementById('scheduler-selected-shift-id');
        if (hidden) hidden.value = '';
        setSchedulerActionStatus('', 'info', true);
        renderSchedulerBranchFilters(schedulerCoordinationData || {});
        renderSchedulerAvailabilityStrip();
        renderSchedulerAssignableEngineers();
        renderSchedulerQueue();
        setTextIfPresent('scheduler-selected-action-label', 'Select a schedule from the priority queue to assign or reschedule.');
    }

    function findSchedulerActionShift(shiftId) {
        const rows = schedulerDispatchData && Array.isArray(schedulerDispatchData.priority_queue)
            ? schedulerDispatchData.priority_queue
            : [];
        const queued = rows.find(row => Number(row.id) === Number(shiftId));
        if (queued) return queued;
        // Board blocks can be schedules that are not in the queue (on time, assigned).
        for (const lane of ((schedulerCoordinationData || {}).availability || [])) {
            const visit = (lane.visits || []).find(row => Number(row.id) === Number(shiftId));
            if (visit) return visit;
        }
        return null;
    }

    function selectSchedulerActionShift(shiftId) {
        const row = findSchedulerActionShift(shiftId);
        schedulerSelectedShift = row;
        cancelSchedulerLaneAssign();
        const hidden = document.getElementById('scheduler-selected-shift-id');
        if (hidden) hidden.value = row ? row.id : '';

        if (row) {
            setTextIfPresent('scheduler-selected-action-label', [row.client || 'No client', row.date, row.task, row.engineers, row.priority_reason].filter(Boolean).join(' • '));
            if (row.date) {
                const dateInput = document.getElementById('scheduler-reschedule-date');
                if (dateInput) dateInput.value = row.date;
            }
            if (row.time_start) {
                const startInput = document.getElementById('scheduler-reschedule-start');
                if (startInput) startInput.value = convertTimeLabelToInputValue(row.time_start);
            }
            if (row.time_end) {
                const endInput = document.getElementById('scheduler-reschedule-end');
                if (endInput) endInput.value = convertTimeLabelToInputValue(row.time_end);
            }
        }

        renderSchedulerAssignableEngineers();
        renderSchedulerQueue();
        renderSchedulerAvailabilityStrip();
        setSchedulerActionStatus('', 'info', true);
    }

    function convertTimeLabelToInputValue(value) {
        const raw = String(value || '').trim();
        if (/^\d{2}:\d{2}$/.test(raw)) return raw;

        const match = raw.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
        if (!match) return '';
        let hour = Number(match[1]);
        const minute = match[2];
        const meridiem = match[3].toUpperCase();
        if (meridiem === 'PM' && hour < 12) hour += 12;
        if (meridiem === 'AM' && hour === 12) hour = 0;
        return `${String(hour).padStart(2, '0')}:${minute}`;
    }

    function selectSchedulerEngineerForAssign(engineerId) {
        const select = document.getElementById('scheduler-assign-engineers');
        if (!select || !engineerId) return;
        Array.from(select.options).forEach(option => {
            if (Number(option.value) === Number(engineerId)) {
                option.selected = true;
            }
        });
    }

    function getSelectedSchedulerShiftId() {
        const hidden = document.getElementById('scheduler-selected-shift-id');
        return hidden ? Number(hidden.value || 0) : 0;
    }

    function setSchedulerActionStatus(message, state = 'info', hide = false) {
        const box = document.getElementById('scheduler-action-status');
        if (!box) return;
        if (hide || !message) {
            box.className = 'scheduler-action-status small mt-3 d-none';
            box.innerHTML = '';
            return;
        }

        const classMap = {
            success: 'text-success',
            error: 'text-danger',
            info: 'text-muted'
        };
        box.className = `scheduler-action-status small mt-3 fw-bold ${classMap[state] || classMap.info}`;
        box.innerHTML = message;
    }

    function getSelectedSchedulerEngineerIds() {
        const select = document.getElementById('scheduler-assign-engineers');
        if (!select) return [];
        return Array.from(select.selectedOptions).map(option => Number(option.value)).filter(Boolean);
    }

    async function submitSchedulerQuickAssign() {
        const shiftId = getSelectedSchedulerShiftId();
        const engineerIds = getSelectedSchedulerEngineerIds();

        if (!shiftId) {
            setSchedulerActionStatus('<i class="fa-solid fa-triangle-exclamation me-1"></i>Select a schedule first.', 'error');
            return;
        }
        if (!engineerIds.length) {
            setSchedulerActionStatus('<i class="fa-solid fa-triangle-exclamation me-1"></i>Select at least one engineer.', 'error');
            return;
        }

        await submitSchedulerAction('/scheduler_quick_assign_shift', {
            shift_id: shiftId,
            engineer_ids: engineerIds
        }, 'Assignment updated. Dashboard refreshed.');
    }

    async function submitSchedulerQuickReschedule() {
        const shiftId = getSelectedSchedulerShiftId();
        const dateInput = document.getElementById('scheduler-reschedule-date');
        const startInput = document.getElementById('scheduler-reschedule-start');
        const endInput = document.getElementById('scheduler-reschedule-end');

        if (!shiftId) {
            setSchedulerActionStatus('<i class="fa-solid fa-triangle-exclamation me-1"></i>Select a schedule first.', 'error');
            return;
        }

        if (!dateInput || !dateInput.value || !startInput || !startInput.value) {
            setSchedulerActionStatus('<i class="fa-solid fa-triangle-exclamation me-1"></i>Select date and start time.', 'error');
            return;
        }

        await submitSchedulerAction('/scheduler_quick_reschedule_shift', {
            shift_id: shiftId,
            date: dateInput.value,
            start_time: startInput.value,
            end_time: endInput && endInput.value ? endInput.value : ''
        }, 'Schedule rescheduled. Dashboard refreshed.');
    }

    async function submitSchedulerAction(url, payload, successMessage) {
        setSchedulerActionStatus('<i class="fa-solid fa-circle-notch fa-spin me-1"></i>Saving scheduler action...', 'info');

        try {
            const response = await fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': typeof getCSRFToken === 'function' ? getCSRFToken() : ''
                },
                body: JSON.stringify(payload)
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok || data.status !== 'success') {
                throw new Error(data.message || data.error || `Request failed (${response.status}).`);
            }

            setSchedulerActionStatus(`<i class="fa-solid fa-circle-check me-1"></i>${escapeHtml(data.message || successMessage)}`, 'success');
            schedulerSelectedShift = null;
            const hidden = document.getElementById('scheduler-selected-shift-id');
            if (hidden) hidden.value = '';
            await Promise.all([
                loadSchedulerDispatchIntelligence(),
                loadSchedulerCoordinationTools()
            ]);
        } catch (error) {
            console.warn('Scheduler quick action failed:', error);
            setSchedulerActionStatus(`<i class="fa-solid fa-triangle-exclamation me-1"></i>${escapeHtml(error.message || 'Scheduler action failed.')}`, 'error');
        }
    }

    // Writes a metric and colours it only when it is above zero (data-metric-tone names
    // the colour), so a zero always reads neutral.
    function setMetricValue(elementId, value) {
        const el = document.getElementById(elementId);
        if (!el) return;
        el.innerText = value;
        const tone = el.dataset.metricTone;
        if (tone) el.classList.toggle(`dashboard-metric-${tone}`, Number(value) > 0);
    }

    async function loadMyPendingTsrCount() {
        if (!dashboardHasEngineerProfile) return;
        try {
            const data = await fetchJsonOrThrow('/get_my_pending_tsr_count');
            setMetricValue('count-my-pending-tsr', Number((data || {}).pending_tsr || 0));
        } catch (error) {
            console.warn('[Dashboard] Pending TSR count could not be loaded', error);
            setTextIfPresent('count-my-pending-tsr', '–');
        }
    }

    // Shared by "Needs you today" and the staff "Waiting on you" card.
    function renderDashboardTodayRows(list, rows) {
        list.innerHTML = rows.map(row => (
            `<a class="dashboard-today-row" href="${escapeHtml(row.href || '/timeline')}">`
            + `<span class="dashboard-today-accent ${row.accent}" aria-hidden="true"></span>`
            + '<span class="dashboard-today-body">'
            + `<span class="dashboard-today-title">${escapeHtml(row.title)}</span>`
            + `<span class="dashboard-today-hint">${escapeHtml(row.hint)}</span>`
            + '</span>'
            + `<span class="dashboard-today-action">${escapeHtml(row.action)} →</span>`
            + '</a>'
        )).join('');
    }

    function renderDashboardClear(list, message) {
        list.innerHTML = '<div class="dashboard-today-clear">'
            + '<i class="fa-solid fa-circle-check" aria-hidden="true"></i>'
            + `<span>${escapeHtml(message)}</span>`
            + '</div>';
    }

    async function loadStaffWaiting() {
        const list = document.getElementById('staff-waiting-list');
        if (!list || !dashboardStaffLanding) return;
        try {
            const data = await fetchJsonOrThrow('/api/nav/pending-summary');
            const approvals = Number((data || {}).approvals_pending || 0);
            const requests = Number((data || {}).my_requests_action || 0);
            const rows = [];
            if (approvals) {
                rows.push({
                    accent: 'is-warning',
                    title: approvals === 1 ? '1 request is waiting for your approval' : `${approvals} requests are waiting for your approval`,
                    hint: 'Approvals',
                    action: 'Review',
                    href: '/approvals'
                });
            }
            if (requests) {
                rows.push({
                    accent: 'is-warning',
                    title: requests === 1 ? '1 of your requests needs attention' : `${requests} of your requests need attention`,
                    hint: 'My Requests',
                    action: 'Open',
                    href: '/accounting_center'
                });
            }
            if (!rows.length) {
                renderDashboardClear(list, 'Nothing is waiting on you right now.');
                return;
            }
            renderDashboardTodayRows(list, rows);
        } catch (error) {
            console.warn('[Dashboard] Waiting items could not be loaded', error);
            list.innerHTML = '<div class="dashboard-today-clear">'
                + '<span>Could not check what is waiting on you.</span>'
                + '<button type="button" class="btn btn-sm btn-outline-secondary fw-bold ms-auto" onclick="loadStaffWaiting()">Retry</button>'
                + '</div>';
        }
    }

    function getCurrentEngineerTasks() {
        if (!dashboardHasEngineerProfile) return [];
        return allOpenTasksRaw.filter(isTaskAssignedToCurrentEngineer);
    }

    function updateEngineerSummaryCards() {
        if (!dashboardHasEngineerProfile) return;

        const myTasks = getCurrentEngineerTasks();
        const todayStart = new Date();
        todayStart.setHours(0, 0, 0, 0);

        const upcomingVisits = myTasks.filter(task => {
            const taskDate = parseDashboardDate(task.task_date);
            return taskDate && taskDate >= todayStart;
        }).length;

        const continuationCount = myTasks.filter(task => task.status === 'For Continuation').length;
        const waitingCount = myTasks.filter(task => ['Waiting for P.O', 'Waiting for Parts'].includes(task.status)).length;

        const buckets = workOrderBuckets(myTasks);
        setTextIfPresent('count-my-today', buckets.today.length);
        setMetricValue('count-my-overdue', buckets.overdue.length);
        // active / upcoming left the header line in the work-order remodel; kept for any
        // page that still carries them.
        setTextIfPresent('count-my-active', myTasks.length);
        setTextIfPresent('count-my-upcoming', upcomingVisits);
        setMetricValue('count-my-continuation', continuationCount);
        setMetricValue('count-my-waiting', waitingCount);

        renderEngineerTodayHelp(buckets.today);
        renderEngineerTodayPanel(myTasks, todayStart);
    }

    // Visits today card helper: the earliest timed visit today ("09:00 AM").
    function renderEngineerTodayHelp(todayTasks) {
        const times = todayTasks.map(task => task.time_start).filter(Boolean)
            .sort((a, b) => schedulerTimeToMinutes(a) - schedulerTimeToMinutes(b));
        setTextIfPresent('engineer-today-line', todayTasks.length ? 'Scheduled for today' : 'Nothing scheduled today');
        setTextIfPresent('engineer-today-help', times.length ? `First at ${times[0]}` : '');
    }

    // "Needs you today" is derived entirely from tasks already loaded for the tables
    // below. It issues no requests of its own -- the point is to surface what matters
    // first, not to fetch more. Its section was merged into My Work Orders (phase B), so
    // without #engineer-today-list this returns at once; kept for existing callers.
    function renderEngineerTodayPanel(myTasks, todayStart) {
        const list = document.getElementById('engineer-today-list');
        if (!list) return;

        const overdue = myTasks.filter(task => {
            const taskDate = parseDashboardDate(task.task_date);
            return taskDate && taskDate < todayStart && task.status !== 'Completed';
        });
        const dueToday = myTasks.filter(task => {
            const taskDate = parseDashboardDate(task.task_date);
            if (!taskDate) return false;
            return taskDate.toDateString() === todayStart.toDateString();
        });
        const continuation = myTasks.filter(task => task.status === 'For Continuation');
        const waiting = myTasks.filter(task => ['Waiting for P.O', 'Waiting for Parts'].includes(task.status));

        const rows = [];

        function describe(tasks) {
            const first = tasks[0] || {};
            const place = first.client || 'Unassigned facility';
            return tasks.length === 1 ? place : `${place} and ${tasks.length - 1} more`;
        }

        // Each row opens the timeline on the week of the first task it names.
        if (overdue.length) {
            rows.push({
                accent: 'is-danger',
                title: overdue.length === 1 ? '1 visit is past its scheduled date' : `${overdue.length} visits are past their scheduled date`,
                hint: describe(overdue),
                action: 'Review',
                href: dashboardTimelineHref(overdue[0])
            });
        }
        if (dueToday.length) {
            rows.push({
                accent: '',
                title: dueToday.length === 1 ? '1 visit scheduled today' : `${dueToday.length} visits scheduled today`,
                hint: describe(dueToday),
                action: 'Open',
                href: dashboardTimelineHref(dueToday[0])
            });
        }
        if (continuation.length) {
            rows.push({
                accent: 'is-warning',
                title: continuation.length === 1 ? '1 job is for continuation' : `${continuation.length} jobs are for continuation`,
                hint: describe(continuation),
                action: 'Continue',
                href: dashboardTimelineHref(continuation[0])
            });
        }
        if (waiting.length) {
            rows.push({
                accent: 'is-warning',
                title: waiting.length === 1 ? '1 job is waiting on parts or P.O.' : `${waiting.length} jobs are waiting on parts or P.O.`,
                hint: describe(waiting),
                action: 'Check',
                href: dashboardTimelineHref(waiting[0])
            });
        }

        if (!rows.length) {
            const next = myTasks
                .filter(task => {
                    const taskDate = parseDashboardDate(task.task_date);
                    return taskDate && taskDate > todayStart;
                })
                .sort((a, b) => dashboardDateValue(a.task_date) - dashboardDateValue(b.task_date))[0];
            renderDashboardClear(list, next
                ? `Nothing needs you today. Next visit: ${next.task_date}, ${next.client || 'facility to be confirmed'}.`
                : 'Nothing needs your attention right now.');
            return;
        }

        renderDashboardTodayRows(list, rows);
    }

    /**
     * MASTER DATA LOADER:
     * Dispatches concurrent fetch requests to sync dashboard metrics from server.
     */
    async function loadDashboard() {
        setDashboardLoadState('loading');
        
        try {
            let tasks = [];

            if (dashboardSchedulerOnly) {
                // Schedulers pass is_admin_authorized(), so they used to take the admin
                // branch below and fetch four payloads that render nowhere: admin-counters
                // and open-technical-tasks are both gated off for a scheduler account, so
                // the counter writes no-op'd and the company-wide open-task list -- every
                // open shift, no date window, no limit -- was downloaded and discarded.
                // The scheduler sections load their own data further down.
                tasks = [];
            } else if (dashboardAdminView) {
                const [engs, clis, prods, adminTasks] = await Promise.all([
                    fetchJsonOrThrow('/get_engineers'),
                    fetchJsonOrThrow('/get_clients'),
                    fetchJsonOrThrow('/get_products'),
                    fetchJsonOrThrow('/get_open_tasks')
                ]);

                tasks = adminTasks;
                setTextIfPresent('count-engineers', Array.isArray(engs) ? engs.length : 0);
                setTextIfPresent('count-clients', Array.isArray(clis) ? clis.length : 0);
                setTextIfPresent('count-products', Array.isArray(prods) ? prods.length : 0);
            } else {
                // Pure engineer speed path: skip admin counters.
                tasks = await fetchJsonOrThrow('/get_open_tasks');
            }

            const hrCategories = [
                "Sick Leave", 
                "Vacation Leave", 
                "Emergency Leave", 
                "Paternity Leave", 
                "Maternity Leave", 
                "Training"
            ];
            
            allOpenTasksRaw = (Array.isArray(tasks) ? tasks : []).filter(t => !hrCategories.includes(t.task));
            setDashboardLoadState('ready');
            
            // Capability-based dashboard rendering for pure engineer, admin, scheduler, and hybrid users.
            if (dashboardHasEngineerProfile) {
                updateEngineerSummaryCards();
                renderMyTasks();
                loadMyPendingTsrCount();
                // Fetched once for the header strip; the Done this week tab reuses the rows.
                if (workOrdersDone === null) {
                    workOrdersDone = false;
                    loadMyDoneTasks();
                }
                if (!dashboardChartState.requested) {
                    dashboardChartState.requested = true;
                    loadEngineerActivity();
                }
            }

            if (dashboardStaffLanding) {
                loadStaffWaiting();
            }

            if (dashboardSchedulerOnly) {
                loadSchedulerCoordinationTools();
                loadSchedulerDispatchIntelligence();
            }

            if (dashboardManagerView && !dashboardSchedulerOnly) {
                // Two requests where there were four. The watchlist payload rides along
                // with the overview rather than needing its own round-trip.
                loadManagerApprovals();
                loadManagerOverview();
                if (!dashboardChartState.companyRequested) {
                    dashboardChartState.companyRequested = true;
                    loadManagerActivity();
                }
            }

            // The recent-activity section and its 5-second poll used to be loaded here,
            // behind `adminView && !managerView` -- a condition no account can satisfy, so it
            // never ran. Retired with the hybrid ratification, and with them the whole feed
            // chain in this file: fetchActivityLog, renderMobileActivityList, getActivityMeta
            // and formatActivityText, all of which only that section reached.
            //
            // /activity_page is unaffected: templates/activity.html carries its own loader
            // against /get_activity_logs and never used any of the above. The endpoint this
            // feed used to call was left registered at the time, since retiring a route is a
            // separate decision from retiring the markup; that decision has since been taken
            // and it is gone.

            populateEngineerFilter();
            filterAndRender();

        } catch (dashboardError) {
            console.error("CRITICAL: Dashboard Data Stream Failed:", dashboardError);
            setDashboardLoadState('error', 'Dashboard data could not be loaded. Please check your connection or retry.');
        }
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function dashboardStatusClass(status) {
        const value = String(status || '').toLowerCase();
        if (value.includes('waiting for p.o')) return 'dashboard-status-po';
        if (value.includes('waiting for parts')) return 'dashboard-status-parts';
        if (value.includes('continuation')) return 'dashboard-status-continuation';
        return 'dashboard-status-progress';
    }

    // Kept for existing callers. Status colours are fixed semantic pairs (DESIGN.md:
    // never re-theme status with the accent), shared by the tables and the phone cards.
    function dashboardBootstrapStatusClass(status) {
        return `dashboard-status-chip ${dashboardStatusClass(status)}`;
    }

    function dashboardStatusChip(status) {
        return `<span class="${dashboardBootstrapStatusClass(status)}">${escapeHtml(status || 'In Progress')}</span>`;
    }

    // Days past the last scheduled day of an open task; 0 when not late. Open tasks are
    // never Completed, so any past date means the visit was not closed on time. Done
    // work orders (Completed) are never late.
    function dashboardDaysLate(task) {
        if (task.status === 'Completed') return 0;
        const end = parseDashboardDate(task.range_end_date || task.task_date);
        if (!end) return 0;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const days = Math.round((today - end) / 86400000);
        return days > 0 ? days : 0;
    }

    function dashboardLateChip(task) {
        const days = dashboardDaysLate(task);
        return days ? `<span class="dashboard-late-chip">${escapeHtml(days)} day${days === 1 ? '' : 's'} late</span>` : '';
    }

    // The timeline jumps to the week of ?date= (applyTimelineUrlDateTarget).
    function dashboardTimelineHref(task) {
        const date = String((task || {}).raw_sort_date || (task || {}).task_date || '');
        return /^\d{4}-\d{2}-\d{2}$/.test(date) ? `/timeline?date=${date}` : '/timeline';
    }

    function dashboardEquipmentLabel(task) {
        const productName = task.product_name || task.product || '';
        const serial = task.serial || task.product_id || '';
        if (productName && serial) return `${productName} (${serial})`;
        return productName || serial || 'No equipment listed';
    }

    function dashboardTaskDateLabel(task) {
        return task.display_range || task.task_date || 'No date';
    }

    function buildDashboardTaskMobileCard(task, options = {}) {
        const compact = Boolean(options.compact);
        const late = dashboardDaysLate(task) > 0;
        return `
            <a class="dashboard-mobile-task-card${late ? ' is-late' : ''}" href="${escapeHtml(dashboardTimelineHref(task))}"${options.workOrder ? ` data-work-order-id="${escapeHtml(task.id)}"` : ''}>
                <div class="dashboard-mobile-card-top">
                    <div>
                        <div class="dashboard-mobile-card-date">${escapeHtml(dashboardTaskDateLabel(task))} ${dashboardLateChip(task)} ${workOrderTsrChip(task)}</div>
                        <div class="dashboard-mobile-card-title">${escapeHtml(task.client || 'No facility')}</div>
                    </div>
                    ${dashboardStatusChip(task.status)}
                </div>
                <div class="dashboard-mobile-card-body">
                    <div class="dashboard-mobile-card-row">
                        <i class="fa-solid fa-user-gear"></i>
                        <span>${escapeHtml(task.engineer || loggedInUser || 'Engineer')}</span>
                    </div>
                    <div class="dashboard-mobile-card-row">
                        <i class="fa-solid fa-microscope"></i>
                        <span>${escapeHtml(dashboardEquipmentLabel(task))}</span>
                    </div>
                    <div class="dashboard-mobile-card-row">
                        <i class="fa-solid fa-screwdriver-wrench"></i>
                        <span>${escapeHtml(task.task || 'No task details')}</span>
                    </div>
                    ${compact ? '' : `
                    <div class="dashboard-mobile-card-row">
                        <i class="fa-solid fa-clock"></i>
                        <span>Created ${escapeHtml(formatCreatedOn(task.created_at))}</span>
                    </div>`}
                </div>
            </a>
        `;
    }

    // Phones show 20 cards at a time; the company-wide list used to render all of them.
    const DASHBOARD_MOBILE_PAGE_SIZE = 20;

    function renderMobileTaskList(containerId, tasks, options = {}) {
        const container = document.getElementById(containerId);
        if(!container) return;

        container._dashboardTasks = tasks || [];
        container._dashboardOptions = options;
        container._dashboardLimit = DASHBOARD_MOBILE_PAGE_SIZE;
        drawMobileTaskList(container);
    }

    function drawMobileTaskList(container) {
        const tasks = container._dashboardTasks || [];
        if(!tasks.length){
            container.innerHTML = '';
            return;
        }

        const shown = tasks.slice(0, container._dashboardLimit);
        const remaining = tasks.length - shown.length;
        container.innerHTML = shown.map(task => buildDashboardTaskMobileCard(task, container._dashboardOptions)).join('')
            + (remaining > 0
                ? `<button type="button" class="btn btn-outline-secondary fw-bold w-100 dashboard-show-more">Show ${Math.min(remaining, DASHBOARD_MOBILE_PAGE_SIZE)} more <span class="fw-normal">(${remaining} left)</span></button>`
                : '');

        const more = container.querySelector('.dashboard-show-more');
        if (more) {
            more.addEventListener('click', () => {
                container._dashboardLimit += DASHBOARD_MOBILE_PAGE_SIZE;
                drawMobileTaskList(container);
            });
        }
    }

    function parseDashboardDate(value) {
        if (!value) return null;
        const parts = String(value).split('-').map(Number);
        if (parts.length === 3 && parts.every(Number.isFinite)) {
            return new Date(parts[0], parts[1] - 1, parts[2]);
        }
        const fallback = new Date(value);
        return isNaN(fallback.getTime()) ? null : fallback;
    }

    function dashboardDateValue(value) {
        const parsed = parseDashboardDate(value);
        return parsed ? parsed.getTime() : 0;
    }

    function isTaskAssignedToCurrentEngineer(task) {
        const ids = Array.isArray(task.engineer_ids) ? task.engineer_ids.map(Number).filter(Number.isFinite) : [];
        if (loggedInEngineerId && ids.includes(loggedInEngineerId)) {
            return true;
        }

        const names = Array.isArray(task.engineer_names) && task.engineer_names.length
            ? task.engineer_names
            : String(task.engineer || '').split(',');
        const userToken = String(loggedInUser || '').trim().toLowerCase();
        if (!userToken) return false;

        return names.some(name => String(name || '').trim().toLowerCase().includes(userToken));
    }

    // ---- My Work Orders (dashboard remodel phase B, MaintainX model) ----
    // Tabs filter the engineer's own open tasks (already loaded); "Done this week" is
    // fetched from /get_my_done_tasks the first time it is opened.
    const WORK_ORDER_TABS = ['today', 'overdue', 'upcoming', 'waiting', 'done'];
    const WORK_ORDER_EMPTY = {
        today: 'No visits today.',
        overdue: 'Nothing overdue.',
        upcoming: 'No upcoming visits.',
        waiting: 'Nothing waiting on parts or P.O.',
        done: 'No visits completed in the last 7 days.'
    };
    let workOrdersTab = '';
    let workOrdersDone = null;
    let workOrdersReturnFocus = null;

    function workOrderBuckets(myTasks) {
        const todayStart = new Date();
        todayStart.setHours(0, 0, 0, 0);
        const day = task => parseDashboardDate(task.task_date);
        return {
            today: myTasks.filter(task => day(task) && day(task).getTime() === todayStart.getTime()),
            overdue: myTasks.filter(task => dashboardDaysLate(task) > 0),
            upcoming: myTasks.filter(task => day(task) && day(task) > todayStart),
            waiting: myTasks.filter(task => ['Waiting for P.O', 'Waiting for Parts'].includes(task.status))
        };
    }

    // Only done rows carry has_tsr; open visits get their TSR after completion.
    function workOrderTsrChip(task) {
        if (task.has_tsr === undefined) return '';
        return task.has_tsr
            ? '<span class="work-order-tsr is-done">TSR uploaded</span>'
            : '<span class="work-order-tsr is-missing">TSR missing</span>';
    }

    function workOrderTimeLabel(task) {
        if (!task.time_start) return '';
        return task.time_end ? `${task.time_start} – ${task.time_end}` : task.time_start;
    }

    function setWorkOrdersTab(tab) {
        if (!WORK_ORDER_TABS.includes(tab)) return;
        workOrdersTab = tab;
        closeWorkOrderPanel(false);
        renderMyTasks();
    }

    async function loadMyDoneTasks() {
        try {
            const rows = await fetchJsonOrThrow('/get_my_done_tasks');
            workOrdersDone = Array.isArray(rows) ? rows : [];
        } catch (error) {
            console.warn('[Dashboard] Done this week could not be loaded', error);
            workOrdersDone = undefined;
        }
        renderEngineerWeek();
        if (workOrdersTab === 'done') renderMyTasks();
    }

    // Done this week card: visits finished Monday to today, from the Done this week rows
    // (/get_my_done_tasks covers the last 7 days, so every day from Monday is present).
    function renderEngineerWeek() {
        const count = document.getElementById('engineer-week-count');
        if (!count) return;
        if (!Array.isArray(workOrdersDone)) {
            count.textContent = '–';
            return;
        }
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const monday = new Date(today);
        monday.setDate(today.getDate() - (today.getDay() + 6) % 7);
        const total = workOrdersDone.filter(task => {
            const day = parseDashboardDate(task.task_date);
            return day && day >= monday && day <= today;
        }).length;
        animateDashboardNumber(count, total);
        renderEngineerWeekBadge();
    }

    // The card's badge: Monday-to-today against the same days last week, both from the
    // Visits completed series (same definition as the Done this week rows).
    function renderEngineerWeekBadge() {
        const badge = document.getElementById('engineer-week-badge');
        const points = engineerSeriesPoints;
        if (!badge || !points.length) return;
        const todayIndex = (new Date().getDay() + 6) % 7;
        const sum = list => list.reduce((total, point) => total + Number(point.value || 0), 0);
        const thisWeek = sum(points.slice(-(todayIndex + 1)));
        const lastWeek = sum(points.slice(-(todayIndex + 8), -7));
        const delta = thisWeek - lastWeek;
        badge.className = `dash-stat-badge${delta > 0 ? ' is-better' : ''}`;
        badge.innerHTML = delta === 0
            ? 'Same as last week'
            : `<i class="fa-solid fa-arrow-${delta > 0 ? 'up' : 'down'}" aria-hidden="true"></i> ${Math.abs(delta)} vs last week`;
    }

    // ---- Visits completed area chart (Dashboard Style) ----
    // One chart per page: the engineer's own (engineer-activity) or the company's
    // (manager-activity, managers and hybrids). prefix names the chart's element ids.
    const dashboardChartState = {points: [], range: 90, index: null, firstDraw: true, requested: false,
                                 companyRequested: false, prefix: 'engineer-activity', comparePoints: []};
    const DASHBOARD_CHART_RANGES = {90: 'Last 3 months', 30: 'Last 30 days', 7: 'Last 7 days'};
    // The engineer's own series also feeds the Done this week badge, chart or not (hybrids).
    let engineerSeriesPoints = [];

    async function loadEngineerActivity() {
        const chart = document.getElementById('engineer-activity-chart');
        if (!chart && !document.getElementById('engineer-week-badge')) return;
        try {
            const data = await fetchJsonOrThrow('/get_dashboard_series?metric=my_completed&days=90');
            engineerSeriesPoints = Array.isArray((data || {}).points) ? data.points : [];
        } catch (error) {
            console.warn('[Dashboard] Visits completed could not be loaded', error);
            if (chart) chart.innerHTML = '<p class="dash-chart-empty">Could not load completed visits. Refresh the page to try again.</p>';
            return;
        }
        if (chart) {
            dashboardChartState.points = engineerSeriesPoints;
            setDashboardChartRange(dashboardChartState.range);
        }
        renderEngineerWeekBadge();
    }

    async function loadManagerActivity() {
        const chart = document.getElementById('manager-activity-chart');
        if (!chart) return;
        dashboardChartState.prefix = 'manager-activity';
        try {
            const [completed, scheduled] = await Promise.all([
                fetchJsonOrThrow('/get_dashboard_series?metric=company_completed&days=90'),
                fetchJsonOrThrow('/get_dashboard_series?metric=company_scheduled&days=90'),
            ]);
            dashboardChartState.points = Array.isArray((completed || {}).points) ? completed.points : [];
            dashboardChartState.comparePoints = Array.isArray((scheduled || {}).points) ? scheduled.points : [];
        } catch (error) {
            console.warn('[Dashboard] Company visits completed could not be loaded', error);
            chart.innerHTML = '<p class="dash-chart-empty">Could not load completed visits. Refresh the page to try again.</p>';
            return;
        }
        setDashboardChartRange(dashboardChartState.range);
    }

    function setDashboardChartRange(range) {
        const days = DASHBOARD_CHART_RANGES[range] ? Number(range) : 90;
        dashboardChartState.range = days;
        dashboardChartState.index = null;
        document.querySelectorAll('.dash-segment-btn').forEach(button => {
            button.setAttribute('aria-pressed', String(Number(button.dataset.range) === days));
        });
        const prefix = dashboardChartState.prefix;
        setTextIfPresent(`${prefix}-sub`, DASHBOARD_CHART_RANGES[days] + (days === 90 ? ', by week' : ''));
        const byRange = series => {
            const daily = series.slice(-days);
            return days === 90 ? groupDashboardPointsByWeek(daily) : daily;
        };
        const points = byRange(dashboardChartState.points);
        // The manager chart compares against visits scheduled; the engineer chart has no compare.
        const comparePoints = prefix === 'manager-activity' ? byRange(dashboardChartState.comparePoints) : [];
        renderDashboardAreaChart(
            document.getElementById(`${prefix}-chart`),
            points,
            {unit: 'visit', label: DASHBOARD_CHART_RANGES[days].toLowerCase(), weekly: days === 90,
             readout: document.getElementById(`${prefix}-readout`),
             compare: points.length && comparePoints.length === points.length ? {points: comparePoints} : null}
        );
    }

    // Three months of daily 0-2 counts read as spikes, so that range is drawn as weekly
    // totals, counted back from today (the oldest group may be shorter than 7 days).
    function groupDashboardPointsByWeek(points) {
        const groups = [];
        for (let end = points.length; end > 0; end -= 7) {
            const week = points.slice(Math.max(0, end - 7), end);
            groups.unshift({date: week[0].date, value: week.reduce((sum, point) => sum + Number(point.value || 0), 0)});
        }
        return groups;
    }

    function formatDashboardChartDay(value, withWeekday) {
        const date = new Date(`${value}T00:00:00`);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleDateString('en-US', withWeekday
            ? {weekday: 'short', month: 'short', day: 'numeric'}
            : {month: 'short', day: 'numeric'});
    }

    // One smooth line with a light fill, three gridlines and a few date labels. Pointer,
    // tap and arrow keys move a marker and write the day into the readout line.
    // options.compare = {points} adds a muted dashed line (the manager chart's visits
    // scheduled), drawn on the same scale and named in the readout; same length as points.
    function renderDashboardAreaChart(container, points, options) {
        if (!container) return;
        const readout = options.readout;
        const plural = n => `${n} ${options.unit}${n === 1 ? '' : 's'}`;
        const values = points.map(point => Number(point.value || 0));
        const total = values.reduce((sum, value) => sum + value, 0);
        const compare = options.compare
            ? options.compare.points.map(point => Number(point.value || 0))
            : null;
        const compareTotal = compare ? compare.reduce((sum, value) => sum + value, 0) : 0;
        const summary = compare
            ? `${total} of ${compareTotal} scheduled ${options.unit}${compareTotal === 1 ? '' : 's'} completed in the ${options.label}`
            : `${plural(total)} in the ${options.label}`;
        if (!points.length || (total === 0 && compareTotal === 0)) {
            container.innerHTML = `<p class="dash-chart-empty">No ${compare ? 'scheduled' : 'completed'} visits in this range.</p>`;
            if (readout) readout.textContent = '';
            return;
        }

        const width = Math.max(container.clientWidth, 280);
        const height = width < 576 ? 160 : 200;
        const pad = {top: 12, right: 8, bottom: 24, left: 8};
        const top = Math.max(4, Math.ceil(Math.max(...values, ...(compare || [])) / 2) * 2);
        const x = i => pad.left + (points.length === 1 ? 0 : i * (width - pad.left - pad.right) / (points.length - 1));
        const y = v => pad.top + (1 - v / top) * (height - pad.top - pad.bottom);
        const smooth = series => {
            let path = `M${x(0)},${y(series[0])}`;
            for (let i = 1; i < series.length; i += 1) {
                const mid = (x(i - 1) + x(i)) / 2;
                path += ` C${mid},${y(series[i - 1])} ${mid},${y(series[i])} ${x(i)},${y(series[i])}`;
            }
            return path;
        };
        const line = smooth(values);
        const base = y(0);
        const grid = [0, top / 2, top].map(v =>
            `<line class="dash-chart-grid" x1="${pad.left}" x2="${width - pad.right}" y1="${y(v)}" y2="${y(v)}"/>` +
            (v ? `<text class="dash-chart-axis" x="${pad.left}" y="${y(v) - 4}">${v}</text>` : '')).join('');
        const tickCount = Math.min(points.length, width < 576 ? 3 : 5);
        const ticks = Array.from({length: tickCount}, (_, n) =>
            Math.round(n * (points.length - 1) / Math.max(tickCount - 1, 1)));
        const labels = ticks.map((i, n) => {
            const anchor = n === 0 ? 'start' : (n === ticks.length - 1 ? 'end' : 'middle');
            return `<text class="dash-chart-axis" x="${x(i)}" y="${height - 6}" text-anchor="${anchor}">${escapeHtml(formatDashboardChartDay(points[i].date))}</text>`;
        }).join('');

        const animate = dashboardChartState.firstDraw && !dashboardReducedMotion.matches;
        dashboardChartState.firstDraw = false;
        container.innerHTML = `<svg class="dash-chart-svg${animate ? ' is-drawing' : ''}" viewBox="0 0 ${width} ${height}" width="100%" height="${height}" tabindex="0" role="img" aria-label="Visits ${compare ? 'scheduled and ' : ''}completed, ${escapeHtml(summary)}. Use the left and right arrow keys to read each ${options.weekly ? 'week' : 'day'}.">
            ${grid}
            ${compare ? `<path class="dash-chart-line is-compare" d="${smooth(compare)}"/>` : ''}
            <path class="dash-chart-fill" d="${line} L${x(values.length - 1)},${base} L${x(0)},${base} Z"/>
            <path class="dash-chart-line" d="${line}" pathLength="1"/>
            <line class="dash-chart-cursor d-none" y1="${pad.top}" y2="${base}"/>
            ${compare ? '<circle class="dash-chart-dot is-compare d-none" r="3.5"/>' : ''}
            <circle class="dash-chart-dot d-none" r="4"/>
            ${labels}
        </svg>`;
        if (readout) readout.textContent = summary;

        const svg = container.querySelector('svg');
        const cursor = svg.querySelector('.dash-chart-cursor');
        const dot = svg.querySelector('.dash-chart-dot:not(.is-compare)');
        const compareDot = svg.querySelector('.dash-chart-dot.is-compare');
        const show = index => {
            dashboardChartState.index = index;
            if (index === null) {
                cursor.classList.add('d-none');
                dot.classList.add('d-none');
                if (compareDot) compareDot.classList.add('d-none');
                if (readout) readout.textContent = summary;
                return;
            }
            cursor.setAttribute('x1', x(index));
            cursor.setAttribute('x2', x(index));
            dot.setAttribute('cx', x(index));
            dot.setAttribute('cy', y(values[index]));
            cursor.classList.remove('d-none');
            dot.classList.remove('d-none');
            if (compareDot) {
                compareDot.setAttribute('cx', x(index));
                compareDot.setAttribute('cy', y(compare[index]));
                compareDot.classList.remove('d-none');
            }
            const when = options.weekly
                ? `Week of ${formatDashboardChartDay(points[index].date)}`
                : formatDashboardChartDay(points[index].date, true);
            if (readout) {
                readout.textContent = compare
                    ? `${when} · ${compare[index]} scheduled · ${values[index]} completed`
                    : `${when} · ${plural(values[index])}`;
            }
        };
        const nearest = event => {
            const box = svg.getBoundingClientRect();
            const px = (event.clientX - box.left) / box.width * width;
            const step = (width - pad.left - pad.right) / Math.max(points.length - 1, 1);
            return Math.min(points.length - 1, Math.max(0, Math.round((px - pad.left) / step)));
        };
        svg.addEventListener('pointermove', event => show(nearest(event)));
        svg.addEventListener('pointerdown', event => show(nearest(event)));
        svg.addEventListener('pointerleave', event => { if (event.pointerType === 'mouse') show(null); });
        svg.addEventListener('blur', () => show(null));
        svg.addEventListener('keydown', event => {
            const last = points.length - 1;
            const current = dashboardChartState.index === null ? last + 1 : dashboardChartState.index;
            const moves = {ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: last};
            if (!(event.key in moves)) return;
            event.preventDefault();
            show(Math.min(last, Math.max(0, moves[event.key])));
        });
    }

    let dashboardChartResizeTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(dashboardChartResizeTimer);
        dashboardChartResizeTimer = setTimeout(() => {
            if (dashboardChartState.points.length) setDashboardChartRange(dashboardChartState.range);
        }, 200);
    });

    /**
     * Personalization Logic.
     * Renders the active work-order tab of the tasks assigned to the current user.
     */
    function renderMyTasks() {
        const targetBody = document.getElementById('my-tasks-body');
        const emptyMsg = document.getElementById('no-my-tasks');

        if(!targetBody) return;

        const buckets = workOrderBuckets(getCurrentEngineerTasks());
        const tableWrap = document.getElementById('my-tasks-table-wrap');
        const emptyText = document.getElementById('no-my-tasks-text');

        ['today', 'overdue', 'upcoming', 'waiting'].forEach(tab => setTextIfPresent(`work-orders-count-${tab}`, buckets[tab].length));
        setTextIfPresent('work-orders-count-done', Array.isArray(workOrdersDone) ? workOrdersDone.length : '');
        // First visit: open the first tab that has work in it.
        if (!workOrdersTab) {
            workOrdersTab = ['today', 'overdue', 'upcoming', 'waiting'].find(tab => buckets[tab].length) || 'today';
        }
        document.querySelectorAll('.work-orders-tab').forEach(button => {
            button.setAttribute('aria-selected', String(button.dataset.tab === workOrdersTab));
        });

        let tasks = buckets[workOrdersTab] || [];
        let message = WORK_ORDER_EMPTY[workOrdersTab];
        if (workOrdersTab === 'done') {
            if (workOrdersDone === null) {
                workOrdersDone = false;
                loadMyDoneTasks();
            }
            tasks = Array.isArray(workOrdersDone) ? workOrdersDone : [];
            if (workOrdersDone === false) message = 'Loading visits completed this week…';
            if (workOrdersDone === undefined) message = 'Could not load completed visits. Open the tab again to retry.';
            if (workOrdersDone === undefined) workOrdersDone = null;
        }

        targetBody.innerHTML = "";

        if (tasks.length === 0) {
            emptyMsg.classList.remove('d-none');
            if (emptyText) emptyText.textContent = message;
            // No header row over an empty table: one line says it.
            if (tableWrap) tableWrap.classList.add('d-none');
            renderMobileTaskList('my-tasks-mobile-list', []);
        } else {
            emptyMsg.classList.add('d-none');
            if (tableWrap) tableWrap.classList.remove('d-none');
            renderMobileTaskList('my-tasks-mobile-list', tasks, { compact: true, workOrder: true });

            // The date link opens the detail panel (delegated click below); the href keeps
            // the timeline reachable with a modifier click or without JS.
            targetBody.innerHTML = tasks.map(task => `
                <tr class="small dashboard-my-task-row work-order-row${dashboardDaysLate(task) ? ' dashboard-row-late' : ''}" data-work-order-id="${escapeHtml(task.id)}">
                    <td class="ps-3">
                        <a class="fw-bold dashboard-row-link" href="${escapeHtml(dashboardTimelineHref(task))}" data-work-order-id="${escapeHtml(task.id)}">${escapeHtml(dashboardTaskDateLabel(task))}</a>
                        <div class="xsmall text-muted">${escapeHtml(workOrderTimeLabel(task))}</div>
                        ${dashboardLateChip(task)}
                    </td>
                    <td>
                        <strong>${escapeHtml(task.client || 'No facility')}</strong>
                    </td>
                    <td>
                        <div class="fw-bold text-dark">${escapeHtml(dashboardEquipmentLabel(task))}</div>
                    </td>
                    <td class="text-end pe-3">${dashboardStatusChip(task.status)} ${workOrderTsrChip(task)}</td>
                </tr>`).join('');
        }
    }

    function findWorkOrder(id) {
        const pool = allOpenTasksRaw.concat(Array.isArray(workOrdersDone) ? workOrdersDone : []);
        return pool.find(task => String(task.id) === String(id));
    }

    function openWorkOrderPanel(id, trigger) {
        const panel = document.getElementById('work-order-panel');
        const body = document.getElementById('work-order-panel-body');
        const task = findWorkOrder(id);
        if (!panel || !body || !task) return false;

        const field = (label, value) => `<dt>${escapeHtml(label)}</dt><dd>${value}</dd>`;
        const tsr = task.has_tsr === undefined
            ? 'Upload after the visit is completed'
            : (task.has_tsr ? 'Uploaded' : 'Missing');
        document.getElementById('work-order-panel-title').textContent = task.client || 'Work order';
        body.innerHTML = '<dl class="work-order-fields">'
            + field('Status', `${dashboardStatusChip(task.status)} ${dashboardLateChip(task)}`)
            + field('Date', escapeHtml([dashboardTaskDateLabel(task), workOrderTimeLabel(task)].filter(Boolean).join(', ')))
            + field('Facility', escapeHtml(task.client || 'No facility'))
            + field('Equipment', escapeHtml(task.product_name || task.product || 'No equipment listed'))
            + field('Serial', escapeHtml(task.serial || '—'))
            + field('Engineers', escapeHtml((task.engineer_names || []).join(', ') || task.engineer || '—'))
            + field('TSR', escapeHtml(tsr))
            + field('Task', escapeHtml(task.task || 'No task details'))
            + '</dl>'
            + `<a class="btn btn-primary fw-bold w-100" href="${escapeHtml(dashboardTimelineHref(task))}">Open on timeline</a>`;

        document.querySelectorAll('.work-order-row.is-selected').forEach(row => row.classList.remove('is-selected'));
        const row = document.querySelector(`.work-order-row[data-work-order-id="${CSS.escape(String(task.id))}"]`);
        if (row) row.classList.add('is-selected');

        workOrdersReturnFocus = trigger || null;
        panel.hidden = false;
        document.getElementById('work-orders-layout')?.classList.add('has-panel');
        document.body.classList.add('work-order-sheet-open');
        document.getElementById('work-order-panel-close')?.focus();
        return true;
    }

    function closeWorkOrderPanel(restoreFocus = true) {
        const panel = document.getElementById('work-order-panel');
        if (!panel || panel.hidden) return;
        panel.hidden = true;
        document.getElementById('work-orders-layout')?.classList.remove('has-panel');
        document.body.classList.remove('work-order-sheet-open');
        document.querySelectorAll('.work-order-row.is-selected').forEach(row => row.classList.remove('is-selected'));
        if (!restoreFocus) return;
        const target = workOrdersReturnFocus && workOrdersReturnFocus.isConnected
            ? workOrdersReturnFocus
            : document.querySelector('.work-orders-tab[aria-selected="true"]');
        if (target) target.focus();
    }

    // Rows, date links and phone cards open the panel; a modifier click still follows
    // the link to the timeline.
    document.addEventListener('click', event => {
        const hit = event.target.closest('#work-orders-list [data-work-order-id]');
        if (!hit || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const link = hit.closest('a') || hit.querySelector('a[data-work-order-id]');
        if (openWorkOrderPanel(hit.dataset.workOrderId, link || hit)) event.preventDefault();
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') closeWorkOrderPanel();
    });

    /**
     * AGGREGATION LOGIC:
     * Consolidates multi-day technical visits.
     */
    function groupTasksByRange(tasksList) {
        if (!tasksList.length) return [];
        
        const taskGroups = {};
        tasksList.forEach(item => {
            const productKey = item.product_id || item.serial || item.product_name || item.product || '';
            const compositeKey = `${item.engineer}|${item.client_id || item.client}|${productKey}|${item.task}|${item.status}`;
            if (!taskGroups[compositeKey]) {
                taskGroups[compositeKey] = [];
            }
            taskGroups[compositeKey].push(item);
        });

        const mergedResults = [];
        
        for (let key in taskGroups) {
            let instances = taskGroups[key];
            instances.sort((a, b) => dashboardDateValue(a.task_date) - dashboardDateValue(b.task_date));

            let sequenceBuffer = [instances[0]];
            
            for (let i = 1; i <= instances.length; i++) {
                let previousRec = instances[i - 1];
                let currentRec = instances[i];
                let isSequential = false;
                if (currentRec) {
                    let dP = parseDashboardDate(previousRec.task_date);
                    let dC = parseDashboardDate(currentRec.task_date);
                    if (dP && dC && Math.round((dC - dP) / (1000 * 60 * 60 * 24)) === 1) isSequential = true;
                }

                if (isSequential) {
                    sequenceBuffer.push(currentRec);
                } else {
                    let rStart = sequenceBuffer[0];
                    let rEnd = sequenceBuffer[sequenceBuffer.length - 1];
                    let sDate = parseDashboardDate(rStart.task_date);
                    let eDate = parseDashboardDate(rEnd.task_date);
                    let startLabel = rStart.task_date || '';
                    let endLabel = rEnd.task_date || startLabel;
                    if (sDate) startLabel = `${sDate.getFullYear()}-${String(sDate.getMonth() + 1).padStart(2, '0')}-${String(sDate.getDate()).padStart(2, '0')}`;
                    if (eDate) endLabel = `${eDate.getFullYear()}-${String(eDate.getMonth() + 1).padStart(2, '0')}-${String(eDate.getDate()).padStart(2, '0')}`;
                    let rangeLabel = startLabel === endLabel ? startLabel : `${startLabel} → ${endLabel}`;
                    
                    mergedResults.push({
                        ...rStart,
                        display_range: rangeLabel,
                        raw_sort_date: rStart.task_date,
                        range_end_date: rEnd.task_date
                    });
                    
                    if (currentRec) sequenceBuffer = [currentRec];
                }
            }
        }
        return mergedResults;
    }

    const OPEN_TASK_SORT_MODES = ['scheduled_latest', 'scheduled_oldest', 'created_latest'];

    function setOpenTasksSort(mode) {
        currentSortMode = OPEN_TASK_SORT_MODES.includes(mode) ? mode : 'scheduled_latest';
        const select = document.getElementById('sort-mode');
        if (select && select.value !== currentSortMode) select.value = currentSortMode;
        filterAndRender();
    }

    // Kept for existing callers: cycles to the next sort mode.
    function toggleSort() {
        const next = OPEN_TASK_SORT_MODES[(OPEN_TASK_SORT_MODES.indexOf(currentSortMode) + 1) % OPEN_TASK_SORT_MODES.length];
        setOpenTasksSort(next);
    }

    function taskEngineerNames(task) {
        const names = Array.isArray(task.engineer_names) && task.engineer_names.length
            ? task.engineer_names
            : String(task.engineer || '').split(',');
        return names.map(name => String(name || '').trim()).filter(name => name && name !== 'None');
    }

    function populateEngineerFilter() {
        const select = document.getElementById('filter-engineer');
        if (!select) return;
        const current = select.value;
        const names = Array.from(new Set(allOpenTasksRaw.flatMap(taskEngineerNames))).sort((a, b) => a.localeCompare(b));
        select.innerHTML = '<option value="">All engineers</option>'
            + names.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
        if (names.includes(current)) select.value = current;
    }

    function formatCreatedOn(value) {
        if (!value) return "-";

        // Backend sends format like: YYYY-MM-DD HH:MM
        const parts = String(value).split(" ");
        if (parts.length < 2) return value;

        const datePart = parts[0];
        const timePart = parts[1];

        const d = new Date(`${datePart}T${timePart}:00`);
        if (isNaN(d.getTime())) return value;

        return d.toLocaleString('en-US', {
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        });
    }

    function filterAndRender() {
        const statusFilter = document.getElementById('filter-status');
        const targetBody = document.getElementById('open-tasks-body');
        if (!statusFilter || !targetBody) return;

        const activeFilter = statusFilter.value;
        const engineerFilter = (document.getElementById('filter-engineer') || {}).value || '';
        const searchText = String((document.getElementById('open-tasks-search') || {}).value || '').trim().toLowerCase();
        let processedList = groupTasksByRange(allOpenTasksRaw);
        let filteredTasks = processedList.filter(t => {
            if (activeFilter && t.status !== activeFilter) return false;
            if (engineerFilter && !taskEngineerNames(t).includes(engineerFilter)) return false;
            if (searchText) {
                const haystack = [t.client, t.engineer, t.product_name || t.product, t.serial, t.task]
                    .map(value => String(value || '').toLowerCase()).join(' ');
                if (!haystack.includes(searchText)) return false;
            }
            return true;
        });

        filteredTasks.sort((a, b) => {
            const scheduledA = parseDashboardDate(a.raw_sort_date || a.task_date) || new Date(0);
            const scheduledB = parseDashboardDate(b.raw_sort_date || b.task_date) || new Date(0);
            const createdA = new Date(a.created_at || 0);
            const createdB = new Date(b.created_at || 0);

            if (currentSortMode === 'scheduled_oldest') {
                return scheduledA - scheduledB;
            }

            if (currentSortMode === 'created_latest') {
                return createdB - createdA;
            }

            return scheduledB - scheduledA;
        });

        targetBody.innerHTML = "";

        if (filteredTasks.length === 0) {
            document.getElementById('no-tasks-msg').classList.remove('d-none');
            setTextIfPresent('no-tasks-text', (activeFilter || engineerFilter || searchText)
                ? 'No open tasks match these filters.'
                : 'No open technical tasks.');
            renderMobileTaskList('open-tasks-mobile-list', []);
        } else {
            document.getElementById('no-tasks-msg').classList.add('d-none');
            renderMobileTaskList('open-tasks-mobile-list', filteredTasks);

            targetBody.innerHTML = filteredTasks.map(task => {
                return `
                    <tr class="small${dashboardDaysLate(task) ? ' dashboard-row-late' : ''}">
                        <td class="ps-4">
                            <a class="fw-bold dashboard-row-link" href="${escapeHtml(dashboardTimelineHref(task))}">${escapeHtml(task.display_range)}</a>
                            ${dashboardLateChip(task)}
                        </td>
                        <td><strong>${escapeHtml(task.engineer)}</strong></td>
                        <td>${escapeHtml(task.client)}</td>
                        <td class="text-muted">${escapeHtml(task.task)}</td>
                        <td>${dashboardStatusChip(task.status)}</td>
                        <td class="text-end pe-4 text-muted font-monospace">${escapeHtml(formatCreatedOn(task.created_at))}</td>
                    </tr>`;
            }).join('');
        }
    }
    
    // Application Entry
    initDashboardDragAndDrop();
    loadDashboard();

function submitPw(){
    const pw = document.getElementById('newPw').value;
    if(pw.length < 8){ alert('Minimum 8 characters required'); return; }

    fetch('/force_change_password_api', {
        method: 'POST',
        headers: {
            'Content-Type':'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ new_password: pw })
    })
    .then(res => res.json())
    .then(data => {
        if(data.status === 'success'){
            location.reload();
        } else {
            alert(data.message || 'Password not valid');
        }
    });
}

// Collapsible reference sections (engineer view). Uses the Bootstrap Collapse API that
// is already loaded by layout.html, and keeps aria-expanded in sync with the arrow.
(function () {
    document.addEventListener('DOMContentLoaded', function () {
        const toggle = document.getElementById('open-tasks-toggle');
        const panel = document.getElementById('open-tasks-panel');
        if (!toggle || !panel || typeof bootstrap === 'undefined') return;

        const collapse = new bootstrap.Collapse(panel, { toggle: false });

        toggle.addEventListener('click', function () {
            const expanded = toggle.getAttribute('aria-expanded') === 'true';
            expanded ? collapse.hide() : collapse.show();
        });

        panel.addEventListener('shown.bs.collapse', function () {
            toggle.setAttribute('aria-expanded', 'true');
        });
        panel.addEventListener('hidden.bs.collapse', function () {
            toggle.setAttribute('aria-expanded', 'false');
        });
    });
})();
