"""Regression coverage for the one-time Reimbursement approval-column migration."""

import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
_ISOLATED_APP_IMPORT = "app" not in sys.modules
_DISPOSABLE_DB_PATH = pathlib.Path(tempfile.gettempdir()) / (
    f"medical_service_reimbursement_migration_{uuid.uuid4().hex}.db"
)
if _ISOLATED_APP_IMPORT:
    os.environ["MEDICAL_SERVICE_TEST_DB"] = str(_DISPOSABLE_DB_PATH)
os.environ.setdefault("SECRET_KEY", "reimbursement-migration-tests")

import app as app_module  # noqa: E402

TEST_DB_PATH = pathlib.Path(app_module.DATABASE_PATH).resolve()
if TEST_DB_PATH == (ROOT / "scheduler.db").resolve():
    raise AssertionError("The migration regression must never use protected scheduler.db")


APPROVAL_COLUMNS = (
    "status",
    "created_at",
    "updated_at",
    "submitted_at",
    "approved_at",
    "approved_by_id",
    "rejected_at",
    "rejected_by_id",
    "approval_remarks",
    "approval_action",
    "approval_name_snapshot",
    "approval_title_snapshot",
    "approval_signature_snapshot",
    "approval_signature_layout",
    "approval_signed_at",
    "paid_at",
    "paid_by_id",
    "payment_reference",
    "payment_method",
    "payment_remarks",
    "excluded_rows_json",
)


@unittest.skipUnless(
    _ISOLATED_APP_IMPORT,
    "The focused migration fixture owns a disposable app import and is skipped in shared discovery",
)
class ReimbursementMigrationLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=True)
        configured_path = pathlib.Path(app_module.DATABASE_PATH).resolve()
        if configured_path != TEST_DB_PATH.resolve():
            raise AssertionError(
                f"The migration regression must use its disposable database, not {configured_path}"
            )

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.db.session.remove()
            app_module.db.engine.dispose()
        for suffix in ("", "-wal", "-shm", "-journal"):
            path = pathlib.Path(f"{TEST_DB_PATH}{suffix}")
            if path.exists():
                path.unlink()

    def setUp(self):
        with self.app.app_context():
            app_module.db.session.rollback()
            app_module.db.session.remove()
            app_module.db.engine.dispose()
        for suffix in ("", "-wal", "-shm", "-journal"):
            path = pathlib.Path(f"{TEST_DB_PATH}{suffix}")
            if path.exists():
                path.unlink()
        if hasattr(app_module, "_reimbursement_approval_columns_ready"):
            app_module._reimbursement_approval_columns_ready = False

    def tearDown(self):
        with self.app.app_context():
            app_module.db.session.rollback()
            app_module.db.session.remove()
            app_module.db.engine.dispose()

    def _create_header_table(self, current_schema, statuses=()):
        column_definitions = ["id INTEGER PRIMARY KEY"]
        if current_schema:
            column_definitions.extend(f"{column_name} TEXT" for column_name in APPROVAL_COLUMNS)
        else:
            column_definitions.append("status TEXT")

        connection = sqlite3.connect(TEST_DB_PATH)
        try:
            connection.execute(
                "CREATE TABLE reimbursement_header (" + ", ".join(column_definitions) + ")"
            )
            for row_id, status in statuses:
                connection.execute(
                    "INSERT INTO reimbursement_header (id, status) VALUES (?, ?)",
                    (row_id, status),
                )
            connection.commit()
        finally:
            connection.close()

    def _independent_write(self):
        connection = sqlite3.connect(TEST_DB_PATH, timeout=0.1)
        try:
            connection.execute("CREATE TABLE migration_lock_probe (id INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO migration_lock_probe (id) VALUES (1)")
            connection.commit()
        finally:
            connection.close()

    def test_current_schema_releases_write_transaction(self):
        self._create_header_table(current_schema=True, statuses=((1, ""),))

        with self.app.app_context():
            before_status = app_module.db.session.execute(
                app_module.db.text("SELECT status FROM reimbursement_header WHERE id = 1")
            ).scalar_one()
            before_changes = app_module.db.session.execute(
                app_module.db.text("SELECT total_changes()")
            ).scalar_one()
            app_module.ensure_reimbursement_approval_columns()
            after_status = app_module.db.session.execute(
                app_module.db.text("SELECT status FROM reimbursement_header WHERE id = 1")
            ).scalar_one()
            after_changes = app_module.db.session.execute(
                app_module.db.text("SELECT total_changes()")
            ).scalar_one()
            self.assertEqual(before_status, "")
            self.assertEqual(after_status, before_status)
            self.assertEqual(after_changes, before_changes)
            self._independent_write()
            self.assertTrue(getattr(app_module, "_reimbursement_approval_columns_ready", False))

    def test_legacy_schema_adds_missing_columns_and_preserves_status(self):
        self._create_header_table(
            current_schema=False,
            statuses=((1, ""), (2, "Submitted")),
        )

        with self.app.app_context():
            app_module.ensure_reimbursement_approval_columns()
            columns = {
                row[1]
                for row in app_module.db.session.execute(
                    app_module.db.text("PRAGMA table_info(reimbursement_header)")
                ).fetchall()
            }
            self.assertTrue(set(APPROVAL_COLUMNS).issubset(columns))
            statuses = dict(
                app_module.db.session.execute(
                    app_module.db.text("SELECT id, status FROM reimbursement_header ORDER BY id")
                ).fetchall()
            )
            self.assertEqual(statuses, {1: "", 2: "Submitted"})
            self.assertTrue(getattr(app_module, "_reimbursement_approval_columns_ready", False))

            app_module.ensure_reimbursement_approval_columns()
            self._independent_write()

    def test_failed_migration_remains_retryable(self):
        self._create_header_table(current_schema=True)

        with self.app.app_context():
            with patch.object(
                app_module.db.session,
                "execute",
                side_effect=RuntimeError("synthetic migration failure"),
            ):
                app_module.ensure_reimbursement_approval_columns()

            self.assertFalse(getattr(app_module, "_reimbursement_approval_columns_ready", False))
            app_module.ensure_reimbursement_approval_columns()
            self.assertTrue(getattr(app_module, "_reimbursement_approval_columns_ready", False))
            self._independent_write()


if __name__ == "__main__":
    unittest.main()
