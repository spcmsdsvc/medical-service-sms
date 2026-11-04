"""A serial correction from TSR revision keeps the product's BSID and room (plans.md, 2026-11-04)."""

import types
from datetime import date, datetime
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

    def test_serial_correction_moves_po_and_link_and_keeps_other_schedules(self):
        m = app_module
        suffix = uuid.uuid4().hex[:8].upper()
        old_serial, new_serial = f'MOVE-OLD-{suffix}', f'MOVE-NEW-{suffix}'
        vieworks_serial = f'MOVE-VW-{suffix}'
        with m.app.test_request_context():
            m.db.create_all()
            m.ensure_product_contract_column()
            m.ensure_purchase_order_schema()
            m.ensure_product_vieworks_link_table()
            client = m.Client(name=f'Move Client {suffix}', address='Move address')
            engineer = m.Engineer(employee_id=f'MOVE-{suffix}', name=f'Move Engineer {suffix}', initials=f'Z{suffix[:3]}')
            m.db.session.add_all([client, engineer])
            m.db.session.flush()
            m.db.session.add(m.Product(
                serial_number=old_serial, name='Move Machine', bsid=f'BSID-MOVE-{suffix}', client_id=client.id,
            ))
            po = m.PurchaseOrder(
                client_id=client.id, po_number=f'MOVE-PO-{suffix}', po_date=date(2026, 11, 4),
                po_type='single', product_serial=old_serial,
            )
            m.db.session.add(po)
            m.db.session.flush()
            m.db.session.add(m.PurchaseOrderMachine(purchase_order_id=po.id, product_serial=old_serial))
            m.db.session.add(m.ProductVieworksLink(product_serial=old_serial, vieworks_serial=vieworks_serial))
            # A Vieworks schedule that happens to use the same serial must keep it.
            other = m.Shift(
                title='Vieworks visit', start_time=datetime(2026, 11, 4, 8), end_time=datetime(2026, 11, 4, 16),
                engineer_id=engineer.id, equipment_source='vieworks', product_id=old_serial,
            )
            m.db.session.add(other)
            m.db.session.commit()
            ids = {'client': client.id, 'engineer': engineer.id, 'po': po.id, 'other': other.id}
            try:
                shift = types.SimpleNamespace(product_id=old_serial, equipment_source='product')
                result = m.correct_product_from_tsr_revision(shift, {
                    '_tsr_equipment_correction_requested': True,
                    'tsr-serial-no': new_serial,
                    'tsr-equipment-model': 'Move Machine',
                })
                m.db.session.commit()
                m.db.session.expire_all()

                self.assertIsNone(m.db.session.get(m.Product, old_serial))
                self.assertEqual(m.db.session.get(m.PurchaseOrder, ids['po']).product_serial, new_serial)
                self.assertEqual(
                    [row.product_serial for row in m.PurchaseOrderMachine.query.filter_by(purchase_order_id=ids['po'])],
                    [new_serial],
                )
                self.assertEqual(
                    [row.product_serial for row in m.ProductVieworksLink.query.filter_by(vieworks_serial=vieworks_serial)],
                    [new_serial],
                )
                self.assertEqual(m.db.session.get(m.Shift, ids['other']).product_id, old_serial)
                self.assertEqual(result['linked_purchase_order_count'], 1)
            finally:
                m.db.session.rollback()
                m.ProductVieworksLink.query.filter_by(vieworks_serial=vieworks_serial).delete()
                m.PurchaseOrderMachine.query.filter_by(purchase_order_id=ids['po']).delete()
                m.PurchaseOrder.query.filter_by(id=ids['po']).delete()
                m.Shift.query.filter_by(id=ids['other']).delete()
                m.Product.query.filter(m.Product.serial_number.in_([old_serial, new_serial])).delete()
                m.Engineer.query.filter_by(id=ids['engineer']).delete()
                m.Client.query.filter_by(id=ids['client']).delete()
                m.db.session.commit()


if __name__ == '__main__':
    unittest.main()
