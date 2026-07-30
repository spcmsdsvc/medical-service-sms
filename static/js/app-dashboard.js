/* Extracted from the inline <script> blocks in templates/dashboard.html.
   Behaviour is unchanged; only the 12 template-injected constants moved to
   window.__dashboardConfig, set inline by the template before this loads. */

    (function(){
        function renderDashboardChangelogPrompt(data){
            const panel = document.getElementById('dashboard-whats-new');
            const latest = data?.latest_unread;
            if(!panel) return;
            if(!latest || Number(data.unread_count || 0) <= 0){
                panel.style.display = 'none';
                return;
            }
            document.getElementById('dashboard-whats-new-date').textContent = `${Number(data.unread_count || 0)} unread update${Number(data.unread_count || 0) === 1 ? '' : 's'} | ${latest.release_date || ''}`;
            document.getElementById('dashboard-whats-new-title').textContent = latest.title || "What's New";
            document.getElementById('dashboard-whats-new-summary').textContent = latest.summary || `${Number(latest.item_count || 0)} improvement(s) are ready to review.`;
            panel.style.display = '';
        }
        window.addEventListener('changelog:summary', event => renderDashboardChangelogPrompt(event.detail || {}));
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
        const dateOptions = {
            timeZone: 'Asia/Manila',
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        };

        const manilaTime = new Intl.DateTimeFormat('en-US', clockOptions).format(now);
        const manilaDate = new Intl.DateTimeFormat('en-US', dateOptions).format(now);
        
        document.getElementById('system-clock').innerText = manilaTime;
        document.getElementById('current-date').innerText = manilaDate;
    }

    setInterval(updateClock, 1000);
    updateClock();
    
    // Global Dataset Context
    let allOpenTasksRaw = []; 
    let currentSortMode = 'scheduled_latest'; 
    let managerOverviewData = null;
    let schedulerCoordinationData = null;
    let schedulerDispatchData = null;
    let schedulerBranchFilter = 'ALL';
    let schedulerQueueFilter = 'all';
    let schedulerSelectedShift = null;

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
        localStorage.removeItem(dashboardLayoutStorageKey);
        localStorage.removeItem(dashboardCollapsedStorageKey);
        localStorage.removeItem(dashboardHiddenStorageKey);
        // Clear the account copy too, otherwise the next load restores what was reset.
        syncDashboardLayoutToAccount([], []).finally(() => location.reload());
    }

    function initDashboardDragAndDrop() {
        addDashboardDragHandles();
        applySavedDashboardOrder();
        applyHiddenDashboardSections();
        applySavedCollapsedStates();
        setDashboardCustomizeMode(false);

        // Then reconcile against the account copy, which wins. Runs after the cached
        // layout is already applied so there is no visible reflow on the common path.
        loadDashboardLayoutFromAccount();

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
        if (!panel) return;

        if (!data || data.is_approver !== true || data.workflows_enabled !== true) {
            panel.classList.add('d-none');
            return;
        }
        panel.classList.remove('d-none');

        const counts = data.counts || {};
        const modules = Array.isArray(data.modules) ? data.modules : [];
        setTextIfPresent('manager-approvals-total', counts.pending_total || 0);

        const aging = document.getElementById('manager-approvals-aging');
        if (aging) {
            const agingTotal = Number(counts.aging_total || 0);
            const threshold = Number(data.aging_threshold_days || 5);
            if (agingTotal) {
                aging.textContent = `${agingTotal} waiting more than ${threshold} days â€” oldest ${counts.oldest_days || 0} days`;
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
            const panel = document.getElementById('manager-approvals');
            if (panel) panel.classList.add('d-none');
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

    function managerWatchlistTypeLabel(type) {
        const labels = {
            severe_overdue: 'Severely overdue',
            aged_tsr: 'TSR missing',
            waiting: 'Blocked',
            repeat_equipment: 'Repeat equipment',
            high_risk_client: 'Client at risk'
        };
        return labels[String(type || '')] || 'Attention';
    }

    function renderManagerWatchlist(data) {
        const container = document.getElementById('manager-watchlist-list');
        if (!container) return;

        const rows = Array.isArray((data || {}).watchlist) ? data.watchlist : [];
        const total = Number((data || {}).watchlist_total || rows.length);
        setTextIfPresent('manager-watchlist-count', `${total} item${total === 1 ? '' : 's'}`);

        const caption = document.getElementById('manager-watchlist-caption');
        if (caption && total > rows.length) {
            caption.textContent = `Showing the ${rows.length} most pressing of ${total}`;
        }

        if (!rows.length) {
            container.innerHTML = `
                <div class="manager-watchlist-clear">
                    <i class="fa-solid fa-circle-check" aria-hidden="true"></i>
                    <span>Nothing needs management attention right now.</span>
                </div>`;
            return;
        }

        container.innerHTML = rows.map(row => `
            <div class="manager-watchlist-row">
                <span class="manager-watchlist-accent is-${escapeHtml(row.tone || 'watch')}" aria-hidden="true"></span>
                <span class="manager-watchlist-body">
                    <span class="manager-watchlist-title">${escapeHtml(row.title || '')}</span>
                    <span class="manager-watchlist-hint">${escapeHtml(row.subtitle || '')} â€¢ ${escapeHtml(row.detail || '')}</span>
                </span>
                <span class="manager-watchlist-tag">${escapeHtml(managerWatchlistTypeLabel(row.type))}</span>
            </div>
        `).join('');
    }

    async function loadManagerOverview() {
        if (!dashboardManagerView || dashboardSchedulerOnly) return;

        try {
            const data = await fetchJsonOrThrow('/get_manager_overview');
            managerOverviewData = data || {};
            const counts = managerOverviewData.counts || {};
            setTextIfPresent('manager-open-count', counts.open_schedules || 0);
            setTextIfPresent('manager-overdue-count', counts.overdue_schedules || 0);
            setTextIfPresent('manager-pending-tsr-count', counts.pending_tsr || 0);
            setTextIfPresent('manager-waiting-count', counts.waiting_items || 0);

            renderManagerRisk(managerOverviewData);
            renderManagerDirection(managerOverviewData);
            renderManagerWatchlist(managerOverviewData);
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
                caption.textContent = 'Most urgent first â€” select a row to assign or reschedule it';
            } else if (shown < total) {
                caption.textContent = `Showing ${shown} of ${total} â€” most urgent first, select a row to work on it`;
            } else {
                caption.textContent = `${shown} to work through â€” most urgent first, select a row`;
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
                    onclick="selectSchedulerActionShift(${Number(row.id) || 0})">
                <span class="scheduler-queue-accent ${schedulerQueueAccent(row.category)}" aria-hidden="true"></span>
                <span class="scheduler-queue-body">
                    <span class="scheduler-queue-title">${escapeHtml(row.client || 'No client')} â€” ${escapeHtml(row.task || 'Untitled')}</span>
                    <span class="scheduler-queue-hint">${escapeHtml(row.priority_reason || '')} â€¢ ${escapeHtml(when)} â€¢ ${escapeHtml(row.engineers || 'Unassigned')}</span>
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
        setTextIfPresent('scheduler-risk-detail', parts.join(' â€¢ '));
    }

    function renderSchedulerMetrics() {
        const counts = (schedulerDispatchData || {}).counts || {};
        // Filter buttons read queue_counts, which is counted from the de-duplicated queue,
        // so each button's number equals the rows its filter produces. counts.* holds the
        // raw bucket totals, where a schedule can appear in two buckets at once.
        const queueCounts = (schedulerDispatchData || {}).queue_counts || {};
        setTextIfPresent('scheduler-queue-count', (schedulerDispatchData || {}).priority_queue_total || 0);
        setTextIfPresent('scheduler-overdue-count', queueCounts.overdue || 0);
        setTextIfPresent('scheduler-unassigned-count', queueCounts.unassigned || 0);
        setTextIfPresent('scheduler-waiting-count', queueCounts.waiting || 0);
        setTextIfPresent('scheduler-pending-tsr-count', queueCounts.tsr || 0);
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

    function schedulerAvailabilityClass(level) {
        const value = String(level || '').toLowerCase();
        if (value === 'busy') return 'scheduler-availability-busy';
        if (value === 'watch') return 'scheduler-availability-watch';
        return 'scheduler-availability-available';
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

    function renderSchedulerAvailabilityStrip() {
        const container = document.getElementById('scheduler-availability-strip');
        if (!container) return;

        const rows = getSchedulerFilteredAvailability();
        setTextIfPresent('scheduler-availability-count', `${rows.length} engineer${rows.length === 1 ? '' : 's'}`);

        if (!rows.length) {
            container.innerHTML = `<div class="dashboard-team-empty">No engineer availability found for this branch. Try All Branches or refresh tools.</div>`;
            return;
        }

        container.innerHTML = rows.slice(0, 24).map(row => {
            const level = row.loadLevel;
            return `
            <button type="button" class="scheduler-availability-chip ${schedulerAvailabilityClass(level)}" onclick="selectSchedulerEngineerForAssign(${Number(row.engineer_id) || 0})">
                <span class="scheduler-availability-avatar">${escapeHtml(row.initials || '?')}</span>
                <span class="scheduler-availability-main">
                    <strong>${escapeHtml(row.name || 'Engineer')}</strong>
                    <small>${escapeHtml(row.branch || 'No branch')} â€¢ ${escapeHtml(row.today_tasks || 0)} today â€¢ ${escapeHtml(row.next_7_days || 0)} week</small>
                </span>
                <span class="badge ${schedulerAvailabilityBadgeClass(level)}">${escapeHtml(schedulerAvailabilityLabel(level))}</span>
            </button>`;
        }).join('');
    }

    function renderSchedulerAssignableEngineers() {
        const select = document.getElementById('scheduler-assign-engineers');
        if (!select) return;

        // Same source as the chips above, so an option can never label an engineer
        // differently from the chip the scheduler just clicked.
        const filteredRows = getSchedulerFilteredAvailability();

        select.innerHTML = filteredRows.map(row => `
            <option value="${Number(row.engineer_id) || 0}">
                ${escapeHtml(row.name || 'Engineer')} â€” ${escapeHtml(row.branch || 'No branch')} â€” ${escapeHtml(schedulerAvailabilityLabel(row.loadLevel))}
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
        return rows.find(row => Number(row.id) === Number(shiftId)) || null;
    }

    function selectSchedulerActionShift(shiftId) {
        const row = findSchedulerActionShift(shiftId);
        schedulerSelectedShift = row;
        const hidden = document.getElementById('scheduler-selected-shift-id');
        if (hidden) hidden.value = row ? row.id : '';

        if (row) {
            setTextIfPresent('scheduler-selected-action-label', `${row.client || 'No client'} â€¢ ${row.date || ''} â€¢ ${row.task || ''} â€¢ ${row.priority_reason || ''}`);
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

        setTextIfPresent('count-my-active', myTasks.length);
        setTextIfPresent('count-my-upcoming', upcomingVisits);
        setTextIfPresent('count-my-continuation', continuationCount);
        setTextIfPresent('count-my-waiting', waitingCount);

        renderEngineerTodayPanel(myTasks, todayStart);
    }

    // "Needs you today" is derived entirely from tasks already loaded for the tables
    // below. It issues no requests of its own -- the point is to surface what matters
    // first, not to fetch more.
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

        if (overdue.length) {
            rows.push({
                accent: 'is-danger',
                title: overdue.length === 1 ? '1 visit is past its scheduled date' : `${overdue.length} visits are past their scheduled date`,
                hint: describe(overdue),
                action: 'Review'
            });
        }
        if (dueToday.length) {
            rows.push({
                accent: '',
                title: dueToday.length === 1 ? '1 visit scheduled today' : `${dueToday.length} visits scheduled today`,
                hint: describe(dueToday),
                action: 'Open'
            });
        }
        if (continuation.length) {
            rows.push({
                accent: 'is-warning',
                title: continuation.length === 1 ? '1 job is for continuation' : `${continuation.length} jobs are for continuation`,
                hint: describe(continuation),
                action: 'Continue'
            });
        }
        if (waiting.length) {
            rows.push({
                accent: 'is-warning',
                title: waiting.length === 1 ? '1 job is waiting on parts or P.O.' : `${waiting.length} jobs are waiting on parts or P.O.`,
                hint: describe(waiting),
                action: 'Check'
            });
        }

        if (!rows.length) {
            list.innerHTML = '<div class="dashboard-today-clear">'
                + '<i class="fa-solid fa-circle-check" aria-hidden="true"></i>'
                + '<span>Nothing needs your attention right now.</span>'
                + '</div>';
            return;
        }

        list.innerHTML = rows.map(row => (
            '<a class="dashboard-today-row" href="/timeline">'
            + `<span class="dashboard-today-accent ${row.accent}" aria-hidden="true"></span>`
            + '<span class="dashboard-today-body">'
            + `<span class="dashboard-today-title">${escapeHtml(row.title)}</span>`
            + `<span class="dashboard-today-hint">${escapeHtml(row.hint)}</span>`
            + '</span>'
            + `<span class="dashboard-today-action">${escapeHtml(row.action)} â†’</span>`
            + '</a>'
        )).join('');
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
            }

            // The recent-activity section and its 5-second poll used to be loaded here,
            // behind `adminView && !managerView` -- a condition no account can satisfy, so it
            // never ran. Retired with the hybrid ratification, and with them the whole feed
            // chain in this file: fetchActivityLog, renderMobileActivityList, getActivityMeta
            // and formatActivityText, all of which only that section reached.
            //
            // /activity_page is unaffected: templates/activity.html carries its own loader
            // against /get_activity_logs and never used any of the above. That does leave
            // /get_recent_activity without a caller -- noted for pending-work rather than
            // removed here, since retiring a route is a separate decision.

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

    function dashboardBootstrapStatusClass(status) {
        const value = String(status || '').toLowerCase();
        if (value.includes('waiting for p.o')) return 'bg-warning text-dark';
        if (value.includes('waiting for parts')) return 'bg-info text-dark';
        if (value.includes('continuation')) return 'bg-dark';
        return 'bg-primary';
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
        return `
            <div class="dashboard-mobile-task-card">
                <div class="dashboard-mobile-card-top">
                    <div>
                        <div class="dashboard-mobile-card-date">${escapeHtml(dashboardTaskDateLabel(task))}</div>
                        <div class="dashboard-mobile-card-title">${escapeHtml(task.client || 'No facility')}</div>
                    </div>
                    <span class="dashboard-mobile-status ${dashboardStatusClass(task.status)}">${escapeHtml(task.status || 'In Progress')}</span>
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
            </div>
        `;
    }

    function renderMobileTaskList(containerId, tasks, options = {}) {
        const container = document.getElementById(containerId);
        if(!container) return;

        if(!tasks || !tasks.length){
            container.innerHTML = '';
            return;
        }

        container.innerHTML = tasks.map(task => buildDashboardTaskMobileCard(task, options)).join('');
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

    /**
     * Personalization Logic.
     * Filters the dataset to show only tasks assigned to the current user.
     */
    function renderMyTasks() {
        const targetBody = document.getElementById('my-tasks-body');
        const emptyMsg = document.getElementById('no-my-tasks');

        if(!targetBody) return;

        const myTasks = getCurrentEngineerTasks();

        targetBody.innerHTML = "";

        if (myTasks.length === 0) {
            emptyMsg.classList.remove('d-none');
            renderMobileTaskList('my-tasks-mobile-list', []);
        } else {
            emptyMsg.classList.add('d-none');
            renderMobileTaskList('my-tasks-mobile-list', myTasks, { compact: true });

            targetBody.innerHTML = myTasks.map(task => `
                <tr class="small dashboard-my-task-row">
                    <td class="ps-4">
                        <div class="fw-bold text-primary">${escapeHtml(dashboardTaskDateLabel(task))}</div>
                    </td>
                    <td>
                        <strong>${escapeHtml(task.client || 'No facility')}</strong>
                    </td>
                    <td>
                        <div class="fw-bold text-dark">${escapeHtml(dashboardEquipmentLabel(task))}</div>
                        <div class="xsmall text-muted">Product / Serial</div>
                    </td>
                    <td class="text-muted">${escapeHtml(task.task || 'No task details')}</td>
                    <td class="text-end pe-4"><span class="badge ${dashboardBootstrapStatusClass(task.status)} shadow-none py-2 px-3 dashboard-task-badge">${escapeHtml(task.status || 'In Progress')}</span></td>
                </tr>`).join('');
        }
    }

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
                    let rangeLabel = startLabel === endLabel ? startLabel : `${startLabel} â†’ ${endLabel}`;
                    
                    mergedResults.push({
                        ...rStart,
                        display_range: rangeLabel,
                        raw_sort_date: rStart.task_date
                    });
                    
                    if (currentRec) sequenceBuffer = [currentRec];
                }
            }
        }
        return mergedResults;
    }

    function toggleSort() {
        const label = document.getElementById('sort-btn');

        if (currentSortMode === 'scheduled_latest') {
            currentSortMode = 'scheduled_oldest';
            label.innerHTML = '<i class="fa-solid fa-sort me-1"></i> Sort: Oldest Scheduled';
        } else if (currentSortMode === 'scheduled_oldest') {
            currentSortMode = 'created_latest';
            label.innerHTML = '<i class="fa-solid fa-sort me-1"></i> Sort: Latest Created';
        } else {
            currentSortMode = 'scheduled_latest';
            label.innerHTML = '<i class="fa-solid fa-sort me-1"></i> Sort: Latest Scheduled';
        }

        filterAndRender();
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
        let processedList = groupTasksByRange(allOpenTasksRaw);
        let filteredTasks = processedList.filter(t => !activeFilter || t.status === activeFilter);

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
            renderMobileTaskList('open-tasks-mobile-list', []);
        } else {
            document.getElementById('no-tasks-msg').classList.add('d-none');
            renderMobileTaskList('open-tasks-mobile-list', filteredTasks);

            targetBody.innerHTML = filteredTasks.map(task => {
                let statusCSS = "bg-primary";
                if (task.status === "Waiting for P.O") statusCSS = "bg-warning text-dark";
                else if (task.status === "Waiting for Parts") statusCSS = "bg-info";
                else if (task.status === "For Continuation") statusCSS = "bg-dark";

                return `
                    <tr class="small">
                        <td class="ps-4"><span class="fw-bold text-primary">${escapeHtml(task.display_range)}</span></td>
                        <td><strong>${escapeHtml(task.engineer)}</strong></td>
                        <td>${escapeHtml(task.client)}</td>
                        <td class="text-muted">${escapeHtml(task.task)}</td>
                        <td><span class="badge ${statusCSS} shadow-none py-2 px-3" style="font-size: 0.65rem;">${escapeHtml(task.status)}</span></td>
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
