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


class TestOutboundStockRules(TestBase):
    def setUp(self):
        super(TestOutboundStockRules, self).setUp()

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_export_stock_rules(self):
        """ Tests the export of several stock rules, with the filter
            set at the company.
        """
        route = self.env['stock.location.route'].create({
            'name': 'TC_Route #1',
        })
        location_1 = self._create_location('TC_Location_1')
        location_2 = self._create_location('TC_Location_2', parent=location_1)
        self.env['stock.rule'].create({
            'action': 'pull',
            'auto': 'manual',
            'location_id': location_1.id,
            'name': 'TC_Rule #1',
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'procure_method': 'make_to_stock',
            'route_id': route.id,
        })
        target_rule = self.env['stock.rule'].create({
            'action': 'pull',
            'auto': 'manual',
            'location_id': location_2.id,
            'name': 'TC_Rule #2',
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'procure_method': 'make_to_order',
            'route_id': route.id,
            'delay': 0,
        })
        self.env.user.company_id.stock_rules_domain = "[('location_id', '=', {})]".format(
            target_rule.location_id.id)

        xml_str_actual = self.exporter.export_stock_rules(
            ctx={'test_export_stock_rules': True, 'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- Stock Rules -->',
            '<itemdistributions>',
            '<itemdistribution>',
            '<destination name="{loc_name}" subcategory="{loc_id}" description="location"/>'.format(
                loc_name=target_rule.location_id.complete_name,
                loc_id=target_rule.location_id.id
            ),
            '<leadtime>P{}D</leadtime>'.format(target_rule.delay),
            '</itemdistribution>',
            '</itemdistributions>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_export_stock_rules_for_route_applied_for_warehouses(self):
        """ Tests the export of a stock rule belonging to a route
            that applies to warehouses.
        """
        route = self.env['stock.location.route'].create({
            'name': 'TC_Route #1',
            'warehouse_selectable': True,
        })
        location_1 = self._create_location('TC_Location_1')
        location_2 = self._create_location('TC_Location_2', parent=location_1)
        target_rule = self.env['stock.rule'].create({
            'action': 'pull',
            'auto': 'manual',
            'location_id': location_2.id,
            'name': 'TC_Rule #2',
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'procure_method': 'make_to_order',
            'route_id': route.id,
            'delay': 0,
        })
        # self.env.user.company_id.stock_rules_domain = "[('location_id', '=', {})]".format(
        #     target_rule.location_id.id)

        xml_str_actual = self.exporter.export_stock_rules(
            ctx={'test_export_stock_rules': True, 'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- Stock Rules -->',
            '<itemdistributions>',
            '<itemdistribution>',
            '<item name="All"/>',
            '<destination name="{loc_name}" subcategory="{loc_id}" description="location"/>'.format(
                loc_name=target_rule.location_id.complete_name,
                loc_id=target_rule.location_id.id
            ),
            '<leadtime>P{}D</leadtime>'.format(target_rule.delay),
            '</itemdistribution>',
            '</itemdistributions>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)
