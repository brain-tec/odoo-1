# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 by frePPLe bv
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import odoo
import logging
from xml.etree.cElementTree import iterparse
from datetime import datetime

logger = logging.getLogger(__name__)


class importer(object):
    def __init__(self, req, database=None, company=None, mode=1, imported_pos=None, imported_pickings=None):
        self.env = req.env
        self.database = database
        self.company = company
        self.datafile = req.httprequest.files.get("frePPLe plan")

        # The mode argument defines different types of runs:
        #  - Mode 1:
        #    Export of the complete plan. This first erase all previous frePPLe
        #    proposals in draft state.
        #  - Mode 2:
        #    Incremental export of some proposed transactions from frePPLe.
        #    In this mode mode we are not erasing any previous proposals.
        self.mode = mode

        # Dictionary that stores as key the supplier id and as value the associated PO id.
        # This dict is used to aggregate the exported PO lines for a same supplier inside a same PO
        if imported_pos is None:
            imported_pos = {}
        self.imported_pos = imported_pos

        # Dictionary that stores as key the source and destination locations of the picking,
        # and as value the associated picking id.
        # This dict is used to aggregate the exported stock moves for a same pair of locations inside
        # a same picking
        if imported_pickings is None:
            imported_pickings = {}
        self.imported_pickings = {}

    def _cancel_draft_frepple_POs(self):
        # Deleting draft Frepple POs created in previous import, and removing them
        # from the dictionary of imported pos
        recs = self.env["purchase.order"].search([("state", "=", "draft"),
                                                  ("origin", "=", "frePPLe")])
        recs.unlink()
        for rec in recs:
            rec_key = list(self.imported_pos.keys())[list(self.imported_pos.values()).index(rec.id)]
            del self.imported_pos[rec_key]
        return recs

    def _cancel_draft_frepple_MOs(self):
        # Deleting draft Frepple MOs created in previous import
        recs = self.env["mrp.production"].search([("state", "=", "draft"),
                                                  ("origin", "=", "frePPLe")])
        recs.unlink()
        return recs

    def _cancel_draft_frepple_DOs(self):
        # Deleting draft Frepple pickings created in previous import, and removing them
        # from the dictionary of imported pickings
        recs = self.env["stock.picking"].search([("state", "=", "draft"),
                                                 ("origin", "=", "frePPLe")])
        recs.unlink()
        for rec in recs:
            rec_key = list(self.imported_pickings.keys())[list(self.imported_pickings.values()).index(rec.id)]
            del self.imported_pickings[rec_key]
        return recs

    def run(self):
        msg = []

        if self.mode == 1:
            # Cancel previous draft pickings
            cancelled_DOs = self._cancel_draft_frepple_DOs()
            msg.append("Removed %s old draft pickings" % len(cancelled_DOs))

            # Cancel previous draft purchase orders
            cancelled_POs = self._cancel_draft_frepple_POs()
            msg.append("Removed %s old draft purchase orders" % len(cancelled_POs))

            # Cancel previous draft manufacturing orders
            cancelled_MOs = self._cancel_draft_frepple_MOs()
            msg.append("Removed %s old draft manufacturing orders" % len(cancelled_MOs))

        # Parsing the XML data file
        count_po_line = 0
        count_move = 0
        count_mo = 0

        for event, elem in iterparse(self.datafile, events=("start", "end")):
            if event == "end" and elem.tag == "operationplan":
                try:
                    order_type = elem.get("ordertype")

                    if order_type == "PO":
                        self._create_or_update_po_line(elem, self.company, self.imported_pos)
                        count_po_line += 1

                    elif order_type == "DO":
                        self._create_or_update_stock_move(elem, self.company, self.imported_pickings)
                        count_move += 1

                    elif order_type == "MO":
                        self._create_or_update_mo(elem, self.company)
                        count_mo += 1

                except Exception as e:
                    logger.error("Exception %s" % e)
                    msg.append(str(e))
                # Remove the element now to keep the DOM tree small
                root.clear()
            elif event == "start" and elem.tag == "operationplans":
                # Remember the root element
                root = elem

        # Be polite, and reply to the post
        msg.append("Processed %s uploaded PO lines" % count_po_line)
        msg.append("Processed %s uploaded Stock Moves" % count_move)
        msg.append("Processed %s uploaded Manufacturing Orders" % count_mo)
        return "\n".join(msg)

    def _create_or_update_po_line(self, elem, company, imported_pos):
        self.env['purchase.order.line']._create_or_update_from_frepple_po_line(elem, company, imported_pos)

    def _create_or_update_stock_move(self, elem, company, imported_pickings):
        self.env['stock.move']._create_or_update_from_frepple_stock_move(elem, company, imported_pickings)

    def _create_or_update_mo(self, elem, company):
        self.env['mrp.production']._create_or_update_from_frepple_mo(elem, company)
