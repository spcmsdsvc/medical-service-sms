"""Regression coverage for unique engineer initials and the guarded legacy repair."""

import os
import pathlib
import tempfile
import unittest
import uuid

os.environ.setdefault(
    'MEDICAL_SERVICE_TEST_DB',
    str(pathlib.Path(tempfile.gettempdir()) / 'medical_service_engineer_initials_tests.db'),
)

import app as app_module  # noqa: E402


class EngineerInitialsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:8].upper()
        cls.created_engineer_ids = []
        cls.created_user_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_admin_capability_columns()
            cls.superadmin = app_module.User.query.filter_by(username='jonamar').first()
            if not cls.superadmin:
                cls.superadmin = app_module.User(
                    username='jonamar',
                    password=app_module.generate_password_hash('test-password'),
                    role='superadmin',
                    is_active=True,
                )
                app_module.db.session.add(cls.superadmin)
                app_module.db.session.flush()
                cls.created_user_ids.append(cls.superadmin.id)
            cls.superadmin.role = 'superadmin'
            cls.superadmin.is_active = True
            cls.holder = app_module.Engineer(
                employee_id=f'INIT-{cls.suffix}-HOLDER',
                name=f'Initial Holder {cls.suffix}',
                initials=f'HLD{cls.suffix[:2]}',
                branch='Manila',
            )
            cls.target = app_module.Engineer(
                employee_id=f'INIT-{cls.suffix}-TARGET',
                name=f'Initial Target {cls.suffix}',
                initials=f'TGT{cls.suffix[:2]}',
                branch='Manila',
            )
            app_module.db.session.add_all([cls.holder, cls.target])
            app_module.db.session.commit()
            cls.created_engineer_ids.extend([cls.holder.id, cls.target.id])
            cls.superadmin_id = cls.superadmin.id
            cls.holder_id = cls.holder.id
            cls.target_id = cls.target.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for engineer_id in reversed(cls.created_engineer_ids):
                engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    app_module.db.session.delete(engineer)
            for user_id in reversed(cls.created_user_ids):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    @classmethod
    def _client_for(cls, user_id):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    @classmethod
    def _engineer_payload(cls, employee_id, name, initials, **overrides):
        payload = {
            'staff_type': 'engineer',
            'employee_id': employee_id,
            'name': name,
            'initials': initials,
            'branch': 'Manila',
            'phone': '',
            'email': '',
        }
        payload.update(overrides)
        return payload

    def _track_created_engineer(self, response, employee_id):
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            engineer = app_module.Engineer.query.filter_by(employee_id=employee_id).first()
            self.assertIsNotNone(engineer)
            self.created_engineer_ids.append(engineer.id)
            user = app_module.db.session.get(app_module.User, engineer.user_id) if engineer.user_id else None
            if user:
                self.created_user_ids.append(user.id)
            return engineer

    def test_add_refuses_case_insensitive_duplicate_and_names_holder(self):
        client = self._client_for(self.superadmin_id)
        initials = f'ZZQ{self.suffix[:2]}'
        holder_employee_id = f'INIT-{self.suffix}-ADD-HOLDER'
        duplicate_employee_id = f'INIT-{self.suffix}-ADD-DUPLICATE'
        holder_response = client.post(
            '/add_engineer',
            json=self._engineer_payload(
                holder_employee_id,
                f'Add Holder {self.suffix}',
                initials,
            ),
        )
        holder = self._track_created_engineer(holder_response, holder_employee_id)

        duplicate = client.post(
            '/add_engineer',
            json=self._engineer_payload(
                duplicate_employee_id,
                f'Add Duplicate {self.suffix}',
                initials.lower(),
            ),
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.get_data(as_text=True))
        self.assertIn(holder.name, duplicate.get_json()['message'])

    def test_update_refuses_duplicate_but_allows_own_case_change_and_missing_fields_are_400(self):
        client = self._client_for(self.superadmin_id)
        with self.app.app_context():
            holder = app_module.db.session.get(app_module.Engineer, self.holder_id)
            target = app_module.db.session.get(app_module.Engineer, self.target_id)
            holder_initials = holder.initials
            target_initials = target.initials
            target_payload = {
                'employee_id': target.employee_id,
                'name': target.name,
                'initials': holder_initials.lower(),
                'branch': target.branch,
                'phone': target.phone or '',
                'email': target.email or '',
            }

        duplicate = client.put(f'/update_engineer/{self.target_id}', json=target_payload)
        self.assertEqual(duplicate.status_code, 400, duplicate.get_data(as_text=True))
        self.assertIn(holder.name, duplicate.get_json()['message'])

        own_case = dict(target_payload, initials=target_initials.lower())
        updated = client.put(f'/update_engineer/{self.target_id}', json=own_case)
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))

        missing = client.put(
            f'/update_engineer/{self.target_id}',
            json={'employee_id': target_payload['employee_id']},
        )
        self.assertEqual(missing.status_code, 400, missing.get_data(as_text=True))

    def test_guarded_legacy_correction_changes_only_the_anchored_record(self):
        original_flag = app_module._engineer_initials_correction_ready
        target_created = False
        other_created = False
        with self.app.app_context():
            target = app_module.Engineer.query.filter_by(employee_id='00021').first()
            if not target:
                target = app_module.Engineer(
                    employee_id='00021',
                    name='Temporary Legacy Engineer',
                    initials='TMP',
                    branch='Manila',
                )
                app_module.db.session.add(target)
                app_module.db.session.flush()
                target_created = True

            other = app_module.Engineer.query.filter_by(employee_id='18-185').first()
            if not other:
                other = app_module.Engineer(
                    employee_id='18-185',
                    name='Temporary Other Engineer',
                    initials='JP',
                    branch='Manila',
                )
                app_module.db.session.add(other)
                app_module.db.session.flush()
                other_created = True

            target_original = (target.name, target.initials)
            other_original = (other.name, other.initials)
            target.name = 'Jocel Prudente'
            target.initials = 'JP'
            app_module.db.session.commit()
            app_module._engineer_initials_correction_ready = False

            app_module.ensure_unique_engineer_initials()
            self.assertEqual(target.initials, 'JOP')
            self.assertEqual((other.name, other.initials), other_original)

            # Reset the flag so this genuinely re-runs the anchored match rather than
            # short-circuiting on it. Without the reset this only proved the flag works,
            # not that the 'JP' half of the anchor is what protects a manual edit.
            target.initials = 'JX'
            app_module.db.session.commit()
            app_module._engineer_initials_correction_ready = False
            app_module.ensure_unique_engineer_initials()
            self.assertEqual(target.initials, 'JX')

            if target_created:
                app_module.db.session.delete(target)
            else:
                target.name, target.initials = target_original
            if other_created:
                app_module.db.session.delete(other)
            else:
                other.name, other.initials = other_original
            app_module.db.session.commit()
            app_module._engineer_initials_correction_ready = original_flag

    def test_the_duplicate_scan_does_not_rerun_on_every_call(self):
        """This runs from @app.before_request, so it must not re-read every engineer row.

        It shipped scanning the whole table per request -- measured ~0.35 ms against
        ~0.04 ms for a flag-guarded sibling, growing with the engineer table. Asserted by
        behaviour rather than by timing: seed a duplicate WITHOUT clearing the flag and the
        cached answer must come back unchanged, which is only possible if no query ran.
        """
        original_flag = app_module._engineer_initials_correction_ready
        original_cache = app_module._engineer_initials_duplicates
        created = []
        with self.app.app_context():
            try:
                app_module._engineer_initials_correction_ready = False
                warm = app_module.ensure_unique_engineer_initials()

                shared = f'D{self.suffix[:2]}'.upper()
                for index in (1, 2):
                    engineer = app_module.Engineer(
                        employee_id=f'DUPSCAN-{self.suffix}-{index}',
                        name=f'Dup Scan {index}', initials=shared, branch='Manila',
                    )
                    app_module.db.session.add(engineer)
                    app_module.db.session.flush()
                    created.append(engineer)
                app_module.db.session.commit()

                self.assertEqual(
                    app_module.ensure_unique_engineer_initials(), warm,
                    'the scan re-ran despite the ready flag being set',
                )

                # A deliberate reset must still see the new duplicate, or the cache would
                # be hiding a real signal rather than skipping redundant work.
                app_module._engineer_initials_correction_ready = False
                self.assertIn(shared, app_module.ensure_unique_engineer_initials())
            finally:
                for engineer in created:
                    app_module.db.session.delete(engineer)
                app_module.db.session.commit()
                app_module._engineer_initials_correction_ready = original_flag
                app_module._engineer_initials_duplicates = original_cache


if __name__ == '__main__':
    unittest.main()
