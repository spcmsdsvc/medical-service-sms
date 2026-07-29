import unittest

from tests.sw_cache_version import (
    assert_cache_version_at_least,
    get_cache_version,
)


REAL_SHAPE = "const CACHE_VERSION = 'medical-service-pwa-offline-navigation-v39-login-refresh';"


class ServiceWorkerCacheVersionHelperTests(unittest.TestCase):
    """Guards the shared helper so it can never become a vacuous assertion.

    The literal-string assertions this replaced were silently broken across v36,
    v37 and v38. A loose replacement that passes on anything would be worse than
    the original, so the failure cases are pinned here.
    """

    def test_parses_number_and_label(self):
        self.assertEqual(get_cache_version(REAL_SHAPE), (39, 'login-refresh'))

    def test_reads_the_live_app_source(self):
        version_number, label = get_cache_version()
        self.assertGreaterEqual(version_number, 39)
        self.assertTrue(label)

    def test_passes_at_and_above_the_shipped_floor(self):
        for minimum in (35, 38, 39):
            assert_cache_version_at_least(self, minimum, REAL_SHAPE)

    def test_rejects_a_version_older_than_the_floor(self):
        old = "const CACHE_VERSION = 'medical-service-pwa-offline-navigation-v30-old';"
        with self.assertRaises(AssertionError):
            assert_cache_version_at_least(self, 35, old)

    def test_rejects_a_missing_or_malformed_constant(self):
        for bad_source in (
            'no service worker here at all',
            "const CACHE_VERSION = 'medical-service-pwa-offline-navigation-login';",
            "const CACHE_VERSION = 'something-else-v40-x';",
        ):
            with self.assertRaises(AssertionError):
                assert_cache_version_at_least(self, 35, bad_source)


if __name__ == '__main__':
    unittest.main()
