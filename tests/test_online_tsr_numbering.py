"""The TSR number lookup must never be the thing that stops an engineer working.

A field report came back showing "Unable to assign the next TSR number." with the engineer
online and no way to tell why. The number is assigned before the TSR can be saved, so anything
that raises here blocks the save completely.

Two causes are pinned below. The first is a whole class of bug: `OnlineTsrSubmission.__table__
.create(checkfirst=True)` silently skips a table that already exists, so a column added to the
model later never reaches a live database and every read of it raises "no such column". The
second is that a failing index statement used to abort the same helper, turning a constraint
problem into a total outage.
"""

import os
import pathlib
import re
import sqlite3
import tempfile
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from tests.sw_cache_version import assert_cache_version_at_least

ROOT = pathlib.Path(__file__).resolve().parents[1]

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_offline_schedule_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


class OnlineTsrSubmissionMigrationTests(unittest.TestCase):
    """The migration list has to keep up with the model, or reads start failing."""

    # Present in the very first CREATE TABLE, so they cannot be missing from a live database
    # and are not candidates for an additive ALTER.
    ORIGINAL_COLUMNS = {'id', 'shift_id', 'payload_json'}

    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.ensure_source = source.split('def ensure_online_tsr_submission_table(')[1].split('\ndef ')[0]

    def test_every_model_column_is_covered_by_the_migration(self):
        """The general guard. A column added to the model later must be added here too.

        This is what makes the class of bug impossible to reintroduce quietly: adding a column
        to OnlineTsrSubmission without an ALTER here fails this test rather than failing in the
        field, months later, on one database.
        """
        model_columns = {column.name for column in app_module.OnlineTsrSubmission.__table__.columns}
        additive = model_columns - self.ORIGINAL_COLUMNS
        self.assertTrue(additive, 'the model should have columns beyond the original three')

        missing = sorted(
            name for name in additive
            if f'ADD COLUMN {name} ' not in self.ensure_source
        )
        self.assertEqual(
            missing, [],
            'these model columns have no additive migration, so a live database created '
            'before them will raise "no such column" on every read: ' + ', '.join(missing)
        )

    def test_tsr_number_specifically_is_covered(self):
        """Named on its own because this is the one that blocked the field."""
        self.assertIn('ADD COLUMN tsr_number VARCHAR(120)', self.ensure_source)

    def test_an_index_failure_does_not_abort_the_helper(self):
        """A missing index degrades things; it must not stop every TSR being saved."""
        index_block = self.ensure_source.split('for statement in index_statements:')[1]
        self.assertIn('try:', index_block)
        self.assertIn('except Exception', index_block)

    def test_columns_stay_fatal(self):
        """Only indexes were softened. A column that cannot be added is a real failure."""
        column_block = self.ensure_source.split('for column_name, statement in column_statements.items():')[1]
        column_block = column_block.split('for statement in index_statements:')[0]
        self.assertNotIn('except', column_block)

    def test_a_legacy_table_is_repaired_in_place(self):
        """Functional: build the broken shape and prove the helper fixes it.

        The suite shares one database, so this uses its own throwaway file and drives the
        migration statements read out of the helper rather than touching the live engine.
        """
        statements = re.findall(r'"(ALTER TABLE online_tsr_submission ADD COLUMN [^"]+)"', self.ensure_source)
        self.assertTrue(statements, 'no ALTER statements found to exercise')

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'legacy.db')
            connection = sqlite3.connect(path)
            connection.execute(
                'CREATE TABLE online_tsr_submission ('
                ' id INTEGER PRIMARY KEY, shift_id INTEGER NOT NULL, payload_json TEXT NOT NULL)'
            )
            connection.commit()

            before = {row[1] for row in connection.execute('PRAGMA table_info(online_tsr_submission)')}
            self.assertNotIn('tsr_number', before, 'positive control: the column must start missing')

            existing = set(before)
            for statement in statements:
                name = statement.split('ADD COLUMN ')[1].split(' ')[0]
                if name not in existing:
                    connection.execute(statement)
            connection.commit()

            after = {row[1] for row in connection.execute('PRAGMA table_info(online_tsr_submission)')}
            connection.close()

        self.assertIn('tsr_number', after, 'the migration did not repair the legacy table')


