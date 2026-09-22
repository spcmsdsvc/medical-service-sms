"""Focused server checks for Calibration Report temporary-model approval."""

import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB = pathlib.Path(tempfile.gettempdir()) / f"medical_service_calibration_temporary_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB))
os.environ.setdefault("SECRET_KEY", "calibration-temporary-test-only")

import app as app_module  # noqa: E402


SIGNATURE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAHgAAAAeCAYAAADnydqVAAAAVElEQVR42u3WsQkAMAwEsdt/"
    "aWeDlMEEHfwCVuNGX5cTABZgARZgARZgAQYswAIswAKsJ8CVLRtgwIABy5MlwAIswAIswIA"
    "FWIAFWIAFWIAFWJcOqjWBWhan81EAAAAASUVORK5CYII="
)


def temporary_payload(model_name, source='temporary'):
    return {
        'tsr-number': 'TSR-TEMP-77',
        'calibration_report': {
            'certificate': {
                'bsid': 'B-TEMP-77',
                'model_source': source,
                'equipment_model': model_name,
            },
            'facility': {'name': 'Temporary Model Clinic'},
            'machine': {
                'modality': 'Digital Angiography System',
                'model': model_name,
                'serial_number': 'TEMP-SN-77',
            },
            'calibration': {
                'machine_calibration_date': '2026-08-20',
                'next_calibration_date': '2027-08-20',
            },
        },
    }


