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

UNDER_DEVELOPMENT = False
UNDER_DEVELOPMENT_MSG = 'Test skipped because of being under development'


class TestInboundOrdertypeDo(TestBase):
    def setUp(self):
        super(TestInboundOrdertypeDo, self).setUp()
        self.product = self._create_product('Product #1', price=1)
        self.dest_loc = self._create_location('Destination Location')
        self.source_loc = self._create_location('Source Location')

    def _create_xml(self, reference, product, source_location, destination_location, qty, datetime_xml=None):
        if datetime_xml is None:
            datetime_xml = fields.Datetime.to_string(fields.Datetime.now()).replace(' ', 'T')
        xml_content = '''<?xml version="1.0" encoding="UTF-8" ?>
            <plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" source="odoo_1">
                <operationplans>
                    <operationplan reference="{reference}" ordertype="DO"
                      start="{datetime}" end="{datetime}"
                      quantity="{qty:0.6f}" status="proposed"
                      item="{product_name}" item_id="{product_id}"
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
                   datetime=datetime_xml)
        fd, xml_file_path = mkstemp(prefix='frepple_inbound_xml_', dir="/tmp")
        f = open(xml_file_path, 'w')
        f.write(xml_content)
        f.close()
        os.close(fd)
        return xml_content, xml_file_path

    def _assert_expected(self, picking, move_line, expected_qty):
        """ We are always asserting the same. So the assertions are extracted here.
        """
        self.assertEqual(len(picking.move_line_ids), 1)
        self.assertEqual(len(picking.move_lines), 1)
        self.assertEqual(move_line.product_id, self.product)
        self.assertEqual(move_line.move_id.product_id, self.product)
        self.assertEqual(move_line.product_uom_qty, expected_qty)
        self.assertEqual(move_line.move_id.product_uom_qty, expected_qty)
        self.assertEqual(len(picking), 1)
        self.assertEqual(picking.location_dest_id, self.dest_loc)
        self.assertEqual(picking.location_id, self.source_loc)
        self.assertEqual(move_line.picking_id, picking)
        self.assertEqual(move_line.move_id.picking_id, picking)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_do_all_new(self):
        """ Tests an input XML that creates a new move and a new picking.
        """
        stock_picking = self.env['stock.picking']
        stock_move_line = self.env['stock.move.line']

        ref = 'ref-001'
        qty = 100

        self.assertFalse(stock_move_line.search([
            ('frepple_reference', '=', ref),
        ]))
        self.assertFalse(stock_picking.search([
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ]))

        _, xml_file = self._create_xml(
            ref, self.product, self.source_loc, self.dest_loc, qty=qty)
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.run()
        f.close()

        move_line = stock_move_line.search([('frepple_reference', '=', ref)])
        picking = stock_picking.search([
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ])
        self.assertEqual(len(move_line), 1)
        self._assert_expected(picking, move_line, qty)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_do_moveline_new_picking_exists(self):
        """ Tests an input XML that creates a new move and adds it to a picking that already exists.
        """
        stock_picking = self.env['stock.picking']
        stock_move_line = self.env['stock.move.line']

        datetime_str_odoo = fields.Datetime.to_string(fields.Datetime.now())
        datetime_str_xml = datetime_str_odoo.replace(' ', 'T')

        # A picking already exists.
        picking = self._create_internal_picking(
            self.source_loc, self.dest_loc, defaults={'scheduled_date': datetime_str_odoo})
        self.assertFalse(picking.move_lines)
        self.assertFalse(picking.move_line_ids)

        ref = 'ref-002'
        qty = 200
        _, xml_file = self._create_xml(
            ref, self.product, self.source_loc, self.dest_loc, qty=qty, datetime_xml=datetime_str_xml)
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.run()
        f.close()

        move_line = stock_move_line.search([('frepple_reference', '=', ref)])
        self.assertEqual(stock_picking.search([
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ]), picking)
        self.assertEqual(len(move_line), 1)
        self._assert_expected(picking, move_line, qty)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_do_moveline_exists_picking_new(self):
        """ Tests an input XML that updates an already existing move, that is not yet for a picking
        """
        stock_picking = self.env['stock.picking']
        stock_move_line = self.env['stock.move.line']

        ref = 'ref-003'
        qty = 300

        # The move line already exists.
        move_line = self._create_move_line(
            self.source_loc, self.dest_loc, self.product,
            defaults_move={'product_uom_qty': qty},
            defaults_move_line={'frepple_reference': ref})

        self.assertEqual(stock_move_line.search([
            ('frepple_reference', '=', ref),
        ]), move_line)
        self.assertFalse(stock_picking.search([
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ]))

        _, xml_file = self._create_xml(
            ref, self.product, self.source_loc, self.dest_loc, qty=qty + 3)
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.run()
        f.close()

        move_line_after = stock_move_line.search([('frepple_reference', '=', ref)])
        self.assertEqual(move_line, move_line_after)
        picking = stock_picking.search([
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ])
        self.assertEqual(len(move_line), 1)
        self._assert_expected(picking, move_line, qty + 3)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_do_moveline_exists_picking_exists(self):
        """ Tests an input XML that updates a move that is already linked to a picking that exists.
        """
        stock_picking = self.env['stock.picking']
        stock_move_line = self.env['stock.move.line']

        datetime_str_odoo = fields.Datetime.to_string(fields.Datetime.now())

        ref = 'ref-003'
        qty = 300

        # The move line already exists.
        move_line = self._create_move_line(
            self.source_loc, self.dest_loc, self.product,
            defaults_move={'product_uom_qty': qty},
            defaults_move_line={'frepple_reference': ref})

        # A picking already exists.
        picking = self._create_internal_picking(
            self.source_loc, self.dest_loc, defaults={'scheduled_date': datetime_str_odoo})
        self.assertFalse(picking.move_lines)
        self.assertFalse(picking.move_line_ids)

        self.assertEqual(stock_move_line.search([
            ('frepple_reference', '=', ref),
        ]), move_line)
        self.assertEqual(stock_picking.search([
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ]), picking)

        _, xml_file = self._create_xml(
            ref, self.product, self.source_loc, self.dest_loc, qty=qty + 7)
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.run()
        f.close()

        move_line_after = stock_move_line.search([('frepple_reference', '=', ref)])
        self.assertEqual(move_line, move_line_after)
        picking_after = stock_picking.search([
            ('location_id', '=', self.source_loc.id),
            ('location_dest_id', '=', self.dest_loc.id),
        ])
        self.assertEqual(picking, picking_after)
        self._assert_expected(picking, move_line, qty + 7)
