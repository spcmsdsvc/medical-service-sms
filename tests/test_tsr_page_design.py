"""Source contracts for the Create TSR task-flow and responsive layout."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "offline_tsr.html").read_text(encoding="utf-8")


class TSRPageDesignContracts(unittest.TestCase):
    def require_text(self, needle, haystack=TEMPLATE, message=None):
        if needle not in haystack:
            self.fail(message or f"Expected page contract is missing: {needle}")

    def test_page_stylesheet_and_worker_precache_are_registered(self):
        self.require_text("css/app-offline-tsr.css")
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.require_text("/static/css/app-offline-tsr.css?v=4", app_source)
        self.require_text(
            "medical-service-pwa-offline-navigation-v179-create-tsr-compact-action-bar",
            app_source,
        )
        self.require_text("app-dark-pages.css') }}?v=29", (ROOT / "templates" / "layout.html").read_text(encoding="utf-8"))
        self.require_text("css/app-offline-tsr.css') }}?v=4")

    def test_schedule_selection_is_first_and_empty_state_routes_to_calendar(self):
        self.require_text('id="tsr-schedule-selection"')
        self.require_text('id="tsr-section-customer-equipment"')
        schedule_at = TEMPLATE.index('id="tsr-schedule-selection"')
        first_section_at = TEMPLATE.index('id="tsr-section-customer-equipment"')
        self.assertLess(schedule_at, first_section_at)

        self.require_text('id="tsr-empty-schedule-state"')
        empty_state = TEMPLATE.split('id="tsr-empty-schedule-state"', 1)[1].split(
            "</section>", 1
        )[0]
        self.require_text("assigned equipment", empty_state.lower())
        self.require_text('href="/timeline"', empty_state)
        self.require_text("Open Calendar", empty_state)
        self.require_text(
            "tsr-empty-schedule-state",
            TEMPLATE.split("function updateCreateTSRScheduleGate", 1)[1].split(
                "function requireStandaloneScheduleForTSRAction", 1
            )[0],
        )

    def test_form_has_four_ordered_sections_and_visit_signoff_stays_in_main_flow(self):
        section_ids = [
            "tsr-section-customer-equipment",
            "tsr-section-service-work",
            "tsr-section-visit-signoff",
            "tsr-section-supporting-documents",
        ]
        for section_id in section_ids:
            self.require_text(f'id="{section_id}"')
        positions = [TEMPLATE.index(f'id="{section_id}"') for section_id in section_ids]
        self.assertEqual(positions, sorted(positions))

        visit_section = TEMPLATE.split('id="tsr-section-visit-signoff"', 1)[1].split(
            'id="tsr-section-supporting-documents"', 1
        )[0]
        for field_id in (
            "tsr-service-date",
            "tsr-serviced-by",
            "tsr-acknowledged-by",
            "serviced-signature-status",
            "acknowledged-signature-status",
        ):
            self.require_text(f'id="{field_id}"', visit_section)

        self.require_text('id="tsr-section-nav"')
        self.require_text('aria-label="TSR sections"')

    def test_one_action_bar_exposes_primary_and_secondary_actions(self):
        self.require_text('id="offline-tsr-action-bar"')
        action_bar = TEMPLATE.split('id="offline-tsr-action-bar"', 1)[1].split(
            'id="calibration-report-overlay"', 1
        )[0]
        self.require_text("Review &amp; Save TSR", action_bar)
        self.require_text("Save Draft", action_bar)
        for label in (
            "Preview TSR",
            "Download PDF",
            "Clear Current TSR",
        ):
            self.require_text(label, action_bar)
        self.assertNotIn("Copy Draft Text", action_bar)
        self.assertNotIn("Start New TSR", action_bar)
        self.require_text('role="group"', action_bar)
        self.require_text('aria-label="Other TSR actions"', action_bar)
        self.assertEqual(TEMPLATE.count('id="offline-tsr-action-bar"'), 1)
        self.assertEqual(TEMPLATE.count('id="standalone-tsr-save-btn"'), 1)
        self.assertEqual(TEMPLATE.count('id="standalone-tsr-draft-btn"'), 1)

    def test_saved_work_is_secondary_and_mobile_action_bar_is_reachable(self):
        self.require_text('id="tsr-schedule-selection"')
        drafts_at = TEMPLATE.index('id="standalone-tsr-drafts-list"')
        schedule_at = TEMPLATE.index('id="tsr-schedule-selection"')
        self.assertGreater(drafts_at, schedule_at)
        details = re.search(
            r'<details\b[^>]*id="standalone-tsr-drafts-disclosure"[^>]*>(.*?)</details>',
            TEMPLATE,
            re.DOTALL,
        )
        self.assertIsNotNone(details)
        self.assertNotIn(" open", details.group(0).split(">", 1)[0])
        self.require_text("Continue Saved Work", details.group(1))

        css_path = ROOT / "static" / "css" / "app-offline-tsr.css"
        self.assertTrue(css_path.exists(), "Expected page layout stylesheet is missing.")
        css = css_path.read_text(encoding="utf-8")
        self.require_text(".offline-tsr-summary-rail", css)
        self.require_text(".offline-tsr-action-bar", css)
        self.require_text("safe-area-inset-bottom", css)
        self.assertRegex(css, r"@media\s*\(max-width:\s*(?:[0-9]+)px\)")

    def test_core_readiness_summary_tracks_only_the_five_core_requirements(self):
        self.require_text('id="tsr-core-readiness-summary"')
        self.require_text('id="tsr-core-readiness-progress"')
        summary = TEMPLATE.split('id="tsr-core-readiness-summary"', 1)[1].split(
            '</section>', 1
        )[0]
        for requirement in (
            "schedule",
            "service-category",
            "actions-taken",
            "serviced-signature",
            "acknowledged-signature",
        ):
            self.require_text(f'data-tsr-core-prerequisite="{requirement}"', summary)

        renderer = TEMPLATE.split("function renderStandaloneTSRCoreReadiness", 1)[1].split(
            "function focusStandaloneTSRCorePrerequisite", 1
        )[0]
        for helper in (
            "hasStandaloneScheduleSelection()",
            "isScheduleEquipmentAssignable(",
            "getMissingTSRCoreDetails(",
            "hasRequiredServicedSignature(",
            "hasRequiredAcknowledgedSignature(",
        ):
            self.require_text(helper, renderer)
        self.assertNotIn("getMissingTSRRecommendedDetails", renderer)
        self.assertNotIn("collectTSRData()", renderer,
                         "The readiness renderer must not recurse through syncActionsText during collection.")
        for field in (
            "document.getElementById('tsr-service-category')",
            "document.getElementById('tsr-service-category-other')",
            "document.getElementById('tsr-actions-taken')",
            "selectedSchedule:getSelectedStandaloneSchedule()",
            "signatures:signatureData",
        ):
            self.require_text(field, renderer)

        gate = TEMPLATE.split("function updateCreateTSRScheduleGate", 1)[1].split(
            "function requireStandaloneScheduleForTSRAction", 1
        )[0]
        self.require_text("renderStandaloneTSRCoreReadiness()", gate)
        for helper in (
            "function syncTSRServiceCategoryFromChecks",
            "function syncActionsText",
            "function updateSignatureStatuses",
        ):
            body = TEMPLATE.split(helper, 1)[1].split("function ", 1)[0]
            self.require_text("renderStandaloneTSRCoreReadiness()", body)

    def test_existing_core_fields_have_visible_required_markers(self):
        for marker in (
            'data-tsr-required="schedule"',
            'data-tsr-required="service-category"',
            'data-tsr-required="actions-taken"',
            'data-tsr-required="serviced-signature"',
            'data-tsr-required="acknowledged-signature"',
        ):
            self.require_text(marker)
        self.require_text('class="offline-tsr-required-marker"')

    def test_live_save_status_reflects_local_and_account_backup_states(self):
        self.require_text('id="standalone-tsr-save-status"')
        self.require_text('id="standalone-tsr-save-status" class="offline-tsr-save-status" role="status" aria-live="polite"')
        self.assertNotIn(">Local Draft</span>", TEMPLATE)
        for state in (
            "no-changes",
            "saving-local",
            "local-saved-pending",
            "backup-in-progress",
            "account-backed-up",
            "local-save-failed",
            "account-backup-failed",
        ):
            self.require_text(f"'{state}'")
        self.require_text("standaloneTSRSaveStatusContextIsActive")
        self.require_text("attachments_not_durable")
        self.require_text("source === 'localstorage'")

    def test_package_two_theme_rules_keep_generated_tsr_white(self):
        css_path = ROOT / "static" / "css" / "app-offline-tsr.css"
        css = css_path.read_text(encoding="utf-8")
        for token in ("--app-primary", "--app-surface", "--app-text", "--app-muted", "--app-border", "--app-focus"):
            self.require_text(token, css)
        dark_css = (ROOT / "static" / "css" / "app-dark-pages.css").read_text(encoding="utf-8")
        self.require_text("offline-tsr-core-readiness", dark_css)
        self.require_text("tsr-print-sheet", dark_css)
        self.require_text("background: #fff !important", dark_css)

    def test_reload_disables_native_scroll_restoration_without_forcing_scroll(self):
        page_head = TEMPLATE.split('{% block page_head %}', 1)[1].split('{% endblock %}', 1)[0]
        for marker in (
            "navigation?.type === 'reload'",
            "window.location.hash",
            "window.history.scrollRestoration = 'manual'",
            "window.addEventListener('pagehide'",
        ):
            self.require_text(marker, page_head)
        self.assertNotIn("scrollTo(", page_head)
        self.assertNotIn("scrollIntoView(", page_head)

    def test_blank_draft_startup_does_not_focus_calibration_or_show_schedule_toast(self):
        draft_load = TEMPLATE.split("async function loadStandaloneTSRDraft()", 1)[1].split("async function saveStandaloneTSRLocalDraft()", 1)[0]
        startup = TEMPLATE.split("const offlineTSRStartup =", 1)[1].split("document.querySelectorAll('.tsr-field')", 1)[0]
        draft_apply = TEMPLATE.split("function applyStandaloneTSRDraftData(data)", 1)[1].split("function setOnlineTSRRevisionContext(context)", 1)[0]
        self.assertNotIn("showMessage:true", draft_load)
        self.assertNotIn("showMessage", startup)
        self.assertNotIn("showMessage", draft_apply)


if __name__ == "__main__":
    unittest.main()
