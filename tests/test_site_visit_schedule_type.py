"""Medical Center Visit - Site Visit: client-only schedules allow a TSR without equipment."""

import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_site_visit_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "site-visit-tests")

import app as app_module  # noqa: E402


class SiteVisitSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timeline = (ROOT / "templates" / "timeline.html").read_text(encoding="utf-8")
        cls.tsr = (ROOT / "templates" / "offline_tsr.html").read_text(encoding="utf-8")

    def test_calendar_offers_site_visit_type(self):
        self.assertIn('<option value="SiteVisit">Medical Center Visit - Site Visit</option>', self.timeline)
        self.assertIn("SITE_VISIT_TITLE_TOKEN = '[Site Visit]'", self.timeline)

    def test_tsr_gates_trust_server_flag_for_any_engineer(self):
        timeline_gate = self.timeline.split("function canCreateTSRWithoutEquipmentForSchedule", 1)[1].split("function ", 1)[0]
        tsr_gate = self.tsr.split("function isFrancisTSRWithoutEquipmentSchedule", 1)[1].split("function ", 1)[0]
        for gate in (timeline_gate, tsr_gate):
            self.assertIn("tsr_without_equipment_allowed === true", gate)


class SiteVisitTsrRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_approval_columns()
            suffix = uuid.uuid4().hex[:8]
            cls.user = app_module.User(
                username=f"site_visit_{suffix}",
                password=app_module.generate_password_hash("test-password"),
                role="engineer",
                is_active=True,
            )
            cls.profile = app_module.Engineer(
                employee_id=f"SV-{suffix}", name="Site Visit Engineer", initials="SE", branch="Manila"
            )
            cls.client = app_module.Client(name=f"Site Visit Client {suffix}", address="Test address")
            app_module.db.session.add_all([cls.user, cls.profile, cls.client])
            app_module.db.session.flush()
            cls.profile.user_id = cls.user.id
            app_module.db.session.commit()
            cls.user_id, cls.profile_id, cls.client_id = cls.user.id, cls.profile.id, cls.client.id

    def _shift(self, title, client_id):
        start = datetime.now().replace(microsecond=0) + timedelta(days=1)
        return app_module.Shift(
            title=title,
            start_time=start,
            end_time=start + timedelta(hours=2),
            engineer_id=self.profile_id,
            client_id=client_id,
            product_id=None,
            equipment_source="product",
        )

    def _validate(self, shift):
        from flask_login import login_user

        with self.app.test_request_context():
            login_user(app_module.db.session.get(app_module.User, self.user_id))
            return app_module.validate_tsr_shift_equipment(shift)

    def test_non_francis_engineer_can_create_tsr_on_site_visit(self):
        with self.app.app_context():
            shift = self._shift("Courtesy call [Site Visit]", self.client_id)
            self.assertTrue(app_module.is_site_visit_shift(shift))
            self.assertEqual(self._validate(shift)["status"], "without_equipment")
            self.assertNotIn("Equipment / Model", app_module.get_online_tsr_missing_core_details(
                shift, {"tsr-service-category": "Repair", "tsr-actions-taken": "Inspected"}
            ))

    def test_plain_visit_without_equipment_stays_blocked(self):
        with self.app.app_context():
            result = self._validate(self._shift("Courtesy call", self.client_id))
            self.assertEqual(result.get("reason"), "missing_equipment_assignment")

    def test_site_visit_without_client_is_not_eligible(self):
        with self.app.app_context():
            shift = self._shift("Courtesy call [Site Visit]", None)
            self.assertFalse(app_module.is_site_visit_shift(shift))
            self.assertEqual(self._validate(shift).get("status"), "blocked")


if __name__ == "__main__":
    unittest.main()
