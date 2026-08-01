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


if __name__ == '__main__':
    unittest.main()
