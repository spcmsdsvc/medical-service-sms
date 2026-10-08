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
    def test_superadmin_role_off_the_list_is_labelled_staff(self):
        account = _account('zz_not_on_the_list')
        self.assertFalse(app_module.is_superadmin_user(account))
        self.assertEqual(app_module.get_display_role(account), 'Staff')

    def test_listed_superadmins_keep_their_labels(self):
        self.assertEqual(
            app_module.get_display_role(_account(app_module.DEVELOPER_SUPERADMIN_USERNAME)),
            'Superadmin',
        )
        for username in app_module.SCHEDULER_USERNAMES:
            self.assertEqual(app_module.get_display_role(_account(username)), 'Scheduler')


if __name__ == '__main__':
    unittest.main()
