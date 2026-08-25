import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module


ROOT = Path(__file__).resolve().parents[1]


class ReportsArchivePaginationSourceTests(unittest.TestCase):
    def test_archive_api_is_all_history_and_capped_at_ten_files(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        route_start = source.index("@app.route('/get_tsr_archive')")
        route_end = source.index("@app.route('/preview_tsr_archive_file", route_start)
        route = source[route_start:route_end]

        self.assertNotIn('analytics_date_bounds()', route)
        self.assertIn('per_page = min(max(requested_per_page, 1), 10)', route)
        self.assertIn('ShiftFile.uploaded_at.desc()', route)
        self.assertIn('Shift.start_time.desc()', route)
        self.assertIn('ShiftFile.id.desc()', route)
        self.assertIn("'sort': 'recently_added'", route)
        self.assertIn("'total_pages': total_pages", route)
        self.assertIn("'rows': page_rows", route)

    def test_archive_filters_are_separate_from_monitoring_dates(self):
        source = (ROOT / 'templates' / 'reports.html').read_text(encoding='utf-8')
        archive_params_start = source.index('function archiveParams(')
        archive_params_end = source.index('function currentArchiveScope', archive_params_start)
        archive_params = source[archive_params_start:archive_params_end]

        self.assertNotIn('reports-start-date', archive_params)
        self.assertNotIn('reports-end-date', archive_params)
        self.assertIn("params.set('per_page', '10')", archive_params)
        self.assertIn('Monitoring Range', source)
        self.assertIn('archive-page-indicator', source)

    def test_archive_exposes_certificate_kind_and_locks_print_copy_for_engineers(self):
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        route_start = app_source.index("@app.route('/get_tsr_archive')")
        route_end = app_source.index("@app.route('/preview_tsr_archive_file", route_start)
        route = app_source[route_start:route_end]
        self.assertIn('certificate_approval_map = calibration_certificate_approval_map_for_files(file_records)', route)
        self.assertIn("'certificate_kind': 'no_signature'", route)
        self.assertIn("'locked': bool(is_no_signature and not no_signature_access)", route)
        self.assertIn("'can_preview': bool(no_signature_access)", route)

        template_source = (ROOT / 'templates' / 'reports.html').read_text(encoding='utf-8')
        self.assertIn('Admin download only', template_source)
        self.assertIn('const locked = Boolean(row.locked', template_source)

    def test_timeline_schedule_card_lists_managed_certificates_and_locks_print_copy(self):
        template_source = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        attachments_start = template_source.index('function buildTimelineTSRAttachmentsHtml(')
        attachments_end = template_source.index('function getTimelineFilePreviewUrl(', attachments_start)
        attachments = template_source[attachments_start:attachments_end]

        self.assertIn('file.is_tsr || file.is_managed_certificate', attachments)
        self.assertIn('file.is_no_signature && (file.locked || file.can_preview === false)', attachments)
        self.assertIn('Admin download only', attachments)
        self.assertIn('escapeHtml(displayName)', attachments)

    def test_regional_admin_uses_read_visibility_for_manila_print_copy(self):
        manila_shift = SimpleNamespace(id=991, branch='Manila')
        approval = SimpleNamespace(shift=manila_shift)
        with patch.object(app_module, 'is_admin_authorized', return_value=True), \
                patch.object(app_module, 'user_can_view_shift_tsr_archive', return_value=True) as can_view, \
                patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=False):
            self.assertTrue(app_module.calibration_certificate_no_signature_admin_can_view(approval))
        can_view.assert_called_once_with(manila_shift)

    def test_engineer_direct_archive_route_still_rejects_no_signature_copy(self):
        file_record = SimpleNamespace(id=136, shift_id=864)
        shift = SimpleNamespace(id=864)
        approval = SimpleNamespace(shift=shift)

        def load_record(model, record_id):
            if model is app_module.ShiftFile:
                return file_record
            if model is app_module.Shift:
                return shift
            return None

        with app_module.app.test_request_context('/preview_tsr_archive_file/136'):
            with patch.object(app_module.db.session, 'get', side_effect=load_record), \
                    patch.object(app_module, 'user_can_view_shift_tsr_archive', return_value=True), \
                    patch.object(app_module, 'calibration_certificate_no_signature_approval_for_file', return_value=approval), \
                    patch.object(app_module, 'calibration_certificate_no_signature_admin_can_view', return_value=False):
                resolved, error_response = app_module._resolve_tsr_archive_file_for_preview(136)

        self.assertIsNone(resolved)
        self.assertEqual(error_response.status_code, 403)

    def test_archive_accepts_only_submission_linked_generated_calibration_report_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / 'calibration-report.docx'
            report_path.write_bytes(b'generated calibration report')
            shift = SimpleNamespace(id=864)
            submission = SimpleNamespace(
                id=27,
                shift_id=864,
                payload_json=json.dumps({
                    '_generated_calibration_report': {
                        'source': 'generated_calibration_report',
                        'file_id': 134,
                    }
                }),
            )
            generated_file = SimpleNamespace(
                id=134,
                shift_id=864,
                filename='calibration-report.docx',
                original_filename='Calibration Report.docx',
                online_tsr_submission_id=27,
            )
            unrelated_file = SimpleNamespace(
                id=135,
                shift_id=864,
                filename='unrelated.docx',
                original_filename='Unrelated.docx',
                online_tsr_submission_id=27,
            )

            def load_record(model, record_id):
                if model is app_module.ShiftFile:
                    return generated_file if record_id == 134 else unrelated_file
                if model is app_module.Shift:
                    return shift
                if model is app_module.OnlineTsrSubmission:
                    return submission
                return None

            with app_module.app.test_request_context('/preview_tsr_archive_file/134'):
                with patch.object(app_module.db.session, 'get', side_effect=load_record), \
                        patch.object(app_module, 'user_can_view_shift_tsr_archive', return_value=True), \
                        patch.object(app_module, 'managed_storage_read_path', return_value=str(report_path)):
                    resolved, error_response = app_module._resolve_tsr_archive_file_for_preview(134)

            self.assertIsNone(error_response)
            self.assertEqual(resolved['ext'], 'docx')

            with app_module.app.test_request_context('/preview_tsr_archive_file/135'):
                with patch.object(app_module.db.session, 'get', side_effect=load_record), \
                        patch.object(app_module, 'user_can_view_shift_tsr_archive', return_value=True), \
                        patch.object(app_module, 'managed_storage_read_path', return_value=str(report_path)):
                    resolved, error_response = app_module._resolve_tsr_archive_file_for_preview(135)

            self.assertIsNone(resolved)
            self.assertEqual(error_response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
