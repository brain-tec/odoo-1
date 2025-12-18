# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 by frePPLe bv
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from odoo import fields, models, api
from odoo.exceptions import UserError

import secrets
import logging
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)


class FreppleRecommendation(models.Model):
    _name = "frepple.recommendation"
    _description = "Frepple Recommendations"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    type = fields.Selection(
        [
            ("purchase", "Purchase"),
            ("mrp", "Manufacturing"),
            ("sale", "Sales"),
            ("stock", "Inventory"),
        ],
        string="Type",
        required=True,
    )

    startdate = fields.Datetime(string="Start Date")
    enddate = fields.Datetime(string="End Date")

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        ondelete="cascade",
    )

    quantity = fields.Float(string="Quantity")

    # for specific recommendation data (supplier, operation...)
    data = fields.Json(string="Data (JSON)", default=dict)

    description = fields.Char(string="Description")

    # Make sure the user cannot create a recommendation.
    # backend should create recommendations like this:
    # self.env["frepple.recommendation"].with_context(frepple_import=True).create(vals)
    @api.model
    def create(self, vals):
        if not self.env.context.get("frepple_import"):
            raise UserError(
                "FrePPLe recommendations cannot be created manually."
            )
        return super().create(vals)

    def action_approve(self):
        for rec in self:
            if rec.type == "purchase":
                # 1. Create a purchase Order
                logger.info(rec.data)
                po_args = {"company_id": self.env.company.id,
                           "partner_id": rec.data["supplier_id"],
                          }
                po = self.env["purchase.order"].with_user(self.env.user).create(po_args)
                po.origin = "frePPLe recommendation"
                # 2. Create a purchase order line
                product = self.env['product.product'].with_user(self.env.user).browse(rec.product_id.id)
                po_line = self.env["purchase.order.line"].with_user(self.env.user).create(
                                {
                                    "order_id": po.id,
                                    "product_id": product.id,
                                    "product_qty": rec.quantity,
                                    "product_uom_id": product.uom_id.id,
                                }
                            )
                d = po_line._prepare_purchase_order_line(
                                product,
                                rec.quantity,
                                product.uom_id,
                                self.company_id,
                                po.partner_id,
                                po,
                            )
                d["date_planned"] = rec.enddate
                # Finally update the PO line
                po_line.write(d)

                # 3. Delete the recommendation
                rec.unlink()
                return True
