import json
import pathlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TsrSubjectScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        cls.timeline_source = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        cls.changelog_source = (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')

    def test_all_subject_scenarios_are_settings_managed(self):
        expected = {
            'standard': 'tsr_client_subject',
            'warranty': 'tsr_client_subject_warranty',
            'foc': 'tsr_client_subject_foc',
            'with_po': 'tsr_client_subject_with_po',
            'po_sc': 'tsr_client_subject_po_sc',
            'po_sv': 'tsr_client_subject_po_sv',
            'installation': 'tsr_client_subject_installation',
        }
        for scenario, template_key in expected.items():
            self.assertIn(f"'{scenario}': {{", self.app_source)
            self.assertIn(f"'template_key': '{template_key}'", self.app_source)

    def test_installation_has_highest_payload_priority(self):
        payload = {
            'tsr-service-category': 'Warranty, Installation',
            'selectedSchedule': {'task': 'System Installation [With P.O.] [SC]'},
        }
        metadata = app_module.get_tsr_subject_payload_metadata(payload)
        self.assertEqual(metadata['scenario'], 'installation')
        self.assertTrue(metadata['with_po'])

    def test_billing_scenario_priority(self):
        cases = (
            ({'selectedSchedule': {'task': 'Repair [With P.O.] [SC]'}}, 'po_sc'),
            ({'selectedSchedule': {'task': 'Repair [With P.O.] [SV]'}}, 'po_sv'),
            ({'selectedSchedule': {'task': 'Repair [With P.O.]'}}, 'with_po'),
            ({'selectedSchedule': {'task': 'Repair [Warranty]'}}, 'warranty'),
            ({'selectedSchedule': {'task': 'Repair [FOC]'}}, 'foc'),
            ({'selectedSchedule': {'task': 'Repair'}}, 'standard'),
        )
        for payload, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    app_module.get_tsr_subject_payload_metadata(payload)['scenario'],
                    expected,
                )

    def test_package_reports_distinct_generated_scenarios(self):
        files = [
            {'id': 10, 'source_type': 'generated'},
            {'id': 11, 'source_type': 'generated'},
            {'id': 12, 'source_type': 'uploaded'},
        ]
        records = {
            (app_module.ShiftFile, 10): SimpleNamespace(online_tsr_submission_id=100),
            (app_module.ShiftFile, 11): SimpleNamespace(online_tsr_submission_id=101),
            (app_module.ShiftFile, 12): SimpleNamespace(online_tsr_submission_id=None),
            (app_module.OnlineTsrSubmission, 100): SimpleNamespace(
                payload_json=json.dumps({'tsr-service-category': 'Installation'})
            ),
            (app_module.OnlineTsrSubmission, 101): SimpleNamespace(
                payload_json=json.dumps({'selectedSchedule': {'task': 'Repair [Warranty]'}})
            ),
        }

        with app_module.app.app_context(), patch.object(
            app_module.db.session,
            'get',
            side_effect=lambda model, record_id: records.get((model, record_id)),
        ):
            metadata = app_module.get_tsr_subject_package_metadata(files)

        self.assertTrue(metadata['mixed'])
        self.assertEqual(metadata['scenarios'], ['installation', 'warranty'])

    def test_uploaded_only_package_uses_standard(self):
        with app_module.app.app_context(), patch.object(app_module.db.session, 'get', return_value=None):
            metadata = app_module.get_tsr_subject_package_metadata([{'id': 55, 'source_type': 'uploaded'}])
        self.assertFalse(metadata['mixed'])
        self.assertEqual(metadata['scenarios'], ['standard'])

    def test_grouped_settings_and_mixed_send_controls_exist(self):
        self.assertIn('Subject Scenario', self.settings_source)
        self.assertIn('switchTSRSubjectScenario', self.settings_source)
        self.assertIn('tsr-subject-scenario-panel', self.timeline_source)
        self.assertIn('subject_scenario: subjectScenario', self.timeline_source)
        self.assertIn("subject_scenario_required", self.app_source)
        self.assertIn('Please select the email subject scenario for this mixed TSR package.', self.app_source)

    def test_release_note_and_cache_bump_are_present(self):
        self.assertIn('2026-07-22-tsr-subject-scenarios', self.changelog_source)
        self.assertIn('v35-tsr-email-preview-cc', self.app_source)


if __name__ == '__main__':
    unittest.main()
