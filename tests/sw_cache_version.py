"""Shared assertion for the service worker cache version.

Several feature tests need to confirm that the service worker cache version was
bumped when that feature shipped. They used to assert one literal version string,
which meant every later bump silently broke unrelated tests -- that is exactly what
happened across v36, v37 and v38.

Assert the version is at least the one the feature shipped in instead, so a future
bump keeps these tests passing while a missing or malformed version still fails.
"""

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]

CACHE_VERSION_PREFIX = 'medical-service-pwa-offline-navigation'

CACHE_VERSION_PATTERN = re.compile(
    r"const CACHE_VERSION = '" + re.escape(CACHE_VERSION_PREFIX) + r"-v(\d+)-([a-z0-9-]+)';"
)


def read_app_source():
    """Return app.py as text."""
    return (ROOT / 'app.py').read_text(encoding='utf-8')


def get_cache_version(app_source=None):
    """Return (version_number, label) parsed from the service worker CACHE_VERSION.

    Raises AssertionError when the constant is missing or does not match the
    expected `<prefix>-vNN-<label>` shape.
    """
    source = read_app_source() if app_source is None else app_source
    match = CACHE_VERSION_PATTERN.search(source)
    if not match:
        raise AssertionError(
            'Service worker CACHE_VERSION not found or malformed in app.py. '
            f"Expected the form: const CACHE_VERSION = '{CACHE_VERSION_PREFIX}-vNN-label';"
        )
    return int(match.group(1)), match.group(2)


def assert_cache_version_at_least(test_case, minimum_version, app_source=None):
    """Assert the service worker cache version is at least `minimum_version`.

    `minimum_version` is the version the calling feature shipped in. Later bumps are
    expected and must not fail the test.
    """
    version_number, label = get_cache_version(app_source)
    test_case.assertGreaterEqual(
        version_number,
        minimum_version,
        f'Service worker cache version is v{version_number}-{label}, which is older '
        f'than v{minimum_version}. The cache version must never move backwards.'
    )
