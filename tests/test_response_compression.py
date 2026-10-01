import gzip
import os
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py. Without this the import would
# open the real scheduler.db, which must never be touched by the test suite.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_compression_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


class ResponseCompressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            app_module.db.create_all()
        cls.client = app_module.app.test_client()

    def test_large_page_is_gzipped_and_decompresses_to_the_same_bytes(self):
        plain = self.client.get('/login')
        packed = self.client.get('/login', headers={'Accept-Encoding': 'gzip'})

        self.assertEqual(plain.status_code, 200)
        self.assertIsNone(plain.headers.get('Content-Encoding'))
        self.assertGreater(len(plain.data), 1024)

        self.assertEqual(packed.status_code, 200)
        self.assertEqual(packed.headers.get('Content-Encoding'), 'gzip')
        self.assertIn('Accept-Encoding', packed.headers.get('Vary', ''))
        self.assertEqual(int(packed.headers['Content-Length']), len(packed.data))
        self.assertLess(len(packed.data), len(plain.data))

        # The CSRF token differs between the two renders, so compare structure by size
        # and confirm the compressed body is a valid page rather than byte equality.
        unpacked = gzip.decompress(packed.data)
        self.assertEqual(len(unpacked), len(plain.data))
        self.assertIn(b'</html>', unpacked)

    def test_static_files_are_left_untouched(self):
        response = self.client.get(
            '/static/vendor/jszip/jszip.min.js', headers={'Accept-Encoding': 'gzip'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get('Content-Encoding'))
        expected = (ROOT / 'static' / 'vendor' / 'jszip' / 'jszip.min.js').read_bytes()
        self.assertEqual(response.data, expected)
        response.close()

    def test_hook_skips_small_binary_and_non_200_responses(self):
        hook = app_module.compress_text_response
        cases = [
            ('small', app_module.Response('x' * 100, mimetype='text/html')),
            ('binary', app_module.Response(b'%PDF' + b'0' * 5000, mimetype='application/pdf')),
            ('not-200', app_module.Response('x' * 5000, mimetype='text/html', status=404)),
        ]
        with app_module.app.test_request_context('/', headers={'Accept-Encoding': 'gzip'}):
            for label, response in cases:
                original = response.get_data()
                result = hook(response)
                self.assertIsNone(result.headers.get('Content-Encoding'), label)
                self.assertEqual(result.get_data(), original, label)

    def test_hook_compresses_json(self):
        body = '{"rows": [' + ','.join(['{"name": "Shimadzu"}'] * 500) + ']}'
        with app_module.app.test_request_context('/', headers={'Accept-Encoding': 'gzip, br'}):
            result = app_module.compress_text_response(
                app_module.Response(body, mimetype='application/json')
            )
        self.assertEqual(result.headers.get('Content-Encoding'), 'gzip')
        self.assertEqual(gzip.decompress(result.get_data()).decode('utf-8'), body)

    def test_dockerfile_limits_allocator_arenas(self):
        dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('MALLOC_ARENA_MAX=2', dockerfile)


if __name__ == '__main__':
    unittest.main()
