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


class TestInboundOrdertypePo(TestBase):
    def setUp(self):
        super(TestInboundOrdertypePo, self).setUp()
        self.product = self._create_product('Main Product', price=2)
        self.supplier, _ = self._create_supplier_seller(
            'Supplier_1', product=self.product, priority=1, price=7, delay=3)
        self.dest_loc = self._create_location('ASM/Stock')
        self.source_loc = self._create_location('Source Location')

    def _create_xml(self, reference, product, supplier, source_location, destination_location, qty, datetime_xml=None):
        if datetime_xml is None:
            datetime_xml = fields.Datetime.to_string(fields.Datetime.now())
        """
            Example
                 <?xml version="1.0" encoding="UTF-8" ?>
                 <plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                     <operationplans>
                        <operationplan 
                        ordertype="PO" 
                        id="186182389105" 
                        item="CAFE ROYAL NS Alu Espresso x36 x5"                        
                        item_id="1,2577"  
                        location="ASM/Stock"  
                        location_id="8"
                        supplier="2404 DELICA AG" 
                        start="2021-12-12 00:00:00" 
                        end="2021-12-13 00:00:00" 
                        quantity="7500.00000000" 
                        criticality="28"/>
                     </operationplans>
                 </plan>    
            """

        xml_content = '''<?xml version="1.0" encoding="UTF-8" ?>
            <plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" source="odoo_1">
                <operationplans>
                    <operationplan  
                      ordertype="PO"
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
                      supplier="{supplier}"
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
                   supplier="{0} {1}".format(supplier.id, supplier.name),
                   uom_id=product.uom_id.id)
        fd, xml_file_path = mkstemp(prefix='frepple_inbound_xml_', dir="/tmp")
        f = open(xml_file_path, 'w')
        f.write(xml_content)
        f.close()
        os.close(fd)
        return xml_content, xml_file_path

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_po(self):
        """ Tests an input XML that creates a new move and a new picking.
        """
        purchaseOrder = self.env['purchase.order']

        ref = 'ref-001'
        qty = 100

        self.assertFalse(purchaseOrder.search([('origin', '=', "frePPLe")]))

        _, xml_file = self._create_xml(
            ref, self.product, self.supplier, self.source_loc, self.dest_loc, qty=qty)
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.company = self.env.user.company_id
        self.importer.run()
        f.close()

        po = purchaseOrder.search([('origin', '=', "frePPLe")])
        self.assertEqual(len(po), 1)
        self.assertEqual(po.order_line.product_id.name, self.product.name)
