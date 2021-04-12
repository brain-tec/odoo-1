# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 by frePPLe bv
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
import logging
import time

from odoo import api, models, fields, exceptions
from odoo.addons.base.models.res_partner import _tz_get

_logger = logging.getLogger(__name__)

try:
    import jwt
except Exception:
    _logger.error(
        "PyJWT module has not been installed. Please install the library from https://pypi.python.org/pypi/PyJWT"
    )


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = "res.company"

    @api.model
    def _get_default_frepple_bom_dummy_route_id(self):
        return self.env.ref('frepple.dummy_mrp_routing_frepple', raise_if_not_found=False)

    def _frepple_export_language(self):
        return self.env['res.lang'].search([], limit=1)

    manufacturing_warehouse = fields.Many2one(
        "stock.warehouse", "Manufacturing warehouse", ondelete="set null"
    )
    calendar = fields.Many2one("resource.calendar", "Calendar", ondelete="set null")
    webtoken_key = fields.Char("Webtoken key", size=128)
    frepple_server = fields.Char("frePPLe web server", size=128)
    sol_domain = fields.Text(
        default="[('order_id.warehouse_id', '!=', False),"
                "('order_id.partner_id', '!=', False),"
                "('product_id', '!=', False)]",
        string="Sale Order Line Domain")
    frepple_bom_dummy_route_id = fields.Many2one(
        "mrp.routing", string='Dummy Route for BoM', required=True,
        default=_get_default_frepple_bom_dummy_route_id,
        help="See the configuration flag for frePPLe.")
    internal_moves_domain = fields.Text(
        "Internal Moves Domain", default="[]")
    stock_rules_domain = fields.Text(
        "Stock Rules Domain", default="[]")
    tz_for_exporting = fields.Selection(
        _tz_get, string='Timezone for exporting frePPLe', required=True, default='UTC',
    )
    frepple_export_language = fields.Many2one(
        'res.lang', string='Export Language', required=True,
        default=lambda self: self._frepple_export_language(),
        help='The language set here is the one that will be used '
             'to export the content using frePPLe.')

    @api.model
    def getFreppleURL(self, navbar=True, _url="/"):
        """
        Create an authorization header trusted by frePPLe
        """
        user_company_webtoken = self.env.user.company_id.webtoken_key
        if not user_company_webtoken:
            raise exceptions.UserError("FrePPLe company web token not configured")
        encode_params = dict(
            exp=round(time.time()) + 600, user=self.env.user.login, navbar=navbar
        )
        webtoken = jwt.encode(
            encode_params, user_company_webtoken, algorithm="HS256"
        )
        server = self.env.user.company_id.frepple_server
        if not server:
            raise exceptions.UserError("FrePPLe server URL not configured")
        url = "%s%s?webtoken=%s" % (server, _url, webtoken)
        return url
