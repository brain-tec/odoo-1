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


class TestOutboundCustomers(TestBase):
    def setUp(self):
        super(TestOutboundCustomers, self).setUp()

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_customers_ampersand(self):
        """ Generates XML for customer that has an & in its name
        """
        customer_1 = self._create_customer('TC_Brain & Tec')
        xml_str_actual = self.exporter.export_customers(ctx={'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- customers -->',
            '<customers>',
            '<customer name="{} TC_Brain &amp; Tec"/>'.format(customer_1.id),
            '</customers>'
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_customers_no_affiliates(self):
        """ Generates XML for customer that doesn't have affiliates.
        """
        customer_1 = self._create_customer('TC_1')
        customer_2 = self._create_customer('TC_2')
        xml_str_actual = self.exporter.export_customers(ctx={'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- customers -->',
            '<customers>',
            '<customer name="{} {}"/>'.format(customer_1.id, customer_1.name),
            '<customer name="{} {}"/>'.format(customer_2.id, customer_2.name),
            '</customers>'
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)
