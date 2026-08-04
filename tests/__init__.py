"""Test package for Medical Service SMS.

Makes `tests` a real package so shared helpers such as `tests.sw_cache_version`
import identically under `unittest discover -s tests` and `unittest tests.<module>`.

It also pins one **fresh** database for the whole run, and that is what makes the suite
trustworthy rather than merely tidy.

Every test module pins `MEDICAL_SERVICE_TEST_DB` with `os.environ.setdefault`, so under
`unittest discover` the first module to import wins and every module shares its database.
That file used to live in the temp directory and survive between runs, so state accumulated:
a run could fail on data left behind by an earlier one while the same module passed in
isolation. That is exactly how `test_completed_delta_matches_the_seeded_weeks` came to fail
with `0 != 1` on a developer machine and pass on a clean one -- and why verifying with an
explicitly pinned brand-new database reported success and hid it.

Setting the variable here, before any test module is imported, makes every module's
`setdefault` a no-op and gives each run its own file. Modules still clean up after themselves
in `tearDownClass`; this makes a missed cleanup unable to poison the next run.
"""

import atexit
import os
import pathlib
import tempfile
import uuid

_RUN_DB = pathlib.Path(tempfile.gettempdir()) / f'medical_service_test_run_{uuid.uuid4().hex}.db'

# An explicit value from the environment still wins, so anyone who needs to inspect a
# database after a run can point at their own path.
if not os.environ.get('MEDICAL_SERVICE_TEST_DB'):
    os.environ['MEDICAL_SERVICE_TEST_DB'] = str(_RUN_DB)

    @atexit.register
    def _remove_run_database():
        """Clean up this run's database, and sweep any earlier ones.

        On Windows SQLite may still hold the file at interpreter exit, so the delete can
        fail through no fault of ours. Sweeping every `medical_service_test_run_*` file older
        than an hour keeps that from accumulating indefinitely -- without this the fix for
        stale state would quietly become a different litter problem.
        """
        import time

        for suffix in ('', '-wal', '-shm'):
            try:
                _RUN_DB.with_name(_RUN_DB.name + suffix).unlink()
            except OSError:
                pass

        cutoff = time.time() - 3600
        for stale in _RUN_DB.parent.glob('medical_service_test_run_*'):
            try:
                if stale.stat().st_mtime < cutoff:
                    stale.unlink()
            except OSError:
                pass
