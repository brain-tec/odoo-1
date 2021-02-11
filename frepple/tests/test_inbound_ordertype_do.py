##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from tempfile import mkstemp
import os
from unittest import skipIf
from odoo.addons.frepple.tests.test_base import TestBase
from odoo import fields
from dateutil.relativedelta import relativedelta

UNDER_DEVELOPMENT = False
UNDER_DEVELOPMENT_MSG = 'Test skipped because of being under development'


class TestInboundOrdertypeDo(TestBase):
    def setUp(self):
        super(TestInboundOrdertypeDo, self).setUp()
        self.product = self._create_product('Product #1', price=1)
        self.dest_loc = self._create_location('Destination Location')
        self.source_loc = self._create_location('Source Location')
        warehouse = self.env.ref('stock.warehouse0')
        warehouse.lot_stock_id = self.dest_loc
        warehouse.int_type_id.default_location_src_id = self.source_loc
        warehouse.int_type_id.default_location_dest_id = self.dest_loc

    def _create_xml(self, reference, product, source_location, destination_location, qty, datetime_xml=None):
        if datetime_xml is None:
            datetime_xml = fields.Datetime.to_string(fields.Datetime.now()).replace(' ', 'T')
        xml_content = '''<?xml version="1.0" encoding="UTF-8" ?>
            <plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" source="odoo_1">
                <operationplans>
                    <operationplan reference="{reference}" ordertype="DO"
                      start="{datetime}" end="{datetime}"
                      quantity="{qty:0.6f}" status="proposed"
                      item="{product_name}" item_id="{uom_id},{product_id}"
                      origin="{origin_name}" origin_id="{origin_id}"
                      destination="{location_name}" destination_id="{location_id}"
                      criticality="1"
                    />
                </operationplans>
            </plan>
        '''.format(reference=reference,
                   product_name=product.name,
                   product_id=product.id,
                   location_name=destination_location.name,
                   location_id=destination_location.id,
                   origin_name=source_location.name,
                   origin_id=source_location.id,
                   qty=qty,
                   datetime=datetime_xml,
                   uom_id=product.uom_id.id)
        fd, xml_file_path = mkstemp(prefix='frepple_inbound_xml_', dir="/tmp")
        f = open(xml_file_path, 'w')
        f.write(xml_content)
        f.close()
        os.close(fd)
        return xml_content, xml_file_path

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_do_new_picking_new_move(self):
        """ Tests an input XML that creates a new move and a new picking.
        """
        stock_picking = self.env['stock.picking']
        stock_move = self.env['stock.move']

        ref = 'ref-001'
        qty = 100

        self.assertFalse(stock_picking.search([
            ('origin', '=', 'frePPLe'),
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ]))

        datetime_str_odoo = fields.Datetime.to_string(fields.Datetime.now() + relativedelta(minutes=15))
        datetime_str_xml = datetime_str_odoo.replace(' ', 'T')

        _, xml_file = self._create_xml(
            ref, self.product, self.source_loc, self.dest_loc, qty=qty, datetime_xml=datetime_str_xml)
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.company = self.env.user.company_id
        self.importer.run()
        f.close()

        move = stock_move.search([('frepple_reference', '=', ref)])
        picking = stock_picking.search([
            ('origin', '=', 'frePPLe'),
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ])
        self.assertEqual(len(move), 1)
        self.assertEqual(len(picking), 1)
        self.assertEqual(len(picking.move_line_ids), 0)
        self.assertEqual(len(picking.move_lines), 1)
        self.assertEqual(move.product_id, self.product)
        self.assertEqual(move.product_uom_qty, qty)
        self.assertEqual(picking.location_dest_id, self.dest_loc)
        self.assertEqual(picking.location_id, self.source_loc)
        self.assertEqual(move.picking_id, picking)
        # There was no picking nor move. The new picking has just one move, so its scheduled date
        # matches the expected date of the new move created
        self.assertEqual(picking.scheduled_date, move.date_expected)
        # New move stores as date_expected the right value
        self.assertEqual(fields.Datetime.to_string(move.date_expected), datetime_str_odoo)

    def _do_existing_picking_new_move_importer(self, existing_ref, ref, qty, importer_mode, datetime_str_xml):
        stock_move = self.env['stock.move']

        # A picking already exists.
        # 'scheduled_date': datetime_str_odoo No need to assign scheduled date to picking as
        # it will take the earliest from moves
        picking = self._create_internal_picking(
            self.source_loc, self.dest_loc, defaults={'origin': 'frePPLe'})
        self.assertFalse(picking.move_lines)
        self.assertFalse(picking.move_line_ids)

        # A move already exists.
        move = self._create_move(
            self.source_loc, self.dest_loc, self.product,
            defaults={'product_uom_qty': qty, 'picking_id': picking.id, 'frepple_reference': existing_ref})

        self.assertEqual(stock_move.search([('frepple_reference', '=', existing_ref)]), move)

        _, xml_file = self._create_xml(
            ref, self.product, self.source_loc, self.dest_loc, qty=qty, datetime_xml=datetime_str_xml)
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.company = self.env.user.company_id
        self.importer.mode = importer_mode
        self.importer.imported_pickings[(self.source_loc.id, self.dest_loc.id)] = picking.id
        self.importer.run()
        f.close()
        return picking, move

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_do_existing_picking_new_move_importer_mode_2(self):
        """ Tests an input XML that creates a new move and adds it to a picking that already exists.
        """
        existing_ref = 'ref-001'
        ref = 'ref-002'
        qty = 200

        datetime_str_odoo = fields.Datetime.to_string(fields.Datetime.now() + relativedelta(minutes=15))
        datetime_str_xml = datetime_str_odoo.replace(' ', 'T')

        existing_picking, existing_move = self._do_existing_picking_new_move_importer(
            existing_ref, ref, qty, importer_mode=2, datetime_str_xml=datetime_str_xml)

        stock_picking = self.env['stock.picking']
        stock_move = self.env['stock.move']

        self.assertEqual(self.importer.mode, 2)
        new_move = stock_move.search([('frepple_reference', '=', ref)])
        frepple_pickings = stock_picking.search([
            ('origin', '=', 'frePPLe'),
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ])
        self.assertEqual(frepple_pickings, existing_picking)
        self.assertEqual(len(new_move), 1)
        self.assertEqual(len(existing_picking), 1)
        self.assertEqual(len(frepple_pickings), 1)
        self.assertEqual(len(existing_picking.move_line_ids), 0)
        self.assertEqual(len(existing_picking.move_lines), 2)
        self.assertEqual(new_move.product_id, self.product)
        self.assertEqual(new_move.product_uom_qty, qty)
        self.assertEqual(existing_picking.location_dest_id, self.dest_loc)
        self.assertEqual(existing_picking.location_id, self.source_loc)
        self.assertEqual(new_move.picking_id, existing_picking)
        # Date of the picking is the minimum of the two moves. As we are creating the new one 15 min later,
        # that has to match the time of the existing move
        self.assertEqual(existing_picking.scheduled_date, existing_move.date_expected)
        # New move stores as date_expected the right value (15 min later than the existing move)
        self.assertEqual(fields.Datetime.to_string(new_move.date_expected), datetime_str_odoo)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_do_existing_picking_new_move_importer_mode_1(self):
        """ Tests an input XML that creates a new move and adds it to a new picking,
            as the existing picking was in draft and it is deleted
        """
        existing_ref = 'ref-001'
        ref = 'ref-002'
        qty = 200

        datetime_str_odoo = fields.Datetime.to_string(fields.Datetime.now() + relativedelta(minutes=15))
        datetime_str_xml = datetime_str_odoo.replace(' ', 'T')

        existing_picking, existing_move = self._do_existing_picking_new_move_importer(
            existing_ref, ref, qty, importer_mode=1, datetime_str_xml=datetime_str_xml)

        stock_picking = self.env['stock.picking']
        stock_move = self.env['stock.move']

        self.assertEqual(self.importer.mode, 1)
        new_move = stock_move.search([('frepple_reference', '=', ref)])
        frepple_pickings = stock_picking.search([
            ('origin', '=', 'frePPLe'),
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ])

        self.assertEqual(len(new_move), 1)
        self.assertEqual(len(existing_picking), 1)
        # Just 1 as the existing picking was deleted and a new one was created
        self.assertEqual(len(frepple_pickings), 1)
        self.assertEqual(len(frepple_pickings.move_line_ids), 0)
        self.assertEqual(len(frepple_pickings.move_lines), 1)
        self.assertEqual(new_move.product_id, self.product)
        self.assertEqual(new_move.product_uom_qty, qty)
        self.assertEqual(frepple_pickings.location_dest_id, self.dest_loc)
        self.assertEqual(frepple_pickings.location_id, self.source_loc)
        self.assertEqual(new_move.picking_id, frepple_pickings)
        # As existing picking and move were deleted, the new picking has just one move, so its scheduled date
        # matches the expected date of the new move created
        self.assertEqual(frepple_pickings.scheduled_date, new_move.date_expected)
        # New move stores as date_expected the right value (15 min later than the existing move)
        self.assertEqual(fields.Datetime.to_string(new_move.date_expected), datetime_str_odoo)