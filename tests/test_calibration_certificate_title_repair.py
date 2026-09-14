"""Guarded one-time Calibration Certificate approver-title repair coverage.

The tests use only disposable external SQLite/storage fixtures and never touch the
repository scheduler.db.  The command is intentionally imported from ``scripts``
without importing the application until a test explicitly needs the real PDF
builder.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB = pathlib.Path(tempfile.gettempdir()) / f"medical_service_title_repair_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB))
os.environ.setdefault("SECRET_KEY", "calibration-title-repair-test-only")

import app as app_module  # noqa: E402
from scripts import repair_calibration_certificate_titles as repair  # noqa: E402


SIGNATURE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAHgAAAAeCAYAAADnydqVAAAAVElEQVR42u3WsQkAMAwEsdt/"
    "aWeDlMEEHfwCVuNGX5cTABZgARZgARZgAQYswAIswAKsJ8CVLRtgwIABy5MlwAIswAIswIA"
    "FWIAFWIAFWIAFWJcOqjWBWhan81EAAAAASUVORK5CYII="
)


def certificate_payload():
    return {
        "tsr-number": "TSR-TITLE-REPAIR",
        "calibration_report": {
            "certificate": {"bsid": "B-TITLE-01"},
            "facility": {"name": "Title Repair Clinic"},
            "machine": {
                "modality": "Digital Angiography System",
                "model": "MobileDart Evolution MX9",
                "serial_number": "SN-TITLE-01",
            },
            "calibration": {
                "machine_calibration_date": "2026-08-20",
                "next_calibration_date": "2027-08-20",
            },
        },
    }


class _FakeStorage:
    def __init__(self, root):
        self.root = pathlib.Path(root)
        self.mode = "volume"
        self.writes_volume = True
        self.writes_bucket = False
        self.bucket_enabled = False
        self.bucket_configured = False
        self.objects = {}
        self.write_order = []
        self.fail_replace = False

    def normalize_key(self, key):
        return "/".join(part for part in str(key).replace("\\", "/").split("/") if part not in {"", ".", ".."})

    def upload_bytes(self, key, data, **kwargs):
        self.write_order.append(("bucket", key))
        self.objects[self.normalize_key(key)] = bytes(data)

    def delete(self, key):
        self.objects.pop(self.normalize_key(key), None)


class _FakeSession:
    def __init__(self):
        self.commit_count = 0
        self.rollback_count = 0
        self.info = {}

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


class _FakeDb:
    def __init__(self):
        self.session = _FakeSession()


class _FakeApp:
    def __init__(self, root):
        self.app = SimpleNamespace(config={"UPLOAD_FOLDER": str(root)})
        self.db = _FakeDb()
        self.file_storage = _FakeStorage(root)
        self.STORAGE_PREFIX_REPORTS = "reports"
        self.CalibrationCertificateApproval = object
        self.ShiftFile = object
        self.User = object
        self._files = {}
        self._approvals = {}
        self._users = {}
        self.audit = []
        self.now = datetime(2026, 9, 14, 10, 0, 0)

    def get_shift_file_disk_name(self, file_rec):
        return file_rec.filename

    def get_shift_file_display_name(self, file_rec):
        return file_rec.original_filename or file_rec.filename

    def managed_storage_key(self, prefix, local_path):
        return self.file_storage.normalize_key(f"{prefix}/{pathlib.Path(local_path).name}")

    def managed_storage_content_type(self, filename, fallback="application/octet-stream"):
        return "application/pdf" if str(filename).lower().endswith(".pdf") else fallback

    def get_manila_today(self):
        return self.now.date()

    def get_manila_time(self):
        return self.now

    def ensure_calibration_certificate_approval_table(self):
        return None

    def ensure_universal_approval_audit_table(self):
        return None

    def record_universal_approval_audit(self, *args, **kwargs):
        self.audit.append({"args": args, "kwargs": kwargs})

    def calibration_certificate_mapped_snapshot(self, raw):
        snapshot = json.loads(raw or "{}") if isinstance(raw, str) else raw
        fields = ("Textfield", "Text1", "Text2", "Text3", "Text4", "Text5", "Text6", "Textfield-0")
        if not isinstance(snapshot, dict) or any(not str(snapshot.get(field) or "").strip() for field in fields):
            return None
        return {field: snapshot[field] for field in fields}

    def parse_online_tsr_payload_json(self, submission):
        return json.loads(submission.payload_json or "{}")

    def build_calibration_certificate_pdf(self, *args, **kwargs):
        return app_module.build_calibration_certificate_pdf(*args, **kwargs)

    def _read_file_bytes(self, file_rec):
        return self._files[file_rec.id]


def _fake_approval(user, *, approval_id=1, status="Approved", latest=True, title_snapshot="Old Title", rendered_title="Old Title"):
    file_rec = SimpleNamespace(
        id=approval_id + 100,
        filename=f"signed-{approval_id}.pdf",
        original_filename=f"Calibration_Certificate_CERT-{approval_id}.pdf",
        shift_id=41,
        online_tsr_submission_id=51,
    )
    submission = SimpleNamespace(id=51, shift_id=41, payload_json=json.dumps({"tsr-number": "TSR"}))
    mapped = {
        "Textfield": f"CERT-{approval_id}", "Text1": "Equipment", "Text2": "Model",
        "Text3": "SN", "Text4": "2026/08/20", "Text5": "2027/08/20",
        "Text6": "Clinic", "Textfield-0": "TSR",
    }
    approval = SimpleNamespace(
        id=approval_id,
        shift_id=41,
        online_tsr_submission_id=51,
        revision_no=1,
        is_latest=latest,
        status=status,
        certificate_number=f"CERT-{approval_id}",
        mapped_data_json=json.dumps(mapped),
        template_sha256=getattr(app_module, "CALIBRATION_CERTIFICATE_RUNTIME_SHA256", ""),
        signed_shift_file_id=file_rec.id,
        no_signature_shift_file_id=approval_id + 200,
        approver_user_id=user.id,
        approver=user,
        approver_name_snapshot=user.name,
        approver_title_snapshot=title_snapshot,
        approver_signature_snapshot=SIGNATURE,
        approved_at=datetime(2026, 8, 20, 12, 0, 0),
        artifact_created_at=datetime(2026, 8, 20, 12, 0, 0),
        updated_at=datetime(2026, 8, 20, 12, 0, 0),
        signed_shift_file=file_rec,
        online_tsr_submission=submission,
        _rendered_title=rendered_title,
    )
    return approval, file_rec, submission


class CalibrationCertificateTitleResolutionTests(unittest.TestCase):
    def setUp(self):
        self.app = app_module.app

    def _pdf(self, name, title):
        with self.app.app_context():
            data, values, fingerprint = app_module.build_calibration_certificate_pdf(
                certificate_payload(), approver=name, signature_data=SIGNATURE,
                approval_title=title, certificate_number_override="2026-0820-B-TITLE-01",
                mapped_values_override={
                    "Textfield": "2026-0820-B-TITLE-01", "Text1": "Digital Angiography System",
                    "Text2": "MobileDart Evolution MX9", "Text3": "SN-TITLE-01",
                    "Text4": "2026/08/20", "Text5": "2027/08/20", "Text6": "Title Repair Clinic",
                    "Textfield-0": "TSR-TITLE-REPAIR",
                },
            )
        return data, values, fingerprint

    def test_rendered_title_resolution_supports_robert_and_rodito(self):
        for username, name in (("robert", "Robert Rio"), ("rodito", "Rodito Aretano")):
            with self.subTest(username=username):
                pdf_bytes, _, _ = self._pdf(name, "Calibration Manager")
                self.assertEqual(repair.extract_rendered_title(pdf_bytes, expected_name=name), "Calibration Manager")

    def test_stale_pdf_is_candidate_when_snapshot_already_matches_current_title(self):
        pdf_bytes, _, _ = self._pdf("Robert Rio", "Old Title")
        user = SimpleNamespace(id=1, username="robert", name="Robert Rio", approval_title="New Title")
        approval, file_rec, submission = _fake_approval(user, title_snapshot="New Title")
        fake = _FakeApp(tempfile.mkdtemp(prefix="title-repair-inspect-"))
        fake._files[file_rec.id] = pdf_bytes
        with patch.object(repair, "_read_signed_certificate_bytes", return_value=pdf_bytes), \
                patch.object(repair, "_submission_for_approval", return_value=submission):
            result = repair.inspect_approval(fake, approval)
        self.assertTrue(result["eligible"])
        self.assertFalse(result["stored_title_mismatch"])
        self.assertTrue(result["rendered_title_mismatch"])

    def test_pending_historical_and_unrelated_users_are_excluded(self):
        for username, status, latest in (("robert", "Pending", True), ("robert", "Approved", False), ("jane", "Approved", True)):
            with self.subTest(username=username, status=status, latest=latest):
                user = SimpleNamespace(id=1, username=username, name=username.title(), approval_title="New Title")
                approval, file_rec, submission = _fake_approval(user, status=status, latest=latest)
                fake = _FakeApp(tempfile.mkdtemp(prefix="title-repair-exclusion-"))
                fake._files[file_rec.id] = b"not a pdf"
                with patch.object(repair, "_read_signed_certificate_bytes", return_value=b"not a pdf"), \
                        patch.object(repair, "_submission_for_approval", return_value=submission):
                    result = repair.inspect_approval(fake, approval)
                self.assertFalse(result["eligible"])


class CalibrationCertificateTitleRepairGuardTests(unittest.TestCase):
    def test_apply_requires_explicit_ids_and_expected_count(self):
        with self.assertRaises(repair.RepairGuardError):
            repair.run_repair(Mock(), apply=True, approval_ids=[], expected_count=0)
        with self.assertRaises(repair.RepairGuardError):
            repair.run_repair(Mock(), apply=True, approval_ids=[1, 2], expected_count=1)

    def test_dry_run_never_writes_storage_or_commits(self):
        fake = Mock()
        fake.db.session.commit = Mock()
        fake.db.session.rollback = Mock()
        with patch.object(repair, "_collect_approval_rows", return_value=[]), \
                patch.object(repair, "_apply_one", side_effect=AssertionError("dry-run must not apply")):
            result = repair.run_repair(fake, apply=False)
        self.assertEqual(result["mode"], "dry-run")
        fake.db.session.commit.assert_not_called()

    def test_cli_parser_supports_repeatable_approver_and_approval_id(self):
        args = repair.parse_args(["--approver", "robert", "--approver", "rodito", "--approval-id", "3", "--approval-id", "4", "--expected-count", "2", "--apply"])
        self.assertEqual(args.approvers, ["robert", "rodito"])
        self.assertEqual(args.approval_ids, [3, 4])
        self.assertTrue(args.apply)


class CalibrationCertificateTitleRepairStorageTests(unittest.TestCase):
    def test_backup_precedes_replace_and_backup_hash_is_verified(self):
        with tempfile.TemporaryDirectory(prefix="title-repair-storage-") as root:
            fake = _FakeApp(root)
            target = pathlib.Path(root) / "signed.pdf"
            original = b"original-certificate"
            replacement = b"replacement-certificate"
            target.write_bytes(original)
            calls = []

            with patch.object(repair, "_storage_write_bytes", side_effect=lambda *args, **kwargs: calls.append((args, kwargs)) or repair._real_storage_write_bytes(*args, **kwargs)):
                backup = repair._backup_original(fake, "1", str(target), original, "Certificate.pdf")
                repair._replace_certificate_storage(fake, str(target), replacement, "Certificate.pdf")

            self.assertEqual(target.read_bytes(), replacement)
            self.assertEqual(hashlib.sha256(pathlib.Path(backup["path"]).read_bytes()).hexdigest(), backup["sha256"])
            self.assertEqual([item[1].get("purpose") for item in calls], ["backup", "replacement"])

    def test_restore_after_storage_failure_keeps_original_bytes(self):
        with tempfile.TemporaryDirectory(prefix="title-repair-restore-") as root:
            fake = _FakeApp(root)
            target = pathlib.Path(root) / "signed.pdf"
            original = b"original-certificate"
            target.write_bytes(original)
            original_writer = repair._storage_write_bytes
            calls = []

            def failing_replace(*args, **kwargs):
                calls.append(kwargs.get("purpose"))
                if kwargs.get("purpose") == "replacement":
                    raise OSError("replace failed")
                return original_writer(*args, **kwargs)

            with patch.object(repair, "_storage_write_bytes", side_effect=failing_replace):
                backup = repair._backup_original(fake, "2", str(target), original, "Certificate.pdf")
                with self.assertRaises(OSError):
                    try:
                        repair._replace_certificate_storage(fake, str(target), b"new", "Certificate.pdf")
                    finally:
                        repair._restore_original(fake, str(target), original, "Certificate.pdf")
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(backup["sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(calls, ["backup", "replacement", "restore"])


class CalibrationCertificateTitleRepairPdfTests(unittest.TestCase):
    def test_real_pdf_verification_requires_letter_flattened_and_current_identity(self):
        with app_module.app.app_context():
            data, values, fingerprint = app_module.build_calibration_certificate_pdf(
                certificate_payload(), approver="Robert Rio", signature_data=SIGNATURE,
                approval_title="Calibration Manager", certificate_number_override="2026-0820-B-TITLE-01",
                mapped_values_override={
                    "Textfield": "2026-0820-B-TITLE-01", "Text1": "Digital Angiography System",
                    "Text2": "MobileDart Evolution MX9", "Text3": "SN-TITLE-01",
                    "Text4": "2026/08/20", "Text5": "2027/08/20", "Text6": "Title Repair Clinic",
                    "Textfield-0": "TSR-TITLE-REPAIR",
                },
            )
        verified = repair.verify_regenerated_certificate(
            data,
            mapped_values=values,
            approver_name="Robert Rio",
            approval_title="Calibration Manager",
            signature_data=SIGNATURE,
        )
        self.assertEqual(verified["sha256"], fingerprint)
        self.assertEqual(verified["page_count"], 1)
        self.assertEqual(verified["division_count"], 1)
        self.assertEqual(repair.extract_rendered_title(data, expected_name="Robert Rio"), "Calibration Manager")

    def test_audit_and_metadata_contract_are_explicit(self):
        source = pathlib.Path(repair.__file__).read_text(encoding="utf-8")
        for required in ("approver_title_snapshot", "certificate_fingerprint", "artifact_created_at", "updated_at", "old_sha256", "new_sha256", "title_repaired"):
            self.assertIn(required, source)


class CalibrationCertificateTitleRepairIntegrationTests(unittest.TestCase):
    """Exercise the real DB/storage/audit path against one disposable DB."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.db = app_module.db

    def setUp(self):
        self.original_upload_folder = self.app.config.get("UPLOAD_FOLDER")
        self.storage = tempfile.TemporaryDirectory(prefix="calibration_title_repair_integration_")
        self.app.config["UPLOAD_FOLDER"] = self.storage.name
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
        self.app.config["UPLOAD_FOLDER"] = self.original_upload_folder
        self.storage.cleanup()

    def _make_approval(self, *, username="robert", name="Robert Rio", current_title="New Current Title", old_title="Old Title", status="Approved", latest=True):
        suffix = uuid.uuid4().hex[:8]
        payload = certificate_payload()
        payload["tsr-number"] = f"TSR-{suffix}"
        payload["calibration_report"]["certificate"]["bsid"] = f"B-{suffix}"
        payload["calibration_report"]["machine"]["serial_number"] = f"SN-{suffix}"
        mapped = {
            "Textfield": f"2026-0820-B-{suffix}",
            "Text1": "Digital Angiography System",
            "Text2": "MobileDart Evolution MX9",
            "Text3": f"SN-{suffix}",
            "Text4": "2026/08/20",
            "Text5": "2027/08/20",
            "Text6": "Title Repair Clinic",
            "Textfield-0": payload["tsr-number"],
        }
        with self.app.app_context():
            engineer = app_module.Engineer(employee_id=f"TITLE-{suffix}", name=f"Title Engineer {suffix}", initials="TE")
            user = app_module.User(username=username, password="test-only", role="superadmin", approval_title=current_title)
            self.db.session.add_all([engineer, user])
            self.db.session.flush()
            shift = app_module.Shift(
                title=f"Title Repair {suffix}",
                start_time=datetime(2026, 8, 20),
                end_time=datetime(2026, 8, 20, 1),
                engineer_id=engineer.id,
                status="Completed",
            )
            self.db.session.add(shift)
            self.db.session.flush()
            submission = app_module.OnlineTsrSubmission(
                shift_id=shift.id,
                tsr_number=payload["tsr-number"],
                status="completed",
                submission_token=f"title-repair-{suffix}",
                payload_json=json.dumps(payload),
                submitted_by_user_id=user.id,
                revision_no=1,
                is_latest=True,
            )
            self.db.session.add(submission)
            self.db.session.flush()
            signed_name = f"shift_{shift.id}_{suffix}_signed.pdf"
            old_bytes, _, old_fingerprint = app_module.build_calibration_certificate_pdf(
                payload,
                approver=name,
                signature_data=SIGNATURE,
                approval_title=old_title,
                certificate_number_override=mapped["Textfield"],
                mapped_values_override=mapped,
            )
            pathlib.Path(self.storage.name, signed_name).write_bytes(old_bytes)
            signed_file = app_module.ShiftFile(
                shift_id=shift.id,
                filename=signed_name,
                original_filename=f"Calibration_Certificate_{suffix}.pdf",
                online_tsr_submission_id=submission.id,
            )
            no_signature_name = f"shift_{shift.id}_{suffix}_no_signature.pdf"
            no_signature_bytes = b"immutable no-signature copy"
            pathlib.Path(self.storage.name, no_signature_name).write_bytes(no_signature_bytes)
            no_signature_file = app_module.ShiftFile(
                shift_id=shift.id,
                filename=no_signature_name,
                original_filename=f"Calibration_Certificate_{suffix}_No_Signature.pdf",
                online_tsr_submission_id=submission.id,
            )
            self.db.session.add_all([signed_file, no_signature_file])
            self.db.session.flush()
            approval = app_module.CalibrationCertificateApproval(
                shift_id=shift.id,
                online_tsr_submission_id=submission.id,
                requester_user_id=user.id,
                revision_no=1,
                is_latest=latest,
                status=status,
                certificate_fingerprint=old_fingerprint,
                certificate_number=mapped["Textfield"],
                mapped_data_json=json.dumps(mapped),
                template_sha256=app_module.CALIBRATION_CERTIFICATE_RUNTIME_SHA256,
                unsigned_artifact_path="private-review.pdf",
                signed_shift_file_id=signed_file.id,
                no_signature_shift_file_id=no_signature_file.id,
                approver_user_id=user.id,
                approver_name_snapshot=name,
                approver_title_snapshot=old_title,
                approver_signature_snapshot=SIGNATURE,
                approved_at=datetime(2026, 8, 20),
                artifact_created_at=datetime(2026, 8, 20),
                updated_at=datetime(2026, 8, 20),
            )
            self.db.session.add(approval)
            self.db.session.commit()
            return approval.id, signed_name, no_signature_name, old_bytes, no_signature_bytes

    def test_apply_preserves_linkage_metadata_and_no_signature_and_records_audit(self):
        approval_id, signed_name, no_signature_name, old_bytes, no_signature_bytes = self._make_approval()
        with self.app.app_context():
            before = self.db.session.get(app_module.CalibrationCertificateApproval, approval_id)
            before_ids = (before.signed_shift_file_id, before.no_signature_shift_file_id, before.revision_no, before.certificate_number, before.online_tsr_submission_id)
            result = repair.run_repair(app_module, approvers=["robert"], approval_ids=[approval_id], apply=True, expected_count=1)
            self.assertFalse(result["errors"])
            after = self.db.session.get(app_module.CalibrationCertificateApproval, approval_id)
            self.assertEqual(after.approver_title_snapshot, "New Current Title")
            self.assertEqual(after.signed_shift_file_id, before_ids[0])
            self.assertEqual(after.no_signature_shift_file_id, before_ids[1])
            self.assertEqual((after.revision_no, after.certificate_number, after.online_tsr_submission_id), before_ids[2:])
            self.assertNotEqual(after.certificate_fingerprint, hashlib.sha256(old_bytes).hexdigest())
            self.assertEqual(pathlib.Path(self.storage.name, no_signature_name).read_bytes(), no_signature_bytes)
            self.assertEqual(repair.extract_rendered_title(pathlib.Path(self.storage.name, signed_name).read_bytes(), "Robert Rio"), "New Current Title")
            audit = app_module.UniversalApprovalAuditTrail.query.filter_by(module="calibration_certificate", record_id=approval_id, action="title_repaired").one()
            metadata = json.loads(audit.metadata_json)
            self.assertEqual(metadata["old_title"], "Old Title")
            self.assertEqual(metadata["new_title"], "New Current Title")
            self.assertEqual(metadata["old_sha256"], hashlib.sha256(old_bytes).hexdigest())
            self.assertEqual(metadata["new_sha256"], after.certificate_fingerprint)

    def test_dry_run_does_not_write_bytes_metadata_or_audit(self):
        approval_id, signed_name, _, old_bytes, _ = self._make_approval()
        with self.app.app_context():
            before = self.db.session.get(app_module.CalibrationCertificateApproval, approval_id)
            before_state = (before.approver_title_snapshot, before.certificate_fingerprint, before.artifact_created_at, before.updated_at)
            result = repair.run_repair(app_module, approvers=["robert"], approval_ids=[approval_id], apply=False)
            self.assertEqual(result["summary"]["eligible"], 1)
            self.assertEqual(pathlib.Path(self.storage.name, signed_name).read_bytes(), old_bytes)
            self.db.session.expire_all()
            after = self.db.session.get(app_module.CalibrationCertificateApproval, approval_id)
            self.assertEqual((after.approver_title_snapshot, after.certificate_fingerprint, after.artifact_created_at, after.updated_at), before_state)
            self.assertEqual(app_module.UniversalApprovalAuditTrail.query.filter_by(record_id=approval_id).count(), 0)

    def test_apply_is_idempotent_and_second_run_adds_no_audit_or_backup(self):
        approval_id, _, _, _, _ = self._make_approval()
        with self.app.app_context():
            first = repair.run_repair(app_module, approvers=["robert"], approval_ids=[approval_id], apply=True, expected_count=1)
            self.assertEqual(first["summary"]["applied"], 1)
            audit_count = app_module.UniversalApprovalAuditTrail.query.filter_by(record_id=approval_id, action="title_repaired").count()
            second = repair.run_repair(app_module, approvers=["robert"], approval_ids=[approval_id], apply=True, expected_count=1)
            self.assertEqual(second["summary"]["already_current"], 1)
            self.assertEqual(second["summary"]["applied"], 0)
            self.assertEqual(app_module.UniversalApprovalAuditTrail.query.filter_by(record_id=approval_id, action="title_repaired").count(), audit_count)

    def test_status_change_is_rejected_without_storage_or_db_mutation(self):
        approval_id, signed_name, _, old_bytes, _ = self._make_approval()
        with self.app.app_context():
            approval = self.db.session.get(app_module.CalibrationCertificateApproval, approval_id)
            approval.status = "Returned"
            self.db.session.commit()
            result = repair.run_repair(app_module, approvers=["robert"], approval_ids=[approval_id], apply=True, expected_count=1)
            self.assertEqual(result["summary"]["errors"], 1)
            self.assertEqual(pathlib.Path(self.storage.name, signed_name).read_bytes(), old_bytes)
            self.assertEqual(app_module.UniversalApprovalAuditTrail.query.filter_by(record_id=approval_id).count(), 0)

    def test_storage_failure_restores_original_and_database_failure_rolls_back(self):
        approval_id, signed_name, _, old_bytes, _ = self._make_approval()
        with self.app.app_context():
            with patch.object(repair, "_replace_certificate_storage", side_effect=OSError("storage failure")):
                result = repair.run_repair(app_module, approvers=["robert"], approval_ids=[approval_id], apply=True, expected_count=1)
            self.assertEqual(result["summary"]["errors"], 1)
            self.assertEqual(pathlib.Path(self.storage.name, signed_name).read_bytes(), old_bytes)
            approval = self.db.session.get(app_module.CalibrationCertificateApproval, approval_id)
            self.assertEqual(approval.approver_title_snapshot, "Old Title")

            original_commit = self.db.session.commit
            with patch.object(self.db.session, "commit", side_effect=RuntimeError("database failure")):
                result = repair.run_repair(app_module, approvers=["robert"], approval_ids=[approval_id], apply=True, expected_count=1)
            self.assertEqual(result["summary"]["errors"], 1)
            self.assertEqual(pathlib.Path(self.storage.name, signed_name).read_bytes(), old_bytes)
            self.db.session.commit = original_commit
            self.db.session.expire_all()
            approval = self.db.session.get(app_module.CalibrationCertificateApproval, approval_id)
            self.assertEqual(approval.approver_title_snapshot, "Old Title")
            self.assertEqual(app_module.UniversalApprovalAuditTrail.query.filter_by(record_id=approval_id, action="title_repaired").count(), 0)


if __name__ == "__main__":
    unittest.main()
