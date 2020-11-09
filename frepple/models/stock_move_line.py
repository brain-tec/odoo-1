##############################################################################
# Copyright (c) 2020 brain-tec AG (https://bt-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

import os
import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    frepple_reference = fields.Char('Reference (frePPLe)')

    @api.model
    def _create_or_update_from_frepple_operation_plan(self, elem):
        """ Receives an XML subtree from an input file from frePPLe,
            in particular an <operationplan>, and creates a stock.move
            for it; or updates it if it already exists.

            I'm assuming here that the inbound follows the same content
            than the outbound I'm sending, which includes, among other things,
            the ID of the products so that we don't have to search them by
            name. Would be good that we exported the reference of the product
            instead.
        """
        product_product = self.env['product.product']
        stock_location = self.env['stock.location']
        stock_move = self.env['stock.move']

        elem_reference = elem.get('reference')
        elem_date = (elem.get('start') or elem.get('end', '')).replace('T', ' ')

        from_location = self.env['stock.location']
        to_location = self.env['stock.location']
        product = self.env['product.product']  # To silent the IDE.

        # If we find at least one error, we inform and skip the element update/creation.
        errors = []

        for sub_elem in elem:

            if sub_elem.tag == 'item':
                # If we receive the ID of the product inside the parameter category_id, we use it.
                # If we don't receive it, then we have to search the product using its name only.
                product_search_domain = [('name', '=', sub_elem.get('name'))]
                subcategory_attr = sub_elem.get('subcategory')
                if subcategory_attr and ',' in subcategory_attr and subcategory_attr.split(',')[-1].isdigit():
                    product_id = int(subcategory_attr.split(',')[-1])
                    product_search_domain.append(('id', '=', product_id))
                product = product_product.search(product_search_domain)
                if not product:
                    errors.append('No product was found for {}'.format(product_search_domain))
                elif len(product) > 1:
                    errors.append('More than one product was found for {}'.format(product_search_domain))

            elif sub_elem.tag in {'origin', 'location'}:
                # If we receive the ID of the location as the parameter subcategory, we use it.
                # If we don't receive it, then we have to search the location using its name only.
                location_search_domain = [('name', '=', sub_elem.get('name'))]
                subcategory_attr = sub_elem.get('subcategory')
                if subcategory_attr and subcategory_attr.isdigit():
                    location_id = int(subcategory_attr)
                    location_search_domain.append(('id', '=', location_id))
                location = stock_location.search(location_search_domain)
                if not location:
                    errors.append('No location was found for {}'.format(location_search_domain))
                elif len(location) > 1:
                    errors.append('More than one location was found for {}'.format(location_search_domain))
                else:
                    if sub_elem.tag == 'origin':
                        from_location = location
                    else:  # if sub_elem.tag == 'location'
                        to_location = location

        if not from_location:
            errors.append('No origin location found.')
        if not to_location:
            errors.append('No destination location found.')

        if errors:
            _logger.error('The following errors were found when processing <operationplan> with '
                          'ordertype "DO" for reference {}: {}'.format(elem_reference, os.linesep.join(errors)))
        else:
            # TODO: Code to deal with states different than proposed and approved is pending.
            #       The other statuses don't allow an edit in the UI, probably neither in the
            #       backend ─ this has to be checked to know what we can update safely and
            #       what we can't update (or can update, but being super-careful).
            status_mapping = {
                'proposed': 'draft',
                'approved': 'waiting',
                # 'approved': 'confirmed',
                # 'approved': 'partially_available',
                'confirmed': 'assigned',
                'completed': 'done',
                'closed': 'cancel',
            }
            move_line_values = {
                'frepple_reference': elem_reference,
                'state': status_mapping.get(elem.get('status'), 'draft'),
                'location_dest_id': to_location.id,
                'location_id': from_location.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'product_uom_qty': elem.get('quantity'),
                # 'move_id': ?.id  # To add it later.
            }
            move_values = {
                'name': 'frePPLe - {} - {}'.format(elem_reference, product.name),
                'location_id': from_location.id,
                'location_dest_id': to_location.id,
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': elem.get('quantity'),
                'state': status_mapping.get(elem.get('status'), 'draft'),
                'date': elem_date,
                'date_expected': elem_date,
            }
            move_line = self.search([
                ('frepple_reference', '=', elem_reference),
                ('state', 'not in', ['done', 'cancel']),
            ])
            if move_line:
                move_line.write(move_line_values)
                move = move_line.move_id
                move.write(move_values)
            else:
                move = stock_move.create(move_values)
                move_line_values['move_id'] = move.id
                move_line = self.create(move_line_values)

            # We group the move into a picking. If doesn't already exists, we create it.
            if not move.picking_id:
                picking = self.env['stock.picking'].search([
                    ('state', 'in', ['draft', 'waiting']),
                    ('scheduled_date', '=', elem_date),
                    ('location_id', '=', from_location.id),
                    ('location_dest_id', '=', to_location.id),
                ], limit=1)
                if not picking:
                    picking = self.env['stock.picking'].create({
                        'picking_type_id': self.env.ref('stock.picking_type_internal').id,
                        'scheduled_date': elem_date,
                        'location_id': from_location.id,
                        'location_dest_id': to_location.id,
                    })
                move.picking_id = picking
                move_line.picking_id = picking
