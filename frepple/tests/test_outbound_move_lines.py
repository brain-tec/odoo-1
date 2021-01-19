##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from unittest import skipIf
from odoo.addons.frepple.tests.test_base import TestBase
from odoo import fields

UNDER_DEVELOPMENT = False
UNDER_DEVELOPMENT_MSG = 'Test skipped because of being under development'


class TestOutboundMoveLines(TestBase):
    def setUp(self):
        super(TestOutboundMoveLines, self).setUp()

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_discard_moves_with_same_location_as_origin_and_destination(self):
        """ Exports all moves except those having as location the same for
            the origin and the destination.
        """
        location = self._create_location('Origin Location #1')
        product = self._create_product('Product #1', price=7)
        self._create_move_line(location, location, product)

        self.assertEqual(self.env.user.company_id.internal_moves_domain, '[]')
        xml_str_actual = self.exporter.export_move_lines(
            ctx={'test_export_move_lines': True, 'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- Stock Move Lines -->',
            '<operationplans>',
            '</operationplans>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_export_all_moves(self):
        """ Exports all moves.
        """
        warehouse_orig = self._create_warehouse('TC_Orig')
        orig_location = self._create_location('Origin Location #1')
        warehouse_orig.lot_stock_id = orig_location

        warehouse_dest = self._create_warehouse('TC_Dest')
        dest_location = self._create_location('Destination Location #1')
        warehouse_dest.lot_stock_id = dest_location

        product = self._create_product('Product #1', price=7)
        move_line = self._create_move_line(orig_location, dest_location, product)

        self.assertEqual(self.env.user.company_id.internal_moves_domain, '[]')
        xml_str_actual = self.exporter.export_move_lines(
            ctx={'test_export_move_lines': True, 'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- Stock Move Lines -->',
            '<operationplans>',
            '<operationplan ordertype="DO" reference="{}" start="{}" quantity="1.0" status="proposed">'.format(
                move_line.id,
                fields.Datetime.context_timestamp(move_line, move_line.date).strftime("%Y-%m-%dT%H:%M:%S"),
            ),
            '<item name="{product_name}" subcategory="{subcategory}" description="Product"/>'.format(
                product_name=product.name, subcategory='{},{}'.format(self.kgm_uom.id, product.id)),
            '<location name="{location_name}" subcategory="{location_id}" description="Dest. location"/>'.format(
                location_name=dest_location.complete_name, location_id=dest_location.id),
            '<origin name="{location_name}" subcategory="{location_id}" description="Origin location"/>'.format(
                location_name=orig_location.complete_name, location_id=orig_location.id),
            '</operationplan>',
            '</operationplans>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_export_filtered_moves(self):
        """ Exports only the moves filtered by the filter defined on the res.company.
        """
        orig_location_1 = self._create_location('Origin Location #1')
        dest_location_1 = self._create_location('Destination Location #1',
                                                parent=self._create_location('Parent of Destination Location #1'))
        orig_location_2 = self._create_location('Origin Location #2')
        dest_location_2 = self._create_location('Destination Location #2',
                                                parent=self._create_location('Parent of Destination Location #2'))

        warehouse_orig_1 = self._create_warehouse('TC_O1')
        warehouse_orig_1.lot_stock_id = orig_location_1
        warehouse_orig_2 = self._create_warehouse('TC_O2')
        warehouse_orig_2.lot_stock_id = orig_location_2
        warehouse_dest_1 = self._create_warehouse('TC_D1')
        warehouse_dest_1.lot_stock_id = dest_location_1
        warehouse_dest_2 = self._create_warehouse('TC_D2')
        warehouse_dest_2.lot_stock_id = dest_location_2

        product_1 = self._create_product('Product #1', price=7)
        product_2 = self._create_product('Product #2', price=13)
        move_line_1 = self._create_move_line(orig_location_1, dest_location_1, product_1)
        move_line_2 = self._create_move_line(orig_location_2, dest_location_2, product_2)

        self.assertEqual(self.env.user.company_id.internal_moves_domain, '[]')
        xml_str_actual_1 = self.exporter.export_move_lines(
            ctx={'test_export_move_lines': True, 'test_prefix': 'TC_'})
        xml_str_expected_1 = '\n'.join([
            '<!-- Stock Move Lines -->',
            '<operationplans>',
            '<operationplan ordertype="DO" reference="{}" start="{}" quantity="1.0" status="proposed">'.format(
                move_line_1.id,
                fields.Datetime.context_timestamp(move_line_1, move_line_1.date).strftime("%Y-%m-%dT%H:%M:%S"),
            ),
            '<item name="{product_name}" subcategory="{subcategory}" description="Product"/>'.format(
                product_name=product_1.name, subcategory='{},{}'.format(self.kgm_uom.id, product_1.id)),
            '<location name="{location_name}" subcategory="{location_id}" description="Dest. location"/>'.format(
                location_name=dest_location_1.complete_name, location_id=dest_location_1.id),
            '<origin name="{location_name}" subcategory="{location_id}" description="Origin location"/>'.format(
                location_name=orig_location_1.complete_name, location_id=orig_location_1.id),
            '</operationplan>',
            '<operationplan ordertype="DO" reference="{}" start="{}" quantity="1.0" status="proposed">'.format(
                move_line_2.id,
                fields.Datetime.context_timestamp(move_line_2, move_line_2.date).strftime("%Y-%m-%dT%H:%M:%S"),
            ),
            '<item name="{product_name}" subcategory="{subcategory}" description="Product"/>'.format(
                product_name=product_2.name, subcategory='{},{}'.format(self.kgm_uom.id, product_2.id)),
            '<location name="{location_name}" subcategory="{location_id}" description="Dest. location"/>'.format(
                location_name=dest_location_2.complete_name, location_id=dest_location_2.id),
            '<origin name="{location_name}" subcategory="{location_id}" description="Origin location"/>'.format(
                location_name=orig_location_2.complete_name, location_id=orig_location_2.id),
            '</operationplan>',
            '</operationplans>',
        ])
        self.assertEqual(xml_str_actual_1, xml_str_expected_1)

        self.env.user.company_id.internal_moves_domain = "[('product_id', '=', {})]".format(product_1.id)
        xml_str_actual_2 = self.exporter.export_move_lines(
            ctx={'test_export_move_lines': True, 'test_prefix': 'TC_'})
        xml_str_expected_2 = '\n'.join([
            '<!-- Stock Move Lines -->',
            '<operationplans>',
            '<operationplan ordertype="DO" reference="{}" start="{}" quantity="1.0" status="proposed">'.format(
                move_line_1.id,
                fields.Datetime.context_timestamp(move_line_1, move_line_1.date).strftime("%Y-%m-%dT%H:%M:%S"),
            ),
            '<item name="{product_name}" subcategory="{subcategory}" description="Product"/>'.format(
                product_name=product_1.name, subcategory='{},{}'.format(self.kgm_uom.id, product_1.id)),
            '<location name="{location_name}" subcategory="{location_id}" description="Dest. location"/>'.format(
                location_name=dest_location_1.complete_name, location_id=dest_location_1.id),
            '<origin name="{location_name}" subcategory="{location_id}" description="Origin location"/>'.format(
                location_name=orig_location_1.complete_name, location_id=orig_location_1.id),
            '</operationplan>',
            '</operationplans>',
        ])
        self.assertEqual(xml_str_actual_2, xml_str_expected_2)
