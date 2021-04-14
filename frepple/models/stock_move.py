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


class StockMove(models.Model):
    _inherit = 'stock.move'

    frepple_reference = fields.Char('Reference (frePPLe)', copy=False)

    @api.model
    def _create_or_update_from_frepple_stock_move(self, elem, company, imported_pickings):
        """ Receives an XML subtree from an input file from frePPLe,
            in particular an <operationplan>, and creates a stock.move
            for it inside a picking. A picking is created/selected for each pair or source/dest locations and
            all received moves are associated correspondingly
        """
        StockPicking = self.env['stock.picking']
        ProductProduct = self.env['product.product']
        StockLocation = self.env['stock.location']
        UomUom = self.env['uom.uom']

        elem_reference = elem.get('reference')
        elem_date = (elem.get('start')).replace('T', ' ')
        uom_id, item_id = elem.get("item_id").split(",")

        # If we find at least one error, we inform and skip the element update/creation.
        errors = []

        product_id = int(item_id)
        product = ProductProduct.browse(product_id)
        if not product:
            errors.append('No product was found with id {}'.format(product_id))

        uom_id = int(uom_id)
        uom = UomUom.browse(uom_id)
        if not uom:
            errors.append('No uom was found with id {}'.format(uom_id))

        # Determines the origin location.
        origin_location_id = int(elem.get('origin_id', 0))
        from_location = StockLocation.browse(origin_location_id)
        if not from_location:
            errors.append('No location was found with id {}'.format(origin_location_id))

        # Determines the destination location.
        destination_location_id = int(elem.get('destination_id', 0))
        to_location = StockLocation.browse(destination_location_id)
        if not to_location:
            errors.append('No location was found with id {}'.format(destination_location_id))

        if errors:
            _logger.error('The following errors were found when processing <operationplan> with '
                          'ordertype "DO" for reference {}: {}'.format(elem_reference, os.linesep.join(errors)))
        else:
            # DO is a move.
            # We create a picking in draft with that move, otherwise,
            # if there is an existing picking for the source/dest locations,
            # we add the move there to group all those moves coming from frepple

            picking_key = (from_location.id, to_location.id)

            if picking_key not in imported_pickings:
                picking_type_id = self.env['stock.picking.type'].search(
                    [('default_location_src_id', 'child_of', from_location.id),
                     ('default_location_dest_id', 'child_of', to_location.id),
                     ('code', '=', 'internal')], limit=1)
                if not picking_type_id:
                    picking_type_id = self.env.ref('stock.picking_type_internal')

                # no need to set location_id and location_dest_id as they are set from picking type
                # with onchange
                # No need to set scheduled_date as elem_date, as it will take automatically the earliest date
                # from all move expected dates
                picking_values = [
                    ['picking_type_id', picking_type_id],
                    ['origin', 'frePPLe']
                ]
                f_picking = Form(StockPicking)
                for key, value in picking_values:
                    setattr(f_picking, key, value)
                picking = f_picking.save()
                imported_pickings[picking_key] = picking.id

            picking = StockPicking.browse(imported_pickings[picking_key])

            # The move will be always new, as the frepple reference is new each time
            # Coming from a picking the locations are set from the picking, as well as date and date_expected
            #['date', elem_date],
            move_values = [
                ['product_id', product],
                ['product_uom', uom],
                ['product_uom_qty', elem.get('quantity')],
                ['date_expected', elem_date],
                ['frepple_reference', elem_reference],
                ['location_id', from_location],     # Should be automatically set by picking type
                ['location_dest_id', to_location],  # Should be automatically set by picking type
            ]

            with Form(picking) as f_picking:
                with f_picking.move_ids_without_package.new() as f_move:
                    for key, value in move_values:
                        setattr(f_move, key, value)
