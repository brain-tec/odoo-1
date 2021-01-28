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
    def __init__(self, req, database=None, company=None, mode=1):
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

    def run(self):
        msg = []

        mfg_order = self.env["mrp.production"]
        if self.mode == 1:
            # Cancel previous draft purchase quotations
            m = self.env["purchase.order"]
            recs = m.search([("state", "=", "draft"), ("origin", "=", "frePPLe")])
            recs.write({"state": "cancel"})
            recs.unlink()
            msg.append("Removed %s old draft purchase orders" % len(recs))

            # Cancel previous draft manufacturing orders
            recs = mfg_order.search(
                [
                    "|",
                    ("state", "=", "draft"),
                    ("state", "=", "cancel"),
                    ("origin", "=", "frePPLe"),
                ]
            )
            recs.write({"state": "cancel"})
            recs.unlink()
            msg.append("Removed %s old draft manufacturing orders" % len(recs))

        # Parsing the XML data file
        countproc = 0
        countsm = 0
        countmfg = 0

        # dictionary that stores as key the supplier id and the associated po id
        # this dict is used to aggregate the exported POs for a same supplier
        # into one PO in odoo with multiple lines
        supplier_reference = {}

        # dictionary that stores as key a tuple (product id, supplier id)
        # and as value a poline odoo object
        # this dict is used to aggregate POs for the same product supplier
        # into one PO with sum of quantities and min date
        product_supplier_dict = {}

        for event, elem in iterparse(self.datafile, events=("start", "end")):
            if event == "end" and elem.tag == "operationplan":
                try:
                    ordertype = elem.get("ordertype")

                    if ordertype == "PO":
                        self._create_or_update_po(elem, self.company, supplier_reference, product_supplier_dict)
                        countproc += 1

                    elif ordertype == "DO":
                        self._create_or_update_stock_move_line(elem)
                        countsm += 1

                    elif ordertype == "MO":
                        self._create_or_update_mo(elem, self.company)
                        countmfg += 1

                except Exception as e:
                    logger.error("Exception %s" % e)
                    msg.append(str(e))
                # Remove the element now to keep the DOM tree small
                root.clear()
            elif event == "start" and elem.tag == "operationplans":
                # Remember the root element
                root = elem

        # Be polite, and reply to the post
        msg.append("Processed %s uploaded procurement orders" % countproc)
        msg.append("Processed %s uploaded stock moves" % countsm)
        msg.append("Processed %s uploaded manufacturing orders" % countmfg)
        return "\n".join(msg)

    def _create_or_update_po(self, elem, company, supplier_reference, product_supplier_dict):
        self.env['purchase.order']._create_or_update_from_frepple_po(elem, company, supplier_reference,
                                                                     product_supplier_dict)

    def _create_or_update_stock_move_line(self, elem):
        self.env['stock.move.line']._create_or_update_from_frepple_operation_plan(elem)

    def _create_or_update_mo(self, elem, company):
        self.env['mrp.production']._create_or_update_from_frepple_mo(elem, company)
