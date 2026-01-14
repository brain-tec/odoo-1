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

import logging
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

    tab = fields.Selection(
        [
            ("purchase", "Purchase"),
            ("mrp", "Manufacturing"),
            ("sale", "Sales"),
            ("stock", "Inventory"),
        ],
        string="Tab",
        required=True,
    )

    type = fields.Selection(
        [
            ("purchase", "purchase"),
            ("produce", "produce"),
            ("reschedule", "reschedule"),
            ("adjustreorderingrule", "adjustreorderingrule"),
            ("latedelivery", "late delivery"),
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

    # for specific recommendation data (partner_id, operation...)
    data = fields.Json(string="Data (JSON)", default=dict)

    recommendation = fields.Html(string="Recommendation")

    res_partner_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        ondelete="cascade",
    )

    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Sales Order Line",
        ondelete="cascade",
    )

    sale_order_id = fields.Many2one(
        related="sale_order_line_id.order_id",
        string="Sales Order",
        readonly=True,
        store=True,
    )

    mrp_production_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        ondelete="cascade",
    )

    # Make sure the user cannot create a recommendation.
    # backend should create recommendations like this:
    # self.env["frepple.recommendation"].with_context(frepple_import=True).create(vals)
    @api.model
    def create(self, vals):
        if not self.env.context.get("frepple_import"):
            raise UserError("FrePPLe recommendations cannot be created manually.")
        for item in vals:
            if item.get("recommendation"):
                item["recommendation"] = self._format_recommendation(
                    item.get("recommendation")
                )
        return super().create(vals)

    def action_approve(self):
        to_unlink = self.browse()  # empty recordset

        # One PO per supplier
        # key is supplier id, value is po object
        pos = {}

        # One PO line per supplier,product
        # key is (supplier_id, product_id)
        # value is po line
        po_lines = {}

        for rec in self:
            if rec.type == "purchase":

                # 1. Check if a PO already exists for that supplier
                if rec.res_partner_id.id in pos:
                    po = pos[rec.res_partner_id.id]

                # 2 Else create a PO
                else:
                    po_args = {
                        "company_id": self.env.company.id,
                        "partner_id": rec.res_partner_id.id,
                    }
                    po = (
                        self.env["purchase.order"]
                        .with_user(self.env.user)
                        .create(po_args)
                    )
                    po.origin = "frePPLe recommendation"

                    pos[rec.res_partner_id.id] = po

                # 2. check if a Purchase Order Line already exists for that product
                product = rec.product_id

                if (rec.res_partner_id.id, product.id) in po_lines:
                    po_line = po_lines[(rec.res_partner_id.id, product.id)]
                    po_line.date_planned = min(po_line.date_planned, rec.enddate)
                    po_line.product_qty += rec.quantity
                else:
                    po_line = (
                        self.env["purchase.order.line"]
                        .with_user(self.env.user)
                        .create(
                            {
                                "order_id": po.id,
                                "product_id": product.id,
                                "product_qty": rec.quantity,
                                "product_uom_id": product.uom_id.id,
                            }
                        )
                    )

                    vals = po_line._prepare_purchase_order_line(
                        product,
                        rec.quantity,
                        product.uom_id,
                        self.company_id,
                        po.partner_id,
                        po,
                    )
                    vals["date_planned"] = rec.enddate
                    po_line.write(vals)
                    po_lines[(rec.res_partner_id.id, product.id)] = po_line

                # Mark recommendation for deletion
                to_unlink |= rec

            elif rec.type == "produce":
                # 1. Create Manufacturing Order
                mo_args = {
                    "company_id": self.env.company.id,
                    "bom_id": rec.data["bom_id"],
                    "product_qty": rec.quantity,
                    "date_start": rec.startdate,
                    "date_finished": rec.enddate,
                    "product_id": rec.product_id.id,
                    "product_uom_id": rec.product_id.uom_id.id,
                    # "picking_type_id": picking.id,
                    "qty_producing": 0.00,
                    "origin": "frePPLe recommendation",
                }
                mo = self.env["mrp.production"].with_user(self.env.user).create(mo_args)

                # Mark recommendation for deletion
                to_unlink |= rec

        # unlink ALL approved recommendations at once
        if to_unlink:
            to_unlink.unlink()

        return True

    def action_generate_recommendations(self):
        # 1. Get the list of active companies from the environment
        active_companies = self.env.companies

        # 2. Check if more than one company is selected
        if len(active_companies) > 1:
            raise UserError(
                "You have multiple companies selected. "
                "Please select only one company before generating recommendations."
            )

        # 3. Get the single active company ID
        # (self.env.company always returns the 'current' or first active company)
        company_id = self.env.company.id

        # 4. Launch the job
        self.env["frepple.job"].action_launch(company_id)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Computing frePPLe recommendations",
                "message": f"Data collection started for {self.env.company.name}.",
                "type": "success",
                "sticky": False,
            },
        }

    # Used to format the recommendation in the list view
    def _format_recommendation(self, raw_text):
        lines = raw_text.split("\\n")
        if not lines:
            return ""
        first_line = f"<b>{lines[0]}</b>"
        if len(lines) > 1:
            # Wrap remaining lines in a small tag
            other_lines = "<br/>".join(lines[1:])
            return f"{first_line}<br/><small class='text-muted'>{other_lines}</small>"
        return first_line

    def action_open_forecast(self):
        self.ensure_one()
        if not self.product_id:
            return False

        # This method is defined in the 'stock' module and returns the correct action.
        action = self.product_id.action_product_forecast_report()

        # Ensure the context is pointing to our specific product
        action["context"] = {
            "active_id": self.product_id.id,
            "active_model": "product.product",
        }
        return action
