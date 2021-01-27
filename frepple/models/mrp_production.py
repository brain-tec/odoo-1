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

        elem_reference = elem.get('id')

        # If we find at least one error, we inform and skip the element update/creation.
        errors = []

        uom_id, item_id = elem.get("item_id").split(",")

        # Determines the product.
        product_search_domain = [
            ('id', '=', int(item_id)),
            ('name', '=', elem.get('item', '')),
        ]
        product = product_product.search(product_search_domain)
        if not product:
            errors.append('No product was found for {}'.format(product_search_domain))
        elif len(product) > 1:
            errors.append('More than one product was found for {}'.format(product_search_domain))

        # Determines the uom.
        uom_search_domain = [
            ('id', '=', int(uom_id)),
        ]
        uom = uom_uom.search(uom_search_domain)
        if not uom:
            errors.append('No uom was found for {}'.format(uom_search_domain))
        elif len(uom) > 1:
            errors.append('More than one uom was found for {}'.format(uom_search_domain))

        # # Determines the origin location.
        # location_search_domain = [
        #     ('id', '=', elem.get('origin_id', 0)),
        #     ('name', '=', elem.get('origin', '')),
        # ]
        # from_location = stock_location.search(location_search_domain)
        # if not from_location:
        #     errors.append('No location was found for {}'.format(location_search_domain))
        # elif len(from_location) > 1:
        #     errors.append('More than one location was found for {}'.format(location_search_domain))

        # Determines the destination location.
        location_search_domain = [
            ('id', '=', int(elem.get('location_id', 0))),
            ('name', '=', elem.get('location', '')),
        ]
        to_location = stock_location.search(location_search_domain)
        if not to_location:
            errors.append('No location was found for {}'.format(location_search_domain))
        elif len(to_location) > 1:
            errors.append('More than one location was found for {}'.format(location_search_domain))

        # if not from_location:
        #     errors.append('No origin location found.')
        if not to_location:
            errors.append('No destination location found.')

        # Determines the bom.
        bom_search_domain = [
            ('id', '=', int(elem.get("operation").split(" ", 1)[0])),
        ]
        bom = mrp_bom.search(bom_search_domain)
        if not bom:
            errors.append('No bom was found for {}'.format(bom_search_domain))
        elif len(bom) > 1:
            errors.append('More than one bom was found for {}'.format(bom_search_domain))

        if errors:
            _logger.error('The following errors were found when processing <operationplan> with '
                          'ordertype "MO" for reference {}: {}'.format(elem_reference, os.linesep.join(errors)))
        else:
            # TODO no place to store the criticality
            # # elem.get('criticality'),
            mo_values = {
                'frepple_reference': elem_reference,
                'product_qty': elem.get('quantity'),
                'date_planned_start': elem.get("start").replace('T', ' '),
                'date_planned_finished': elem.get("end").replace('T', ' '),
                'product_id': product,
                'company_id': company,
                'product_uom_id': uom,
                'location_src_id': to_location,
                'bom_id': bom,
                'origin': "frePPLe"
            }

            mo = self.search([('frepple_reference', '=', elem_reference)])

            if mo:
                f = Form(mo)
            else:
                f = Form(self)
            for key, value in mo_values.items():
                setattr(f, key, value)
            f.save()
