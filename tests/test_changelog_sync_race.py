import unittest
from unittest import mock

from sqlalchemy.exc import IntegrityError

import app as app_module


class ChangelogSyncRaceTests(unittest.TestCase):
    def test_duplicate_insert_from_another_worker_is_retried_not_raised(self):
        calls = []

        def fake_sync():
            calls.append(1)
            if len(calls) == 1:
                raise IntegrityError('INSERT', {}, Exception('UNIQUE constraint failed'))

        with mock.patch.object(app_module, '_changelog_tables_ready', True), \
                mock.patch.object(app_module, '_changelog_manifest_synced', False), \
                mock.patch.object(app_module, 'sync_changelog_release_manifest', side_effect=fake_sync):
            app_module.ensure_changelog_tables()
            self.assertTrue(app_module._changelog_manifest_synced)
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
