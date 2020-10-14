##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from unittest import skipIf
from odoo.addons.frepple.tests.test_base import TestBase

UNDER_DEVELOPMENT = False
UNDER_DEVELOPMENT_MSG = 'Test skipped because of being under development'


class TestOutboundLocations(TestBase):
    def setUp(self):
        super(TestOutboundLocations, self).setUp()
        self.exporter.calendar = 'CALENDAR'

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_flat_locations(self):
        """ Generates an XML for locations, with no sub-locations.
        """
        warehouse_1 = self._create_warehouse('TC_W1')
        location_1 = self._create_location('TC_Location_1')
        warehouse_1.wh_input_stock_loc_id = location_1
        xml_str_actual = self.exporter.export_locations(ctx={'test_export_locations': True, 'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- warehouses -->',
            '<locations>',
            '<location name="{}" subcategory="{}" description="warehouse">'.format(
                warehouse_1.name, warehouse_1.id),
            '<available name="CALENDAR"/>',
            '<members>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                location_1.complete_name, location_1.id),
            '<available name="CALENDAR"/>',
            '</location>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                warehouse_1.view_location_id.complete_name, warehouse_1.view_location_id.id),
            '<available name="CALENDAR"/>',
            '</location>',
            '</members>',
            '</location>',
            '</locations>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_locations_with_children_one_level(self):
        """ Generates an XML for locations, with one level of sub-locations.
        """
        warehouse_1 = self._create_warehouse('TC_W1')
        location_1 = self._create_location('TC_Location_1')
        location_1_1 = self._create_location('TC_Location_1_1', parent=location_1)

        warehouse_1.wh_input_stock_loc_id = location_1
        xml_str_actual = self.exporter.export_locations(ctx={'test_export_locations': True, 'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- warehouses -->',
            '<locations>',
            '<location name="{}" subcategory="{}" description="warehouse">'.format(
                warehouse_1.name, warehouse_1.id),
            '<available name="CALENDAR"/>',
            '<members>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                location_1.complete_name, location_1.id),
            '<available name="CALENDAR"/>',
            '<members>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                location_1_1.complete_name, location_1_1.id),
            '<available name="CALENDAR"/>',
            '</location>',
            '</members>',
            '</location>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                warehouse_1.view_location_id.complete_name, warehouse_1.view_location_id.id),
            '<available name="CALENDAR"/>',
            '</location>',
            '</members>',
            '</location>',
            '</locations>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_locations_with_children_more_than_one_level(self):
        """ Generates an XML for locations, with more than one level of sub-locations.
        """
        warehouse_1 = self._create_warehouse('TC_W1')
        location_1 = self._create_location('TC_Location_1')
        location_1_1 = self._create_location('TC_Location_1_1', parent=location_1)
        location_1_2 = self._create_location('TC_Location_1_2', parent=location_1)
        location_1_2_1 = self._create_location('TC_Location_1_2_1', parent=location_1_2)
        location_1_2_2 = self._create_location('TC_Location_1_2_2', parent=location_1_2)
        warehouse_1.wh_input_stock_loc_id = location_1
        xml_str_actual = self.exporter.export_locations(ctx={'test_export_locations': True, 'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- warehouses -->',
            '<locations>',
            '<location name="{}" subcategory="{}" description="warehouse">'.format(
                warehouse_1.name, warehouse_1.id),
            '<available name="CALENDAR"/>',
            '<members>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                location_1.complete_name, location_1.id),
            '<available name="CALENDAR"/>',
            '<members>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                location_1_1.complete_name, location_1_1.id),
            '<available name="CALENDAR"/>',
            '</location>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                location_1_2.complete_name, location_1_2.id),
            '<available name="CALENDAR"/>',
            '<members>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                location_1_2_1.complete_name, location_1_2_1.id),
            '<available name="CALENDAR"/>',
            '</location>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                location_1_2_2.complete_name, location_1_2_2.id),
            '<available name="CALENDAR"/>',
            '</location>',
            '</members>',
            '</location>',
            '</members>',
            '</location>',
            '<location name="{}" subcategory="{}" description="location">'.format(
                warehouse_1.view_location_id.complete_name, warehouse_1.view_location_id.id),
            '<available name="CALENDAR"/>',
            '</location>',
            '</members>',
            '</location>',
            '</locations>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)
