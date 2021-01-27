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
        self.product = self._create_product('Main Product', price=2)
        self.sub_product_1 = self._create_product('Sub Product 1', price=1)
        self.sub_product_2 = self._create_product('Sub Product 2', price=1)
        self.bom = self._create_bom(self.product, [self.sub_product_1, self.sub_product_2])
        self.dest_loc = self._create_location('ASM/Stock')
        self.source_loc = self._create_location('Source Location')

    def _create_xml(self, reference, product, bom, source_location, destination_location, qty, datetime_xml=None):
        if datetime_xml is None:
            datetime_xml = fields.Datetime.to_string(fields.Datetime.now())
        """
            Example
            <operationplan 
             ordertype="MO" 
             id="186182386060"
             item="CAFE ROYAL DG R Box x96 x16 x6" 
             location="ASM/Stock"
             location_id="8" 
             operation="957 CAFE ROYAL DG R Box x96 x16 x6 @ ASM/Stock" 
             start="2021-02-07 00:00:00" 
             end="2021-02-08 00:00:00" 
             quantity="60.00000000"
             item_id="1,3563" 
             criticality="0"/>             
            """

        xml_content = '''<?xml version="1.0" encoding="UTF-8" ?>
            <plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" source="odoo_1">
                <operationplans>
                    <operationplan  
                      ordertype="MO"
                      id="{id}"
                      item="{product_name}" 
                      item_id="{uom_id},{product_id}"
                      start="{datetime}" 
                      end="{datetime}"
                      quantity="{qty:0.6f}"
                      origin="{origin_name}" 
                      origin_id="{origin_id}"
                      location="{location_name}" 
                      location_id="{location_id}"
                      operation="{operation}"
                      criticality="0"
                    />
                </operationplans>
            </plan>
        '''.format(id=reference,
                   product_name=product.name,
                   product_id=product.id,
                   location_name=destination_location.name,
                   location_id=destination_location.id,
                   origin_name=source_location.name,
                   origin_id=source_location.id,
                   qty=qty,
                   datetime=datetime_xml,
                   operation="{0} {1} @ {2}".format(bom.id, product.name, destination_location.name),
                   uom_id=product.uom_id.id)
        fd, xml_file_path = mkstemp(prefix='frepple_inbound_xml_', dir="/tmp")
        f = open(xml_file_path, 'w')
        f.write(xml_content)
        f.close()
        os.close(fd)
        return xml_content, xml_file_path

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_mo(self):
        """ Tests an input XML that creates a new move and a new picking.
        """
        mrpProduction = self.env['mrp.production']

        ref = 'ref-001'
        qty = 100

        self.assertFalse(mrpProduction.search([('origin', '=', "frePPLe")]))

        _, xml_file = self._create_xml(
            ref, self.product, self.bom, self.source_loc, self.dest_loc, qty=qty)
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.company = self.env.user.company_id
        self.importer.run()
        f.close()

        mrp_production = mrpProduction.search([('origin', '=', "frePPLe")])
        self.assertEqual(len(mrp_production), 1)
        self.assertEqual(mrp_production.move_raw_ids.mapped('product_id.name'), self.bom.mapped('bom_line_ids.product_id.name'))
