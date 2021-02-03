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

    frepple_reference = fields.Char('Reference (frePPLe)')

    @api.model
    def _create_or_update_from_frepple_mo(self, elem, company):
        """ Receives an XML subtree from an input file from frePPLe,
            in particular an <operationplan>, and creates a mrp.production
            for it; or updates it if it already exists.

            I'm assuming here that the inbound follows the same content
            than the outbound I'm sending, which includes, among other things,
            the ID of the products so that we don't have to search them by
            name. Would be good that we exported the reference of the product
            instead.
        """
        product_product = self.env['product.product']
        uom_uom = self.env['uom.uom']
        stock_location = self.env['stock.location']
        mrp_bom = self.env['mrp.bom']
        stock_warehouse = self.env['stock.warehouse']

        elem_reference = elem.get('id')

        # If we find at least one error, we inform and skip the element update/creation.
        errors = []

        uom_id, item_id = elem.get("item_id").split(",")

        product_id = int(item_id)
        product = product_product.browse(product_id)
        if not product:
            errors.append('No product was found with id {}'.format(product_id))

        uom_id = int(uom_id)
        uom = uom_uom.browse(uom_id)
        if not uom:
            errors.append('No uom was found with id {}'.format(uom_id))

        location_id = int(elem.get('location_id'))
        location = stock_location.browse(location_id)
        if not location:
            errors.append('No location was found with id {}'.format(location_id))

        if location:
            warehouse = stock_warehouse.search([('lot_stock_id', '=', location.id)])
            if not warehouse:
                errors.append('No warehouse was found with Location Stock having id {}'.format(location_id))
            picking_type = warehouse.manu_type_id
            if not picking_type:
                errors.append('No Operation Type was found with type Manufacturing associated to warehouse '
                              'with id {}'.format(warehouse.id))

        bom_id = int(elem.get("operation").split(" ", 1)[0])
        bom = mrp_bom.browse(bom_id)
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

            mo = self.search([('frepple_reference', '=', elem_reference)])

            if mo:
                with Form(mo) as f:
                    for key, value in mo_values:
                        setattr(f, key, value)
            else:
                f = Form(self)
                for key, value in mo_values:
                    setattr(f, key, value)
                f.save()
