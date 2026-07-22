import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TsrFilenameTemplateSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        cls.tsr_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.changelog_source = (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')

    def test_filename_template_is_settings_managed(self):
        self.assertIn("'tsr_pdf_filename': {", self.app_source)
        self.assertIn("'template_type': 'filename'", self.app_source)
        self.assertIn('NCS_TSR_{billing_marker}_Shimadzu_', self.app_source)
        self.assertIn("'label': 'TSR PDF Filename'", self.app_source)
        self.assertIn('<span>Templates</span>', self.settings_source)

    def test_all_filename_placeholders_are_available(self):
        for placeholder in (
            'tsr_number', 'client_name', 'product_name', 'machine_name',
            'serial_number', 'serial', 'task', 'service_case', 'service_date',
            'date_mmddyyyy', 'date_yyyymmdd', 'engineer_initials',
            'billing_marker', 'billing_tags', 'warranty', 'foc', 'with_po',
            'sc', 'sv',
        ):
            self.assertIn(f"'{placeholder}'", self.app_source)

    def test_settings_preview_supports_billing_scenarios(self):
        for scenario in ('standard', 'warranty', 'foc', 'po', 'po_sc', 'po_sv'):
            self.assertIn(f'{scenario}:', self.settings_source)
        self.assertIn('sanitizeTSRFilenamePreview', self.settings_source)

    def test_online_offline_and_legacy_queue_paths_are_covered(self):
        self.assertIn('render_tsr_pdf_filename(context)', self.app_source)
        self.assertIn('TSR_FILENAME_TEMPLATE_CACHE_KEY', self.tsr_source)
        self.assertIn('_tsr_filename_template:activeTSRFilenameTemplate', self.tsr_source)
        self.assertIn("if(String(payload?._tsr_filename_template || '').trim())", self.tsr_source)

    def test_generated_tsr_recognition_does_not_require_filename_text(self):
        self.assertIn('def is_system_generated_tsr_file(file_rec):', self.app_source)
        self.assertIn('def shift_file_is_recognized_tsr(file_rec):', self.app_source)
        self.assertIn('if shift_file_is_recognized_tsr(file_rec):', self.app_source)

    def test_release_note_and_cache_bump_are_present(self):
        self.assertIn('2026-07-22-tsr-filename-template', self.changelog_source)
        self.assertIn('v34-tsr-subject-scenarios', self.app_source)


if __name__ == '__main__':
    unittest.main()