class CalibrationTemporaryModelServerTests(unittest.TestCase):
    def _body_status(self, response):
        if isinstance(response, tuple):
            body, status = response
        else:
            body, status = response, response.status_code
        return body.get_json(), status

    def _fixture(self, model_name):
        app = app_module.app
        db = app_module.db
        db.create_all()
        app_module.ensure_calibration_certificate_approval_table()
        app_module.ensure_universal_approval_audit_table()
        requester = app_module.User(
            username=f'temporary_requester_{uuid.uuid4().hex[:8]}',
            password='test-only', role='engineer',
        )
        approver = app_module.User(
            username=f'temporary_approver_{uuid.uuid4().hex[:8]}',
            password='test-only', role='superadmin', approval_title='Calibration Manager',
        )
        db.session.add_all([requester, approver])
        db.session.flush()
        requester_engineer = app_module.Engineer(
            user_id=requester.id, employee_id=f'TEMP-REQ-{uuid.uuid4().hex[:8]}',
            name='Temporary Requester', initials='TR', branch='Manila',
        )
        approver_engineer = app_module.Engineer(
            user_id=approver.id, employee_id=f'TEMP-APP-{uuid.uuid4().hex[:8]}',
            name='Calibration Manager', initials='CM', branch='Manila', signature_data=SIGNATURE,
        )
        client = app_module.Client(name=f'Temporary Model Clinic {uuid.uuid4().hex[:8]}')
        db.session.add_all([requester_engineer, approver_engineer, client])
        db.session.flush()
        product = app_module.Product(
            serial_number=f'TEMP-{uuid.uuid4().hex[:8]}', name='Digital Angiography System',
            client_id=client.id, bsid=f'B-TEMP-{uuid.uuid4().hex[:6]}',
        )
        db.session.add(product)
        db.session.flush()
        shift = app_module.Shift(
            title='Temporary Model Calibration', start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1), engineer_id=requester_engineer.id,
            client_id=client.id, product_id=product.serial_number, status='Completed',
        )
        db.session.add(shift)
        db.session.flush()
        payload = temporary_payload(model_name)
        submission = app_module.OnlineTsrSubmission(
            shift_id=shift.id, tsr_number='TSR-TEMP-77', client_name=client.name,
            product_name=product.name, serial_number=product.serial_number,
            submitted_by_user_id=requester.id, submitted_by_name=requester_engineer.name,
            status='completed', submission_token=f'temporary-{uuid.uuid4().hex}',
            payload_json=json.dumps(payload), revision_no=1, is_latest=True,
        )
        db.session.add(submission)
        db.session.commit()
        return requester, approver, shift, submission

    def test_strict_catalog_and_effective_catalog_are_separate(self):
        with app_module.app.app_context():
            app_module.db.create_all()
            app_module.ensure_calibration_certificate_model_table()
            strict = app_module.calibration_certificate_catalog()
            self.assertEqual(len(strict['models']), 47)
            self.assertEqual(set(strict), {'equipment_names', 'models'})
            model = app_module.CalibrationCertificateModel(
                model_name='Temporary Effective 9000',
                normalized_model_key='temporaryeffective9000',
                status='Approved',
                requested_at=app_module.get_manila_time(),
                approved_at=app_module.get_manila_time(),
            )
            app_module.db.session.add(model)
            app_module.db.session.commit()
            effective = app_module.calibration_certificate_effective_catalog()
            self.assertEqual(len(effective['models']), len(strict['models']) + len(effective['approved_models']))
            self.assertIn('Temporary Effective 9000', effective['models'])
            self.assertEqual(
                next(item['id'] for item in effective['approved_models'] if item['model_name'] == 'Temporary Effective 9000'),
                model.id,
            )

    def test_normalized_duplicate_rejected_name_can_be_resubmitted(self):
        with app_module.app.app_context():
            app_module.db.create_all()
            first = app_module.get_or_create_calibration_certificate_model('Temporary Model 9000', 41)
            app_module.db.session.commit()
            second = app_module.get_or_create_calibration_certificate_model('temporary-model-9000', 42)
            self.assertEqual(first.id, second.id)
            self.assertEqual(second.status, 'Pending')
            self.assertEqual(second.model_name, 'temporary-model-9000')
            second.status = 'Rejected'
            second.return_remarks = 'Use the exact model label.'
            app_module.db.session.commit()
            resubmitted = app_module.get_or_create_calibration_certificate_model('TEMPORARY MODEL 9000', 43)
            self.assertEqual(resubmitted.id, first.id)
            self.assertEqual(resubmitted.status, 'Pending')
            self.assertEqual(resubmitted.return_remarks, None)

    def test_unlisted_requires_marker_and_server_rejects_invalid_temporary_text(self):
        base = temporary_payload('Unlisted Model 9000', source='catalog')['calibration_report']
        with app_module.app.app_context():
            implicit_errors, _ = app_module.calibration_certificate_catalog_errors(base)
            self.assertTrue(any('exact catalog Equipment Model' in error for error in implicit_errors))
            base['certificate']['model_source'] = 'temporary'
            valid_errors, _ = app_module.calibration_certificate_catalog_errors(base)
            self.assertEqual(valid_errors, [])
            values, missing, _ = app_module.calibration_certificate_values({'calibration_report': base})
            self.assertEqual(values['Text2'], 'Unlisted Model 9000')
            self.assertNotIn('Equipment Model', missing)
            for invalid in ('A' * 41, 'Model\nWithBreak', '   '):
                invalid_report = temporary_payload(invalid)['calibration_report']
                errors, _ = app_module.calibration_certificate_catalog_errors(invalid_report)
                self.assertTrue(errors, invalid)

    def test_temporary_submission_is_pending_and_exposes_exact_model_without_signed_artifact(self):
        app = app_module.app
        with tempfile.TemporaryDirectory(prefix='calibration_temporary_submission_') as storage_root:
            original_upload_folder = app.config.get('UPLOAD_FOLDER')
            app.config['UPLOAD_FOLDER'] = storage_root
            try:
                with app.app_context(), app.test_request_context('/'):
                    requester, _approver, _shift, submission = self._fixture('Temporary Submission 9000')
                    with patch.object(app_module, 'get_assigned_approvers_for_requester', return_value=[]), \
                            patch.object(app_module, 'create_system_notification'):
                        result = app_module.submit_calibration_certificate_for_submission(submission)
                    self.assertTrue(result['ok'])
                    approval = result['approval']
                    self.assertEqual(approval.model_source, 'temporary')
                    self.assertIsNone(approval.signed_shift_file_id)
                    self.assertIsNone(approval.no_signature_shift_file_id)
                    self.assertEqual(json.loads(approval.mapped_data_json)['Text2'], 'Temporary Submission 9000')
                    model = app_module.CalibrationCertificateModel.query.filter_by(id=approval.model_catalog_id).one()
                    self.assertEqual(model.status, 'Pending')
                    serialized = app_module.calibration_certificate_approval_to_dict(approval, include_urls=False)
                    self.assertEqual(serialized['model_name'], 'Temporary Submission 9000')
                    self.assertEqual(serialized['temporary_model_status'], 'Pending')
                    self.assertTrue(serialized['temporary_model_pending'])
                    self.assertIn('shared approved', serialized['model_approval_message'])
                    self.assertTrue(list(pathlib.Path(storage_root).rglob('*')))
                    self.assertEqual(requester.id, approval.requester_user_id)
            finally:
                app.config['UPLOAD_FOLDER'] = original_upload_folder
                with app.app_context():
                    app_module.db.session.remove()

    def test_routed_approval_promotes_atomically_and_return_rejects_without_promotion(self):
        app = app_module.app
        with tempfile.TemporaryDirectory(prefix='calibration_temporary_approval_') as storage_root:
            original_upload_folder = app.config.get('UPLOAD_FOLDER')
            app.config['UPLOAD_FOLDER'] = storage_root
            try:
                with app.app_context(), app.test_request_context('/'):
                    _requester, approver, _shift, submission = self._fixture('Temporary Approval 9000')
                    with patch.object(app_module, 'get_assigned_approvers_for_requester', return_value=[]), \
                            patch.object(app_module, 'create_system_notification'):
                        result = app_module.submit_calibration_certificate_for_submission(submission)
                    approval = result['approval']
                    model_id = approval.model_catalog_id
                    app_module.login_user(approver)
                    with patch.object(app_module, 'calibration_certificate_approver_can_act', return_value=False):
                        denied, status = self._body_status(app_module.approve_calibration_certificate(approval.id))
                    self.assertEqual(status, 403)
                    self.assertFalse(denied.get('success', False))
                    with patch.object(app_module, 'calibration_certificate_approver_can_act', return_value=True), \
                            patch.object(app_module, 'approval_signature_required_response', return_value=None), \
                            patch.object(app_module, 'build_calibration_certificate_pdf', return_value=(b'signed', None, 'signed-fingerprint')), \
                            patch.object(app_module, 'build_calibration_certificate_no_signature_pdf', return_value=(b'unsigned', None, '')), \
                            patch.object(app_module, 'managed_storage_write_bytes', side_effect=OSError('isolated storage failure')):
                        failed, status = self._body_status(app_module.approve_calibration_certificate(approval.id))
                    self.assertEqual(status, 500)
                    self.assertTrue(failed.get('retryable'))
                    app_module.db.session.expire_all()
                    pending = app_module.db.session.get(app_module.CalibrationCertificateApproval, approval.id)
                    self.assertEqual(pending.status, 'Pending')
                    self.assertIsNone(pending.signed_shift_file_id)
                    self.assertEqual(app_module.db.session.get(app_module.CalibrationCertificateModel, model_id).status, 'Pending')
                    with patch.object(app_module, 'calibration_certificate_approver_can_act', return_value=True), \
                            patch.object(app_module, 'approval_signature_required_response', return_value=None), \
                            patch.object(app_module, 'build_calibration_certificate_pdf', return_value=(b'signed', None, 'signed-fingerprint')), \
                            patch.object(app_module, 'build_calibration_certificate_no_signature_pdf', return_value=(b'unsigned', None, '')), \
                            patch.object(app_module, 'managed_storage_write_bytes', return_value=None), \
                            patch.object(app_module, 'create_system_notification'):
                        approved, status = self._body_status(app_module.approve_calibration_certificate(approval.id))
                    self.assertEqual(status, 200)
                    self.assertTrue(approved['success'])
                    app_module.db.session.expire_all()
                    decided = app_module.db.session.get(app_module.CalibrationCertificateApproval, approval.id)
                    promoted = app_module.db.session.get(app_module.CalibrationCertificateModel, model_id)
                    self.assertEqual(decided.status, 'Approved')
                    self.assertIsNotNone(decided.signed_shift_file_id)
                    self.assertEqual(promoted.status, 'Approved')
                    self.assertIn('Temporary Approval 9000', app_module.calibration_certificate_effective_catalog()['models'])
                    app_module.logout_user()

                    _requester, approver, _shift, submission = self._fixture('Temporary Return 9000')
                    with patch.object(app_module, 'get_assigned_approvers_for_requester', return_value=[]), \
                            patch.object(app_module, 'create_system_notification'):
                        result = app_module.submit_calibration_certificate_for_submission(submission)
                    returned_approval = result['approval']
                    returned_model_id = returned_approval.model_catalog_id
                    app_module.login_user(approver)
                    with app.test_request_context('/', method='POST', json={'remarks': 'Confirm the exact temporary model label.'}), \
                            patch.object(app_module, 'calibration_certificate_approver_can_act', return_value=True), \
                            patch.object(app_module, 'create_system_notification'):
                        returned, status = self._body_status(app_module.return_calibration_certificate(returned_approval.id))
                    self.assertEqual(status, 200)
                    self.assertTrue(returned['success'])
                    app_module.db.session.expire_all()
                    returned_row = app_module.db.session.get(app_module.CalibrationCertificateApproval, returned_approval.id)
                    returned_model = app_module.db.session.get(app_module.CalibrationCertificateModel, returned_model_id)
                    self.assertEqual(returned_row.status, 'Returned')
                    self.assertEqual(returned_model.status, 'Rejected')
                    self.assertIsNone(returned_row.signed_shift_file_id)
                    resubmitted = app_module.get_or_create_calibration_certificate_model('Temporary Return 9000', returned_row.requester_user_id)
                    self.assertEqual(resubmitted.id, returned_model_id)
                    self.assertEqual(resubmitted.status, 'Pending')
                    app_module.logout_user()
            finally:
                app.config['UPLOAD_FOLDER'] = original_upload_folder
                with app.app_context():
                    app_module.db.session.remove()


if __name__ == '__main__':
    unittest.main()
