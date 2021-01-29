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
from datetime import datetime

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _get_po_line_values(self, elem, product, uom):
        return {
            "product_id": product,
            "product_qty": elem.get("quantity"),
            "product_uom": uom,
            "date_planned": elem.get("end"),
            "price_unit": 0,
            "name": product.name,
        }

    @api.model
    def _create_or_update_from_frepple_po(self, elem, company, supplier_reference, product_supplier_dict):

        ResPartner = self.env['res.partner']
        product_product = self.env['product.product']
        uom_uom = self.env['uom.uom']

        # If we find at least one error, we inform and skip the element update/creation.
        errors = []

        uom_id, item_id = elem.get("item_id").split(",")

        supplier_id = int(elem.get("supplier").split(" ", 1)[0])
        supplier = ResPartner.browse(supplier_id)
        if not supplier:
            errors.append('No supplier was found with id {}'.format(supplier_id))

        product_id = int(item_id)
        product = product_product.browse(product_id)
        if not product:
            errors.append('No product was found with id {}'.format(product_id))

        uom_id = int(uom_id)
        uom = uom_uom.browse(uom_id)
        if not uom:
            errors.append('No uom was found with id {}'.format(uom_id))

        # TODO Odoo has no place to store the location and criticality
        # int(elem.get('location_id')),
        # elem.get('criticality'),
        po_values = {
            "company_id": company,
            "partner_id": supplier,
            "origin": "frePPLe",
        }

        po_line_values = self._get_po_line_values(elem, product, uom)

        if supplier.id not in supplier_reference:

            f = Form(self)
            for key, value in po_values.items():
                setattr(f, key, value)
            po = f.save()
            supplier_reference[supplier.id] = po.id

        if (item_id, supplier.id) not in product_supplier_dict:
            po = self.browse(supplier_reference[supplier.id])
            with Form(po) as f:
                with f.order_line.new() as line_f:
                    for line_key, line_value in po_line_values.items():
                        setattr(line_f, line_key, line_value)

            product_supplier_dict[(item_id, supplier.id)] = po.order_line.id
        else:
            po_line = product_supplier_dict[(item_id, supplier.id)]
            po_line.date_planned = min(
                po_line.date_planned,
                datetime.strptime(elem.get("end"), "%Y-%m-%d %H:%M:%S"),
            )
            po_line.product_qty = po_line.product_qty + float(elem.get("quantity"))