class OnlineTsrNumberRouteTests(unittest.TestCase):
    """When numbering does fail, the engineer must be told something actionable."""

    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.route = source.split("@app.route('/get_next_online_tsr_number')")[1].split('\ndef attach_online_tsr_pdf_to_shift')[0]

    def test_the_failure_names_the_cause(self):
        """A bare message sent a field report back with nothing to act on."""
        self.assertIn('type(exc).__name__', self.route)
        self.assertIn('traceback.print_exc()', self.route)
        self.assertIn("'detail'", self.route)

    def test_the_headline_message_is_kept(self):
        # The wording engineers and the changelog already know stays at the front.
        self.assertIn('Unable to assign the next TSR number.', self.route)


class OnlineTsrNumberPreviewTests(unittest.TestCase):
    """The blank Create TSR form must show the next server-backed number."""

    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.template = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_server_sequence_advances_after_an_existing_submission(self):
        class FakeQuery:
            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return [SimpleNamespace(tsr_number='20990102-01-ENG')]

        with app_module.app.app_context():
            with patch.object(app_module, 'ensure_online_tsr_submission_table'), \
                    patch.object(app_module.OnlineTsrSubmission, 'query', FakeQuery()):
                next_number = app_module.online_tsr_next_number_for_date(date(2099, 1, 2), 'ENG')

        self.assertEqual(next_number, '20990102-02-ENG')

    def test_each_blank_form_invalidates_cached_preview_before_generating(self):
        start = self.template.index('function initializeBlankStandaloneTSR(){')
        end = self.template.index('\nasync function clearStandaloneTSRPage', start)
        initialize = self.template[start:end]
        self.assertIn('invalidateTSRNumberPreview();', initialize)
        self.assertLess(
            initialize.index('invalidateTSRNumberPreview();'),
            initialize.index('generateTSRNumber();'),
        )

    def test_inflight_old_preview_cannot_overwrite_the_new_blank_form(self):
        start = self.template.index('let tsrNumberPreviewRefreshPending = false;')
        end = self.template.index('\nfunction selectedScheduleHasLinkedSchedules', start)
        preview = self.template[start:end]
        self.assertIn('tsrNumberPreviewGeneration', preview)
        self.assertIn('tsrNumberPreviewNeedsRefresh', preview)
        self.assertIn('if(requestGeneration !== tsrNumberPreviewGeneration)', preview)
        self.assertIn('tsrNumberPreviewNeedsRefresh = true;', preview)
        self.assertIn("void refreshTSRNumberPreviewFromServer('', initials);", preview)

    def test_reconnect_retries_a_provisional_preview(self):
        start = self.template.index('function scheduleOfflineTSRAutoSync(){')
        end = self.template.index('\nasync function submitStandaloneTSROnline', start)
        auto_sync = self.template[start:end]
        self.assertLess(
            auto_sync.index('return syncOfflineTSRQueue({ silent:false });'),
            auto_sync.index('invalidateTSRNumberPreview();'),
        )
        self.assertIn("void refreshTSRNumberPreviewFromServer('', getEngineerInitialsSafe());", auto_sync)

    def test_service_worker_cache_is_bumped_for_the_preview_fix(self):
        assert_cache_version_at_least(self, 117, self.app_source)


class OnlineTsrNumberManifestTests(unittest.TestCase):
    def test_release_manifest_mentions_the_preview_fix(self):
        import json

        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        release = next(item for item in manifest['releases'] if item['release_key'] == '2026-08-26-appearance-accent-themes')
        self.assertTrue(any(
            item['item_key'] == '2026-08-26-tsr-number-preview-refresh'
            for item in release['items']
        ))


if __name__ == '__main__':
    unittest.main()
