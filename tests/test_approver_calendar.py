"""Approver-only accounts see the Calendar in the menu, and it opens view-only (2026-10-23)."""

import os
import pathlib
import tempfile
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_approver_calendar_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

READ_ONLY_APPROVER_TRUE = '"true" === "true";\n    const timelineReadOnlyHR'


class ApproverCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        suffix = uuid.uuid4().hex[:8]
        cls.user_ids, cls.engineer_ids = [], []
        with cls.app.app_context():
            app_module.db.create_all()
            approver = app_module.User(
                username=f'vp{suffix}', password=app_module.generate_password_hash('test-password'),
                role='approver', can_approve_requests=True, is_active=True,
            )
            engineer_user = app_module.User(
                username=f'eng{suffix}', password=app_module.generate_password_hash('test-password'),
                role='engineer', is_active=True,
            )
            app_module.db.session.add_all([approver, engineer_user])
            app_module.db.session.flush()
            # The approver keeps a Personnel row for the signature, as in production.
            for user, tag in ((approver, 'VP'), (engineer_user, 'EN')):
                engineer = app_module.Engineer(
                    user_id=user.id, employee_id=f'{tag}-{suffix}', name=f'{tag} Person {suffix}',
                    initials=f'{tag}{suffix[:3]}'.upper(), branch='Manila',
                )
                app_module.db.session.add(engineer)
                app_module.db.session.flush()
                cls.engineer_ids.append(engineer.id)
            app_module.db.session.commit()
            cls.approver_id, cls.engineer_user_id = approver.id, engineer_user.id
            cls.user_ids += [approver.id, engineer_user.id]

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for engineer_id in cls.engineer_ids:
                engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    app_module.db.session.delete(engineer)
            app_module.db.session.flush()
            app_module.ApprovalRouting.query.filter(app_module.or_(
                app_module.ApprovalRouting.requester_user_id.in_(cls.user_ids),
                app_module.ApprovalRouting.approver_user_id.in_(cls.user_ids),
            )).delete(synchronize_session=False)
            for user_id in cls.user_ids:
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.expire(user)
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def _client(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_approver_with_personnel_row_gets_a_read_only_calendar(self):
        client = self._client(self.approver_id)
        page = client.get('/timeline')
        self.assertEqual(page.status_code, 200)
        self.assertTrue(READ_ONLY_APPROVER_TRUE in page.get_data(as_text=True), 'read-only approver flag')
        self.assertEqual(client.get('/get_timeline_data?offset=0&branch=ALL').status_code, 200)

    def test_approver_menu_shows_calendar(self):
        html = self._client(self.approver_id).get('/approvals').get_data(as_text=True)
        nav = html.split('<nav class="sidebar-nav"', 1)[1].split('</nav>', 1)[0]
        self.assertTrue('href="/timeline"' in nav, 'Calendar link in the approver menu')
        self.assertFalse('href="/offline-tsr"' in nav, 'Create TSR stays hidden')

    def test_engineer_calendar_stays_editable(self):
        page = self._client(self.engineer_user_id).get('/timeline').get_data(as_text=True)
        self.assertFalse(READ_ONLY_APPROVER_TRUE in page, 'engineer is not read-only')


if __name__ == '__main__':
    unittest.main()
