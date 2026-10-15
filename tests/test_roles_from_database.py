"""User roles plan (2026-10-15): rights come from User.role and per-account switches, never usernames."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_roles_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


def _account(username, role, **extra):
    return types.SimpleNamespace(username=username, role=role, is_authenticated=True, is_active=True, **extra)


class RoleHelperTests(unittest.TestCase):
    def test_renaming_a_scheduler_keeps_its_rights(self):
        for name in ('diary', 'renamed_scheduler'):
            account = _account(name, 'scheduler')
            self.assertTrue(app_module.is_scheduler_user(account))
            self.assertTrue(app_module.is_superadmin_user(account))
            self.assertFalse(app_module.is_manager_dashboard_user(account))

    def test_changing_the_role_changes_the_rights(self):
        account = _account('rodito', 'manager')
        self.assertTrue(app_module.is_manager_primary_user(account))
        self.assertTrue(app_module.is_admin_authorized(account))
        account.role = 'engineer'
        self.assertFalse(app_module.is_manager_primary_user(account))
        self.assertFalse(app_module.is_admin_authorized(account))

    def test_superadmin_role_alone_grants_superadmin_rights(self):
        # The stray 'hannah' login had the role but no name-list entry, so no rights.
        self.assertTrue(app_module.is_superadmin_user(_account('hannah', 'superadmin')))

    def test_regional_admin_comes_from_the_role(self):
        self.assertTrue(app_module.is_regional_admin_user(_account('any_regional', 'regional_admin')))
        self.assertFalse(app_module.is_regional_admin_user(_account('kevin', 'engineer')))

    def test_support_engineer_is_an_engineer_that_cannot_do_field_work(self):
        account = _account('se', 'support_engineer', can_approve_requests=False)
        self.assertTrue(app_module.is_engineer_type(account))
        self.assertTrue(app_module.is_support_engineer(account))
        self.assertFalse(app_module.can_do_field_work(account))
        self.assertFalse(app_module.can_back_up_tsr_drafts(account))
        self.assertTrue(app_module.can_do_field_work(_account('eng', 'engineer', can_approve_requests=False)))

    def test_protected_account_cannot_be_reset_by_another_superadmin(self):
        protected = _account('dev', 'superadmin', id=1, is_protected_account=True)
        other = _account('boss', 'superadmin', id=2)
        allowed, _ = app_module.can_reset_password_for_user(protected, other)
        self.assertFalse(allowed)
        self.assertTrue(app_module.is_engineer_primary_user(protected))
        self.assertFalse(app_module.is_engineer_primary_user(other))
        # Positive control: the same actor may reset an unprotected account.
        allowed, _ = app_module.can_reset_password_for_user(_account('x', 'engineer', id=3), other)
        self.assertTrue(allowed)

    def test_scheduler_cannot_reset_admin_or_engineer_type_passwords(self):
        scheduler = _account('s', 'scheduler', id=10)
        for role in ('superadmin', 'manager', 'scheduler', 'engineer', 'support_engineer'):
            allowed, _ = app_module.can_reset_password_for_user(_account('t', role, id=11), scheduler)
            self.assertFalse(allowed, role)
        allowed, _ = app_module.can_reset_password_for_user(_account('t', 'staff', id=11), scheduler)
        self.assertTrue(allowed)


class RoleMigrationTests(unittest.TestCase):
    """Runs the one-time migration in a separate process on its own database."""

    SCRIPT = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import app as m
from werkzeug.security import generate_password_hash as h
with m.app.app_context():
    m.db.create_all()
    m.ensure_user_admin_capability_columns()
    m.ensure_approval_routing_schema()
    def user(name, role):
        u = m.User(username=name, role=role, is_active=True, password=h('x'))
        m.db.session.add(u); m.db.session.flush(); return u
    rodito, diary, hanna = user('rodito', 'superadmin'), user('diary', 'superadmin'), user('hanna', 'superadmin')
    jonamar, stray, hannah = user('jonamar', 'superadmin'), user('diarydizon', 'engineer'), user('hannah', 'superadmin')
    lone = user('lone_engineer', 'engineer')
    m.db.session.add(m.Engineer(employee_id='12-139', name='Diary Dizon', initials='DD', user_id=stray.id))
    m.db.session.add(m.ApprovalRouting(requester_user_id=hannah.id, approver_user_id=rodito.id, request_scope='all', active=True))
    m.db.session.add(m.ApprovalRouting(requester_user_id=lone.id, approver_user_id=rodito.id, request_scope='all', active=False))
    m.db.session.add(m.TsrDraft(user_id=hannah.id, draft_key='k', payload_json='{}'))
    m.db.session.commit()
    m.run_role_migrations()
    m._role_migrations_checked = False
    diary.role = 'engineer'; m.db.session.commit()   # a later Settings change must survive
    m.run_role_migrations()
    names = {u.username: [u.role, bool(u.is_active), bool(u.is_protected_account), bool(u.is_default_approver)]
             for u in m.User.query.all()}
    profile = m.Engineer.query.filter_by(employee_id='12-139').first()
    route = m.ApprovalRouting.query.filter_by(requester_user_id=lone.id).first()
    print('RESULT' + json.dumps({'users': names, 'profile_owner': profile.user_id == diary.id,
                                 'lone_route_active': bool(route.active)}))
'''

    def test_migration_moves_roles_once_and_keeps_accounts_with_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, MEDICAL_SERVICE_TEST_DB=str(pathlib.Path(tmp) / 'roles.db'), PYTHONUTF8='1')
            env.pop('RAILWAY_ENVIRONMENT', None)
            done = subprocess.run([sys.executable, '-c', self.SCRIPT, str(ROOT)], cwd=tmp, env=env,
                                  capture_output=True, text=True, timeout=240)
            line = next((l for l in done.stdout.splitlines() if l.startswith('RESULT')), None)
            self.assertIsNotNone(line, done.stdout[-2000:] + done.stderr[-4000:])
            result = json.loads(line[len('RESULT'):])
        users = result['users']
        self.assertEqual(users['rodito'][0], 'manager')
        self.assertTrue(users['rodito'][3], 'rodito becomes the default approver')
        self.assertEqual(users['hanna'][0], 'scheduler')
        self.assertEqual(users['diary'][0], 'engineer', 'the second run must not undo a Settings change')
        self.assertTrue(users['jonamar'][2], 'jonamar becomes the protected account')
        self.assertNotIn('diarydizon', users)
        self.assertTrue(result['profile_owner'])
        # Owns a TSR draft, so it is kept, inactive -- never deleted with its history.
        self.assertIn('hannah', users)
        self.assertFalse(users['hannah'][1])
        self.assertTrue(result['lone_route_active'], 'a requester with no active route is routed to the default approver')


class RoleRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.ids = {}
        suffix = uuid.uuid4().hex[:8]
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_admin_capability_columns()
            app_module.ensure_approval_routing_schema()

            def user(key, role, **extra):
                account = app_module.User(username=f'roles_{key}_{suffix}', role=role, is_active=True,
                                          password=app_module.generate_password_hash('x'), **extra)
                app_module.db.session.add(account)
                app_module.db.session.flush()
                cls.ids[key] = account.id
                return account

            user('super', 'superadmin')
            user('super2', 'superadmin')
            user('protected', 'superadmin', is_protected_account=True)
            user('approver', 'engineer', can_approve_requests=True, is_default_approver=True)
            user('staff', 'staff')
            support = user('support', 'support_engineer')
            engineer = user('engineer', 'engineer')
            app_module.db.session.add(app_module.Engineer(
                employee_id=f'SE-{suffix}', name=f'Support {suffix}', initials=f'S{suffix[:3]}', branch='Manila',
                user_id=support.id))
            app_module.db.session.add(app_module.Engineer(
                employee_id=f'EN-{suffix}', name=f'Engineer {suffix}', initials=f'E{suffix[:3]}', branch='Manila',
                user_id=engineer.id))
            app_module.db.session.commit()

    def client(self, key):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.ids[key])
            session['_fresh'] = True
        return client

    def change_role(self, actor, target, role):
        return self.client(actor).post('/settings/update-user-role', json={'user_id': self.ids[target], 'role': role})

    def test_role_dropdown_rules_and_audit(self):
        self.assertEqual(self.change_role('super', 'super', 'engineer').status_code, 403)       # own account
        self.assertEqual(self.change_role('super', 'protected', 'engineer').status_code, 403)   # protected
        self.assertEqual(self.change_role('super', 'staff', 'wizard').status_code, 400)        # bad value
        self.assertEqual(self.change_role('staff', 'engineer', 'staff').status_code, 403)      # not superadmin
        self.assertEqual(self.change_role('super', 'staff', 'approver').status_code, 400)      # no Can Approve
        changed = self.change_role('super', 'staff', 'support_engineer')
        self.assertEqual(changed.status_code, 200, changed.get_data(as_text=True))
        self.assertEqual(changed.get_json()['display_role'], 'Support Engineer')
        with self.app.app_context():
            audit = app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.ilike('%Changed role of roles_staff_%')).first()
            self.assertIsNotNone(audit)
            self.assertIn('Staff -> Support Engineer', audit.action)
        self.assertEqual(self.change_role('super', 'staff', 'staff').status_code, 200)

    def test_last_active_superadmin_cannot_be_demoted(self):
        with self.app.app_context():
            account = app_module.db.session.get(app_module.User, self.ids['super2'])
            others = app_module.User.query.filter(
                app_module.User.role.in_(app_module.SUPERADMIN_FAMILY_ROLES), app_module.User.id != account.id).all()
            saved = [(u, u.is_active) for u in others]
            for other in others:
                other.is_active = False
            app_module.db.session.commit()
            try:
                with self.app.test_request_context():
                    from flask_login import login_user
                    actor = app_module.User(id=-1, username='ghost', role='superadmin', is_active=True)
                    login_user(actor)
                    self.assertEqual(app_module.role_change_denial(account, 'engineer'),
                                     'This is the last active superadmin account.')
            finally:
                for other, active in saved:
                    other.is_active = active
                app_module.db.session.commit()

    def test_protected_switch_only_by_a_protected_account(self):
        refused = self.client('super').post('/settings/update-approval-user', json={
            'user_id': self.ids['protected'], 'is_protected_account': False, 'is_active': True})
        self.assertEqual(refused.status_code, 400)
        deactivate = self.client('super').post('/settings/update-approval-user', json={
            'user_id': self.ids['protected'], 'is_active': False})
        self.assertEqual(deactivate.status_code, 400)
        with self.app.app_context():
            self.assertTrue(app_module.db.session.get(app_module.User, self.ids['protected']).is_protected_account)

    def test_tsr_grant_is_any_engineer_with_a_profile_and_never_staff(self):
        granted = self.client('super').post('/settings/update-approval-user', json={
            'user_id': self.ids['engineer'], 'can_create_tsr_without_equipment': True, 'is_active': True})
        self.assertEqual(granted.status_code, 200, granted.get_data(as_text=True))
        refused = self.client('super').post('/settings/update-approval-user', json={
            'user_id': self.ids['staff'], 'can_create_tsr_without_equipment': True, 'is_active': True})
        self.assertEqual(refused.status_code, 400)

    def test_removed_route_stays_removed_and_new_accounts_get_default_routes(self):
        with self.app.app_context():
            app_module.ApprovalRouting.query.filter_by(requester_user_id=self.ids['staff']).delete()
            app_module.db.session.commit()
        self.assertEqual(self.client('super').get('/settings/approval-routing-data').status_code, 200)
        with self.app.app_context():
            self.assertEqual(app_module.ApprovalRouting.query.filter_by(requester_user_id=self.ids['staff']).count(), 0)

        created = self.client('super').post('/add_engineer', json={
            'staff_type': 'hr', 'name': f'Routed Person {uuid.uuid4().hex[:6]}'})
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        with self.app.app_context():
            new_user = app_module.User.query.filter_by(username=created.get_json()['username']).first()
            route = app_module.ApprovalRouting.query.filter_by(requester_user_id=new_user.id).first()
            self.assertIsNotNone(route)
            self.assertEqual(route.approver_user_id, self.ids['approver'])
            app_module.ApprovalRouting.query.filter_by(requester_user_id=new_user.id).delete()
            app_module.db.session.delete(new_user)
            app_module.db.session.commit()

    def test_support_engineer_is_view_only(self):
        client = self.client('support')
        self.assertEqual(client.post('/add_product', json={'serial_number': 'X'}).status_code, 403)
        self.assertEqual(client.post('/add_shift', json={}).status_code, 403)
        self.assertEqual(client.post('/update_shift/1', json={}).status_code, 403)
        self.assertEqual(client.post('/save_tsr_draft', json={}).status_code, 403)
        self.assertEqual(client.get('/offline-tsr').status_code, 302)
        self.assertEqual(client.post('/save_cash_advance', json={}).status_code, 403)
        self.assertEqual(client.get('/cash_advance').status_code, 302)
        self.assertEqual(client.post('/save_travel_request_draft', json={'purpose': 'x'}).status_code, 403)
        # Viewing and their own requests still work.
        self.assertEqual(client.get('/get_tsr_archive').status_code, 200)
        self.assertEqual(client.get('/reimbursement').status_code, 200)
        self.assertEqual(client.get('/timeline').status_code, 200)
        # Positive control: an engineer is not stopped by the Support Engineer gate.
        self.assertNotEqual(self.client('engineer').get('/offline-tsr').status_code, 302)

    def test_support_engineer_participant_needs_no_signature(self):
        with self.app.app_context():
            support = app_module.db.session.get(app_module.User, self.ids['support'])
            engineer = app_module.db.session.get(app_module.User, self.ids['engineer'])
            people = [
                {'user': engineer, 'role': 'lead', 'signature_data': ''},
                {'user': support, 'role': 'participant', 'signature_data': ''},
            ]
            original = app_module.get_travel_request_signature_people
            app_module.get_travel_request_signature_people = lambda request_rec: people
            try:
                missing = app_module.get_travel_request_missing_signature_people(object())
            finally:
                app_module.get_travel_request_signature_people = original
            self.assertEqual([person['user'].id for person in missing], [engineer.id])


if __name__ == '__main__':
    unittest.main()
