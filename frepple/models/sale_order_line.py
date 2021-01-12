##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from odoo import models, api, _
from odoo.addons.frepple.misc.tree import Node
from collections import deque
from xml.sax.saxutils import quoteattr
import ast
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

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
            nodes.append(Node(field_type, attrs={'name': field_name, 'value': field_value}))
        return nodes

    def _get_customer_name_for_demands(self):
        """ Returns the name of a customer in a <demand> item.
        """
        self.ensure_one()
        return '{} {}'.format(self.order_id.partner_id.id, self.order_id.partner_id.name)

    @api.model
    def _frepple_export(self):
        """ Returns a string with the XML encoding the list of sale.order.lines.
        """
        demands_node = Node('demands')
        self._frepple_export_nodes(demands_node)
        return '\n'.join(['<!-- sales order lines -->'] + demands_node.to_list_xml())

    @api.model
    def _frepple_export_nodes(self, demands_node):
        """ Fills the demands_node with children nodes.
        """
        product_product = self.env['product.product']

        # Get all sales order lines
        so_lines_datas = self.env['sale.order.line'].search_read(
            ast.literal_eval(self.env.user.company_id.sol_domain),
            ['qty_delivered', 'state', 'product_id', 'product_uom_qty', 'product_uom', 'order_id'],
            order='order_id, id')

        if 'test_prefix' in self.env.context:
            filtered_so_lines_datas = []
            for so_line_data in so_lines_datas:
                sale_order = self.env['sale.order'].browse(so_line_data['order_id'][0])
                if sale_order.partner_id.name.startswith(self.env.context['test_prefix']):
                    filtered_so_lines_datas.append(so_line_data)
            so_lines_datas = filtered_so_lines_datas

        # We cache the sale order, since it's likely consecutive iterations have the same sale order.
        sale_order = None
        for so_line_data in so_lines_datas:
            if sale_order is None or sale_order.id != so_line_data['order_id'][0]:
                sale_order = self.env['sale.order'].browse(so_line_data['order_id'][0])

            so_line = self.env['sale.order.line'].browse(so_line_data['id'])

            # Will change later, if state == 'sale' and there are pending things to deliver.
            product_uom_qty = so_line_data['product_uom_qty']

            # Maps the Odoo's status to the frePPLe status for sale orders.
            state = sale_order.state
            if state == 'draft':
                frepple_status = 'quote'
            elif state == 'sale':
                delivered_uom_qty = so_line_data['product_uom_qty'] - so_line_data['qty_delivered']
                if delivered_uom_qty <= 0:
                    frepple_status = 'closed'
                else:
                    frepple_status = 'open'
                    product_uom_qty = delivered_uom_qty
            elif state in ('done', 'sent'):
                frepple_status = 'closed'
            else:  # if state == "cancel":
                frepple_status = 'canceled'

            name = '%s %d' % (sale_order.name, so_line_data['id'])
            product = product_product.browse(so_line_data['product_id'][0])
            location = sale_order.warehouse_id.lot_stock_id.complete_name
            customer_name = so_line._get_customer_name_for_demands()
            due = getattr(sale_order, 'commitment_date', False) or sale_order.date_order

            uom = self.env['uom.uom'].browse(so_line_data['product_uom'][0])
            try:
                qty = uom._compute_quantity(product_uom_qty, product.uom_id, raise_if_failure=True)
            except Exception:
                qty = 0
                _logger.warning(_("Can't convert from {} for product {} (ID={})").format(
                    uom.name, product.name, product.id))

            demand_node = Node(
                'demand', odoo_record=so_line, attrs={
                    'name': name,
                    'quantity': str(qty),
                    'due': due.strftime('%Y-%m-%dT%H:%M:%S'),
                    'minshipment': sale_order.picking_policy == 'one' and qty or '1.0',
                    'status': frepple_status,
                    'priority': '10',
                }, children=deque([
                    Node('item', attrs={'name': product.name}),
                    Node('customer', attrs={'name': customer_name}),
                    Node('location', attrs={'name': location}),
                ]))
            demand_node.children.extend(so_line._frepple_generate_common_field_nodes())
            demands_node.children.append(demand_node)
