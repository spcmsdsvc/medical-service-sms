"""A serial correction from TSR revision keeps the product's BSID and room (plans.md, 2026-11-04)."""

import types
import unittest
import uuid

import app as app_module


class TsrSerialCorrectionKeepsBsidTests(unittest.TestCase):
    def test_serial_correction_keeps_bsid_and_room(self):
        suffix = uuid.uuid4().hex[:8].upper()
        old_serial, new_serial = f'BSIDKEEP-OLD-{suffix}', f'BSIDKEEP-NEW-{suffix}'
        bsid = f'BSID-KEEP-{suffix}'
        app = app_module.app
        with app.test_request_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.db.session.add(app_module.Product(
                serial_number=old_serial, name='Keep Machine', room='Room 4', bsid=bsid,
            ))
            app_module.db.session.commit()
            try:
                shift = types.SimpleNamespace(product_id=old_serial, equipment_source='product')
                result = app_module.correct_product_from_tsr_revision(shift, {
                    '_tsr_equipment_correction_requested': True,
                    'tsr-serial-no': new_serial,
                    'tsr-equipment-model': 'Keep Machine',
                })
                app_module.db.session.commit()

                self.assertEqual(result['status'], 'updated')
                self.assertIsNone(app_module.db.session.get(app_module.Product, old_serial))
                corrected = app_module.db.session.get(app_module.Product, new_serial)
                self.assertEqual(corrected.bsid, bsid)
                self.assertEqual(corrected.room, 'Room 4')
            finally:
                app_module.db.session.rollback()
                for serial in (old_serial, new_serial):
                    product = app_module.db.session.get(app_module.Product, serial)
                    if product:
                        app_module.db.session.delete(product)
                app_module.db.session.commit()


if __name__ == '__main__':
    unittest.main()
