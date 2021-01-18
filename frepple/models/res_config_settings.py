# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 by frePPLe bv
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
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

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    manufacturing_warehouse = fields.Many2one(
        "stock.warehouse",
        "Manufacturing warehouse",
        related="company_id.manufacturing_warehouse",
        readonly=False,
    )
    calendar = fields.Many2one(
        "resource.calendar", "Calendar", related="company_id.calendar", readonly=False
    )
    webtoken_key = fields.Char(
        "Webtoken key", size=128, related="company_id.webtoken_key", readonly=False
    )
    frepple_server = fields.Char(
        "frePPLe server", size=128, related="company_id.frepple_server", readonly=False
    )
    sol_domain = fields.Text(
        string="Sale Order Line Domain", related="company_id.sol_domain", readonly=False)
    frepple_bom_dummy_route_id = fields.Many2one(
        "mrp.routing", string="Route for BoM",
        related="company_id.frepple_bom_dummy_route_id", readonly=False,
        help="The frePPLe XML requires to indicate a route for every BoM. Odoo does not "
             "require this, thus this dummy route will be used to export BoM from Odoo "
             "to frePPLe in a way that the XML is compliant.")
    tz_for_exporting = fields.Selection(related="company_id.tz_for_exporting", readonly=False)
