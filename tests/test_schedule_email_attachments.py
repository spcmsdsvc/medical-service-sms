import os
import tempfile
import unittest
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from werkzeug.datastructures import FileStorage, MultiDict

import app as app_module


class ScheduleEmailAttachmentTests(unittest.TestCase):
    def test_schedule_upload_limits_match_accounting_rules(self):
        self.assertEqual(app_module.SCHEDULE_ATTACHMENT_INTAKE_MAX_BYTES, 35 * 1024 * 1024)
        self.assertEqual(app_module.SCHEDULE_ATTACHMENT_STORED_MAX_BYTES, 2 * 1024 * 1024)
        self.assertEqual(app_module.SCHEDULE_MANUAL_UPLOAD_LIMIT, 10)
        self.assertEqual(app_module.SCHEDULE_ATTACHMENT_EXTENSIONS, {'pdf', 'png', 'jpg', 'jpeg'})

    def test_validation_rejects_linked_job_above_ten_manual_uploads(self):
        files = [
            FileStorage(stream=BytesIO(b'%PDF-test'), filename=f'image-{index}.pdf', content_type='application/pdf')
            for index in range(2)
        ]
        shift = SimpleNamespace(id=17)
        upload_data = MultiDict([('report_file', item) for item in files])
        with app_module.app.test_request_context('/update_shift/17', method='POST', data=upload_data):
            with patch.object(app_module, 'get_linked_schedule_manual_upload_count', return_value=9):
                valid, message = app_module.validate_uploaded_report_files(shift)

        self.assertFalse(valid)
        self.assertIn('up to 10', message)
        self.assertIn('you may add 1 more', message)

    def test_email_package_orders_tsr_then_supporting_pdf_and_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            generated_path = os.path.join(temp_dir, 'generated.pdf')
            supporting_pdf_path = os.path.join(temp_dir, 'quotation.pdf')
            supporting_image_path = os.path.join(temp_dir, 'site-photo.jpg')
            for path, content in (
                (generated_path, b'generated'),
                (supporting_pdf_path, b'pdf'),
                (supporting_image_path, b'jpg'),
            ):
                with open(path, 'wb') as output:
                    output.write(content)

            records = [
                SimpleNamespace(id=2, filename='quotation.pdf', original_filename='Quotation.pdf', uploaded_at=None),
                SimpleNamespace(id=3, filename='site-photo.jpg', original_filename='Site Photo.jpg', uploaded_at=None),
            ]
            shift = SimpleNamespace(
                id=17,
                files=records,
                start_time=datetime(2026, 7, 17, 8, 0),
            )
            generated = {
                'id': 1,
                'shift_id': 17,
                'filename': 'generated.pdf',
                'display_name': 'TSR_generated.pdf',
                'path': generated_path,
                'source_type': 'generated',
                'source_label': 'Generated TSR',
                'service_date': '2026-07-17',
                'file_size': os.path.getsize(generated_path),
            }

            path_map = {
                'quotation.pdf': supporting_pdf_path,
                'site-photo.jpg': supporting_image_path,
            }

            def resolve_path(_prefix, local_path):
                return path_map[os.path.basename(local_path)]

            with patch.object(app_module, 'get_tsr_files_for_shift', return_value=[generated]), \
                    patch.object(app_module, 'get_linked_schedule_file_shifts', return_value=[shift]), \
                    patch.object(app_module, 'get_linked_schedule_generated_file_ids', return_value={1}), \
                    patch.object(app_module, 'get_legacy_incomplete_tsr_file_policy', return_value={}), \
                    patch.object(app_module, 'managed_storage_read_path', side_effect=resolve_path):
                package = app_module.get_tsr_email_files_for_shift(shift)

        self.assertEqual([item['source_type'] for item in package], [
            'generated',
            'supporting_pdf',
            'supporting_image',
        ])
        self.assertTrue(package[0]['is_tsr'])
        self.assertFalse(package[1]['is_tsr'])
        self.assertFalse(package[2]['is_tsr'])


if __name__ == '__main__':
    unittest.main()
