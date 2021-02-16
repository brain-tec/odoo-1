##############################################################################
# Copyright (c) 2020 brain-tec AG (https://bt-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

import os
import logging
from odoo import models, api, fields
from odoo.tests import Form

_logger = logging.getLogger(__name__)


class ManufacturingOrder(models.Model):
    _inherit = 'mrp.production'

    frepple_reference = fields.Char('Reference (frePPLe)', copy=False)

    @api.model
    def _create_or_update_from_frepple_mo(self, elem, company):
        """ Receives an XML subtree from an input file from frePPLe,
            in particular an <operationplan>, and creates a mrp.production
            for it.
        """
        ProductProduct = self.env['product.product']
        UomUom = self.env['uom.uom']
        StockLocation = self.env['stock.location']
        MrpBom = self.env['mrp.bom']
        StockWarehouse = self.env['stock.warehouse']

        elem_reference = elem.get('id')

        # If we find at least one error, we inform and skip the element update/creation.
        errors = []

        uom_id, item_id = elem.get("item_id").split(",")

        product_id = int(item_id)
        product = ProductProduct.browse(product_id)
        if not product:
            errors.append('No product was found with id {}'.format(product_id))

        uom_id = int(uom_id)
        uom = UomUom.browse(uom_id)
        if not uom:
            errors.append('No uom was found with id {}'.format(uom_id))

        location_id = int(elem.get('location_id'))
        location = StockLocation.browse(location_id)
        if not location:
            errors.append('No location was found with id {}'.format(location_id))

        if location:
            warehouse = StockWarehouse.search([('lot_stock_id', '=', location.id)])
            if not warehouse:
                errors.append('No warehouse was found with Location Stock having id {}'.format(location_id))
            picking_type = warehouse.manu_type_id
            if not picking_type:
                errors.append('No Operation Type was found with type Manufacturing associated to warehouse '
                              'with id {}'.format(warehouse.id))

        bom_id = int(elem.get("operation").split(" ", 1)[0])
        bom = MrpBom.browse(bom_id)
        if not bom:
            errors.append('No bom was found with id {}'.format(bom_id))

        if errors:
            _logger.error('The following errors were found when processing <operationplan> with '
                          'ordertype "MO" for reference {}: {}'.format(elem_reference, os.linesep.join(errors)))
        else:
            # TODO no place to store the criticality
            # # elem.get('criticality'),

            # location is not set as both scr and dest locations are set by onchange of picking_type_id
            # Order is relevant in this list, as onchanges of those fields will be called in that order
            # bom & picking_type_id should be called before qty otherwise it's reset to 1 and uom as well is reset
            mo_values = [
                ('company_id', company),
                ('product_id', product),
                ('picking_type_id', picking_type),
                ('bom_id', bom),
                ('product_uom_id', uom),
                ('product_qty', elem.get('quantity')),
                ('frepple_reference', elem_reference),
                ('date_planned_start', elem.get("start").replace('T', ' ')),
                ('date_planned_finished', elem.get("end").replace('T', ' ')),
                ('origin', "frePPLe"),
            ]

            # No need to search for existing mo, as every time frepple do an import will change the reference
            # Unlike imports for PO and DO, here we don't work at line level, so we just create each time the MO
            # and it will create the lines (components) through calling the onchange of bom
            f = Form(self)
            for key, value in mo_values:
                setattr(f, key, value)
            mo = f.save()
