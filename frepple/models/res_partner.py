##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from xml.sax.saxutils import quoteattr
from odoo import models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

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
        return []

    def _frepple_generate_common_fields_xml(self):
        self.ensure_one()
        xml_str = []
        for field_type, field_name, field_value in self._frepple_get_common_fields():
            xml_str.append('<{} name="{}" value={}/>'.format(
                field_type, field_name, quoteattr(field_value)))
        return xml_str

    def _frepple_customer_name(self):
        self.ensure_one()
        return '{} {}'.format(self.id, self.name)

    def _frepple_export_customer_tags_xml(self):
        """ Exports as a frePPLe's <customer>
        """
        xml_str = []
        for record in self:
            customer_name = record._frepple_customer_name()
            common_fields = record._frepple_generate_common_fields_xml()
            if common_fields:
                xml_str.append('<customer name={}>'.format(quoteattr(customer_name)))
                xml_str.extend(common_fields)
                xml_str.append('</customer>')
            else:
                xml_str.append('<customer name={}/>'.format(quoteattr(customer_name)))
        return xml_str

    @api.model
    def _frepple_export_customers_content_xml(self):
        xml_str = []
        customers = self.env['res.partner'].search([
            ('customer_rank', '>', 0),
            ('parent_id', '=', False),
        ], order='id')
        if 'test_prefix' in self.env.context:
            customers = customers.filtered(
                lambda customer: customer.name.startswith(self.env.context['test_prefix']))
        xml_str.extend(customers._frepple_export_customer_tags_xml())
        return xml_str

    @api.model
    def _frepple_export_customers_xml(self):
        """ Export as a frePPLe's <customers>
        """
        xml_str = [
            '<!-- customers -->',
            '<customers>',
        ]
        xml_str.extend(self._frepple_export_customers_content_xml())
        xml_str.append('</customers>')
        return '\n'.join(xml_str)
