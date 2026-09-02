"""Focused coverage for selectable Service Files email delivery.

The first run of this file is intentionally fail-first: these assertions describe the
new public shape and contracts before the application implementation is added.
"""

import inspect
import json
import pathlib
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
from tests.sw_cache_version import assert_cache_version_at_least


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ServiceFileDeliverySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        cls.timeline_source = (ROOT / "templates" / "timeline.html").read_text(encoding="utf-8")
        cls.settings_source = (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
        cls.releases_source = (ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8")

    def test_shift_file_sent_marker_and_public_attachment_shape_exist(self):
        self.assertIn("last_emailed_at", self.app_source)
        self.assertIn("selected_attachment_ids", self.app_source)
        self.assertIn("was_sent", self.app_source)
        self.assertIn("service_file_delivery", self.app_source)

    def test_service_file_labels_replace_outbound_tsr_labels(self):
        self.assertIn("Send Service Files", self.timeline_source)
        self.assertIn("Service Files Client Email CC", self.settings_source)
        self.assertIn("Service Files Client Email Subject", self.settings_source)
        self.assertIn("2026-09-02-service-file-delivery", self.releases_source)
        assert_cache_version_at_least(self, 119, self.app_source)

    def test_selection_controls_are_accessible_and_refresh_is_wired(self):
        for expected in (
            "Select Unsent",
            "Select All",
            'type="checkbox"',
            "refreshTimelineGrid()",
            "selected_attachment_ids",
            "attachments_changed",
        ):
            self.assertIn(expected, self.timeline_source)

    def test_delivery_summary_categories_and_hr_redaction_are_present(self):
        for expected in (
            "calibration_report",
            "calibration_certificate",
            "supporting",
            "not_applicable",
            "partial",
            "sent_count",
            "last_sent_at",
        ):
            self.assertIn(expected, self.app_source)
        redaction = inspect.getsource(app_module.redact_timeline_payload_for_hr)
        self.assertIn("service_file_delivery", redaction)


class ServiceFileDeliveryPureContractTests(unittest.TestCase):
    def test_attachment_serializer_exposes_sent_state(self):
        info = {
            "id": 41,
            "filename": "tsr.pdf",
            "display_name": "TSR.pdf",
            "uploaded_at": "2026-09-02T08:00:00+08:00",
            "service_date": "2026-09-01",
            "source_type": "generated",
            "source_label": "Generated TSR",
            "file_size": 12,
            "is_tsr": True,
            "was_sent": True,
            "last_emailed_at": "2026-09-02T09:00:00+08:00",
        }
        serialized = app_module.serialize_tsr_email_attachment(info)
        self.assertTrue(serialized["was_sent"])
        self.assertEqual(serialized["last_emailed_at"], info["last_emailed_at"])

    def test_existing_subject_rows_render_generalized_settings_label(self):
        template = SimpleNamespace(
            id=8,
            template_key="tsr_client_subject",
            template_type="subject",
            label="TSR Client Email Subject",
            description="Legacy label",
            template_value="[TSR] {client_name}",
            is_active=True,
            created_at=None,
            updated_at=None,
        )
        serialized = app_module.email_template_setting_to_dict(template)
        self.assertEqual(serialized["label"], "Service Files Client Email Subject")
        self.assertEqual(serialized["template_value"], template.template_value)

    def _package(self):
        return [
            {
                "id": 1,
                "shift_id": 17,
                "filename": "tsr.pdf",
                "display_name": "TSR.pdf",
                "path": "tsr.pdf",
                "is_tsr": True,
                "attachment_type": "tsr",
                "source_type": "generated",
                "source_label": "Generated TSR",
                "service_date": "2026-09-01",
                "last_emailed_at": "",
                "was_sent": False,
            },
            {
                "id": 2,
                "shift_id": 17,
                "filename": "certificate.pdf",
                "display_name": "Certificate.pdf",
                "path": "certificate.pdf",
                "is_tsr": False,
                "attachment_type": "supporting",
                "source_type": "calibration_certificate",
                "source_label": "Calibration Certificate",
                "service_date": "2026-09-01",
                "last_emailed_at": "2026-09-02T09:00:00+08:00",
                "was_sent": True,
            },
        ]

    def test_explicit_empty_selection_is_rejected(self):
        shift = SimpleNamespace(id=17, title="Service", files=[])
        with patch.object(app_module, "get_tsr_files_for_shift", return_value=self._package()[:1]), \
                patch.object(app_module, "get_tsr_email_files_for_shift", return_value=self._package()), \
                patch.object(app_module, "get_tsr_email_attachment_manifest_signature", return_value="manifest"):
            message, error, status = app_module.prepare_tsr_client_email_message(
                shift,
                {"emails": ["client@example.com"], "selected_attachment_ids": []},
            )
        self.assertIsNone(message)
        self.assertEqual(status, 400)
        self.assertIn("select", (error or "").lower())

    def test_stale_selection_is_rejected(self):
        shift = SimpleNamespace(id=17, title="Service", files=[])
        with patch.object(app_module, "get_tsr_files_for_shift", return_value=self._package()[:1]), \
                patch.object(app_module, "get_tsr_email_files_for_shift", return_value=self._package()), \
                patch.object(app_module, "get_tsr_email_attachment_manifest_signature", return_value="manifest"):
            message, error, status = app_module.prepare_tsr_client_email_message(
                shift,
                {
                    "emails": ["client@example.com"],
                    "selected_attachment_ids": [999],
                    "attachment_manifest_signature": "manifest",
                },
            )
        self.assertIsNone(message)
        self.assertEqual(status, 409)
        self.assertIn("attachment", (error or "").lower())

    def test_valid_subset_is_used_for_actual_attachments(self):
        shift = SimpleNamespace(id=17, title="Service", files=[])
        package = self._package()
        patches = (
            patch.object(app_module, "get_tsr_files_for_shift", return_value=package[:1]),
            patch.object(app_module, "get_tsr_email_files_for_shift", return_value=package),
            patch.object(app_module, "get_tsr_email_attachment_manifest_signature", return_value="manifest"),
            patch.object(app_module, "get_tsr_subject_package_metadata", return_value={"mixed": False, "scenarios": ["standard"]}),
            patch.object(app_module, "build_tsr_client_email_subject", return_value="Subject"),
            patch.object(app_module, "build_tsr_client_email_bodies", return_value=("Body", "<p>Body</p>")),
            patch.object(app_module, "append_tsr_email_correction_notice", side_effect=lambda shift, text, html: (text, html)),
            patch.object(app_module, "get_tsr_client_system_cc_emails", return_value=[]),
            patch.object(app_module, "get_current_user_email_for_tsr_cc", return_value=""),
            patch.object(app_module, "serialize_tsr_email_attachment", side_effect=lambda item: item),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
            message, error, status = app_module.prepare_tsr_client_email_message(
                shift,
                {"emails": ["client@example.com"], "selected_attachment_ids": [2]},
            )
        self.assertIsNone(error)
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in message["email_attachments"]], [2])

    def test_omitted_selection_keeps_select_all_compatibility(self):
        shift = SimpleNamespace(id=17, title="Service", files=[])
        package = self._package()
        patches = (
            patch.object(app_module, "get_tsr_files_for_shift", return_value=package[:1]),
            patch.object(app_module, "get_tsr_email_files_for_shift", return_value=package),
            patch.object(app_module, "get_tsr_email_attachment_manifest_signature", return_value="manifest"),
            patch.object(app_module, "get_tsr_subject_package_metadata", return_value={"mixed": False, "scenarios": ["standard"]}),
            patch.object(app_module, "build_tsr_client_email_subject", return_value="Subject"),
            patch.object(app_module, "build_tsr_client_email_bodies", return_value=("Body", "<p>Body</p>")),
            patch.object(app_module, "append_tsr_email_correction_notice", side_effect=lambda shift, text, html: (text, html)),
            patch.object(app_module, "get_tsr_client_system_cc_emails", return_value=[]),
            patch.object(app_module, "get_current_user_email_for_tsr_cc", return_value=""),
            patch.object(app_module, "serialize_tsr_email_attachment", side_effect=lambda item: item),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
            message, error, status = app_module.prepare_tsr_client_email_message(shift, {"emails": ["client@example.com"]})
        self.assertIsNone(error)
        self.assertEqual(status, 200)
        self.assertEqual(message["selected_attachment_ids"], [1, 2])
        self.assertEqual([item["id"] for item in message["email_attachments"]], [1, 2])

    def test_calibration_only_follow_up_does_not_claim_tsr_attached(self):
        shift = SimpleNamespace(id=17, title="Service", files=[])
        package = self._package()
        patches = (
            patch.object(app_module, "get_tsr_files_for_shift", return_value=package[:1]),
            patch.object(app_module, "get_tsr_email_files_for_shift", return_value=package),
            patch.object(app_module, "get_tsr_email_attachment_manifest_signature", return_value="manifest"),
            patch.object(app_module, "get_tsr_subject_package_metadata", return_value={"mixed": False, "scenarios": []}),
            patch.object(app_module, "build_tsr_client_email_subject", return_value="Subject"),
            patch.object(app_module, "build_tsr_client_email_bodies", return_value=(
                "Attached is the Technical Service Report (TSR) for the completed service visit.",
                "<p>Attached is the Technical Service Report (TSR) for the completed service visit.</p>",
            )),
            patch.object(app_module, "append_tsr_email_correction_notice", side_effect=lambda shift, text, html: (text, html)),
            patch.object(app_module, "get_tsr_client_system_cc_emails", return_value=[]),
            patch.object(app_module, "get_current_user_email_for_tsr_cc", return_value=""),
            patch.object(app_module, "serialize_tsr_email_attachment", side_effect=lambda item: item),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
            message, error, status = app_module.prepare_tsr_client_email_message(
                shift,
                {"emails": ["client@example.com"], "selected_attachment_ids": [2]},
            )
        self.assertIsNone(error)
        self.assertEqual(status, 200)
        self.assertNotIn("Technical Service Report (TSR)", message["text_body"])
        self.assertIn("No TSR document is attached", message["text_body"])
        self.assertEqual([item["id"] for item in message["email_attachments"]], [2])

    def test_correction_notice_requires_selected_revised_tsr(self):
        shift = SimpleNamespace(id=17, _service_file_selected_ids=[41])
        submission = SimpleNamespace(
            id=7,
            revision_no=2,
            revision_reason="Corrected serial number",
            created_at=datetime(2026, 9, 2, 8, 0),
            payload_json=json.dumps({"_attached_file_id": 41}),
        )
        with patch.object(app_module, "get_linked_schedule_file_shifts", return_value=[shift]), \
                patch.object(app_module, "get_latest_online_tsr_submission_for_shift", return_value=submission):
            text, html = app_module.append_tsr_email_correction_notice(shift, "Body", "<p>Body</p>")
        self.assertIn("Correction notice", text)
        self.assertIn("REV2", html)

        shift._service_file_selected_ids = [2]
        with patch.object(app_module, "get_linked_schedule_file_shifts", return_value=[shift]), \
                patch.object(app_module, "get_latest_online_tsr_submission_for_shift", return_value=submission):
            text, html = app_module.append_tsr_email_correction_notice(shift, "Body", "<p>Body</p>")
        self.assertEqual(text, "Body")
        self.assertEqual(html, "<p>Body</p>")

    def test_delivery_summary_uses_category_states(self):
        shift = SimpleNamespace(id=17, files=[])
        package = self._package()
        with patch.object(app_module, "get_tsr_email_files_for_shift", return_value=package):
            summary = app_module.get_shift_service_file_delivery_summary(shift)
        self.assertEqual(summary["overall"], "partial")
        self.assertEqual(summary["sent_count"], 1)
        self.assertEqual(summary["total_count"], 2)
        self.assertEqual(summary["categories"]["tsr"]["state"], "not_sent")
        self.assertEqual(summary["categories"]["calibration_certificate"]["state"], "sent")

    def test_conservative_backfill_marks_only_exact_proven_tsr(self):
        with app_module.app.app_context(), tempfile.TemporaryDirectory() as temp_root:
            app_module.db.create_all()
            engineer = app_module.Engineer(
                employee_id="delivery-backfill-test",
                name="Delivery Backfill Test",
                initials="DBT",
                branch="Manila",
            )
            app_module.db.session.add(engineer)
            app_module.db.session.flush()
            shift = app_module.Shift(
                title="Delivery backfill test",
                start_time=datetime(2026, 9, 1, 8, 0),
                end_time=datetime(2026, 9, 1, 17, 0),
                engineer_id=engineer.id,
            )
            app_module.db.session.add(shift)
            app_module.db.session.flush()
            tsr_file = app_module.ShiftFile(
                shift_id=shift.id,
                filename="TSR_delivery_backfill.pdf",
            )
            calibration_file = app_module.ShiftFile(
                shift_id=shift.id,
                filename="Calibration Certificate.pdf",
            )
            app_module.db.session.add_all([tsr_file, calibration_file])
            app_module.db.session.flush()
            submission = app_module.OnlineTsrSubmission(
                shift_id=shift.id,
                payload_json=json.dumps({
                    "_attached_file_id": tsr_file.id,
                    "_last_emailed_at": "2026-09-02T09:00:00+08:00",
                }),
                revision_no=1,
            )
            app_module.db.session.add(submission)
            app_module.db.session.commit()

            metadata_path = pathlib.Path(temp_root) / "_tsr_email_metadata.json"
            metadata_path.write_text(json.dumps({
                f"id:{tsr_file.id}": {
                    "source": "sent_tsr_email",
                    "emails": ["client@example.com"],
                },
            }), encoding="utf-8")

            with patch.dict(app_module.app.config, {"UPLOAD_FOLDER": temp_root}), \
                    patch.object(app_module, "_shift_file_last_emailed_at_ready", False):
                app_module.ensure_shift_file_last_emailed_at_column()

            app_module.db.session.expire_all()
            self.assertIsNotNone(app_module.db.session.get(app_module.ShiftFile, tsr_file.id).last_emailed_at)
            self.assertIsNone(app_module.db.session.get(app_module.ShiftFile, calibration_file.id).last_emailed_at)


class ServiceFileDeliveryRouteTests(unittest.TestCase):
    def _message(self):
        attachment = {
            "id": 21,
            "shift_id": 17,
            "filename": "TSR_route_test.pdf",
            "display_name": "TSR route test.pdf",
            "path": "TSR_route_test.pdf",
            "is_tsr": True,
            "attachment_type": "tsr",
            "source_type": "generated",
            "source_label": "Generated TSR",
            "was_sent": False,
            "last_emailed_at": "",
        }
        return {
            "recipient_emails": ["client@example.com"],
            "manual_cc": [],
            "system_cc": [],
            "sender_copy": [],
            "final_cc": [],
            "subject": "Service Files",
            "subject_scenario": "standard",
            "font_key": "arial",
            "font_stack": "Arial, sans-serif",
            "text_body": "Body",
            "html_body": "<p>Body</p>",
            "tsr_files": [attachment],
            "selected_attachments": [attachment],
            "email_attachments": [attachment],
            "selected_attachment_ids": [21],
            "sender_name": "Engineer",
        }

    def _request(self, provider_result, marker_result=None, marker_error=None):
        shift = SimpleNamespace(id=17, title="Route delivery")
        fake_user = SimpleNamespace(is_authenticated=True, username="engineer")
        patches = [
            patch.object(app_module, "current_user", fake_user),
            patch.object(app_module.db.session, "get", return_value=shift),
            patch.object(app_module, "can_work_on_existing_schedule_shift", return_value=True),
            patch.object(app_module, "prepare_tsr_client_email_message", return_value=(self._message(), None, 200)),
            patch.object(app_module, "send_email_with_attachments", return_value=provider_result),
            patch.object(app_module, "get_current_user_email_for_tsr_cc", return_value=""),
            patch.object(app_module, "get_user_remembered_tsr_client_cc_emails", return_value=[]),
            patch.object(app_module.db.session, "add"),
            patch.object(app_module.db.session, "commit"),
        ]
        marker_patch = patch.object(app_module, "mark_service_files_emailed", return_value=marker_result or [])
        if marker_error is not None:
            marker_patch = patch.object(app_module, "mark_service_files_emailed", side_effect=marker_error)
        patches.append(marker_patch)
        metadata_patch = patch.object(app_module, "save_tsr_email_metadata_for_file_infos", return_value=True)
        patches.append(metadata_patch)
        latest_patch = patch.object(app_module, "get_latest_online_tsr_submission_for_shift", return_value=None)
        patches.append(latest_patch)
        remember_patch = patch.object(app_module, "remember_tsr_client_cc_emails", return_value=[])
        patches.append(remember_patch)

        with app_module.app.test_request_context(
            "/send_tsr_client_email/17",
            method="POST",
            json={"emails": ["client@example.com"], "selected_attachment_ids": [21]},
        ):
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12]:
                response = app_module.send_tsr_client_email.__wrapped__(17)
        return response

    def test_provider_failure_does_not_track_files(self):
        with patch.object(app_module, "mark_service_files_emailed") as marker:
            result = self._request((False, "provider failed"))
        response = result[0] if isinstance(result, tuple) else result
        status_code = result[1] if isinstance(result, tuple) else response.status_code
        self.assertEqual(status_code, 500)
        marker.assert_not_called()

    def test_provider_success_returns_selected_attachment_state(self):
        tracked = [SimpleNamespace(id=21, last_emailed_at=datetime(2026, 9, 2, 9, 0))]
        response = self._request((True, "provider sent"), marker_result=tracked)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["selected_attachment_ids"], [21])
        self.assertTrue(payload["attachment_states"][0]["was_sent"])
        self.assertTrue(payload["attachment_states"][0]["last_emailed_at"])

    def test_tracking_failure_returns_success_warning_not_to_resend(self):
        response = self._request((True, "provider sent"), marker_error=RuntimeError("status write failed"))
        self.assertEqual(response.status_code, 200)
        message = response.get_json()["message"].lower()
        self.assertIn("email sent", message)
        self.assertIn("do not resend", message)


if __name__ == "__main__":
    unittest.main()
