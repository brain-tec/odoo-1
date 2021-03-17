##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from unittest import skipIf
from odoo.addons.frepple.tests.test_base_inbound_ordertype_po import TestBaseInboundOrdertypePo

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
