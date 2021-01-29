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


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    frepple_reference = fields.Char('Reference (frePPLe)')

    @api.model
    def _create_or_update_from_frepple_operation_plan(self, elem, company):
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
        uom_uom = self.env['uom.uom']

        elem_reference = elem.get('reference')
        elem_date = (elem.get('start') or elem.get('end', '')).replace('T', ' ')
        uom_id, item_id = elem.get("item_id").split(",")

        # If we find at least one error, we inform and skip the element update/creation.
        errors = []

        product_id = int(item_id)
        product = product_product.browse(product_id)
        if not product:
            errors.append('No product was found with id {}'.format(product_id))

        uom_id = int(uom_id)
        uom = uom_uom.browse(uom_id)
        if not uom:
            errors.append('No uom was found with id {}'.format(uom_id))

        # Determines the origin location.
        origin_location_id = int(elem.get('origin_id', 0))
        from_location = stock_location.browse(origin_location_id)
        if not from_location:
            errors.append('No location was found with id {}'.format(origin_location_id))

        # Determines the destination location.
        destination_location_id = int(elem.get('destination_id', 0))
        to_location = stock_location.browse(destination_location_id)
        if not to_location:
            errors.append('No location was found with id {}'.format(destination_location_id))

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
                'location_dest_id': to_location,
                'location_id': from_location,
                'product_id': product,
                'product_uom_id': uom,
                'product_uom_qty': elem.get('quantity')
                # 'move_id': ?.id  # To add it later.
            }
            move_values = {
                'name': 'frePPLe - {} - {}'.format(elem_reference, product.name),
                'location_id': from_location,
                'location_dest_id': to_location,
                'product_id': product,
                'product_uom': uom,
                'product_uom_qty': elem.get('quantity'),
                'date': elem_date,
                'date_expected': elem_date,
            }

            move_line = self.search([
                ('frepple_reference', '=', elem_reference),
                ('state', 'not in', ['done', 'cancel']),
            ])
            if move_line:
                with Form(move_line) as f_move_line:
                    for key, value in move_line_values.items():
                        setattr(f_move_line, key, value)

                with Form(move_line.move_id) as f_move:
                    for key, value in move_values.items():
                        setattr(f_move, key, value)

                move = move_line.move_id

            else:
                f_move = Form(stock_move)
                for key, value in move_values.items():
                    setattr(f_move, key, value)
                move = f_move.save()
                # state is readonly on the Form, so we assign it separately
                move.state = status_mapping.get(elem.get('status'), 'draft')

                # # As we don't have in the view move_line_ids we create move lines in a new Form. Otherwise
                # # they could be created at the same time with Form
                # TODO: Form not working here because company_id is readonly and required in the view
                # f_move_line = Form(self)
                # for key, value in move_line_values.items():
                #     setattr(f_move_line, key, value)
                # move_line = f_move_line.save()
                # # state is readonly on the Form, so we assign it separately
                # move_line.write({'state': status_mapping.get(elem.get('status'), 'draft'),
                #                  'move_id': move,
                #                  'company_id': company})
                move_line_values = {
                    'frepple_reference': elem_reference,
                    'location_dest_id': to_location.id,
                    'location_id': from_location.id,
                    'product_id': product.id,
                    'product_uom_id': uom.id,
                    'product_uom_qty': elem.get('quantity'),
                    'company_id': company.id,
                    'move_id': move.id
                    # 'move_id': ?.id  # To add it later.
                }
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
                    picking_type_id = self.env['stock.picking.type'].search(
                        [('default_location_src_id', '=', from_location.id),
                         ('default_location_dest_id', '=', to_location.id)], limit=1)
                    if not picking_type_id:
                        picking_type_id = self.env.ref('stock.picking_type_internal')
                    picking_values = {
                        'picking_type_id': picking_type_id,
                        'scheduled_date': elem_date,
                        'location_id': from_location,
                        'location_dest_id': to_location,
                    }
                    f_picking = Form(self.env['stock.picking'])
                    for key, value in picking_values.items():
                        setattr(f_picking, key, value)
                    picking = f_picking.save()
                move.picking_id = picking
                move_line.picking_id = picking
