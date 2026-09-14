"""Regression coverage for the permanent System Backup startup fix.

The configuration contracts are stdlib-only so they can run even when the full Flask
dependency set is unavailable.  The archive progress and reconciliation checks use the
same isolated, temporary paths as the existing backup tests and never touch ``scheduler.db``.
"""

import importlib.util
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "gunicorn.conf.py"
DOCKERFILE = ROOT / "Dockerfile"
PROCFILE = ROOT / "Procfile"
APP_SOURCE = ROOT / "app.py"
TEMPLATE_SOURCE = ROOT / "templates" / "system_backup.html"
_OWNED_TEST_DB = "MEDICAL_SERVICE_TEST_DB" not in os.environ
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_backup_permanent_{uuid.uuid4().hex}.db"
if _OWNED_TEST_DB:
    os.environ["MEDICAL_SERVICE_TEST_DB"] = str(TEST_DB_PATH)


def cleanup_owned_test_db():
    if not _OWNED_TEST_DB:
        return
    for suffix in ("", "-wal", "-shm", "-journal"):
        try:
            (TEST_DB_PATH.parent / (TEST_DB_PATH.name + suffix)).unlink()
        except FileNotFoundError:
            pass


def load_gunicorn_config():
    spec = importlib.util.spec_from_file_location("medical_service_gunicorn_config", CONFIG_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load {CONFIG_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GunicornConfigurationContractTests(unittest.TestCase):

    @staticmethod
    def _server_with_resolved_config(values):
        """Build a server double with Gunicorn's resolved Config interface.

        ``Config.worker_class`` is a loaded worker class, while
        ``Config.worker_class_str`` is the effective worker name.  Keeping both
        forms here catches validators that accidentally compare the class object
        with the configured string.
        """
        resolved = dict(values)
        resolved["worker_class_str"] = resolved.get("worker_class_str", resolved["worker_class"])
        resolved["worker_class"] = type("ThreadWorker", (), {})
        return SimpleNamespace(
            cfg=SimpleNamespace(**resolved),
            log=SimpleNamespace(info=lambda *args: None),
        )

    def test_versioned_config_requires_backup_safe_settings(self):
        config = load_gunicorn_config()
        expected = {
            "worker_class": "gthread",
            "workers": 1,
            "threads": 8,
            "timeout": 180,
            "graceful_timeout": 30,
            "max_requests": 0,
            "max_requests_jitter": 0,
            "reload": False,
            "preload_app": False,
        }
        for name, value in expected.items():
            self.assertEqual(getattr(config, name), value, name)
        self.assertIs(config.on_starting, config.validate_effective_settings)
        self.assertIs(config.on_reload, config.validate_effective_settings)

    def test_conflicting_effective_settings_are_rejected_by_name(self):
        config = load_gunicorn_config()
        expected = config.required_settings()
        for setting, value in expected.items():
            bad_value = {
                "worker_class": "sync",
                "workers": 2,
                "threads": 1,
                "timeout": 60,
                "graceful_timeout": 0,
                "max_requests": 10,
                "max_requests_jitter": 1,
                "reload": True,
                "preload_app": True,
            }[setting]
            values = dict(expected)
            if setting == "worker_class":
                # Gunicorn resolves this setting to a class object.  Its string
                # property is the effective value that the validator must check.
                values["worker_class_str"] = bad_value
            else:
                values[setting] = bad_value
            server = self._server_with_resolved_config(values)
            with self.subTest(setting=setting):
                with self.assertRaisesRegex(RuntimeError, setting):
                    config.validate_effective_settings(server)

    def test_worker_class_class_object_is_validated_by_gunicorn_string_property(self):
        config = load_gunicorn_config()
        server = self._server_with_resolved_config(config.required_settings())
        self.assertIsInstance(server.cfg.worker_class, type)
        self.assertEqual(server.cfg.worker_class_str, "gthread")
        self.assertTrue(config.validate_effective_settings(server))

    def test_harmless_bind_and_logging_overrides_are_allowed(self):
        config = load_gunicorn_config()
        values = config.required_settings()
        values.update({"bind": "127.0.0.1:9001", "accesslog": "-", "errorlog": "-"})
        server = self._server_with_resolved_config(values)
        self.assertTrue(config.validate_effective_settings(server))

    def test_container_and_platform_commands_load_the_same_config(self):
        docker = DOCKERFILE.read_text(encoding="utf-8")
        procfile = PROCFILE.read_text(encoding="utf-8")
        self.assertIn("--config", docker)
        self.assertIn("gunicorn.conf.py", docker)
        self.assertIn("--config gunicorn.conf.py", procfile)
        for command_source in (docker, procfile):
            self.assertNotIn("--worker-class", command_source)
            self.assertNotIn("--workers", command_source)
            self.assertNotIn("--threads", command_source)
            self.assertNotIn("--timeout", command_source)
            self.assertNotIn("--graceful-timeout", command_source)

    def test_config_is_discoverable_from_the_application_working_directory(self):
        # Gunicorn's plain `gunicorn app:app` command searches the current working
        # directory for gunicorn.conf.py.  Keep this as a source-level contract because
        # the Windows test runtime cannot import Gunicorn's POSIX-only fcntl module.
        self.assertEqual(CONFIG_PATH.name, "gunicorn.conf.py")
        self.assertEqual(ROOT.name, "medical-service-sms-railway")
        self.assertIn("worker_class", CONFIG_PATH.read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "posix", "Gunicorn's runtime check requires a POSIX fcntl environment")
    def test_pinned_gunicorn_accepts_defaults_and_rejects_env_override(self):
        with tempfile.TemporaryDirectory(prefix="backup-gunicorn-probe-") as temp_root:
            temp_path = pathlib.Path(temp_root)
            (temp_path / "fixture.py").write_text("def app(environ, start_response):\n    start_response('200 OK', [('Content-Type', 'text/plain')])\n    return [b'ok']\n", encoding="utf-8")
            command = [
                sys.executable,
                "-m",
                "gunicorn",
                "--config",
                str(CONFIG_PATH),
                "--bind",
                "127.0.0.1:0",
                "fixture:app",
            ]

            process = subprocess.Popen(command, cwd=temp_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                output = ""
                for _ in range(100):
                    if process.poll() is not None:
                        output += process.stdout.read() if process.stdout else ""
                        break
                    output += process.stdout.readline() if process.stdout else ""
                    if "backup-safe settings validated" in output:
                        break
                self.assertIn("backup-safe settings validated", output)
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=10)

            cli_conflict = subprocess.run(
                command + ["--workers", "2"],
                cwd=temp_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(cli_conflict.returncode, 0)
            self.assertIn("workers", cli_conflict.stdout)

            conflict_env = os.environ.copy()
            conflict_env["GUNICORN_CMD_ARGS"] = "--workers 2"
            conflict = subprocess.run(
                command,
                cwd=temp_root,
                env=conflict_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(conflict.returncode, 0)
            self.assertIn("workers", conflict.stdout)


class BackupDisplayContractTests(unittest.TestCase):

    def test_bucket_progress_uses_unknown_total_without_a_pre_scan(self):
        source = APP_SOURCE.read_text(encoding="utf-8")
        bucket_start = source.index("# --- bucket objects")
        bucket_end = source.index("# --- auxiliary state", bucket_start)
        bucket_section = source[bucket_start:bucket_end]
        self.assertIn("files_total = 0", bucket_section)
        self.assertIn("files_done=files_done", bucket_section)
        self.assertNotIn("get_bucket_object_snapshot", bucket_section)

    def test_template_distinguishes_unknown_totals_and_overall_progress(self):
        template = TEMPLATE_SOURCE.read_text(encoding="utf-8")
        self.assertIn("Overall progress:", template)
        self.assertIn("filesDone} files archived", template)
        self.assertIn("filesDone} of ${filesTotal} files archived", template)
        self.assertIn("Overall backup build progress", template)

    def test_template_requires_completed_result_for_database_included(self):
        template = TEMPLATE_SOURCE.read_text(encoding="utf-8")
        self.assertIn("databaseConfirmed", template)
        self.assertIn("completed_with_warnings", template)
        self.assertIn("Not confirmed", template)
        self.assertNotIn("job.status === 'failed' ? 'Failed'", template)

    def test_restart_reconciliation_preserves_last_phase_and_uses_interrupted_label(self):
        source = APP_SOURCE.read_text(encoding="utf-8")
        reconcile_start = source.index("def reconcile_backup_job_state():")
        reconcile_end = source.index("def backup_job_is_running", reconcile_start)
        reconcile = source[reconcile_start:reconcile_end]
        self.assertIn("Build interrupted", reconcile)
        self.assertIn("last_phase_label", reconcile)
        self.assertIn("server process changed", reconcile)
        self.assertIn("unfinished build must be restarted", reconcile)
        self.assertNotIn("Nothing was corrupted", reconcile)


class BackupProgressRuntimeTests(unittest.TestCase):
    """Exercise the count contract with a local file total smaller than bucket files."""

    @classmethod
    def setUpClass(cls):
        try:
            import app as app_module
        except Exception as error:  # pragma: no cover - environment-dependent skip
            cls.app_module = None
            cls.import_error = error
        else:
            cls.app_module = app_module
            cls.import_error = None

    def setUp(self):
        if self.app_module is None:
            self.skipTest(f"app dependencies unavailable: {self.import_error}")
        self.temp_root = pathlib.Path(tempfile.mkdtemp(prefix="backup-progress-"))
        self.addCleanup(shutil.rmtree, self.temp_root, True)
        self.db_path = self.temp_root / "source.db"
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("CREATE TABLE backup_probe (value TEXT)")
            connection.execute("INSERT INTO backup_probe(value) VALUES ('backup')")
            connection.commit()
        finally:
            connection.close()
        self.upload_root = self.temp_root / "uploads"
        self.upload_root.mkdir()
        (self.upload_root / "local.txt").write_text("local", encoding="utf-8")
        self.archive_root = self.temp_root / "archives"
        self.archive_root.mkdir()

    def test_bucket_files_do_not_reuse_local_denominator(self):
        app_module = self.app_module
        objects = [SimpleNamespace(key=f"reports/bucket-{index}.pdf", size=4) for index in range(4)]

        class StubStorage:
            bucket_configured = True
            bucket_name = "private-files"

            def test_connection_for_backup(self, *, timeout_seconds):
                return {"ok": True, "message": "connected"}

            def iter_objects_for_backup(self, *, timeout_seconds):
                yield from objects

            def download_bytes_for_backup(self, key, *, timeout_seconds):
                return b"bucket"

        progress = []
        with patch.object(app_module, "BACKUP_ARCHIVE_DIR", str(self.archive_root)), \
                patch.object(app_module, "get_active_sqlite_database_path", return_value=str(self.db_path)), \
                patch.object(app_module, "get_backup_upload_roots", return_value=[str(self.upload_root)]), \
                patch.object(app_module, "managed_storage_roots", return_value=[("reports", None)]), \
                patch.object(app_module, "file_storage", StubStorage()):
            result = app_module.build_system_backup_archive(
                "a" * 16,
                "backup-test",
                progress_sink=lambda **fields: progress.append(dict(fields)),
            )

        self.assertEqual(result["files_total"], 0)
        self.assertEqual(result["files_done"], 6)
        bucket_events = [event for event in progress if event.get("phase") == "bucket"]
        self.assertTrue(bucket_events)
        self.assertEqual(bucket_events[-1]["files_total"], 0)
        self.assertGreater(result["files_done"], 2)


class BackupReconcileRuntimeTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            import app as app_module
        except Exception as error:  # pragma: no cover - environment-dependent skip
            cls.app_module = None
            cls.import_error = error
        else:
            cls.app_module = app_module
            cls.import_error = None

    def test_restart_marks_build_interrupted_without_claiming_database_integrity(self):
        if self.app_module is None:
            self.skipTest(f"app dependencies unavailable: {self.import_error}")
        app_module = self.app_module
        with tempfile.TemporaryDirectory(prefix="backup-reconcile-") as temp_root:
            state_root = pathlib.Path(temp_root)
            state = app_module.empty_backup_job_state()
            state.update({
                "job_id": "job-under-test",
                "boot_id": "old-process",
                "status": "running",
                "phase": "bucket",
                "phase_label": "Downloading private bucket objects",
            })
            with patch.object(app_module, "RUNTIME_STATE_DIR", str(state_root)):
                app_module.save_backup_job_state(state)
                reconciled = app_module.reconcile_backup_job_state()
        self.assertEqual(reconciled["status"], "failed")
        self.assertTrue(reconciled["interrupted"])
        self.assertEqual(reconciled["phase_label"], "Build interrupted")
        self.assertEqual(reconciled["last_phase_label"], "Downloading private bucket objects")
        self.assertIn("server process changed", reconciled["message"])
        self.assertIn("unfinished build must be restarted", reconciled["message"])
        self.assertNotIn("Nothing was corrupted", reconciled["message"])


if _OWNED_TEST_DB:
    import atexit
    atexit.register(cleanup_owned_test_db)


if __name__ == "__main__":
    unittest.main()
