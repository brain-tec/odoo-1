##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.addons.frepple.controllers.outbound import exporter
from odoo.addons.frepple.controllers.inbound import importer
from odoo import SUPERUSER_ID


class TestBase(TransactionCase):
    maxDiff = None

    def setUp(self):
        super(TestBase, self).setUp()
        self.exporter = exporter(req=self, uid=SUPERUSER_ID)

        self.httprequest = lambda: None  # See https://stackoverflow.com/a/2827734
        self.httprequest.files = {'frePPLe plan': False}
        self.importer = importer(req=self)

        # We include just the values that we need here in exporter.uom (the info for the kilos).
        # because our default method to create products uses just kilos. So just kilos
        # are enough for the moment.
        self.kgm_uom = self.env.ref('uom.product_uom_kgm')
        self.exporter.uom = {
            self.kgm_uom.id: {
                'factor': self.kgm_uom.factor,
                'name': self.kgm_uom.name,
                'category': self.kgm_uom.category_id.id,
            }}
        self.exporter.uom_categories = {
            self.kgm_uom.category_id.id: self.kgm_uom.id,
        }

    def _create_move_line(self, from_location, to_location, product, defaults_move=None, defaults_move_line=None):
        defaults_move = defaults_move if defaults_move else {}
        defaults_move_line = defaults_move_line if defaults_move_line else {}
        move_values = {
            'name': 'TC_Ref #1',
            'location_id': from_location.id,
            'location_dest_id': to_location.id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 1.0,
        }
        move_values.update(defaults_move)
        move = self.env['stock.move'].create(move_values)
        move_line_values = {
            'move_id': move.id,
            'product_id': move.product_id.id,
            'product_uom_qty': move.product_uom_qty,
            'qty_done': 1,
            'product_uom_id': move.product_uom.id,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
        }
        move_line_values.update(defaults_move_line)
        return self.env['stock.move.line'].create(move_line_values)

    def _create_customer(self, name, parent=None):
        return self.env['res.partner'].create({
            'customer_rank': 1,
            'name': name,
            'email': '{}@braintec-group.com'.format(name.lower()),
            'is_company': True,
            'parent_id': False if not parent else parent.id,
        })

    def _create_category(self, name, parent=None):
        create_values = {
            'name': name,
            'property_cost_method': 'standard',
        }
        if parent:
            create_values['parent_id'] = parent.id
        return self.env['product.category'].create(create_values)

    def _create_product(self, name, price, category=None):
        """ Creates a product that can be purchased that has kg as its UoM.
        """
        kgm_uom = self.env.ref('uom.product_uom_kgm')
        create_values = {
            'name': name,
            'list_price': price,
            'type': 'product',
            'uom_id': kgm_uom.id,
            'uom_po_id': kgm_uom.id,
            'purchase_ok': True,
        }
        if category:
            create_values['categ_id'] = category.id
        return self.env['product.product'].create(create_values)

    def _create_supplier_seller(self, name, product, priority, price, delay):
        supplier = self.env['res.partner'].create({
            'name': name,
            'supplier_rank': 1,
        })
        seller = self.env['product.supplierinfo'].create({
            'name': supplier.id,
            'product_id': product.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'currency_id': self.env.ref('base.EUR').id,
            'min_qty': 0.0,
            'sequence': priority,
            'price': price,
            'delay': delay,
        })
        return supplier, seller

    def _create_warehouse(self, name, values=None):
        values = values if values else {}
        create_values = {
            'name': name,
            'code': name.upper(),
            'wh_input_stock_loc_id': False,
            'wh_output_stock_loc_id': False,
            'wh_pack_stock_loc_id': False,
            'wh_qc_stock_loc_id': False,
            'view_location_id': False,
        }
        create_values.update(values)
        return self.env['stock.warehouse'].create(create_values)

    def _create_location(self, name, parent=None):
        return self.env['stock.location'].create({
            'name': name,
            'location_id': parent.id if parent else False,
        })

    def _create_quotation(self, client, product, qty, defaults=None, defaults_line=None):
        """ Creates a quotation for the given product & quantity.
        """
        defaults = defaults if defaults else {}
        defaults_line = defaults_line if defaults_line else {}
        create_values_line = {
            'name': product.name,
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': self.env.ref('uom.product_uom_kgm').id,
            'price_unit': 7,
        }
        create_values_line.update(defaults_line)
        create_values = {
            'partner_id': client.id,
            'date_order': fields.Datetime.now(),
            'picking_policy': 'direct',
            'order_line': [(0, 0, create_values_line)],
        }
        create_values.update(defaults)
        sale_order = self.env['sale.order'].create(create_values)
        return sale_order

    def _create_lot(self, name, product, defaults=None):
        defaults = defaults if defaults else {}
        create_values = {
            'name': name,
            'product_id': product.id,
            'company_id': self.env.user.company_id.id,
        }
        create_values.update(defaults)
        return self.env['stock.production.lot'].create(create_values)

    def _increase_qty_for_product(self, product, qty, location, lot):
        """ Increases the quantity on hand of the product in the amount received.
        """
        inventory = self.env['stock.inventory'].create({
            'name': 'Test Inventory Adjustment {}'.format(fields.Datetime.now()),
            'product_ids': [(4, product.id)],
            # 'operating_unit_use_trade_management': False,  # Added so that tests pass in an integrated way.
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'product_qty': qty,
                'prod_lot_id': lot.id if lot else False,
                'location_id': location.id
            })]
        })
        inventory.action_start()
        inventory.action_validate()
        return inventory

    def _create_internal_picking(self, location_src, location_dest, defaults=None):
        defaults = defaults if defaults else {}
        create_values = {
            'picking_type_id': self.env.ref('stock.picking_type_internal').id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
        }
        create_values.update(defaults)
        return self.env['stock.picking'].create(create_values)
