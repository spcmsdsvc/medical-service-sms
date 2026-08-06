(function () {
    'use strict';

    const config = window.ANALYTICS_CAPABILITIES || {};
    const state = { schedule: null, purchaseOrders: null, loading: false };

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
        ['trend-chart', 'branch-chart', 'category-chart', 'branch-bars', 'category-bars', 'status-list', 'engineer-table-body', 'engineer-mobile-list'].forEach((id) => clearNode(byId(id)));
        ['trend-table-body', 'branch-table-body', 'category-table-body'].forEach((id) => clearNode(byId(id)));
        setText('schedule-scope-line', 'Schedule analytics is unavailable for this refresh.');
    }

    function resetPoDisplay() {
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

    function chartScaffold(id, title, description, width = 640, height = 210) {
        const target = byId(id);
        if (!target) return null;
        clearNode(target);
        const svg = svgElement('svg', { id: `${id}-svg`, viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: 'xMidYMid meet' });
        setSvgMeta(svg, title, description);
        target.append(svg);
        return svg;
    }

    function renderTrend(data) {
        const current = data && data.current ? data.current : [];
        const previous = data && data.previous ? data.previous : [];
        const svg = chartScaffold('trend-chart', 'Service activity trend', 'Current-period daily service volume compared with the immediately preceding period.')
            || null;
        const table = byId('trend-table-body');
        clearNode(table);
        const rows = current.map((item, index) => ({ label: item.date, current: item.count, previous: previous[index] ? previous[index].count : 0 }));
        rows.forEach((row) => addTableRow(table, [row.label, row.current, row.previous]));
        if (!svg) return;
        if (!rows.length) {
            svg.append(svgElement('text', { x: 320, y: 110, 'text-anchor': 'middle', class: 'chart-muted' }, 'No trend data'));
            return;
        }
        const max = Math.max(1, ...rows.map((row) => Math.max(row.current, row.previous)));
        const chartHeight = 150;
        const left = 28;
        const bottom = 30;
        const slot = 590 / rows.length;
        rows.forEach((row, index) => {
            const x = left + index * slot + Math.max(2, slot * 0.16);
            const barWidth = Math.max(4, slot * 0.27);
            const currentHeight = (row.current / max) * chartHeight;
            const previousHeight = (row.previous / max) * chartHeight;
            svg.append(
                svgElement('rect', { x, y: 170 - currentHeight, width: barWidth, height: currentHeight, rx: 3, class: 'chart-current' }),
                svgElement('rect', { x: x + barWidth + 2, y: 170 - previousHeight, width: barWidth, height: previousHeight, rx: 3, class: 'chart-previous' }),
                svgElement('text', { x: x + barWidth, y: 198, 'text-anchor': 'middle', class: 'chart-muted' }, row.label.slice(5))
            );
        });
    }

    function renderHorizontalChart(chartId, tableId, rows, title, description) {
        const safeRows = Array.isArray(rows) ? rows.slice(0, 12) : [];
        const svg = chartScaffold(chartId, title, description);
        const table = byId(`${tableId}-body`);
        clearNode(table);
        safeRows.forEach((row) => addTableRow(table, [row.label, row.count, row.previous == null ? '—' : row.previous]));
        if (!svg) return;
        if (!safeRows.length) {
            svg.append(svgElement('text', { x: 320, y: 110, 'text-anchor': 'middle', class: 'chart-muted' }, 'No data'));
            return;
        }
        const max = Math.max(1, ...safeRows.map((row) => Number(row.count) || 0));
        safeRows.forEach((row, index) => {
            const y = 18 + index * 15;
            const width = Math.max(2, ((Number(row.count) || 0) / max) * 430);
            svg.append(
                svgElement('text', { x: 4, y: y + 9, class: 'chart-muted' }, row.label),
                svgElement('rect', { x: 178, y, width, height: 10, rx: 3, class: 'chart-current' }),
                svgElement('text', { x: 620, y: y + 9, 'text-anchor': 'end' }, row.count)
            );
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

    function renderWorkload(engineers) {
        const body = byId('engineer-table-body');
        const mobile = byId('engineer-mobile-list');
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

    function updateSchedule(data) {
        state.schedule = data;
        const flow = data.flow || {};
        renderMetric('schedule-total', flow.total, true);
        renderMetric('schedule-active', flow.active, true);
        renderMetric('schedule-open', flow.open_client_work, true);
        renderMetric('schedule-completed', flow.completed, false);
        renderTrend(data.trend);
        renderHorizontalChart('branch-chart', 'branch-table', data.branches, 'Branch concentration', 'Scoped schedule assignments by engineer branch.');
        renderHorizontalChart('category-chart', 'category-table', data.categories, 'Service mix', 'Schedule categories in the selected period.');
        renderBars('branch-bars', data.branches);
        renderBars('category-bars', data.categories);
        renderStatusList(data.open_statuses);
        renderWorkload(data.engineers);
        const line = byId('schedule-scope-line');
        if (line) line.textContent = `Schedule range: ${data.range.start_date} to ${data.range.end_date} · ${data.branch_label || 'All Branches'} · ${data.range_total} schedules · ${data.assignment_total} assignments · Previous period: ${data.previous_range.start_date} to ${data.previous_range.end_date}`;
    }

    function updatePo(data) {
        state.purchaseOrders = data;
        setText('po-total', data.total);
        const note = byId('po-scope-line');
        if (note) note.textContent = `${data.scope_label || 'Company-wide'} · ${data.range.start_date} to ${data.range.end_date} · counts only; no money values are shown.`;
        renderBars('po-type-bars', data.by_type);
        renderBars('po-client-bars', data.by_client);
        renderBars('po-month-bars', data.by_month);
        renderSimpleTable('po-type-table-body', data.by_type);
        renderSimpleTable('po-client-table-body', data.by_client);
        renderSimpleTable('po-month-table-body', data.by_month);
    }

    function renderSimpleTable(tbodyId, rows) {
        const body = byId(tbodyId);
        clearNode(body);
        (rows || []).forEach((row) => addTableRow(body, [row.label, row.count]));
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
            if (failures.length) setError(failures.map((failure) => failure.error.message).join(' '));
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
        if (mode === 'week') {
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
        setRangePreset('month');
    });
}());
