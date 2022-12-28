##############################################################################
# Copyright (c) 2020 brain-tec AG (https://bt-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from unittest import skipIf
from odoo.addons.frepple.tests.test_base import TestBase

UNDER_DEVELOPMENT = False
UNDER_DEVELOPMENT_MSG = 'Test skipped because of being under development'


class TestStockLocation(TestBase):
    def setUp(self):
        super(TestStockLocation, self).setUp()

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_get_warehouse_stock_location(self):
        loc_1 = self._create_location('L1')
        wh_1 = self._create_warehouse('W1')
        loc_1.location_id = wh_1.view_location_id

        self.assertNotEqual(loc_1, wh_1.lot_stock_id)
        self.assertEqual(loc_1.get_warehouse_stock_location(), wh_1.lot_stock_id)
