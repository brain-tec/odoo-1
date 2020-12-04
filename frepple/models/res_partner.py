##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from odoo import models, api, _
from odoo.exceptions import UserError
from xml.sax.saxutils import quoteattr
from odoo.addons.frepple.misc.tree import Node


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

    def _frepple_generate_common_field_nodes(self):
        """ Generates a set list of Nodes encoding the common attributes.
        """
        self.ensure_one()
        nodes = []
        for field_type, field_name, field_value in self._frepple_get_common_fields():
            nodes.append(Node(field_type, attrs={'name': field_name, 'value': quoteattr(field_value)}))
        return nodes

    def _frepple_get_customer_name(self):
        self.ensure_one()
        return '{} {}'.format(self.id, self.name)

    @api.model
    def _frepple_export_customers(self):
        """ Returns a string with the XML encoding the list of customers.
        """
        customers_node = Node('customers')
        self._frepple_export_nodes(customers_node)
        return '\n'.join(['<!-- customers -->'] + customers_node.to_list_xml())

    @api.model
    def _frepple_export_nodes(self, customers_node):
        """ Builds the tree of <customer> nodes, children of the <customers> node received.
            Intended to be extended.
        """
        if customers_node.name != 'customers':
            raise UserError(_(''))

        customers_domain = [
            ('customer_rank', '>', 0),
            ('parent_id', '=', False),
        ]
        if 'test_prefix' in self.env.context:
            customers_domain.append(
                ('name', '=like', '{}%'.format(self.env.context['test_prefix'])),
            )
        customers = self.env['res.partner'].search(customers_domain, order='id')

        for customer in customers:
            node_customer = Node('customer', attrs={'name': customer._frepple_get_customer_name()})
            for common_field_node in customer._frepple_generate_common_field_nodes():
                node_customer.children.append(common_field_node)
            customers_node.children.append(node_customer)
