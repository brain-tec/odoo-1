##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _frepple_get_common_fields(self):
        """ Intended to be overridden.
            Returns a list of triplets (type, name, value),
            with type being one of
                - booleanproperty
                - stringproperty
                - doubleproperty
                - dateproperty
        """
        self.ensure_one()
        res = [
            ('stringproperty', 'itemstatus', 'active' if self.active else 'inactive'),
        ]
        if self.default_code:
            res.append(('stringproperty', 'internalreference', self.default_code))
        return res
