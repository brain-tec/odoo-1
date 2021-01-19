##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

import re
import odoo
from unittest import skipIf
from odoo.addons.frepple.tests.test_base import TestBase
from odoo import fields

UNDER_DEVELOPMENT = False
UNDER_DEVELOPMENT_MSG = 'Test skipped because of being under development'


@odoo.tests.common.tagged('post_install', '-at_install')
class TestOutboundItems(TestBase):
    def setUp(self):
        super(TestOutboundItems, self).setUp()
        self.customer = self._create_customer('TC_Partner')
        self.product = self._create_product('TC_Product', price=1)

        # export_salesorders needs the following two dictionaries ready inside an exporter.
        self.exporter.product_product = {self.product.id: {'name': self.product.name}}
        self.exporter.uom = {self.env.ref('uom.product_uom_kgm').id: {'factor': 1}}

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_saleorder(self):
        """ Tests the generation of a <demand>, i.e. a sale.order.line
        """
        quotation = self._create_quotation(self.customer, product=self.product, qty=1)

        xml_str_actual = self.exporter.export_salesorders(
            ctx={'test_prefix': 'TC_'})
        due = getattr(quotation, 'commitment_date', False) or quotation.date_order
        xml_str_expected = ''.join(map(re.escape, [
            '<!-- sales order lines -->',
            '<demands>',
            '<demand due="{due}" minshipment="1.0" name="{name}" priority="10" quantity="1.0" '
            'status="quote">'.format(
                name='{} {}'.format(quotation.name, quotation.order_line[0].id),
                due=fields.Datetime.context_timestamp(quotation, due).strftime("%Y-%m-%dT%H:%M:%S"),
            ),
            '<item name="{}"/>'.format(self.product.name),
            '<customer name="{}"/>'.format('{} {}'.format(self.customer.id, self.customer.name)),
            '<location name="{}"/>'.format(quotation.warehouse_id.lot_stock_id.complete_name),
        ]))
        xml_str_expected += r'(<stringproperty .+/>)*'
        xml_str_expected += ''.join(map(re.escape, [
            '</demand>',
            '</demands>',
        ]))
        self.assertRegex(xml_str_actual.replace('\n', ''), xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_saleorder_different_uoms(self):
        """ Tests the generation of a <demand>, i.e. a sale.order.line, with a UOM
            that has to be converted to the reference UOM to display its result.
        """
        quotation = self._create_quotation(
            self.customer, product=self.product, qty=500, defaults_line={
                'product_uom': self.env.ref('uom.product_uom_gram').id,
            })

        xml_str_actual = self.exporter.export_salesorders(
            ctx={'test_prefix': 'TC_'})
        due = getattr(quotation, 'commitment_date', False) or quotation.date_order
        xml_str_expected = ''.join(map(re.escape, [
            '<!-- sales order lines -->',
            '<demands>',
            '<demand due="{due}" minshipment="1.0" name="{name}" priority="10" quantity="0.5" '
            'status="quote">'.format(
                name='{} {}'.format(quotation.name, quotation.order_line[0].id),
                due=fields.Datetime.context_timestamp(quotation, due).strftime("%Y-%m-%dT%H:%M:%S"),
            ),
            '<item name="{}"/>'.format(self.product.name),
            '<customer name="{}"/>'.format('{} {}'.format(self.customer.id, self.customer.name)),
            '<location name="{}"/>'.format(quotation.warehouse_id.lot_stock_id.complete_name),
        ]))
        xml_str_expected += r'(<stringproperty .+/>)*'
        xml_str_expected += ''.join(map(re.escape, [
            '</demand>',
            '</demands>',
        ]))
        self.assertRegex(xml_str_actual.replace('\n', ''), xml_str_expected)
