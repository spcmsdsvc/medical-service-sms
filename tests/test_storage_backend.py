import io
import os
import tempfile
import unittest
from unittest.mock import patch

from storage_backend import (
    FileStorageBackend,
    StorageObjectConflict,
    StorageObjectNotFound,
    sha256_bytes,
)


class FakeS3Error(Exception):
    def __init__(self, code):
        self.response = {'Error': {'Code': code}}
        super().__init__(code)


class FakeBody:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


class FakePaginator:
    def __init__(self, client):
        self.client = client

    def paginate(self, Bucket, Prefix=''):
        contents = [
            {'Key': key, 'Size': len(value['data']), 'LastModified': None}
            for key, value in sorted(self.client.objects.items())
            if key.startswith(Prefix)
        ]
        yield {'Contents': contents}


class FakeS3Client:
    def __init__(self):
        self.objects = {}

    def head_bucket(self, Bucket):
        return {}

    def put_object(self, Bucket, Key, Body, ContentType, Metadata):
        self.objects[Key] = {
            'data': bytes(Body),
            'content_type': ContentType,
            'metadata': dict(Metadata),
        }

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise FakeS3Error('404')
        item = self.objects[Key]
        return {
            'ContentLength': len(item['data']),
            'ContentType': item['content_type'],
            'Metadata': item['metadata'],
        }

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise FakeS3Error('NoSuchKey')
        return {'Body': FakeBody(self.objects[Key]['data'])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def get_paginator(self, name):
        if name != 'list_objects_v2':
            raise AssertionError(name)
        return FakePaginator(self)


class FileStorageBackendTests(unittest.TestCase):
    def build_backend(self, mode='mirror'):
        env = {
            'FILE_STORAGE_MODE': mode,
            'STORAGE_BUCKET_NAME': 'private-files',
            'STORAGE_BUCKET_ENDPOINT': 'https://bucket.example.test',
            'STORAGE_BUCKET_ACCESS_KEY': 'access',
            'STORAGE_BUCKET_SECRET_KEY': 'secret',
            'STORAGE_BUCKET_REGION': 'auto',
            'STORAGE_VOLUME_FALLBACK': 'true',
        }
        with patch.dict(os.environ, env, clear=True):
            backend = FileStorageBackend()
        backend._client = FakeS3Client()
        return backend

    def test_local_default_is_volume(self):
        with patch.dict(os.environ, {}, clear=True):
            backend = FileStorageBackend()
        self.assertEqual(backend.mode, 'volume')
        self.assertFalse(backend.writes_bucket)
        self.assertTrue(backend.writes_volume)

    def test_upload_records_checksum_and_metadata(self):
        backend = self.build_backend()
        data = b'private receipt bytes'
        result = backend.upload_bytes(
            'reimbursements/receipt.pdf',
            data,
            content_type='application/pdf',
            original_filename='Receipt July.pdf',
        )
        self.assertEqual(result.checksum, sha256_bytes(data))
        head = backend.head('reimbursements/receipt.pdf')
        self.assertEqual(head.size, len(data))
        self.assertEqual(head.checksum, sha256_bytes(data))
        self.assertEqual(backend.download_bytes('reimbursements/receipt.pdf'), data)

    def test_upload_file_refuses_different_existing_object(self):
        backend = self.build_backend()
        backend.upload_bytes('reports/file.pdf', b'old', original_filename='file.pdf')
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b'new-content')
            temp_path = temp_file.name
        try:
            with self.assertRaises(StorageObjectConflict):
                backend.upload_file('reports/file.pdf', temp_path, overwrite=False)
        finally:
            os.remove(temp_path)

    def test_upload_file_is_idempotent_for_identical_content(self):
        backend = self.build_backend()
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b'same-content')
            temp_path = temp_file.name
        try:
            first = backend.upload_file('reports/same.pdf', temp_path, overwrite=False)
            second = backend.upload_file('reports/same.pdf', temp_path, overwrite=False)
            self.assertEqual(first.checksum, second.checksum)
            self.assertEqual(len(backend._client.objects), 1)
        finally:
            os.remove(temp_path)

    def test_missing_object_raises_clear_error(self):
        backend = self.build_backend('bucket')
        self.assertIsNone(backend.head('reports/missing.pdf'))
        with self.assertRaises(StorageObjectNotFound):
            backend.download_bytes('reports/missing.pdf')

    def test_object_listing_respects_prefix(self):
        backend = self.build_backend()
        backend.upload_bytes('reports/a.pdf', b'a')
        backend.upload_bytes('travel_requests/b.pdf', b'b')
        keys = [item.key for item in backend.iter_objects('reports/')]
        self.assertEqual(keys, ['reports/a.pdf'])


if __name__ == '__main__':
    unittest.main()
