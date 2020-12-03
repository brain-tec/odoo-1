##############################################################################
# Copyright (c) 2020 brain-tec AG (https://bt-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from odoo import models, fields, tools


class StockLocation(models.Model):
    _inherit = 'stock.location'

    @tools.ormcache('self.id')
    def get_warehouse_stock_location(self):
        """ Returns the stock location for the warehouse the location belongs to.
        """
        self.ensure_one()
        return self.get_warehouse().lot_stock_id
