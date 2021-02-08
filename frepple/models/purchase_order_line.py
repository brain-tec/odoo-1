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


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    frepple_reference = fields.Char('Reference (frePPLe)')

    def _get_po_line_values(self, elem, product, uom):

        # name and price are automatically set by onchange of product_id
        return [
            ["product_id", product],
            ["product_qty", elem.get("quantity")],
            ["product_uom", uom],
            ["date_planned", elem.get("end")],
            ["frepple_reference", elem.get('reference')]
        ]

    @api.model
    def _create_or_update_from_frepple_po_line(self, elem, company, imported_pos):
        """ Receives an XML subtree from an input file from frePPLe,
            in particular an <operationplan>, and creates a purchase.order.line
            for it inside a PO. A PO is created/selected for each supplier gathering all their PO lines
        """

        PurchaseOrder = self.env['purchase.order']
        ResPartner = self.env['res.partner']
        ProductProduct = self.env['product.product']
        UomUom = self.env['uom.uom']
        StockLocation = self.env['stock.location']
        StockWarehouse = self.env['stock.warehouse']

        # If we find at least one error, we inform and skip the element update/creation.
        errors = []

        elem_reference = elem.get('reference')
        uom_id, item_id = elem.get("item_id").split(",")

        supplier_id = int(elem.get("supplier").split(" ", 1)[0])
        supplier = ResPartner.browse(supplier_id)
        if not supplier:
            errors.append('No supplier was found with id {}'.format(supplier_id))

        product_id = int(item_id)
        product = ProductProduct.browse(product_id)
        if not product:
            errors.append('No product was found with id {}'.format(product_id))

        uom_id = int(uom_id)
        uom = UomUom.browse(uom_id)
        if not uom:
            errors.append('No uom was found with id {}'.format(uom_id))

        location_id = int(elem.get('location_id', 0))
        location = StockLocation.browse(location_id)
        if not location:
            errors.append('No location was found with id {}'.format(location))
        else:
            warehouse = StockWarehouse.search([('lot_stock_id', '=', location.id)])
            if not warehouse:
                errors.append('No warehouse was found with Location Stock having id {}'.format(location_id))
            picking_type = warehouse.in_type_id
            if not picking_type:
                errors.append('No Operation Type was found with In Type associated to warehouse '
                              'with id {}'.format(warehouse.id))

        if errors:
            _logger.error('The following errors were found when processing <operationplan> with '
                          'ordertype "PO" for reference {}: {}'.format(elem_reference, os.linesep.join(errors)))
        else:
            # TODO Odoo has no place to store the criticality
            # elem.get('criticality'),

            # Done as a list and not as a dict as the order when assigning values to the Form is important
            po_values = [
                ("company_id", company),
                ('picking_type_id', picking_type),
                ("partner_id", supplier),
                ("origin", "frePPLe"),
            ]

            po_line_values = self._get_po_line_values(elem, product, uom)

            po_key = (supplier.id, location.id)
            if po_key not in imported_pos:

                f = Form(PurchaseOrder)
                for key, value in po_values:
                    setattr(f, key, value)
                po = f.save()
                imported_pos[po_key] = po.id

            po = PurchaseOrder.browse(imported_pos[po_key])
            with Form(po) as f:
                with f.order_line.new() as line_f:
                    for line_key, line_value in po_line_values:
                        setattr(line_f, line_key, line_value)
