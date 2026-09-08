"""Focused source contracts for the Reimbursement page design package."""

import json
import pathlib
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
RELEASES = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))


class ReimbursementDesignSourceTests(unittest.TestCase):
    def test_existing_worksheet_controls_remain_present(self):
        for token in (
            'id="reimStartDate"',
            'id="reimEndDate"',
            'id="reimExpenseTable"',
            'id="reimGrandTotal"',
            'saveReimbursementDraft()',
            'submitReimbursement()',
            'loadReimbursementRows()',
            'recalculateReimbursementTotals()',
        ):
            self.assertIn(token, TEMPLATE)

    def test_active_workspace_precedes_history_and_notifications(self):
        filter_position = TEMPLATE.index('id="reimStartDate"')
        worksheet_position = TEMPLATE.index('id="reimExpenseTable"')
        notifications_position = TEMPLATE.index('id="reimNotificationCard"')
        history_position = TEMPLATE.index('id="reimStatusWindowCard"')

        self.assertLess(filter_position, worksheet_position)
        self.assertLess(worksheet_position, notifications_position)
        self.assertLess(worksheet_position, history_position)

    def test_actions_and_remarks_have_explicit_compact_columns(self):
        self.assertNotIn('.reim-table th:last-child', TEMPLATE)
        self.assertNotIn('.reim-table td:last-child', TEMPLATE)
        self.assertIn('.reim-table th:nth-child(15)', TEMPLATE)
        self.assertIn('.reim-table td:nth-child(15)', TEMPLATE)
        self.assertRegex(TEMPLATE, r'\.reim-table th:nth-child\(15\)[\s\S]{0,300}min-width:\s*390px')
        self.assertIn('.reim-row-actions', TEMPLATE)
        self.assertNotIn('min-width: 64px;', TEMPLATE)

    def test_action_hierarchy_and_destructive_group_are_explicit(self):
        self.assertRegex(TEMPLATE, r'class="reim-btn reim-btn-primary"[^>]+id="reimSubmitBtn"')
        self.assertRegex(TEMPLATE, r'class="reim-btn reim-btn-secondary"[^>]+id="reimSaveDraftBtn"')
        self.assertRegex(TEMPLATE, r'class="reim-btn reim-btn-download"[^>]+id="reimDownloadExcelBtn"')
        group_start = TEMPLATE.index('class="reim-destructive-actions"')
        group_end = TEMPLATE.index('</div>', group_start)
        group = TEMPLATE[group_start:group_end]
        self.assertIn('id="reimDeleteDraftBtn"', group)
        self.assertIn('id="reimClearBtn"', group)
        self.assertIn('.reim-btn-download {', TEMPLATE)
        self.assertIn('var(--app-surface-muted', TEMPLATE)

    def test_remarks_start_compact_and_remain_resizable(self):
        self.assertGreaterEqual(TEMPLATE.count('class="reim-remarks" rows="3"'), 2)
        self.assertIn('min-height: 72px;', TEMPLATE)
        self.assertIn('resize: vertical;', TEMPLATE)
        self.assertIn('.reim-mobile-card .reim-remarks', TEMPLATE)

    def test_worksheet_group_boundaries_numeric_style_and_focus_row_exist(self):
        for column in (4, 14, 15):
            self.assertRegex(
                TEMPLATE,
                rf'\.reim-table :is\(th, td\):nth-child\({column}\)[\s\S]{{0,220}}border-left:',
            )
        self.assertIn('font-variant-numeric: tabular-nums;', TEMPLATE)
        self.assertIn('.reim-table tbody tr:focus-within td', TEMPLATE)
        self.assertIn('.reim-amount:focus-visible', TEMPLATE)

    def test_summary_markup_is_above_the_worksheet_and_has_required_values(self):
        summary_position = TEMPLATE.find('id="reimWorksheetSummary"')
        table_position = TEMPLATE.index('id="reimTableWrap"')
        self.assertGreaterEqual(summary_position, 0)
        self.assertLess(summary_position, table_position)
        self.assertIn('id="reimSummaryDateRange"', TEMPLATE)
        self.assertIn('id="reimSummaryRowCount"', TEMPLATE)
        self.assertIn('id="reimSummaryGrandTotal"', TEMPLATE)
        self.assertIn('Date range', TEMPLATE)
        self.assertIn('Active rows', TEMPLATE)
        self.assertIn('Claim total', TEMPLATE)

    def test_summary_uses_existing_displayed_grand_total_and_current_rows(self):
        self.assertIn('function syncReimbursementWorksheetSummary()', TEMPLATE)
        helper_start = TEMPLATE.index('function syncReimbursementWorksheetSummary()')
        helper_end = TEMPLATE.index('function formatExpenseDate(value)', helper_start)
        helper = TEMPLATE[helper_start:helper_end]
        self.assertIn("getElementById('reimGrandTotal')", helper)
        self.assertIn('.textContent', helper)
        self.assertIn('currentReimbursementRows.length', helper)
        self.assertIn("getElementById('reimStartDate')", helper)
        self.assertIn("getElementById('reimEndDate')", helper)

        recalc_start = TEMPLATE.index('function recalculateReimbursementTotals()')
        recalc_end = TEMPLATE.index('function buildMobileExpenseInputs(row)', recalc_start)
        self.assertIn('syncReimbursementWorksheetSummary();', TEMPLATE[recalc_start:recalc_end])
        summary_apply_start = TEMPLATE.index('function applyReimbursementTotalSummary(payload)')
        summary_apply_end = TEMPLATE.index('function reimbursementServerTotalLabel(summary)', summary_apply_start)
        self.assertIn('syncReimbursementWorksheetSummary();', TEMPLATE[summary_apply_start:summary_apply_end])

    def test_summary_has_date_change_and_render_update_hooks(self):
        self.assertIn('syncReimbursementWorksheetSummary();', TEMPLATE[TEMPLATE.index('function renderReimbursementRows(rows)'):])
        dom_start = TEMPLATE.index("document.addEventListener('DOMContentLoaded'")
        dom_end = TEMPLATE.index('\n    });', dom_start) + len('\n    });')
        dom_block = TEMPLATE[dom_start:dom_end]
        self.assertIn("reimStartDate', 'reimEndDate", dom_block)
        self.assertIn("addEventListener('change'", dom_block)

    def test_visual_hierarchy_uses_theme_neutral_surfaces_and_semibold_headings(self):
        self.assertRegex(
            TEMPLATE,
            r'\.reim-page\s*:is\(h1,\s*h2,\s*h3,\s*h4\)\s*\{[\s\S]{0,260}font-weight:\s*600',
        )
        self.assertRegex(
            TEMPLATE,
            r'\.reim-page\s*:is\([^}]*\.reim-hero[^}]*\)\s*\{[\s\S]{0,420}background:\s*var\(--app-surface',
        )
        self.assertIn('box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);', TEMPLATE)
        self.assertRegex(
            TEMPLATE,
            r'\.reim-page\s*:is\([^}]*\.reim-muted[^}]*\)\s*\{[\s\S]{0,300}font-weight:\s*400',
        )
        self.assertIn('var(--app-border', TEMPLATE)

    def test_mobile_cards_put_expenses_and_total_before_remarks(self):
        helper_start = TEMPLATE.index('function buildMobileExpenseInputs(row)')
        helper_end = TEMPLATE.index('function formatExpenseDate(value)', helper_start)
        helper = TEMPLATE[helper_start:helper_end]
        self.assertLess(helper.index('class="reim-mobile-expense-grid"'), helper.index('class="reim-mobile-total"'))

        mobile_start = TEMPLATE.index('mobile.innerHTML = rows.map(function(row)')
        mobile_end = TEMPLATE.index("        }).join('');", mobile_start)
        mobile_block = TEMPLATE[mobile_start:mobile_end]
        identity_position = min(mobile_block.index('row.client'), mobile_block.index('row.task'))
        expense_position = mobile_block.index('${buildMobileExpenseInputs(row)}')
        remarks_position = mobile_block.index('<textarea class="reim-remarks"')
        self.assertLess(identity_position, expense_position)
        self.assertLess(expense_position, remarks_position)
        for key in (
            'representation', 'car_repair', 'toll_fee', 'gasoline', 'transpo',
            'office_supplies', 'parking', 'per_diem', 'coding', 'others',
        ):
            self.assertIn(key, helper)
        self.assertIn('rows="3"', mobile_block)

    def test_history_cards_have_distinct_amount_metadata_remarks_and_actions_regions(self):
        render_start = TEMPLATE.index('function renderMyReimbursementStatuses(items)')
        render_end = TEMPLATE.index('\n    async function loadMyReimbursementStatuses()', render_start)
        render_block = TEMPLATE[render_start:render_end]
        for token in (
            'reim-status-window-period',
            'reim-status-window-amount',
            'reim-status-window-meta',
            'reim-status-window-remarks',
            'reim-status-window-actions',
        ):
            self.assertIn(token, render_block)
        title_position = render_block.index('reim-status-window-title')
        period_position = render_block.index('reim-status-window-period')
        amount_position = render_block.index('reim-status-window-amount')
        meta_position = render_block.index('reim-status-window-meta')
        remarks_position = render_block.index('reim-status-window-remarks')
        actions_position = render_block.index('reim-status-window-actions')
        self.assertLess(title_position, period_position)
        self.assertLess(period_position, amount_position)
        self.assertLess(amount_position, meta_position)
        self.assertLess(meta_position, remarks_position)
        self.assertLess(remarks_position, actions_position)
        self.assertIn('reimEscape(remarks)', render_block)
        self.assertIn('openReimbursementStatusRecord(', render_block)
        self.assertIn('openRequestRecall(', render_block)
        self.assertRegex(
            TEMPLATE,
            r'\.reim-status-window-actions\s*\{[\s\S]{0,300}align-items:\s*center[\s\S]{0,300}gap:',
        )

    def test_reimbursement_interaction_styling_is_scoped_and_mobile_targets_are_touch_sized(self):
        self.assertRegex(
            TEMPLATE,
            r'\.reim-page\s*:is\([\s\S]{0,260}\.reim-row-delete-btn,[\s\S]{0,120}\.reim-toast-close\s*\):focus-visible',
        )
        self.assertIn('outline: 3px solid var(--app-focus', TEMPLATE)
        self.assertIn('.reim-page.reim-locked .reim-locked-field', TEMPLATE)
        self.assertIn('border: 1px dashed var(--app-border', TEMPLATE)
        self.assertIn('.reim-page:not(.reim-locked) .reim-amount', TEMPLATE)
        mobile_start = TEMPLATE.rindex('@media (max-width: 820px)')
        mobile_end = TEMPLATE.index('</style>', mobile_start)
        mobile_css = TEMPLATE[mobile_start:mobile_end]
        self.assertIn('min-height: 44px;', mobile_css)
        self.assertIn('width: 44px;', mobile_css)
        self.assertIn('height: 44px;', mobile_css)

    def test_reimbursement_design_cache_and_release_record(self):
        self.assertIn('medical-service-pwa-offline-navigation-v146-tsr-signature-finalization', APP_SOURCE)
        matches = [
            release for release in RELEASES.get('releases', [])
            if release.get('release_key') == '2026-09-05-reimbursement-design'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('is_published'))
        self.assertTrue(any(item.get('category') == 'Reimbursement' for item in matches[0].get('items', [])))

    def test_reimbursement_design_polish_release_record(self):
        matches = [
            release for release in RELEASES.get('releases', [])
            if release.get('release_key') == '2026-09-05-reimbursement-design-polish'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('is_published'))
        self.assertTrue(any(item.get('category') == 'Reimbursement' for item in matches[0].get('items', [])))

    def test_column_view_control_has_exact_desktop_choices(self):
        control_start = TEMPLATE.index('class="reim-column-view-control"')
        control_end = TEMPLATE.index('</div>', control_start)
        control = TEMPLATE[control_start:control_end]
        self.assertIn('Schedule columns', control)
        self.assertIn('id="reimColumnView"', control)
        for value, label in (
            ('pinned', 'Pinned'),
            ('unpinned', 'Unpinned'),
            ('compact', 'Compact'),
        ):
            self.assertRegex(control, rf'<option value="{value}"[^>]*>{label}</option>')
        self.assertIn('reim-column-view-control', TEMPLATE)
        self.assertRegex(
            TEMPLATE,
            r'@media \(max-width: 820px\)[\s\S]{0,1200}\.reim-column-view-control\s*\{[\s\S]{0,120}display:\s*none',
        )

    def test_column_view_preference_defaults_and_guards_storage(self):
        self.assertIn("const REIMBURSEMENT_COLUMN_VIEW_KEY = 'reimbursementColumnView';", TEMPLATE)
        self.assertIn("'pinned', 'unpinned', 'compact'", TEMPLATE)
        normalize_start = TEMPLATE.index('function normalizeReimbursementColumnView(')
        normalize_end = TEMPLATE.index('\n    function ', normalize_start + 10)
        normalize = TEMPLATE[normalize_start:normalize_end]
        self.assertIn("return 'pinned';", normalize)
        read_start = TEMPLATE.index('function readReimbursementColumnViewPreference()')
        read_end = TEMPLATE.index('\n    function ', read_start + 10)
        read = TEMPLATE[read_start:read_end]
        self.assertIn('try', read)
        self.assertIn('localStorage.getItem(REIMBURSEMENT_COLUMN_VIEW_KEY)', read)
        self.assertIn('catch', read)
        write_start = TEMPLATE.index('function writeReimbursementColumnViewPreference(')
        write_end = TEMPLATE.index('\n    function ', write_start + 10)
        write = TEMPLATE[write_start:write_end]
        self.assertIn('localStorage.setItem(REIMBURSEMENT_COLUMN_VIEW_KEY', write)
        self.assertIn('catch', write)

    def test_column_view_switch_uses_classes_without_rerendering_rows(self):
        start = TEMPLATE.index('function applyReimbursementColumnView(')
        end = TEMPLATE.index('\n    function ', start + 10)
        controller = TEMPLATE[start:end]
        self.assertIn('classList.remove', controller)
        self.assertIn('classList.add', controller)
        self.assertIn('reim-columns-pinned', controller)
        self.assertIn('reim-columns-unpinned', controller)
        self.assertIn('reim-columns-compact', controller)
        self.assertNotIn('renderReimbursementRows(', controller)
        self.assertIn('syncReimbursementHorizontalScroll();', controller)
        self.assertIn('reimColumnView', controller)

    def test_column_view_css_preserves_vertical_sticky_and_targets_context_columns(self):
        css_start = TEMPLATE.index('/* Reimbursement column view controls')
        css = TEMPLATE[css_start:TEMPLATE.index('</style>', css_start)]
        self.assertIn('.reim-table.reim-columns-unpinned', css)
        self.assertIn('position: static;', css)
        self.assertIn('.reim-table.reim-columns-compact', css)
        self.assertIn('display: none;', css)
        self.assertIn('.reim-table.reim-columns-compact :is(thead th, tbody td):nth-child(1)', css)
        self.assertIn('position: sticky;', css)
        self.assertIn('tfoot td:nth-child(1)', css)
        self.assertIn('tfoot td:nth-child(2)', css)
        self.assertIn('tfoot td:nth-child(3)', css)

    def test_footer_has_explicit_identity_cells_for_each_column_view(self):
        footer_start = TEMPLATE.index('<tfoot id="reimTotalsFoot">')
        footer_end = TEMPLATE.index('</tfoot>', footer_start)
        footer = TEMPLATE[footer_start:footer_end]
        self.assertNotIn('colspan="3"', footer)
        for token in (
            'reim-total-date-cell',
            'reim-total-schedule-cell',
            'reim-total-client-cell',
            'data-total-expense="representation"',
            'data-total-expense="others"',
            'id="reimGrandTotal"',
        ):
            self.assertIn(token, footer)

    def test_compact_rows_offer_escaped_keyboard_accessible_details(self):
        self.assertIn('class="reim-row-details-btn"', TEMPLATE)
        self.assertIn('View details', TEMPLATE)
        details_start = TEMPLATE.index('id="reim-row-details-backdrop"')
        details_end = TEMPLATE.index('</div>', details_start)
        details_markup = TEMPLATE[details_start:details_end]
        self.assertIn('role="dialog"', details_markup)
        self.assertIn('aria-modal="true"', details_markup)
        self.assertIn('id="reim-row-details-close"', details_markup)
        function_start = TEMPLATE.index('function openReimbursementRowDetails(')
        function_end = TEMPLATE.index('\n    function ', function_start + 10)
        function = TEMPLATE[function_start:function_end]
        self.assertIn('currentReimbursementRows.find', function)
        self.assertIn('reimEscape(row.task', function)
        self.assertIn('reimEscape(row.client', function)
        self.assertIn('reimEscape(row.product', function)
        self.assertIn('reimEscape((row.engineers', function)
        self.assertIn("event.key === 'Escape'", function)
        self.assertIn('reim-row-details-close', function)

    def test_column_view_reapplies_after_dom_ready_resize_and_rows_without_touching_mobile(self):
        ready_start = TEMPLATE.index("document.addEventListener('DOMContentLoaded'")
        ready_end = TEMPLATE.index('\n    });', ready_start) + len('\n    });')
        ready = TEMPLATE[ready_start:ready_end]
        self.assertIn('readReimbursementColumnViewPreference()', ready)
        self.assertIn('applyReimbursementColumnView(', ready)
        render_start = TEMPLATE.index('function renderReimbursementRows(rows)')
        render_end = TEMPLATE.index('\n    function normalizeReimbursementLifecycleStatus', render_start)
        render = TEMPLATE[render_start:render_end]
        self.assertIn('applyReimbursementColumnView(', render)
        resize_start = TEMPLATE.index("window.addEventListener('resize'", ready_end)
        resize_end = TEMPLATE.index('\n        });', resize_start) + len('\n        });')
        resize = TEMPLATE[resize_start:resize_end]
        self.assertIn('applyReimbursementColumnView(', resize)
        self.assertIn('buildMobileExpenseInputs(row)', render)
        self.assertIn('reimMobileList', render)

    def test_column_view_release_record_is_published_for_everyone(self):
        matches = [
            release for release in RELEASES.get('releases', [])
            if release.get('release_key') == '2026-09-05-reimbursement-column-views'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('is_published'))
        item = matches[0].get('items', [])[0]
        self.assertEqual(item.get('category'), 'Reimbursement')
        self.assertIn('Pinned', item.get('description', ''))
        self.assertIn('Compact', item.get('description', ''))

    def test_desktop_row_actions_are_under_date_and_final_actions_column_is_removed(self):
        self.assertNotIn('<th>Actions</th>', TEMPLATE)
        self.assertNotIn('nth-child(16)', TEMPLATE)
        self.assertIn('colspan="15"', TEMPLATE)

        render_start = TEMPLATE.index('body.innerHTML = rows.map(function(row)')
        render_end = TEMPLATE.index("        }).join('');", render_start)
        render_block = TEMPLATE[render_start:render_end]
        date_start = render_block.index('<td class="reimb-date-cell">')
        date_end = render_block.index('</td>', date_start)
        date_cell = render_block[date_start:date_end]
        self.assertIn('reim-row-actions', date_cell)
        self.assertIn('reim-row-details-btn', date_cell)
        self.assertIn('reim-row-delete-btn', date_cell)
        self.assertNotIn('Actions', render_block)

        footer_start = TEMPLATE.index('<tfoot id="reimTotalsFoot">')
        footer_end = TEMPLATE.index('</tfoot>', footer_start)
        footer = TEMPLATE[footer_start:footer_end]
        self.assertNotIn('<td></td>\n                        <td></td>', footer)
        self.assertIn('id="reimGrandTotal"', footer)

    def test_action_placement_keeps_column_modes_and_date_geometry(self):
        css_start = TEMPLATE.index('/* Reimbursement column view controls')
        css = TEMPLATE[css_start:TEMPLATE.index('</style>', css_start)]
        self.assertIn('.reim-columns-unpinned', css)
        self.assertIn('.reim-columns-compact', css)
        self.assertIn(':nth-child(1)', css)
        self.assertIn('position: sticky;', css)
        self.assertIn('.reim-row-actions', TEMPLATE)
        self.assertIn('.reim-table td:first-child .reim-row-actions', TEMPLATE)
        self.assertIn('min-width: 104px', TEMPLATE)
        self.assertNotIn('nth-child(16)', TEMPLATE)

    def test_zoom_control_has_exact_presets_and_desktop_scope(self):
        control_start = TEMPLATE.index('class="reim-column-view-control"')
        control_end = TEMPLATE.index('</div>', control_start)
        control = TEMPLATE[control_start:control_end]
        self.assertIn('Worksheet zoom', control)
        self.assertIn('id="reimZoomOutBtn"', control)
        self.assertIn('id="reimZoomLevel"', control)
        self.assertIn('id="reimZoomInBtn"', control)
        self.assertIn('id="reimZoomResetBtn"', control)
        for value in ('60', '70', '80', '90', '100', '110'):
            self.assertRegex(control, rf'<option value="{value}">{value}%</option>')
        self.assertIn('.reim-column-view-control', TEMPLATE)
        self.assertIn('.reim-zoom-control', TEMPLATE)
        mobile_start = TEMPLATE.rindex('@media (max-width: 820px)')
        mobile_end = TEMPLATE.index('</style>', mobile_start)
        self.assertRegex(
            TEMPLATE[mobile_start:mobile_end],
            r'\.reim-zoom-control\s*\{[\s\S]{0,120}display:\s*none',
        )

    def test_zoom_preference_is_guarded_and_clamped(self):
        self.assertIn("const REIMBURSEMENT_ZOOM_KEY = 'reimbursementWorksheetZoom';", TEMPLATE)
        self.assertIn('[60, 70, 80, 90, 100, 110]', TEMPLATE)
        normalize_start = TEMPLATE.index('function normalizeReimbursementZoom(')
        normalize_end = TEMPLATE.index('\n    function ', normalize_start + 10)
        normalize = TEMPLATE[normalize_start:normalize_end]
        self.assertIn(': 100;', normalize)
        self.assertIn('REIMBURSEMENT_ZOOM_LEVELS', normalize)
        read_start = TEMPLATE.index('function readReimbursementZoomPreference()')
        read_end = TEMPLATE.index('\n    function ', read_start + 10)
        read = TEMPLATE[read_start:read_end]
        self.assertIn('try', read)
        self.assertIn('localStorage.getItem(REIMBURSEMENT_ZOOM_KEY)', read)
        self.assertIn('catch', read)
        write_start = TEMPLATE.index('function writeReimbursementZoomPreference(')
        write_end = TEMPLATE.index('\n    function ', write_start + 10)
        write = TEMPLATE[write_start:write_end]
        self.assertIn('localStorage.setItem(REIMBURSEMENT_ZOOM_KEY', write)
        self.assertIn('catch', write)

    def test_zoom_switch_is_class_only_and_resynchronizes_scrollbar(self):
        start = TEMPLATE.index('function applyReimbursementZoom(')
        end = TEMPLATE.index('\n    function ', start + 10)
        controller = TEMPLATE[start:end]
        self.assertIn('classList.remove', controller)
        self.assertIn('reim-zoom-', controller)
        self.assertIn('classList.add', controller)
        self.assertIn('syncReimbursementHorizontalScroll();', controller)
        self.assertNotIn('renderReimbursementRows(', controller)
        self.assertIn('updateReimbursementZoomControls', controller)
        self.assertIn('reim-zoom-', controller)

    def test_zoom_layout_scales_only_desktop_worksheet_surface(self):
        self.assertIn('.reim-table.reim-zoom-', TEMPLATE)
        self.assertIn('--reim-worksheet-scale', TEMPLATE)
        self.assertIn('zoom:', TEMPLATE[TEMPLATE.index('.reim-table.reim-zoom-'):TEMPLATE.index('</style>')])
        self.assertIn('.reim-mobile-list', TEMPLATE)
        self.assertIn('reim-zoom-100', TEMPLATE)
        self.assertIn('reimZoomLevel', TEMPLATE)

    def test_zoom_reapplies_with_column_mode_without_rebuilding_mobile_or_rows(self):
        ready_start = TEMPLATE.index("document.addEventListener('DOMContentLoaded'")
        ready_end = TEMPLATE.index('\n    });', ready_start) + len('\n    });')
        ready = TEMPLATE[ready_start:ready_end]
        self.assertIn('readReimbursementZoomPreference()', ready)
        self.assertIn('applyReimbursementZoom(', ready)
        render_start = TEMPLATE.index('function renderReimbursementRows(rows)')
        render_end = TEMPLATE.index('\n    function normalizeReimbursementLifecycleStatus', render_start)
        render = TEMPLATE[render_start:render_end]
        self.assertIn('applyReimbursementZoom(', render)
        self.assertIn('buildMobileExpenseInputs(row)', render)
        self.assertIn('reimMobileList', render)
        self.assertIn('applyReimbursementColumnView(', render)

    def test_zoom_release_and_cache_record_are_current(self):
        self.assertIn('medical-service-pwa-offline-navigation-v146-tsr-signature-finalization', APP_SOURCE)
        matches = [
            release for release in RELEASES.get('releases', [])
            if release.get('release_key') == '2026-09-05-reimbursement-worksheet-zoom-actions'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('is_published'))
        self.assertTrue(any(item.get('category') == 'Reimbursement' for item in matches[0].get('items', [])))

    def test_focus_control_and_desktop_layout_are_present_without_fullscreen_api(self):
        self.assertIn('id="reimFocusToggle"', TEMPLATE)
        self.assertIn('Expand worksheet', TEMPLATE)
        self.assertIn('Exit focus view', TEMPLATE)
        self.assertIn('reim-focus-active', TEMPLATE)
        self.assertIn('.reim-focus-active .reim-table-wrap', TEMPLATE)
        self.assertNotIn('requestFullscreen', TEMPLATE)
        for selector in (
            '.reim-focus-active .reim-hero',
            '.reim-focus-active #sidebar',
            '.reim-focus-active .reim-notification-card',
            '.reim-focus-active .reim-status-window-card',
        ):
            self.assertIn(selector, TEMPLATE)

    def test_focus_controller_preserves_state_and_defers_escape_to_dialogs(self):
        for token in (
            'function enterReimbursementFocusView()',
            'function exitReimbursementFocusView()',
            'function toggleReimbursementFocusView()',
            'function handleReimbursementFocusViewportChange()',
            'function handleReimbursementFocusKeydown(event)',
            'reimbursementFocusPreviousScrollY',
            'reimbursementFocusPreviousFocus',
            'isReimbursementFocusDialogOpen()',
            'syncReimbursementHorizontalScroll();',
            "event.key !== 'Escape'",
            'reim-dialog-backdrop',
            'reim-row-details-backdrop',
            'reimManualItemModal',
            'reimSignatureModal',
            'window.innerWidth >= 821',
        ):
            self.assertIn(token, TEMPLATE)
        self.assertIn("document.addEventListener('keydown', handleReimbursementFocusKeydown)", TEMPLATE)
        self.assertNotIn("localStorage.setItem('reimbursementFocus", TEMPLATE)

    def test_focus_runtime_restores_scroll_and_focus_and_leaves_live_values_untouched(self):
        focus_start = TEMPLATE.index('const REIMBURSEMENT_FOCUS_PANEL_BUTTONS =')
        focus_end = TEMPLATE.index('function closeReimbursementRowDetails()', focus_start)
        focus_helpers = TEMPLATE[focus_start:focus_end]
        node_script = textwrap.dedent(f"""
            const assert = require('assert');
            const classes = new Set();
            const body = {{ classList: {{
                add(name) {{ classes.add(name); }},
                remove(name) {{ classes.delete(name); }},
                contains(name) {{ return classes.has(name); }}
            }} }};
            const listeners = {{}};
            const label = {{ textContent: '' }};
            const iconClasses = new Set(['fa-expand']);
            const icon = {{ classList: {{
                toggle(name, enabled) {{ if (enabled) iconClasses.add(name); else iconClasses.delete(name); }}
            }} }};
            const button = {{
                setAttribute(name, value) {{ this[name] = value; }},
                querySelector(selector) {{ return selector === 'i' ? icon : label; }}
            }};
            const modalClasses = {{
                'reim-dialog-backdrop': new Set(),
                'reim-row-details-backdrop': new Set(),
                'reimManualItemModal': new Set(),
                'reimSignatureModal': new Set()
            }};
            const elements = {{ reimFocusToggle: button, reimFocusToggleLabel: label }};
            Object.keys(modalClasses).forEach(id => {{
                elements[id] = {{
                    classList: {{ contains(name) {{ return modalClasses[id].has(name); }} }},
                    getAttribute() {{ return null; }},
                    style: {{}}
                }};
            }});
            const previousFocus = {{ focusCalls: 0, focus() {{ this.focusCalls += 1; }} }};
            const document = {{
                body,
                activeElement: previousFocus,
                getElementById(id) {{ return elements[id] || null; }},
                contains() {{ return true; }},
                addEventListener(name, handler) {{ listeners[name] = handler; }}
            }};
            const window = {{
                innerWidth: 1200,
                scrollY: 88,
                scrollTo(value) {{ this.lastScroll = typeof value === 'object' ? value.top : arguments[1] || value; }}
            }};
            let syncCalls = 0;
            function syncReimbursementHorizontalScroll() {{ syncCalls += 1; }}
            {focus_helpers}

            initializeReimbursementFocusView();
            const amount = {{ value: '1250.50' }};
            const remarks = {{ value: 'Taxi to client' }};
            assert.strictEqual(reimbursementFocusViewActive, false);
            assert.strictEqual(label.textContent, 'Expand worksheet');
            enterReimbursementFocusView();
            assert.strictEqual(reimbursementFocusViewActive, true);
            assert.ok(classes.has('reim-focus-active'));
            assert.strictEqual(window.lastScroll, 0);
            assert.strictEqual(label.textContent, 'Exit focus view');
            assert.strictEqual(amount.value, '1250.50');
            assert.strictEqual(remarks.value, 'Taxi to client');

            modalClasses['reim-row-details-backdrop'].add('show');
            let prevented = false;
            listeners.keydown({{ key: 'Escape', preventDefault() {{ prevented = true; }} }});
            assert.strictEqual(reimbursementFocusViewActive, true);
            assert.strictEqual(prevented, false);
            modalClasses['reim-row-details-backdrop'].delete('show');
            listeners.keydown({{ key: 'Escape', preventDefault() {{ prevented = true; }} }});
            assert.strictEqual(reimbursementFocusViewActive, false);
            assert.strictEqual(prevented, true);
            assert.strictEqual(window.lastScroll, 88);
            assert.strictEqual(previousFocus.focusCalls, 1);
            assert.ok(syncCalls >= 2);
            assert.strictEqual(amount.value, '1250.50');
            assert.strictEqual(remarks.value, 'Taxi to client');
        """)
        result = subprocess.run(
            ['node', '-e', node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_focus_release_record_is_published_for_everyone(self):
        matches = [
            release for release in RELEASES.get('releases', [])
            if release.get('release_key') == '2026-09-06-reimbursement-focus-sidebar'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('is_published'))
        self.assertTrue(any(item.get('category') == 'Reimbursement' for item in matches[0].get('items', [])))

    def test_focus_table_is_dominant_with_compact_utility_toolbar(self):
        for token in (
            'id="reimFocusToolbar"',
            'id="reimFocusDatesBtn"',
            'id="reimFocusAddManualBtn"',
            'id="reimFocusStatusBtn"',
            'id="reimFocusHistoryBtn"',
            'id="reimFocusNotificationsBtn"',
            'id="reimFocusReceiptsBtn"',
            'id="reimFocusLprBtn"',
            'id="reimFocusRemovedBtn"',
            'id="reimFocusMoreToggle"',
            'class="reim-focus-panel-close',
            'reim-focus-managed-panel',
        ):
            self.assertIn(token, TEMPLATE)

        focus_start = TEMPLATE.index('/* Reimbursement worksheet focus view.')
        focus_css = TEMPLATE[focus_start:TEMPLATE.index('</style>', focus_start)]
        self.assertIn('body.reim-focus-active .reim-table-card', focus_css)
        self.assertIn('overflow: hidden;', focus_css)
        self.assertIn('body.reim-focus-active .reim-table-wrap', focus_css)
        self.assertIn('min-height: 0;', focus_css)
        self.assertIn('height: 32px;', focus_css)
        self.assertIn('height: calc(100dvh - 64px);', focus_css)
        self.assertIn('top: 72px;', focus_css)
        self.assertIn('.reim-focus-panel-open', focus_css)

    def test_focus_hides_supporting_cards_but_keeps_notices_and_panels_actionable(self):
        focus_start = TEMPLATE.index('/* Reimbursement worksheet focus view.')
        focus_css = TEMPLATE[focus_start:TEMPLATE.index('</style>', focus_start)]
        for selector in (
            'body.reim-focus-active .reim-filter-card',
            'body.reim-focus-active .reim-utility-card',
            'body.reim-focus-active #reimAdditionalReceiptsCard',
            'body.reim-focus-active #reimLprPanel',
            'body.reim-focus-active #reimRemovedRowsPanel',
            'body.reim-focus-active .reim-notification-card',
            'body.reim-focus-active .reim-status-window-card',
        ):
            self.assertIn(selector, focus_css)
        self.assertIn('.reim-submit-notice.show', focus_css)
        self.assertIn('.reim-signature-required-panel.show', focus_css)
        self.assertIn('.reim-delete-draft-panel.show', focus_css)
        self.assertIn('toggleReimbursementFocusPanel(', TEMPLATE)
        self.assertIn('closeReimbursementFocusPanel(', TEMPLATE)

    def test_focus_panel_runtime_keeps_one_panel_and_escape_closes_before_view(self):
        focus_start = TEMPLATE.index('const REIMBURSEMENT_FOCUS_PANEL_BUTTONS =')
        focus_end = TEMPLATE.index('function closeReimbursementRowDetails()', focus_start)
        focus_helpers = TEMPLATE[focus_start:focus_end]
        node_script = textwrap.dedent(f"""
            const assert = require('assert');
            function makeClassList() {{
                const names = new Set();
                return {{
                    add(...values) {{ values.forEach(name => names.add(name)); }},
                    remove(...values) {{ values.forEach(name => names.delete(name)); }},
                    contains(name) {{ return names.has(name); }}
                }};
            }}
            const body = {{ classList: makeClassList() }};
            const listeners = {{}};
            const elements = {{}};
            const panelIds = ['reimFilterCard', 'reimLifecycleBanner', 'reimStatusWindowCard'];
            panelIds.forEach(id => elements[id] = {{
                classList: makeClassList(),
                style: {{}},
                getAttribute() {{ return null; }}
            }});
            ['reimFocusDatesBtn', 'reimFocusStatusBtn', 'reimFocusHistoryBtn'].forEach(id => elements[id] = {{
                hidden: false,
                setAttribute(name, value) {{ this[name] = value; }}
            }});
            elements.reimFocusToggle = {{
                setAttribute(name, value) {{ this[name] = value; }},
                querySelector() {{ return {{ classList: {{ toggle() {{}} }} }}; }}
            }};
            elements.reimFocusToggleLabel = {{ textContent: '' }};
            const document = {{
                body,
                activeElement: elements.reimFocusDatesBtn,
                getElementById(id) {{ return elements[id] || null; }},
                contains() {{ return true; }},
                addEventListener(name, handler) {{ listeners[name] = handler; }},
                removeEventListener() {{}}
            }};
            const window = {{
                innerWidth: 1280,
                scrollY: 40,
                scrollTo() {{}},
                requestAnimationFrame(callback) {{ callback(); }}
            }};
            function syncReimbursementHorizontalScroll() {{}}
            {focus_helpers}
            reimbursementFocusViewActive = true;
            toggleReimbursementFocusPanel('reimFilterCard');
            assert.strictEqual(elements.reimFilterCard.classList.contains('reim-focus-panel-open'), true);
            toggleReimbursementFocusPanel('reimLifecycleBanner');
            assert.strictEqual(elements.reimFilterCard.classList.contains('reim-focus-panel-open'), false);
            assert.strictEqual(elements.reimLifecycleBanner.classList.contains('reim-focus-panel-open'), true);
            let prevented = false;
            handleReimbursementFocusKeydown({{ key: 'Escape', preventDefault() {{ prevented = true; }} }});
            assert.strictEqual(prevented, true);
            assert.strictEqual(elements.reimLifecycleBanner.classList.contains('reim-focus-panel-open'), false);
            assert.strictEqual(reimbursementFocusViewActive, true);
        """)
        result = subprocess.run(
            ['node', '-e', node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_focus_more_panel_reuses_secondary_actions_and_keeps_mobile_untouched(self):
        self.assertIn('id="reimFocusMoreToggle"', TEMPLATE)
        self.assertIn('id="reimFocusMorePanel"', TEMPLATE)
        self.assertIn('reimDownloadExcelBtn', TEMPLATE)
        self.assertIn('reimDeleteDraftBtn', TEMPLATE)
        self.assertIn('reimClearBtn', TEMPLATE)
        self.assertIn('data-focus-panel="reimFocusMorePanel"', TEMPLATE)
        mobile_start = TEMPLATE.rindex('@media (max-width: 820px)')
        mobile_css = TEMPLATE[mobile_start:TEMPLATE.index('</style>', mobile_start)]
        self.assertIn('.reim-focus-toolbar', mobile_css)
        self.assertIn('display: none', mobile_css)
        self.assertIn('.reim-focus-toggle', mobile_css)

    def test_focus_toolbar_release_and_cache_record_are_current(self):
        self.assertIn('medical-service-pwa-offline-navigation-v146-tsr-signature-finalization', APP_SOURCE)
        matches = [
            release for release in RELEASES.get('releases', [])
            if release.get('release_key') == '2026-09-06-reimbursement-focus-toolbar'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('is_published'))
        self.assertTrue(any(item.get('category') == 'Reimbursement' for item in matches[0].get('items', [])))

    def test_focus_toolbar_gates_manual_entry_and_keeps_actionable_errors_visible(self):
        self.assertIn("const focusManualBtn = document.getElementById('reimFocusAddManualBtn');", TEMPLATE)
        self.assertIn('focusManualBtn.disabled = !editable;', TEMPLATE)
        self.assertIn('focusManualBtn.title = editable', TEMPLATE)
        for token in (
            'reim-submit-notice.show',
            'reim-delete-draft-panel.show',
            'reim-signature-required-panel.show',
            'reimbursementFocusPanelPreviousFocus',
        ):
            self.assertIn(token, TEMPLATE)

    def test_zoom_helpers_run_with_limits_storage_failure_and_live_values(self):
        zoom_start = TEMPLATE.index('const REIMBURSEMENT_ZOOM_KEY =')
        zoom_end = TEMPLATE.index('function normalizeReimbursementColumnView', zoom_start)
        zoom_helpers = TEMPLATE[zoom_start:zoom_end]
        node_script = textwrap.dedent(f"""
            const assert = require('assert');
            const storage = new Map();
            let storageThrows = false;
            const localStorage = {{
                getItem(key) {{ if (storageThrows) throw new Error('blocked'); return storage.get(key) || null; }},
                setItem(key, value) {{ if (storageThrows) throw new Error('blocked'); storage.set(key, value); }}
            }};
            let syncCalls = 0;
            function syncReimbursementHorizontalScroll() {{ syncCalls += 1; }}
            const classes = new Set(['reim-columns-compact']);
            const table = {{
                dataset: {{}},
                classList: {{
                    remove(...names) {{ names.forEach(name => classes.delete(name)); }},
                    add(...names) {{ names.forEach(name => classes.add(name)); }},
                    contains(name) {{ return classes.has(name); }}
                }}
            }};
            const elements = {{
                reimExpenseTable: table,
                reimZoomLevel: {{ value: '' }},
                reimZoomOutBtn: {{ disabled: false }},
                reimZoomInBtn: {{ disabled: false }},
                reimZoomResetBtn: {{ disabled: false }}
            }};
            const document = {{ getElementById(id) {{ return elements[id] || null; }} }};
            {zoom_helpers}

            assert.strictEqual(normalizeReimbursementZoom('55'), 100);
            assert.strictEqual(normalizeReimbursementZoom('110'), 110);
            assert.strictEqual(readReimbursementZoomPreference(), 100);
            const amount = {{ value: '1250.50' }};
            const remarks = {{ value: 'Taxi to client' }};
            applyReimbursementZoom(60, true);
            assert.strictEqual(storage.get('reimbursementWorksheetZoom'), '60');
            assert.strictEqual(reimbursementZoomLevel, 60);
            assert.strictEqual(table.dataset.zoomLevel, '60');
            assert.ok(table.classList.contains('reim-zoom-60'));
            assert.ok(table.classList.contains('reim-columns-compact'));
            assert.strictEqual(elements.reimZoomOutBtn.disabled, true);
            assert.strictEqual(elements.reimZoomInBtn.disabled, false);
            assert.strictEqual(elements.reimZoomResetBtn.disabled, false);
            assert.strictEqual(elements.reimZoomLevel.value, '60');
            assert.strictEqual(amount.value, '1250.50');
            assert.strictEqual(remarks.value, 'Taxi to client');
            changeReimbursementZoom(-1);
            assert.strictEqual(reimbursementZoomLevel, 60);
            changeReimbursementZoom(1);
            assert.strictEqual(reimbursementZoomLevel, 70);
            resetReimbursementZoom();
            assert.strictEqual(reimbursementZoomLevel, 100);
            assert.strictEqual(elements.reimZoomResetBtn.disabled, true);
            storageThrows = true;
            assert.doesNotThrow(() => readReimbursementZoomPreference());
            assert.doesNotThrow(() => applyReimbursementZoom(110, true));
            assert.ok(syncCalls >= 5);
        """)
        result = subprocess.run(
            ['node', '-e', node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == '__main__':
    unittest.main()
