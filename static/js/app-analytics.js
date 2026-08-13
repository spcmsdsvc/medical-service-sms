(function () {
    'use strict';

    const config = window.ANALYTICS_CAPABILITIES || {};
    const analyticsConfig = window.ANALYTICS_CONFIG || {};
    const systemStartDate = analyticsConfig.systemStartDate || '2026-05-18';
    const state = { schedule: null, purchaseOrders: null, equipment: null, loading: false };

    function byId(id) { return document.getElementById(id); }

    function setText(id, value) {
        const node = byId(id);
        if (node) node.textContent = value == null || value === '' ? '—' : String(value);
    }

    function clearNode(node) {
        if (node) node.replaceChildren();
    }

    function setError(message) {
        const node = byId('analytics-error');
        if (!node) return;
        node.textContent = message || '';
        node.hidden = !message;
    }

    function resetScheduleDisplay() {
        document.querySelectorAll('[data-schedule-value]').forEach((node) => { node.textContent = '—'; });
        ['trend-chart', 'branch-chart', 'category-chart', 'status-list', 'engineer-table-body', 'engineer-mobile-list'].forEach((id) => clearNode(byId(id)));
        ['trend-table-body', 'branch-table-body', 'category-table-body'].forEach((id) => clearNode(byId(id)));
        setText('schedule-scope-line', 'Schedule analytics is unavailable for this refresh.');
    }

    function resetPoDisplay() {
        state.equipment = null;
        ['equipment-machine-chart', 'equipment-model-chart', 'equipment-coverage-bars', 'equipment-unlinked-bars', 'equipment-machine-table-body', 'equipment-model-table-body', 'equipment-coverage-table-body', 'equipment-unlinked-table-body'].forEach((id) => clearNode(byId(id)));
        document.querySelectorAll('[data-equipment-value]').forEach((node) => { node.textContent = '\u2014'; });
        document.querySelectorAll('[data-po-value]').forEach((node) => { node.textContent = '—'; });
        ['po-type-bars', 'po-client-bars', 'po-month-bars', 'po-type-table-body', 'po-client-table-body', 'po-month-table-body'].forEach((id) => clearNode(byId(id)));
    }

    function resetAllNumbers() {
        resetScheduleDisplay();
        resetPoDisplay();
    }

    function formatDelta(current, previous) {
        if (previous == null) return null;
        const delta = Number(current || 0) - Number(previous || 0);
        if (!delta) return { text: 'No change from previous period', cls: 'is-flat', icon: 'fa-minus' };
        return delta > 0
            ? { text: `Up ${delta} vs previous period`, cls: 'is-up', icon: 'fa-arrow-up' }
            : { text: `Down ${Math.abs(delta)} vs previous period`, cls: 'is-down', icon: 'fa-arrow-down' };
    }

    // The chart's change column has room for a few characters, not a sentence. The long
    // form still reaches assistive tech and hover through the row's <title>.
    function compactDelta(current, previous) {
        if (previous == null) return null;
        const delta = Number(current || 0) - Number(previous || 0);
        if (!delta) return { text: '0', long: 'No change from previous period', cls: 'is-flat' };
        return delta > 0
            ? { text: `+${delta}`, long: `Up ${delta} vs previous period`, cls: 'is-up' }
            : { text: `−${Math.abs(delta)}`, long: `Down ${Math.abs(delta)} vs previous period`, cls: 'is-down' };
    }

    function renderMetric(id, metric, allowPrevious) {
        const value = metric && metric.value != null ? metric.value : 0;
        setText(id, value);
        const deltaNode = byId(`${id}-delta`);
        if (!deltaNode) return;
        deltaNode.replaceChildren();
        deltaNode.classList.remove('is-up', 'is-down', 'is-flat');
        if (!allowPrevious || !metric || metric.previous == null) return;
        const delta = formatDelta(value, metric.previous);
        if (!delta) return;
        const icon = document.createElement('i');
        icon.className = `fa-solid ${delta.icon}`;
        icon.setAttribute('aria-hidden', 'true');
        deltaNode.append(icon, document.createTextNode(` ${delta.text}`));
        deltaNode.classList.add(delta.cls);
    }

    function svgElement(name, attributes, text) {
        const node = document.createElementNS('http://www.w3.org/2000/svg', name);
        Object.entries(attributes || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
        if (text != null) node.textContent = String(text);
        return node;
    }

    function setSvgMeta(svg, title, description) {
        svg.setAttribute('role', 'img');
        const titleId = `${svg.id}-title`;
        const descId = `${svg.id}-desc`;
        const titleNode = svgElement('title', { id: titleId }, title);
        const descNode = svgElement('desc', { id: descId }, description);
        svg.setAttribute('aria-labelledby', `${titleId} ${descId}`);
        svg.append(titleNode, descNode);
    }

    // Charts are drawn at one user unit per CSS pixel, measured from the frame. The first
    // version shipped a fixed 640-unit viewBox scaled with preserveAspectRatio, which needed
    // `min-width: 560px` to stop <text> shrinking to ~6px on a phone -- and that min-width is
    // what made the frame scroll sideways at 375px with no affordance. Measuring instead means
    // the chart is never wider than its container, so there is nothing to scroll, and label
    // text stays at its declared size on every viewport.
    const CHART_MIN_WIDTH = 240;
    const CHART_HEIGHT = 210;

    function chartWidth(target) {
        if (!target) return CHART_MIN_WIDTH;
        const style = window.getComputedStyle(target);
        const padding = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
        return Math.max(CHART_MIN_WIDTH, Math.floor(target.clientWidth - padding));
    }

    function chartScaffold(id, title, description, height = CHART_HEIGHT) {
        const target = byId(id);
        if (!target) return null;
        clearNode(target);
        const width = chartWidth(target);
        // width/height attributes AND a matching viewBox: the viewBox alone would scale, which
        // is the behaviour being removed.
        const svg = svgElement('svg', { id: `${id}-svg`, width, height, viewBox: `0 0 ${width} ${height}` });
        setSvgMeta(svg, title, description);
        target.append(svg);
        return svg;
    }

    // SVG has no text-overflow, so a label that does not fit its column must be cut here. The
    // untruncated text still reaches the row's <title> and the hidden data table, so nothing
    // is actually lost -- 11px bold averages a shade over 6px per character.
    function truncateLabel(label, maxWidth) {
        const text = String(label == null ? '' : label);
        const maxChars = Math.max(3, Math.floor(maxWidth / 6.2));
        return text.length > maxChars ? `${text.slice(0, maxChars - 1)}…` : text;
    }

    function renderTrend(data) {
        const current = data && data.current ? data.current : [];
        const previous = data && data.previous ? data.previous : [];
        const svg = chartScaffold('trend-chart', 'Service activity trend', 'Current-period daily service volume compared with the immediately preceding period.');
        const table = byId('trend-table-body');
        clearNode(table);
        const rows = current.map((item, index) => ({ label: item.date, current: item.count, previous: previous[index] ? previous[index].count : 0 }));
        rows.forEach((row) => addTableRow(table, [row.label, row.current, row.previous]));
        if (!svg) return;
        const width = Number(svg.getAttribute('width'));
        if (!rows.length) {
            svg.append(svgElement('text', { x: width / 2, y: 110, 'text-anchor': 'middle', class: 'chart-muted' }, 'No trend data'));
            return;
        }
        const max = Math.max(1, ...rows.map((row) => Math.max(row.current, row.previous)));
        const chartHeight = 150;
        const left = 6;
        const plotWidth = Math.max(60, width - left - 6);
        const slot = plotWidth / rows.length;
        // A 31-day range cannot carry 31 date labels in 320px. Draw every nth instead of
        // letting them overlap into a grey smear; every row is in the table regardless.
        const labelStep = Math.max(1, Math.ceil(34 / slot));
        rows.forEach((row, index) => {
            const x = left + index * slot + Math.max(1, slot * 0.16);
            const barWidth = Math.max(2, slot * 0.27);
            const currentHeight = (row.current / max) * chartHeight;
            const previousHeight = (row.previous / max) * chartHeight;
            const group = svgElement('g', { class: 'analytics-chart-row' });
            group.append(
                svgElement('rect', { x, y: 170 - currentHeight, width: barWidth, height: currentHeight, rx: 2, class: 'chart-current' }),
                svgElement('rect', { x: x + barWidth + 1, y: 170 - previousHeight, width: barWidth, height: previousHeight, rx: 2, class: 'chart-previous' })
            );
            if (index % labelStep === 0) {
                group.append(svgElement(
                    'text',
                    { x: x + barWidth, y: 198, 'text-anchor': 'middle', class: 'chart-muted' },
                    row.label.slice(5)
                ));
            }
            // Every bar keeps its own tooltip even when its label was thinned out.
            group.append(svgElement('title', {}, `${row.label}: ${row.current} (previous period ${row.previous})`));
            svg.append(group);
        });
    }

    function renderHorizontalChart(chartId, tableId, rows, title, description) {
        const safeRows = Array.isArray(rows) ? rows.slice(0, 12) : [];
        const svg = chartScaffold(chartId, title, description);
        const table = byId(`${tableId}-body`);
        clearNode(table);
        safeRows.forEach((row) => addTableRow(table, [row.label, row.count, row.previous == null ? '—' : row.previous]));
        if (!svg) return;
        const width = Number(svg.getAttribute('width'));
        if (!safeRows.length) {
            svg.append(svgElement('text', { x: width / 2, y: 110, 'text-anchor': 'middle', class: 'chart-muted' }, 'No data'));
            return;
        }
        // Columns as fractions of the measured width. The count and the change each keep their
        // own column -- this chart used to be shadowed by a second, visible bar list that
        // existed only to carry the change figure, and folding it in here leaves one
        // representation of each dataset instead of two stacked copies.
        const hasDelta = safeRows.some((row) => row.previous != null);
        const labelWidth = Math.min(150, Math.max(72, Math.round(width * 0.28)));
        const deltaWidth = hasDelta ? 38 : 0;
        const countWidth = 30;
        const barLeft = labelWidth + 8;
        const barMax = Math.max(20, width - barLeft - countWidth - deltaWidth - 10);
        const countRight = barLeft + barMax + countWidth;
        const max = Math.max(1, ...safeRows.map((row) => Number(row.count) || 0));
        safeRows.forEach((row, index) => {
            const y = 18 + index * 15;
            const barWidth = Math.max(2, ((Number(row.count) || 0) / max) * barMax);
            const rowNode = svgElement('g', { class: 'analytics-chart-row' });
            rowNode.append(
                svgElement('text', { x: 4, y: y + 9, class: 'chart-muted' }, truncateLabel(row.label, labelWidth)),
                svgElement('rect', { x: barLeft, y, width: barWidth, height: 10, rx: 3, class: 'chart-current' }),
                svgElement('text', { x: countRight, y: y + 9, 'text-anchor': 'end' }, row.count)
            );
            const delta = row.previous == null ? null : compactDelta(row.count, row.previous);
            if (delta) {
                rowNode.append(svgElement(
                    'text',
                    { x: width - 4, y: y + 9, 'text-anchor': 'end', class: `chart-delta ${delta.cls}` },
                    delta.text
                ));
            }
            // Per-row tooltip, and the accessible long form of both the compact delta and any
            // label the column was too narrow to show in full. textContent, never an attribute
            // built from data.
            rowNode.append(svgElement(
                'title',
                {},
                delta
                    ? `${row.label}: ${row.count} (${delta.long})`
                    : `${row.label}: ${row.count}`
            ));
            svg.append(rowNode);
        });
    }

    function addTableRow(tbody, values) {
        if (!tbody) return;
        const tr = document.createElement('tr');
        values.forEach((value) => {
            const td = document.createElement('td');
            td.textContent = value == null ? '—' : String(value);
            tr.append(td);
        });
        tbody.append(tr);
    }

    function renderBars(targetId, rows) {
        const target = byId(targetId);
        clearNode(target);
        const safeRows = Array.isArray(rows) ? rows.slice(0, 12) : [];
        if (!target || !safeRows.length) {
            if (target) target.append(emptyMessage('No data in this range.'));
            return;
        }
        const max = Math.max(1, ...safeRows.map((row) => Number(row.count) || 0));
        safeRows.forEach((row) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'analytics-bar-row';
            const label = document.createElement('div');
            label.className = 'analytics-bar-label';
            label.title = row.label || '';
            label.textContent = row.label || 'Unlabelled';
            const track = document.createElement('div');
            track.className = 'analytics-bar-track';
            const fill = document.createElement('div');
            fill.className = 'analytics-bar-fill';
            fill.style.width = `${Math.max(2, ((Number(row.count) || 0) / max) * 100)}%`;
            track.append(fill);
            const value = document.createElement('strong');
            value.className = 'analytics-bar-value';
            value.textContent = String(row.count || 0);
            wrapper.append(label, track, value);
            if (row.previous != null) {
                const delta = document.createElement('span');
                delta.className = 'analytics-delta';
                const detail = formatDelta(row.count, row.previous);
                if (detail) {
                    delta.classList.add(detail.cls);
                    delta.textContent = detail.text;
                }
                wrapper.append(delta);
            }
            target.append(wrapper);
        });
    }

    function emptyMessage(message) {
        const node = document.createElement('div');
        node.className = 'analytics-empty';
        node.textContent = message;
        return node;
    }

    function renderStatusList(rows) {
        const target = byId('status-list');
        clearNode(target);
        if (!target || !rows || !rows.length) {
            if (target) target.append(emptyMessage('No open client work in this range.'));
            return;
        }
        rows.forEach((row) => {
            const item = document.createElement('div');
            item.className = 'analytics-status-row';
            const label = document.createElement('span');
            label.textContent = row.label || 'Unlabelled';
            const value = document.createElement('strong');
            value.textContent = String(row.count || 0);
            item.append(label, value);
            target.append(item);
        });
    }

    function workloadStatus(count) {
        if (count >= 10) return 'High';
        if (count >= 6) return 'Moderate';
        return 'Light';
    }

    function renderWorkload(engineers, total) {
        const body = byId('engineer-table-body');
        const mobile = byId('engineer-mobile-list');
        // "A filter labelled 5 must yield 5": say how many of how many, from the uncapped
        // total the endpoint computes before its slice, rather than a vague sentence.
        const caption = byId('workload-caption');
        if (caption) {
            const shown = Array.isArray(engineers) ? engineers.length : 0;
            const scoped = total == null ? shown : total;
            caption.textContent = scoped > shown
                ? `Showing the ${shown} busiest of ${scoped} scoped engineers.`
                : `Showing all ${scoped} scoped engineer${scoped === 1 ? '' : 's'}.`;
        }
        clearNode(body);
        clearNode(mobile);
        if (!engineers || !engineers.length) {
            if (body) addTableRow(body, ['No workload found.', '', '', '', '']);
            if (mobile) mobile.append(emptyMessage('No workload found.'));
            return;
        }
        engineers.forEach((engineer) => {
            addTableRow(body, [engineer.name, engineer.branch || 'Unassigned', engineer.count, engineer.active, engineer.completed]);
            if (!mobile) return;
            const card = document.createElement('div');
            card.className = 'analytics-mobile-engineer-card';
            const name = document.createElement('strong');
            name.textContent = engineer.name || 'Engineer';
            const branch = document.createElement('small');
            branch.textContent = `${engineer.branch || 'Unassigned'} · ${workloadStatus(Number(engineer.count || 0))}`;
            const stats = document.createElement('div');
            stats.className = 'analytics-mobile-engineer-stats';
            [['Total', engineer.count], ['Active', engineer.active], ['Completed', engineer.completed]].forEach(([label, value]) => {
                const stat = document.createElement('span');
                stat.textContent = label;
                const strong = document.createElement('b');
                strong.textContent = String(value || 0);
                stat.append(strong);
                stats.append(stat);
            });
            card.append(name, branch, stats);
            mobile.append(card);
        });
    }

    const CHART_FRAME_IDS = ['trend-chart', 'branch-chart', 'category-chart', 'equipment-machine-chart', 'equipment-model-chart'];
    const lastChartWidths = {};

    function renderScheduleCharts(data) {
        if (!data) return;
        renderTrend(data.trend);
        renderHorizontalChart('branch-chart', 'branch-table', data.branches, 'Branch concentration', 'Scoped schedule assignments by engineer branch.');
        renderHorizontalChart('category-chart', 'category-table', data.categories, 'Service mix', 'Schedule categories in the selected period.');
        CHART_FRAME_IDS.slice(0, 3).forEach((id) => {
            const node = byId(id);
            if (node && node.clientWidth > 0) lastChartWidths[id] = chartWidth(node);
        });
    }

    function renderEquipmentCharts(data) {
        const equipment = data && data.equipment;
        if (!equipment) return;
        renderHorizontalChart('equipment-machine-chart', 'equipment-machine-table', equipment.by_machine, 'Top machines', 'Machine-linked purchase order counts by serial and model.');
        renderHorizontalChart('equipment-model-chart', 'equipment-model-table', equipment.by_model, 'Equipment models', 'Machine-linked purchase order counts by model.');
        CHART_FRAME_IDS.slice(3).forEach((id) => {
            const node = byId(id);
            if (node && node.clientWidth > 0) lastChartWidths[id] = chartWidth(node);
        });
    }

    // Charts are sized from their container, so a resize has to redraw them. Two guards, both
    // load-bearing: only an INTEGER width change redraws (a sub-pixel reflow would otherwise
    // trip the observer from inside its own callback), and nothing here ever writes to the
    // container's width -- a chart that sets the width it measures is an infinite loop.
    let resizeTimer = null;

    function observeChartResize() {
        if (typeof ResizeObserver === 'undefined') return;
        const observer = new ResizeObserver(() => {
            const changed = CHART_FRAME_IDS.some((id) => {
                const node = byId(id);
                if (!node || node.clientWidth === 0) return false;
                return lastChartWidths[id] !== chartWidth(node);
            });
            if (!changed) return;
            window.clearTimeout(resizeTimer);
            resizeTimer = window.setTimeout(() => {
                if (state.schedule) renderScheduleCharts(state.schedule);
                if (state.purchaseOrders) renderEquipmentCharts(state.purchaseOrders);
            }, 100);
        });
        CHART_FRAME_IDS.forEach((id) => {
            const node = byId(id);
            if (node) observer.observe(node);
        });
    }

    function updateSchedule(data) {
        state.schedule = data;
        // Arrows come from the payload shape: flow metrics carry `previous`, stock metrics
        // carry `basis` and never a comparison. See the note on the endpoint for why
        // `active` cannot have one -- it is exactly `total - completed`.
        const flow = data.flow || {};
        const stock = data.stock || {};
        renderMetric('schedule-total', flow.total, true);
        renderMetric('schedule-active', stock.active, false);
        renderMetric('schedule-open', stock.open_client_work, false);
        renderMetric('schedule-completed', stock.completed, false);
        renderScheduleCharts(data);
        renderStatusList(data.open_statuses);
        renderWorkload(data.engineers, data.engineer_total);
        const line = byId('schedule-scope-line');
        if (line) line.textContent = `Schedule range: ${data.range.start_date} to ${data.range.end_date} · ${data.branch_label || 'All Branches'} · ${data.range_total} schedules · ${data.assignment_total} assignments · Previous period: ${data.previous_range.start_date} to ${data.previous_range.end_date}`;
    }

    function updatePo(data) {
        state.purchaseOrders = data;
        state.equipment = data.equipment || null;
        setText('po-total', data.total);
        const note = byId('po-scope-line');
        if (note) note.textContent = `${data.scope_label || 'Company-wide'} · ${data.range.start_date} to ${data.range.end_date} · counts only; no money values are shown.`;
        renderBars('po-type-bars', data.by_type);
        renderBars('po-client-bars', data.by_client);
        renderBars('po-month-bars', data.by_month);
        renderSimpleTable('po-type-table-body', data.by_type);
        renderSimpleTable('po-client-table-body', data.by_client);
        renderSimpleTable('po-month-table-body', data.by_month);
        renderEquipment(data);
    }

    function renderEquipment(data) {
        const equipment = data && data.equipment ? data.equipment : {};
        setText('equipment-linked-total', equipment.linked_total);
        setText('equipment-unlinked-total', equipment.unlinked_total);
        setText('equipment-linked-pct', equipment.linked_pct == null ? null : `${equipment.linked_pct}%`);
        setText('equipment-machine-total', equipment.machine_total);
        setText('equipment-machine-link-total', equipment.machine_link_total);
        const scope = byId('equipment-scope-line');
        if (scope && data && data.range) scope.textContent = `${data.scope_label || 'Company-wide'} \u00b7 ${data.range.start_date} to ${data.range.end_date} \u00b7 counts only; no money values are shown.`;
        renderBars('equipment-coverage-bars', equipment.by_coverage);
        renderBars('equipment-unlinked-bars', equipment.unlinked_clients);
        renderSimpleTable('equipment-coverage-table-body', equipment.by_coverage);
        renderSimpleTable('equipment-unlinked-table-body', equipment.unlinked_clients);
        renderEquipmentCharts(data);
    }

    function renderSimpleTable(tbodyId, rows) {
        const body = byId(tbodyId);
        clearNode(body);
        (rows || []).forEach((row) => addTableRow(body, [row.label, row.count]));
    }

    function activateTab(tabId, moveFocus) {
        const buttons = Array.from(document.querySelectorAll('[data-analytics-tab]'));
        if (!buttons.length) return;
        const activeButton = buttons.find((button) => button.dataset.analyticsTab === tabId) || buttons[0];
        const activeId = activeButton.dataset.analyticsTab;
        buttons.forEach((button) => {
            const isActive = button === activeButton;
            button.classList.toggle('is-active', isActive);
            button.setAttribute('aria-selected', isActive ? 'true' : 'false');
            button.setAttribute('tabindex', isActive ? '0' : '-1');
        });
        document.querySelectorAll('[data-analytics-panel]').forEach((panel) => {
            const isActive = panel.dataset.analyticsPanel === activeId;
            panel.classList.toggle('is-active', isActive);
            panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
        });
        try { window.localStorage.setItem('medical-service-analytics-tab', activeId); } catch (error) { /* storage may be unavailable */ }
        if (activeId === 'schedule' && state.schedule) renderScheduleCharts(state.schedule);
        if (activeId === 'equipment' && state.purchaseOrders) renderEquipmentCharts(state.purchaseOrders);
        if (moveFocus) activeButton.focus();
    }

    function initAnalyticsTabs() {
        const buttons = Array.from(document.querySelectorAll('[data-analytics-tab]'));
        if (!buttons.length) return;
        buttons.forEach((button, index) => {
            button.addEventListener('click', () => activateTab(button.dataset.analyticsTab, false));
            button.addEventListener('keydown', (event) => {
                let nextIndex = null;
                if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nextIndex = (index + 1) % buttons.length;
                if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nextIndex = (index - 1 + buttons.length) % buttons.length;
                if (event.key === 'Home') nextIndex = 0;
                if (event.key === 'End') nextIndex = buttons.length - 1;
                if (nextIndex == null) return;
                event.preventDefault();
                activateTab(buttons[nextIndex].dataset.analyticsTab, true);
            });
        });
        let storedTab = '';
        try { storedTab = window.localStorage.getItem('medical-service-analytics-tab') || ''; } catch (error) { /* storage may be unavailable */ }
        const validStoredTab = buttons.some((button) => button.dataset.analyticsTab === storedTab);
        const serverTab = buttons.find((button) => button.getAttribute('aria-selected') === 'true');
        activateTab(validStoredTab ? storedTab : (serverTab ? serverTab.dataset.analyticsTab : buttons[0].dataset.analyticsTab), false);
    }

    function queryString() {
        const params = new URLSearchParams();
        const start = byId('analytics-start');
        const end = byId('analytics-end');
        const branch = byId('analytics-branch');
        if (start && start.value) params.set('start_date', start.value);
        if (end && end.value) params.set('end_date', end.value);
        if (branch && branch.value) params.set('branch', branch.value);
        return params.toString();
    }

    window.exportAnalyticsCSV = function () {
        if (config.schedule) window.location.href = `/export_analytics_summary?${queryString()}`;
    };

    function describeFailure(failure) {
        const label = failure.type === 'purchaseOrders' ? 'Purchase order reporting' : 'Schedule analytics';
        const raw = (failure.error && failure.error.message) || '';
        // A TypeError from fetch means the request never reached the server.
        if (!raw || /failed to fetch|networkerror|load failed/i.test(raw)) {
            return `${label} could not be loaded. Check your connection and try again.`;
        }
        return `${label}: ${raw}`;
    }

    async function fetchJson(url) {
        const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.message || `Request failed (${response.status})`);
        return data;
    }

    window.loadAnalytics = async function () {
        if (state.loading) return;
        state.loading = true;
        setError('');
        try {
            const query = queryString();
            const tasks = [];
            if (config.schedule) tasks.push(fetchJson(`/get_analytics_summary?${query}`).then(updateSchedule).catch((error) => ({ type: 'schedule', error })));
            if (config.purchaseOrders) tasks.push(fetchJson(`/get_po_analytics?${query}`).then(updatePo).catch((error) => ({ type: 'purchaseOrders', error })));
            const results = await Promise.all(tasks);
            const failures = results.filter((result) => result && result.error);
            failures.forEach((failure) => failure.type === 'schedule' ? resetScheduleDisplay() : resetPoDisplay());
            // failure.error.message is a JS internal ("Failed to fetch") for a dropped
            // connection, which tells a manager nothing. Surface the server's own message
            // when there is one, and a plain sentence when the request never arrived.
            if (failures.length) setError(failures.map(describeFailure).join(' '));
            const stamp = byId('analytics-last-loaded');
            if (stamp && !failures.length) stamp.textContent = `Updated ${new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
        } finally {
            state.loading = false;
        }
    };

    function setRangePreset(mode) {
        const now = new Date();
        const start = new Date(now);
        const end = new Date(now);
        if (mode === 'all') {
            const systemStart = new Date(`${systemStartDate}T00:00:00`);
            if (!Number.isNaN(systemStart.getTime())) {
                start.setTime(systemStart.getTime());
            } else {
                start.setDate(1);
            }
        } else if (mode === 'week') {
            const mondayOffset = (now.getDay() + 6) % 7;
            start.setDate(now.getDate() - mondayOffset);
            end.setTime(start.getTime());
            end.setDate(start.getDate() + 6);
        } else {
            start.setDate(1);
        }
        const toValue = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
        byId('analytics-start').value = toValue(start);
        byId('analytics-end').value = toValue(end);
        window.loadAnalytics();
    }

    document.addEventListener('DOMContentLoaded', () => {
        const form = byId('analytics-filter-form');
        if (form) form.addEventListener('submit', (event) => { event.preventDefault(); window.loadAnalytics(); });
        document.querySelectorAll('[data-analytics-preset]').forEach((button) => button.addEventListener('click', () => setRangePreset(button.dataset.analyticsPreset)));
        initAnalyticsTabs();
        observeChartResize();
        setRangePreset('all');
    });
}());
