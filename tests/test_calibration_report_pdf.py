"""Focused coverage for retained Calibration Report DOCX to PDF conversion."""

import io
import json
import os
import pathlib
import re
import tempfile
import unittest
import uuid
import zipfile
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB = pathlib.Path(tempfile.gettempdir()) / f"medical_service_calibration_report_pdf_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB))
os.environ.setdefault("SECRET_KEY", "calibration-report-pdf-test-only")

import app as app_module  # noqa: E402


DOCX_TEMPLATE = ROOT / "static" / "templates" / "calibration-report" / "calibration-report-template.docx"
PDF_FIXTURE = ROOT / "static" / "templates" / "calibration-certificate" / "calibration-certificate-runtime-v2.pdf"


class CalibrationReportPdfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.db = app_module.db
        cls.docx_bytes = DOCX_TEMPLATE.read_bytes()
        cls.pdf_bytes = PDF_FIXTURE.read_bytes()

    def setUp(self):
        self.original_upload_folder = self.app.config.get("UPLOAD_FOLDER")
        self.storage = tempfile.TemporaryDirectory(prefix="calibration_report_pdf_storage_")
        self.app.config["UPLOAD_FOLDER"] = self.storage.name
        with self.app.app_context():
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
        self.app.config["UPLOAD_FOLDER"] = self.original_upload_folder
        self.storage.cleanup()

    def _create_source_fixture(self, suffix=None):
        suffix = suffix or uuid.uuid4().hex[:10]
        with self.app.app_context():
            engineer = app_module.Engineer(
                employee_id=f"PDF-ENGINEER-{suffix}",
                name="PDF Test Engineer",
                initials="PTE",
            )
            self.db.session.add(engineer)
            self.db.session.flush()
            shift = app_module.Shift(
                title="Calibration PDF Test",
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1),
                engineer_id=engineer.id,
                status="Completed",
            )
            self.db.session.add(shift)
            self.db.session.flush()
            disk_name = f"shift_{shift.id}_{suffix}_calibration_report.docx"
            source_file = app_module.ShiftFile(
                shift_id=shift.id,
                filename=disk_name,
                original_filename=f"Calibration Report {suffix}.docx",
                upload_token=f"calibration-report-source-{suffix}",
            )
            self.db.session.add(source_file)
            self.db.session.flush()
            submission = app_module.OnlineTsrSubmission(
                shift_id=shift.id,
                tsr_number=f"TSR-PDF-{suffix}",
                status="completed",
                submission_token=f"tsr-pdf-{suffix}",
                payload_json=json.dumps({
                    "_generated_calibration_report": {
                        "source": "generated_calibration_report",
                        "file_id": source_file.id,
                        "filename": source_file.original_filename,
                    },
                    "calibration_report": {
                        "generated": {
                            "attachment_id": source_file.upload_token,
                            "filename": source_file.original_filename,
                        }
                    },
                }),
                revision_no=1,
                is_latest=True,
            )
            self.db.session.add(submission)
            self.db.session.flush()
            source_file.online_tsr_submission_id = submission.id
            self.db.session.commit()
            pathlib.Path(self.storage.name, disk_name).write_bytes(self.docx_bytes)
            return source_file.id, submission.id, disk_name

    def _legacy_docx_bytes(self, focal_large='0'):
        """Build a legacy generated package by changing only recognized visible cells."""
        with zipfile.ZipFile(io.BytesIO(self.docx_bytes), 'r') as package:
            entries = [(info, package.read(info.filename)) for info in package.infolist()]
        document_index = next(
            index for index, (info, _data) in enumerate(entries)
            if info.filename == 'word/document.xml'
        )
        document_xml = entries[document_index][1].decode('utf-8')
        operations = []

        def update_cell(table_index, row_index, cell_index, transform):
            table_start, table_end = app_module._calibration_report_xml_blocks(document_xml, 'tbl')[table_index]
            table_xml = document_xml[table_start:table_end]
            row_start, row_end = app_module._calibration_report_xml_blocks(table_xml, 'tr')[row_index]
            row_xml = table_xml[row_start:row_end]
            cell_start, cell_end = app_module._calibration_report_xml_blocks(row_xml, 'tc')[cell_index]
            cell_xml = row_xml[cell_start:cell_end]
            updated = transform(cell_xml)
            operations.append((table_start + row_start + cell_start, table_start + row_start + cell_end, updated))

        def legacy_dose(cell_xml):
            updated, count = re.subn(
                r'(<w:t\b[^>]*>)u(</w:t>)',
                r'\1m\2',
                cell_xml,
                count=1,
            )
            self.assertEqual(count, 1)
            return updated

        def legacy_small_time(cell_xml):
            updated, count = re.subn(
                r'(<w:t\b[^>]*>)\(msec\)(</w:t>)',
                r'\1(sec)\2',
                cell_xml,
                count=1,
            )
            self.assertEqual(count, 1)
            return updated

        def historical_focal_size(cell_xml):
            updated, count = re.subn(
                r'(<w:t\b[^>]*>)2(</w:t>)',
                r'\g<1>' + str(focal_large) + r'\g<2>',
                cell_xml,
                count=1,
            )
            self.assertEqual(count, 1)
            return updated

        update_cell(2, 3, 3, legacy_dose)
        update_cell(3, 3, 3, legacy_dose)
        update_cell(2, 3, 6, legacy_small_time)
        if focal_large:
            update_cell(3, 1, 0, historical_focal_size)
        for start, end, updated in sorted(operations, reverse=True):
            document_xml = document_xml[:start] + updated + document_xml[end:]
        entries[document_index] = (entries[document_index][0], document_xml.encode('utf-8'))
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as target:
            for info, data in entries:
                target.writestr(info, data)
        return output.getvalue()

    @staticmethod
    def _document_texts(docx_bytes):
        with zipfile.ZipFile(io.BytesIO(docx_bytes), 'r') as package:
            import xml.etree.ElementTree as element_tree
            root = element_tree.fromstring(package.read('word/document.xml'))
        return [
            node.text or ''
            for node in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
        ]

    @staticmethod
    def _document_tables(docx_bytes):
        """Return direct table/row/cell visible text for heading-only assertions."""
        with zipfile.ZipFile(io.BytesIO(docx_bytes), 'r') as package:
            root = ET.fromstring(package.read('word/document.xml'))
        namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        body = root.find('w:body', namespace)
        tables = body.findall('w:tbl', namespace) if body is not None else []
        return [
            [
                [
                    ''.join(node.text or '' for node in cell.findall('.//w:t', namespace))
                    for cell in row.findall('w:tc', namespace)
                ]
                for row in table.findall('w:tr', namespace)
            ]
            for table in tables
        ]

    def _compact_docx_bytes(self):
        """Remove blank measurement rows as the browser generator does for saved reports."""
        legacy_bytes = self._legacy_docx_bytes()
        with zipfile.ZipFile(io.BytesIO(legacy_bytes), 'r') as package:
            entries = [(info, package.read(info.filename)) for info in package.infolist()]
        document_index = next(
            index for index, (info, _data) in enumerate(entries)
            if info.filename == 'word/document.xml'
        )
        document_xml = entries[document_index][1].decode('utf-8')
        removals = []
        for table_index in (2, 3):
            table_start, table_end = app_module._calibration_report_xml_blocks(document_xml, 'tbl')[table_index]
            table_xml = document_xml[table_start:table_end]
            rows = app_module._calibration_report_xml_blocks(table_xml, 'tr')
            for row_start, row_end in rows[5:]:
                removals.append((table_start + row_start, table_start + row_end))
        for start, end in sorted(removals, reverse=True):
            document_xml = document_xml[:start] + document_xml[end:]
        entries[document_index] = (entries[document_index][0], document_xml.encode('utf-8'))
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as target:
            for info, data in entries:
                target.writestr(info, data)
        return output.getvalue()

    def _single_focal_docx_bytes(self, removed_table_index):
        """Build the browser's one-focal-table output variant for repair coverage."""
        legacy_bytes = self._legacy_docx_bytes()
        with zipfile.ZipFile(io.BytesIO(legacy_bytes), 'r') as package:
            entries = [(info, package.read(info.filename)) for info in package.infolist()]
        document_index = next(
            index for index, (info, _data) in enumerate(entries)
            if info.filename == 'word/document.xml'
        )
        document_xml = entries[document_index][1].decode('utf-8')
        table_start, table_end = app_module._calibration_report_xml_blocks(document_xml, 'tbl')[removed_table_index]
        document_xml = document_xml[:table_start] + document_xml[table_end:]
        entries[document_index] = (entries[document_index][0], document_xml.encode('utf-8'))
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as target:
            for info, data in entries:
                target.writestr(info, data)
        return output.getvalue()

    def test_historical_docx_repair_is_fail_closed_and_header_only(self):
        legacy_bytes = self._legacy_docx_bytes()
        inspection = app_module._calibration_report_docx_repair_inspection(legacy_bytes)
        self.assertEqual(inspection['status'], 'repairable')
        self.assertEqual([item['focal_size'] for item in inspection['table_states']], ['FOCAL SIZE: 0.6', 'FOCAL SIZE: 1.0'])

        repaired_bytes, repaired_inspection = app_module._calibration_report_repair_docx_bytes(legacy_bytes)
        self.assertEqual(repaired_inspection['status'], 'already_repaired')
        self.assertEqual([item['focal_size'] for item in repaired_inspection['table_states']], ['FOCAL SIZE: 0.6', 'FOCAL SIZE: 1.0'])
        differences = [
            (before, after)
            for before, after in zip(self._document_texts(legacy_bytes), self._document_texts(repaired_bytes))
            if before != after
        ]
        self.assertEqual(differences.count(('m', 'u')), 2)
        self.assertEqual(differences.count(('(sec)', '(msec)')), 1)
        self.assertEqual(len(differences), 3)
        with zipfile.ZipFile(io.BytesIO(legacy_bytes), 'r') as old_package, zipfile.ZipFile(io.BytesIO(repaired_bytes), 'r') as new_package:
            self.assertEqual(set(old_package.namelist()), set(new_package.namelist()))
            for name in old_package.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(old_package.read(name), new_package.read(name), name)

        blocked = bytearray(legacy_bytes)
        self.assertTrue(blocked)
        self.assertEqual(
            app_module._calibration_report_docx_repair_inspection(b'not-a-docx')['status'],
            'blocked',
        )
        compact_legacy = self._compact_docx_bytes()
        compact_inspection = app_module._calibration_report_docx_repair_inspection(compact_legacy)
        self.assertEqual(compact_inspection['status'], 'repairable')
        compact_repaired, compact_result = app_module._calibration_report_repair_docx_bytes(compact_legacy)
        self.assertEqual(compact_result['status'], 'already_repaired')
        self.assertEqual([item['rows'] for item in compact_result['table_states']], [5, 5])
        self.assertEqual(
            [item['focal_size'] for item in compact_result['table_states']],
            ['FOCAL SIZE: 0.6', 'FOCAL SIZE: 1.0'],
        )
        for removed_table_index in (2, 3):
            with self.subTest(removed_table_index=removed_table_index):
                single_legacy = self._single_focal_docx_bytes(removed_table_index)
                single_inspection = app_module._calibration_report_docx_repair_inspection(single_legacy)
                self.assertEqual(single_inspection['status'], 'repairable')
                _single_repaired, single_result = app_module._calibration_report_repair_docx_bytes(single_legacy)
                self.assertEqual(single_result['status'], 'already_repaired')
                self.assertEqual(len(single_result['table_states']), 1)
                target_inspection = app_module._calibration_report_docx_repair_inspection(
                    single_legacy,
                    target_units={'small': 'mA', 'large': 'mAs'},
                )
                self.assertEqual(target_inspection['status'], 'repairable')
                target_repaired, target_result = app_module._calibration_report_repair_docx_bytes(
                    single_legacy,
                    target_units={'small': 'mA', 'large': 'mAs'},
                )
                self.assertEqual(target_result['status'], 'already_repaired')
                focal = target_result['table_states'][0]['focal']
                self.assertEqual(target_result['table_states'][0]['current_unit'], {'small': 'mA', 'large': 'mAs'}[focal])
                self.assertNotEqual(target_repaired, single_legacy)

    def test_exposure_unit_resolution_uses_model_rule_or_explicit_units(self):
        source_id, submission_id, _disk_name = self._create_source_fixture()
        with self.app.app_context():
            source_file = self.db.session.get(app_module.ShiftFile, source_id)
            submission = self.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            catalog = json.loads(
                (ROOT / 'static' / 'templates' / 'calibration-certificate' / 'calibration-certificate-catalog.json').read_text(
                    encoding='utf-8'
                )
            )
            cases = []
            for catalog_model in catalog['models']:
                expected = 'mA' if any(token in re.sub(r'[^a-z0-9]+', '', catalog_model.casefold()) for token in ('radspeed', 'flexavision')) else 'mAs'
                variants = {catalog_model, catalog_model.upper(), catalog_model.replace(' ', '  ')}
                if 'Flexavision' in catalog_model:
                    variants.update({
                        catalog_model.replace('Flexavision', 'Flexa Vision'),
                        catalog_model.replace('Flexavision', 'FLEX-A VISION'),
                    })
                if 'Radspeed' in catalog_model:
                    variants.update({
                        catalog_model.replace('Radspeed', 'Rad Speed'),
                        catalog_model.replace('Radspeed', 'RAD-SPEED'),
                    })
                cases.extend((variant, expected) for variant in variants)
            cases.extend((model, expected) for model, expected in (
                ('Some unrelated model', 'mAs'),
                ('', 'mAs'),
                (None, 'mAs'),
            ))
            for model, expected in cases:
                report = {'machine': {'model': model}} if model is not None else {'machine': {}}
                submission.payload_json = json.dumps({'calibration_report': report})
                resolution = app_module._calibration_report_exposure_unit_resolution(source_file)
                self.assertEqual(resolution['target_units'], {'small': expected, 'large': expected})
                self.assertEqual(resolution['unit_sources'], {'small': 'model_rule', 'large': 'model_rule'})
                self.assertEqual(resolution['model_rule_unit'], expected)
                self.assertFalse(resolution['explicit'])

            submission.payload_json = json.dumps({
                '_generated_calibration_report': {
                    'source': 'generated_calibration_report',
                    'file_id': source_id,
                    'filename': source_file.original_filename,
                },
                'calibration_report': {
                    'machine': {'model': 'Radspeed'},
                    'exposure_current_units': {'small': 'mA', 'large': 'mAs'},
                    'generated': {
                        'attachment_id': source_file.upload_token,
                        'filename': source_file.original_filename,
                    },
                },
            })
            resolution = app_module._calibration_report_exposure_unit_resolution(source_file)
            self.assertEqual(resolution['target_units'], {'small': 'mA', 'large': 'mAs'})
            self.assertEqual(resolution['unit_sources'], {'small': 'explicit', 'large': 'explicit'})
            self.assertTrue(resolution['explicit'])

            submission.payload_json = json.dumps({
                'calibration_report': {
                    'machine': {'model': 'Radspeed'},
                    'exposure_current_units': {'small': '', 'large': 'invalid'},
                },
            })
            resolution = app_module._calibration_report_exposure_unit_resolution(source_file)
            self.assertEqual(resolution['target_units'], {'small': '', 'large': ''})
            self.assertEqual(resolution['unit_sources'], {'small': 'explicit', 'large': 'explicit'})

    def test_v2_repairs_mixed_current_headers_and_preserves_every_other_cell(self):
        source_id, submission_id, disk_name = self._create_source_fixture()
        with zipfile.ZipFile(io.BytesIO(self.docx_bytes), 'r') as package:
            entries = [(info, package.read(info.filename)) for info in package.infolist()]
        document_index = next(
            index for index, (info, _data) in enumerate(entries)
            if info.filename == 'word/document.xml'
        )
        document_xml = entries[document_index][1].decode('utf-8')
        operations = []

        def update_cell(table_index, row_index, cell_index, transform):
            tables = app_module._calibration_report_xml_blocks(document_xml, 'tbl')
            table_start, table_end = tables[table_index]
            table_xml = document_xml[table_start:table_end]
            row_start, row_end = app_module._calibration_report_xml_blocks(table_xml, 'tr')[row_index]
            row_xml = table_xml[row_start:row_end]
            cell_start, cell_end = app_module._calibration_report_xml_blocks(row_xml, 'tc')[cell_index]
            cell_xml = row_xml[cell_start:cell_end]
            operations.append((table_start + row_start + cell_start, table_start + row_start + cell_end, transform(cell_xml)))

        update_cell(2, 3, 2, lambda cell: app_module._calibration_report_replace_current_unit_heading(cell, 'mAs'))
        update_cell(3, 3, 2, lambda cell: app_module._calibration_report_replace_current_unit_heading(cell, 'mA'))
        for start, end, updated in sorted(operations, reverse=True):
            document_xml = document_xml[:start] + updated + document_xml[end:]
        entries[document_index] = (entries[document_index][0], document_xml.encode('utf-8'))
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as target:
            for info, data in entries:
                target.writestr(info, data)
        mixed_bytes = output.getvalue()
        pathlib.Path(self.storage.name, disk_name).write_bytes(mixed_bytes)

        with self.app.app_context():
            source_file = self.db.session.get(app_module.ShiftFile, source_id)
            submission = self.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            submission.payload_json = json.dumps({
                '_generated_calibration_report': {
                    'source': 'generated_calibration_report',
                    'file_id': source_id,
                    'filename': source_file.original_filename,
                },
                'calibration_report': {
                    'machine': {'model': 'Radspeed'},
                    'exposure_current_units': {'small': 'mA', 'large': 'mAs'},
                    'generated': {
                        'attachment_id': source_file.upload_token,
                        'filename': source_file.original_filename,
                    },
                },
            })
            self.db.session.commit()
            candidate = app_module._calibration_report_repair_candidate_for_file(source_file)
            self.assertEqual(candidate['status'], 'repairable')
            self.assertEqual(candidate['target_units'], {'small': 'mA', 'large': 'mAs'})
            self.assertEqual(candidate['unit_sources'], {'small': 'explicit', 'large': 'explicit'})

        before_tables = self._document_tables(mixed_bytes)
        before_states = app_module._calibration_report_docx_repair_inspection(mixed_bytes, {'small': 'mA', 'large': 'mAs'})
        self.assertEqual(before_states['status'], 'repairable')
        self.assertEqual([item['current_unit'] for item in before_states['table_states']], ['mAs', 'mA'])
        repaired_bytes, repaired_states = app_module._calibration_report_repair_docx_bytes(
            mixed_bytes,
            target_units={'small': 'mA', 'large': 'mAs'},
        )
        self.assertEqual(repaired_states['status'], 'already_repaired')
        self.assertEqual([item['current_unit'] for item in repaired_states['table_states']], ['mA', 'mAs'])
        after_tables = self._document_tables(repaired_bytes)
        for table_index, (before_table, after_table) in enumerate(zip(before_tables, after_tables)):
            self.assertEqual(len(before_table), len(after_table), table_index)
            for row_index, (before_row, after_row) in enumerate(zip(before_table, after_table)):
                self.assertEqual(len(before_row), len(after_row), (table_index, row_index))
                for cell_index, (before_cell, after_cell) in enumerate(zip(before_row, after_row)):
                    if table_index in (2, 3) and row_index == 3 and cell_index == 2:
                        continue
                    self.assertEqual(before_cell, after_cell, (table_index, row_index, cell_index))
        second_bytes, second_states = app_module._calibration_report_repair_docx_bytes(
            repaired_bytes,
            target_units={'small': 'mA', 'large': 'mAs'},
        )
        self.assertEqual(second_states['status'], 'already_repaired')
        self.assertEqual(second_bytes, repaired_bytes)

    def test_historical_repair_preserves_file_ids_delivery_metadata_and_is_idempotent(self):
        source_id, submission_id, disk_name = self._create_source_fixture()
        legacy_bytes = self._legacy_docx_bytes()
        source_path = pathlib.Path(self.storage.name, disk_name)
        source_path.write_bytes(legacy_bytes)
        fixed_emailed_at = datetime(2026, 1, 2, 3, 4, 5)
        with self.app.app_context():
            source_file = self.db.session.get(app_module.ShiftFile, source_id)
            source_file.last_emailed_at = fixed_emailed_at
            pdf_disk_name = f'legacy-linked-{source_id}.pdf'
            pdf_file = app_module.ShiftFile(
                shift_id=source_file.shift_id,
                filename=pdf_disk_name,
                original_filename='Legacy Linked Report.pdf',
                upload_token=f'calibration-report-pdf-legacy-{source_id}',
                online_tsr_submission_id=submission_id,
                uploaded_at=datetime(2025, 12, 1),
                last_emailed_at=fixed_emailed_at,
            )
            self.db.session.add(pdf_file)
            self.db.session.flush()
            pathlib.Path(self.storage.name, pdf_disk_name).write_bytes(self.pdf_bytes)
            job = app_module.CalibrationReportConversion(
                source_shift_file_id=source_id,
                pdf_shift_file_id=pdf_file.id,
                source_sha256='old-source-sha',
                pdf_sha256='old-pdf-sha',
                converter_version='legacy-converter',
                state='ready',
                attempts=1,
                converted_at=datetime(2025, 12, 1),
                updated_at=datetime(2025, 12, 1),
            )
            approval = app_module.CalibrationCertificateApproval(
                shift_id=source_file.shift_id,
                online_tsr_submission_id=submission_id,
                revision_no=1,
                is_latest=True,
                status='Approved',
                certificate_number=f'HIST-{source_id}',
                mapped_data_json='{}',
                template_sha256=app_module.CALIBRATION_CERTIFICATE_RUNTIME_SHA256,
                unsigned_artifact_path=f'calibration-certificates/hist-{source_id}.pdf',
                approved_at=datetime(2025, 12, 1),
            )
            self.db.session.add_all([job, approval])
            self.db.session.commit()
            before_candidate = app_module._calibration_report_repair_candidate_for_file(source_file)
            self.assertEqual(before_candidate['status'], 'repairable')
            self.assertTrue(before_candidate['approved'])
            self.assertTrue(before_candidate['emailed'])
            app_module.ensure_universal_approval_audit_table()
            audit_before = app_module.UniversalApprovalAuditTrail.query.count()

            with patch.object(app_module, 'convert_calibration_report_docx_bytes', return_value=self.pdf_bytes) as converter:
                first = app_module._calibration_report_apply_historical_repair(source_id)
                second = app_module._calibration_report_apply_historical_repair(source_id)

            self.assertEqual(first['status'], 'repaired')
            self.assertEqual(second['status'], 'already_repaired')
            self.assertEqual(converter.call_count, 1)
            self.assertEqual(first['source_file_id'], source_id)
            self.assertEqual(first['pdf_file_id'], pdf_file.id)
            self.assertEqual(first['repair_id'], f'calibration-report-{source_id}')
            refreshed_source = self.db.session.get(app_module.ShiftFile, source_id)
            refreshed_pdf = self.db.session.get(app_module.ShiftFile, pdf_file.id)
            refreshed_job = self.db.session.get(app_module.CalibrationReportConversion, job.id)
            refreshed_approval = self.db.session.get(app_module.CalibrationCertificateApproval, approval.id)
            submission = self.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            self.assertNotEqual(pathlib.Path(self.storage.name, disk_name).read_bytes(), legacy_bytes)
            self.assertEqual(pathlib.Path(self.storage.name, pdf_disk_name).read_bytes(), self.pdf_bytes)
            self.assertEqual(refreshed_source.id, source_id)
            self.assertEqual(refreshed_pdf.id, pdf_file.id)
            self.assertEqual(refreshed_source.original_filename, source_file.original_filename)
            self.assertEqual(refreshed_pdf.original_filename, 'Legacy Linked Report.pdf')
            self.assertEqual(refreshed_source.last_emailed_at, fixed_emailed_at)
            self.assertEqual(refreshed_pdf.last_emailed_at, fixed_emailed_at)
            self.assertEqual(refreshed_approval.status, 'Approved')
            self.assertEqual(refreshed_job.state, 'ready')
            marker = json.loads(submission.payload_json)[app_module.CALIBRATION_REPORT_HISTORICAL_REPAIR_MARKER]
            self.assertEqual(marker['version'], app_module.CALIBRATION_REPORT_HISTORICAL_REPAIR_VERSION)
            self.assertEqual(marker['source_file_id'], source_id)
            self.assertEqual(marker['pdf_file_id'], pdf_file.id)
            self.assertEqual(
                app_module.UniversalApprovalAuditTrail.query.filter_by(
                    module='calibration_report', record_id=source_id,
                    action='historical_repair_repaired',
                ).count(),
                1,
            )
            self.assertGreaterEqual(
                app_module.ActivityLog.query.filter(
                    app_module.ActivityLog.action.ilike('%historical repair completed%')
                ).count(),
                1,
            )
            self.assertGreaterEqual(app_module.UniversalApprovalAuditTrail.query.count(), audit_before + 1)
            manifest_approval = SimpleNamespace(
                id=approval.id,
                revision_no=approval.revision_no,
                report_fingerprint='report-fingerprint',
                certificate_fingerprint='certificate-fingerprint',
            )
            old_manifest = app_module.get_calibration_center_manifest_signature(
                manifest_approval,
                [{'id': pdf_file.id, 'source_type': 'calibration_report', 'display_name': 'Legacy Linked Report.pdf', 'file_size': len(self.pdf_bytes), 'content_fingerprint': 'before'}],
            )
            new_manifest = app_module.get_calibration_center_manifest_signature(
                manifest_approval,
                [{'id': pdf_file.id, 'source_type': 'calibration_report', 'display_name': 'Legacy Linked Report.pdf', 'file_size': len(self.pdf_bytes), 'content_fingerprint': first['pdf_sha256']}],
            )
            self.assertNotEqual(old_manifest, new_manifest)

    def test_historical_repair_creates_missing_pdf_and_rolls_back_storage_failure(self):
        source_id, submission_id, disk_name = self._create_source_fixture()
        legacy_bytes = self._legacy_docx_bytes()
        pathlib.Path(self.storage.name, disk_name).write_bytes(legacy_bytes)
        with self.app.app_context():
            with patch.object(app_module, 'convert_calibration_report_docx_bytes', return_value=self.pdf_bytes):
                result = app_module._calibration_report_apply_historical_repair(source_id)
            self.assertEqual(result['status'], 'repaired')
            job = app_module.calibration_report_conversion_for_source(source_id)
            self.assertIsNotNone(job)
            pdf_file = self.db.session.get(app_module.ShiftFile, job.pdf_shift_file_id)
            self.assertIsNotNone(pdf_file)
            self.assertEqual(pdf_file.online_tsr_submission_id, submission_id)
            self.assertTrue(pathlib.Path(self.storage.name, pdf_file.filename).is_file())

        source_id, submission_id, disk_name = self._create_source_fixture()
        legacy_bytes = self._legacy_docx_bytes()
        source_path = pathlib.Path(self.storage.name, disk_name)
        source_path.write_bytes(legacy_bytes)
        with self.app.app_context():
            source_file = self.db.session.get(app_module.ShiftFile, source_id)
            pdf_disk_name = f'rollback-linked-{source_id}.pdf'
            pdf_file = app_module.ShiftFile(
                shift_id=source_file.shift_id,
                filename=pdf_disk_name,
                original_filename='Rollback Linked.pdf',
                upload_token=f'calibration-report-pdf-rollback-{source_id}',
                online_tsr_submission_id=submission_id,
            )
            self.db.session.add(pdf_file)
            self.db.session.flush()
            original_pdf = self.pdf_bytes
            pathlib.Path(self.storage.name, pdf_disk_name).write_bytes(original_pdf)
            job = app_module.CalibrationReportConversion(
                source_shift_file_id=source_id,
                pdf_shift_file_id=pdf_file.id,
                state='ready', attempts=1,
                source_sha256='rollback-source', pdf_sha256='rollback-pdf',
                updated_at=datetime(2025, 12, 1),
            )
            self.db.session.add(job)
            self.db.session.commit()
            original_replace = app_module._calibration_report_replace_storage_snapshot
            calls = {'count': 0}

            def fail_on_pdf(snapshot, data, original_filename, content_type):
                calls['count'] += 1
                if calls['count'] == 2:
                    raise OSError('simulated managed storage failure')
                return original_replace(snapshot, data, original_filename, content_type)

            with patch.object(app_module, 'convert_calibration_report_docx_bytes', return_value=self.pdf_bytes), \
                    patch.object(app_module, '_calibration_report_replace_storage_snapshot', side_effect=fail_on_pdf):
                result = app_module._calibration_report_apply_historical_repair(source_id)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(source_path.read_bytes(), legacy_bytes)
            self.assertEqual(pathlib.Path(self.storage.name, pdf_disk_name).read_bytes(), original_pdf)
            self.assertEqual(
                app_module.UniversalApprovalAuditTrail.query.filter_by(
                    module='calibration_report', record_id=source_id,
                    action='historical_repair_failed',
                ).count(),
                1,
            )

    def test_docx_and_pdf_validation_happens_before_conversion(self):
        self.assertTrue(app_module._calibration_report_pdf_bytes_are_valid(self.pdf_bytes))
        self.assertFalse(app_module._calibration_report_pdf_bytes_are_valid(b"not a pdf"))
        with self.assertRaisesRegex(ValueError, "not a readable DOCX"):
            app_module._validate_calibration_report_docx_bytes(b"not a docx")

        with patch.object(app_module.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "not a readable DOCX"):
                app_module.convert_calibration_report_docx_bytes(b"not a docx")
            run.assert_not_called()

    def test_conversion_uses_isolated_headless_writer_and_validates_output(self):
        def fake_run(command, **kwargs):
            outdir = pathlib.Path(command[command.index("--outdir") + 1])
            source_path = pathlib.Path(command[-1])
            (outdir / f"{source_path.stem}.pdf").write_bytes(self.pdf_bytes)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.dict(os.environ, {"LIBREOFFICE_BIN": ""}, clear=False), \
                patch.object(app_module.shutil, "which", side_effect=lambda name: "soffice" if name == "soffice" else None), \
                patch.object(app_module.subprocess, "run", side_effect=fake_run) as run:
            converted = app_module.convert_calibration_report_docx_bytes(
                self.docx_bytes,
                "Calibration Report sample.docx",
            )

        self.assertEqual(converted, self.pdf_bytes)
        command = run.call_args.args[0]
        self.assertIn("--headless", command)
        self.assertIn("--convert-to", command)
        self.assertIn("pdf", command)
        self.assertIn("--outdir", command)
        self.assertTrue(any(str(item).startswith("-env:UserInstallation=file:") for item in command))
        self.assertEqual(run.call_args.kwargs["timeout"], app_module.CALIBRATION_REPORT_CONVERTER_TIMEOUT_SECONDS)

    def test_stored_conversion_is_idempotent_and_keeps_source_bytes_private(self):
        source_id, submission_id, disk_name = self._create_source_fixture()
        with self.app.app_context():
            with patch.object(app_module, "convert_calibration_report_docx_bytes", return_value=self.pdf_bytes) as converter:
                first = app_module.convert_calibration_report_source(source_id)
                second = app_module.convert_calibration_report_source(source_id)

            source_file = self.db.session.get(app_module.ShiftFile, source_id)
            job = self.db.session.get(app_module.CalibrationReportConversion, first.id)
            pdf_file = self.db.session.get(app_module.ShiftFile, job.pdf_shift_file_id)
            submission = self.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            marker = json.loads(submission.payload_json)["_generated_calibration_report"]
            self.assertEqual(first.id, second.id)
            self.assertEqual(job.state, "ready")
            self.assertEqual(job.attempts, 1)
            self.assertEqual(converter.call_count, 1)
            self.assertEqual(pdf_file.original_filename, f"Calibration_Report_{disk_name.split('_')[2]}.pdf")
            self.assertEqual(pathlib.Path(self.storage.name, disk_name).read_bytes(), self.docx_bytes)
            self.assertTrue(app_module.calibration_report_source_file_is_private(source_file))
            self.assertEqual(marker["pdf_state"], "ready")
            self.assertEqual(marker["pdf_file_id"], pdf_file.id)
            self.assertEqual(marker["pdf_filename"], pdf_file.original_filename)
            self.assertEqual(
                app_module.get_user_visible_shift_file_records(source_file.shift),
                [],
            )

    def test_legacy_approved_report_is_backfilled_and_becomes_visible(self):
        source_id, submission_id, _ = self._create_source_fixture()
        with self.app.app_context():
            submission = self.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            approval = app_module.CalibrationCertificateApproval(
                shift_id=submission.shift_id,
                online_tsr_submission_id=submission.id,
                revision_no=1,
                is_latest=True,
                status='Approved',
                certificate_number=f'BACKFILL-{submission.id}',
                mapped_data_json='{}',
                template_sha256=app_module.CALIBRATION_CERTIFICATE_RUNTIME_SHA256,
                unsigned_artifact_path=f'calibration-certificates/backfill-{submission.id}.pdf',
                approved_at=datetime.now(),
            )
            self.db.session.add(approval)
            self.db.session.commit()

            original_backfill_state = app_module._calibration_report_conversion_backfill_checked
            app_module._calibration_report_conversion_backfill_checked = False
            try:
                queued = app_module.queue_missing_calibration_report_conversions()
                job = app_module.calibration_report_conversion_for_source(source_id)
                self.assertGreaterEqual(queued, 1)
                self.assertIsNotNone(job)
                self.assertEqual(job.state, 'pending')

                with patch.object(
                    app_module,
                    'convert_calibration_report_docx_bytes',
                    return_value=self.pdf_bytes,
                ):
                    app_module.convert_calibration_report_source(source_id)

                source_file = self.db.session.get(app_module.ShiftFile, source_id)
                shift = self.db.session.get(app_module.Shift, source_file.shift_id)
                visible_files = app_module.get_user_visible_shift_file_records(shift)
                self.assertEqual(len(visible_files), 1)
                self.assertTrue(
                    app_module.is_system_generated_calibration_report_pdf_file(visible_files[0])
                )

                submission.is_latest = False
                newer_submission = app_module.OnlineTsrSubmission(
                    shift_id=shift.id,
                    tsr_number=f'TSR-PDF-NEWER-{submission.id}',
                    status='completed',
                    submission_token=f'tsr-pdf-newer-{submission.id}',
                    payload_json=json.dumps({'_attached_file_id': None}),
                    revision_no=2,
                    parent_submission_id=submission.id,
                    is_latest=True,
                )
                self.db.session.add(newer_submission)
                self.db.session.commit()

                visible_after_tsr_only_revision = app_module.get_user_visible_shift_file_records(shift)
                self.assertEqual(
                    [file_record.id for file_record in visible_after_tsr_only_revision],
                    [visible_files[0].id],
                )
                delivery_state = app_module.get_linked_schedule_calibration_report_file_state([shift])
                self.assertIn(visible_files[0].id, delivery_state['latest_ids'])
            finally:
                app_module._calibration_report_conversion_backfill_checked = original_backfill_state

    def test_exhausted_approved_report_conversion_is_revived(self):
        source_id, submission_id, _ = self._create_source_fixture()
        with self.app.app_context():
            submission = self.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            job = app_module.CalibrationReportConversion(
                source_shift_file_id=source_id,
                state='failed',
                attempts=app_module.CALIBRATION_REPORT_CONVERSION_MAX_ATTEMPTS,
                last_error='temporary conversion failure',
                updated_at=datetime.now(),
            )
            approval = app_module.CalibrationCertificateApproval(
                shift_id=submission.shift_id,
                online_tsr_submission_id=submission.id,
                revision_no=1,
                is_latest=True,
                status='Approved',
                certificate_number=f'RETRY-{submission.id}',
                mapped_data_json='{}',
                template_sha256=app_module.CALIBRATION_CERTIFICATE_RUNTIME_SHA256,
                unsigned_artifact_path=f'calibration-certificates/retry-{submission.id}.pdf',
                approved_at=datetime.now(),
            )
            self.db.session.add_all([job, approval])
            self.db.session.commit()

            original_backfill_state = app_module._calibration_report_conversion_backfill_checked
            app_module._calibration_report_conversion_backfill_checked = False
            try:
                recovered = app_module.queue_missing_calibration_report_conversions()
                self.db.session.refresh(job)
                self.assertGreaterEqual(recovered, 1)
                self.assertEqual(job.state, 'pending')
                self.assertEqual(job.attempts, 0)
                self.assertIsNone(job.last_error)

                with patch.object(
                    app_module,
                    'convert_calibration_report_docx_bytes',
                    return_value=self.pdf_bytes,
                ):
                    app_module.convert_calibration_report_source(source_id)

                source_file = self.db.session.get(app_module.ShiftFile, source_id)
                shift = self.db.session.get(app_module.Shift, source_file.shift_id)
                visible_files = app_module.get_user_visible_shift_file_records(shift)
                self.assertEqual(len(visible_files), 1)
                self.assertTrue(
                    app_module.is_system_generated_calibration_report_pdf_file(visible_files[0])
                )
            finally:
                app_module._calibration_report_conversion_backfill_checked = original_backfill_state

    def test_conversion_failure_persists_retry_state_without_removing_source(self):
        source_id, submission_id, disk_name = self._create_source_fixture()
        with self.app.app_context():
            with patch.object(
                app_module,
                "convert_calibration_report_docx_bytes",
                side_effect=RuntimeError("writer unavailable"),
            ):
                job = app_module.convert_calibration_report_source(source_id)

            submission = self.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            source_file = self.db.session.get(app_module.ShiftFile, source_id)
            marker = json.loads(submission.payload_json)["_generated_calibration_report"]
            self.assertEqual(job.state, "failed")
            self.assertEqual(job.attempts, 1)
            self.assertIsNotNone(job.next_retry_at)
            self.assertIn("writer unavailable", job.last_error)
            self.assertEqual(marker["pdf_state"], "failed")
            self.assertIn("writer unavailable", marker["pdf_error"])
            self.assertTrue(pathlib.Path(self.storage.name, disk_name).is_file())
            self.assertEqual(
                app_module.get_user_visible_shift_file_records(source_file.shift),
                [],
            )

    def test_email_gate_reports_pending_and_failed_latest_pdf_states(self):
        shift = SimpleNamespace(id=1)
        with self.app.app_context():
            with patch.object(app_module, "get_linked_schedule_file_shifts", return_value=[shift]), \
                    patch.object(app_module, "get_linked_schedule_calibration_report_file_state", return_value={
                        "pending_latest_source_ids": {11},
                        "failed_latest_source_ids": set(),
                    }):
                self.assertIn("still being prepared", app_module.get_calibration_report_email_block(shift))

            with patch.object(app_module, "get_linked_schedule_file_shifts", return_value=[shift]), \
                    patch.object(app_module, "get_linked_schedule_calibration_report_file_state", return_value={
                        "pending_latest_source_ids": set(),
                        "failed_latest_source_ids": {11},
                    }):
                self.assertIn("conversion failed", app_module.get_calibration_report_email_block(shift))


if __name__ == "__main__":
    unittest.main()
