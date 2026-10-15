"""The role label must not promise admin rights the account does not have."""

import os
import pathlib
import tempfile
import types
import unittest

# Pin an isolated database BEFORE importing app.py so the suite can never open the real
# scheduler.db.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_display_role_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


def _account(username, role='superadmin'):
    return types.SimpleNamespace(username=username, role=role, is_authenticated=True)


class DisplayRoleLabelTests(unittest.TestCase):
    def test_label_follows_the_role_not_the_username(self):
        expected = {
            'superadmin': 'Superadmin', 'manager': 'Manager', 'scheduler': 'Scheduler',
            'regional_admin': 'Administrator', 'engineer': 'Engineer',
            'support_engineer': 'Support Engineer', 'approver': 'Approver', 'staff': 'Staff',
        }
        for role, label in expected.items():
            self.assertEqual(app_module.get_display_role(_account('zz_any_name', role)), label, role)
        # A former name rule no longer decides anything.
        self.assertEqual(app_module.get_display_role(_account('diary', 'engineer')), 'Engineer')

    def test_superadmin_label_matches_superadmin_rights(self):
        for role in ('superadmin', 'manager', 'scheduler'):
            self.assertTrue(app_module.is_superadmin_user(_account('zz_any_name', role)), role)
        self.assertFalse(app_module.is_superadmin_user(_account('rodito', 'staff')))


if __name__ == '__main__':
    unittest.main()
