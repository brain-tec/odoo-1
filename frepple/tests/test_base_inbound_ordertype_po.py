##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from tempfile import mkstemp
import os
from odoo.addons.frepple.tests.test_base import TestBase
from odoo import fields
from dateutil.relativedelta import relativedelta

UNDER_DEVELOPMENT = True
UNDER_DEVELOPMENT_MSG = 'Test skipped because of being under development'


class TestBaseInboundOrdertypePo(TestBase):
    def initialize_PO_setUp(self):
        self.product = self._create_product('Main Product', price=2)
        self.product2 = self._create_product('Main Product 2', price=4)
        date_now = fields.Datetime.now()
        self.supplier, self.seller = self._create_supplier_seller(
            'Supplier_1', product=self.product, priority=1, price=7, delay=3,
            date_start=date_now - relativedelta(days=1),
            date_end=False)
        self.seller2 = self._create_seller(self.supplier, self.product, priority=1, price=5, delay=5,
                                           date_start=date_now + relativedelta(days=1),
                                           date_end=date_now + relativedelta(days=3))
        self.seller_product2 = self._create_seller(self.supplier, self.product2, priority=1, price=6, delay=6,
                                           date_start=date_now + relativedelta(days=1),
                                           date_end=date_now + relativedelta(days=3))
        self.dest_loc = self._create_location('ASM/Stock')
        self.source_loc = self._create_location('Source Location')
        warehouse = self.env.ref('stock.warehouse0')
        warehouse.lot_stock_id = self.dest_loc
        warehouse.in_type_id.default_location_src_id = self.source_loc
        warehouse.in_type_id.default_location_dest_id = self.dest_loc

    def _create_xml_line(self, reference, product, supplier, source_location, destination_location, qty, datetime_xml):
        xml_content = '''
                    <operationplan  
                      ordertype="PO"
                      reference="{reference}"
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
                    />'''.format(reference=reference,
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
        return xml_content

    def _create_xml(self, lines):
        """
                    Example
                         <?xml version="1.0" encoding="UTF-8" ?>
                         <plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                             <operationplans>
                                <operationplan
                                ordertype="PO"
                                reference="186182389105"
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

        xml_initial_content = '''<?xml version="1.0" encoding="UTF-8" ?>
            <plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" source="odoo_1">
                <operationplans>'''
        xml_lines = []
        for item in lines:
            xml_line = self._create_xml_line(item['reference'], item['product'], item['supplier'],
                                             item['source_location'], item['destination_location'],
                                             item['qty'], item['datetime_xml'])
            xml_lines.append(xml_line)
        xml_lines_content = ''.join(xml_lines)
        xml_final_content = '''
                </operationplans>
            </plan>
        '''
        xml_content = "{0}{1}{2}".format(xml_initial_content, xml_lines_content, xml_final_content)
        fd, xml_file_path = mkstemp(prefix='frepple_inbound_xml_', dir="/tmp")
        f = open(xml_file_path, 'w')
        f.write(xml_content)
        f.close()
        os.close(fd)
        return xml_content, xml_file_path

    def _get_qty(self, qty):
        return qty

    def _get_uom(self):
        return self.product.uom_id.id

    def _ordertype_po_one_line(self):
        """ Tests an input XML that creates a new PO with the received PO line
        """
        purchaseOrder = self.env['purchase.order']

        ref = 'ref-001'
        qty = 100

        self.assertFalse(purchaseOrder.search([('origin', '=', "frePPLe")]))

        # The PO line will be planned for 2 days after the PO is created.
        # That's important as we have a supplier with a different pricing between the day after and 3 days
        # after the PO was created, then that supplier will be chosen and we do some checks about pricing
        datetime_str_odoo = fields.Datetime.to_string(fields.Datetime.now() + relativedelta(days=2))
        datetime_str_xml = datetime_str_odoo.replace(' ', 'T')

        _, xml_file = self._create_xml(
            [{'reference': ref, 'product': self.product, 'supplier': self.supplier,
              'source_location': self.source_loc, 'destination_location': self.dest_loc, 'qty': qty,
              'datetime_xml': datetime_str_xml}]
        )
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.company = self.env.user.company_id
        self.importer.run()
        f.close()

        po = purchaseOrder.search([('origin', '=', "frePPLe")])
        self.assertEqual(len(po), 1)
        self.assertEqual(po.order_line.product_id.name, self.product.name)
        self.assertEqual(po.order_line.product_qty, self._get_qty(qty))
        self.assertEqual(po.order_line.product_uom.id, self._get_uom())
        # The planned date of the PO line is respected to that specified by frepple, instead of changing
        # to another taking into account the delay of the supplier and the date order of the PO
        self.assertEqual(fields.Datetime.to_string(po.order_line.date_planned), datetime_str_odoo)
        # The price is finally assigned as the one of the supplier according to the planned date of the line,
        # unlike in standard odoo where it should be according to the PO order date
        self.assertAlmostEqual(po.order_line.price_unit,
                               self.seller2.product_uom._compute_price(
                                   self.seller2.price, po.order_line.product_uom), 2)
        self.assertEqual(po.order_line.frepple_reference, ref)
        return po

    def _ordertype_po_many_lines(self):
        """ Tests an input XML that creates a PO with two lines being one of them the summary of two
            received lines, as they are for the same vendor and product
        """
        purchaseOrder = self.env['purchase.order']

        ref_1 = 'ref-001'
        ref_2 = 'ref-002'
        ref_product2 = 'ref-003'
        qty_1 = 100
        qty_2 = 200
        qty_product2 = 150

        self.assertFalse(purchaseOrder.search([('origin', '=', "frePPLe")]))

        # Three PO lines, 1 for product2 and 2 for product. All for the same supplier and destinations
        # They are planned for 2 different dates tpo play with the different pricing of the supplier according to
        # dates
        # Both PO lines for product will be summarized in one, and it will keep the oldest planned date
        datetime_str_odoo_1 = fields.Datetime.to_string(fields.Datetime.now() + relativedelta(days=2))
        datetime_str_xml_1 = datetime_str_odoo_1.replace(' ', 'T')
        datetime_str_odoo_2 = fields.Datetime.to_string(fields.Datetime.now() + relativedelta(days=3))
        datetime_str_xml_2 = datetime_str_odoo_2.replace(' ', 'T')

        _, xml_file = self._create_xml(
            [{'reference': ref_product2, 'product': self.product2, 'supplier': self.supplier,
              'source_location': self.source_loc, 'destination_location': self.dest_loc, 'qty': qty_product2,
              'datetime_xml': datetime_str_xml_1},
             {'reference': ref_1, 'product': self.product, 'supplier': self.supplier,
              'source_location': self.source_loc, 'destination_location': self.dest_loc, 'qty': qty_1,
              'datetime_xml': datetime_str_xml_1},
             {'reference': ref_2, 'product': self.product, 'supplier': self.supplier,
              'source_location': self.source_loc, 'destination_location': self.dest_loc, 'qty': qty_2,
              'datetime_xml': datetime_str_xml_2}]
        )
        f = open(xml_file, 'r')
        self.importer.datafile = f
        self.importer.company = self.env.user.company_id
        self.importer.run()
        f.close()

        po = purchaseOrder.search([('origin', '=', "frePPLe")])
        self.assertEqual(len(po), 1)
        self.assertEqual(len(po.order_line), 2)
        order_line_summarized = po.order_line.filtered(lambda x: x.product_id.id == self.product.id)
        self.assertEqual(order_line_summarized.product_id.name, self.product.name)
        self.assertEqual(order_line_summarized.product_qty, self._get_qty(qty_1) + self._get_qty(qty_2))
        self.assertEqual(order_line_summarized.product_uom.id, self._get_uom())
        # The planned date of the PO line is respected to that specified by frepple, instead of changing
        # to another taking into account the delay of the supplier and the date order of the PO
        # It is in addition the oldest of the two received dates from frepple for both summarized lines
        self.assertEqual(fields.Datetime.to_string(order_line_summarized.date_planned), datetime_str_odoo_1)
        # The price is finally assigned as the one of the supplier according to the planned date of the line,
        # unlike in standard odoo where it should be according to the PO order date
        self.assertAlmostEqual(order_line_summarized.price_unit,
                               self.seller2.product_uom._compute_price(
                                    self.seller2.price, order_line_summarized.product_uom), 2)
        self.assertEqual(order_line_summarized.frepple_reference, ','.join([ref_1, ref_2]))
        return po