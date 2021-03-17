##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from unittest import skipIf
from odoo.addons.frepple.tests.test_base_inbound_ordertype_po import TestBaseInboundOrdertypePo
#from tempfile import mkstemp
#import os

UNDER_DEVELOPMENT = False
UNDER_DEVELOPMENT_MSG = 'Test skipped because of being under development'


class TestInboundOrdertypePo(TestBaseInboundOrdertypePo):
    def setUp(self):
        super(TestInboundOrdertypePo, self).setUp()
        self.initialize_PO_setUp()

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_po(self):
        """ Tests an input XML that creates a new PO with the received PO line
        """
        self._ordertype_po_one_line()

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_ordertype_po_many_lines(self):
        """ Tests an input XML that creates a PO with two lines being one of them the summary of two
            received lines, as they are for the same vendor and product
        """
        self._ordertype_po_many_lines()

    # Use this test for copying the resulting xml from frepple s201 and test it in MindFR Test db, instead of
    # on an empty db for tests
    # def test_fake(self):
    #     xml_content = '''<?xml version="1.0" encoding="UTF-8" ?><plan
    #     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><operationplans><operationplan ordertype="PO"
    #     id="186182378745" item="BISCH CRF Sauce Echalotte 300 ml x12" location="ASM/Stock" supplier="2401
    #     BISCHOFSZELL NAHRUNGSMITTEL AG" start="2021-02-21 00:00:00" end="2021-02-22 00:00:00"
    #     quantity="600.00000000" location_id="8" item_id="1,2650" criticality="0"/><operationplan ordertype="PO"
    #     id="186182378751" item="BISCH CRF Sauce Echalotte 300 ml x12" location="ASM/Stock" supplier="2401
    #     BISCHOFSZELL NAHRUNGSMITTEL AG" start="2021-03-24 23:00:00" end="2021-03-25 23:00:00"
    #     quantity="48.00000000" location_id="8" item_id="1,2650" criticality="91"/><operationplan ordertype="PO"
    #     id="186182378816" item="BISCH CRF Sauce Echalotte 300 ml x12" location="ASM/Stock" supplier="2401
    #     BISCHOFSZELL NAHRUNGSMITTEL AG" start="2022-05-19 00:00:00" end="2022-05-20 00:00:00"
    #     quantity="48.00000000" location_id="8" item_id="1,2650" criticality="999"/></operationplans></plan>
    #     '''
    #     fd, xml_file_path = mkstemp(prefix='frepple_inbound_xml_', dir="/tmp")
    #     f = open(xml_file_path, 'w')
    #     f.write(xml_content)
    #     f.close()
    #     os.close(fd)
    #
    #     f = open(xml_file_path, 'r')
    #     self.importer.datafile = f
    #     self.importer.company = self.env.user.company_id
    #     self.importer.run()
    #     f.close()
