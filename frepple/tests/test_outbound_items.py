##############################################################################
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from unittest import skipIf
from odoo.addons.frepple.tests.test_base import TestBase

UNDER_DEVELOPMENT = False
UNDER_DEVELOPMENT_MSG = 'Test skipped because of being under development'


class TestOutboundItems(TestBase):
    def setUp(self):
        super(TestOutboundItems, self).setUp()
        test_warehouse = self.env.ref('stock.warehouse0')
        test_warehouse.code = 'TC_WH'
        self.stock_location = test_warehouse.lot_stock_id

    def _get_supplier_info(self,sellers, suppliers, product):
        stock_rules = self.env['stock.rule'].search(
            [('action', '=', 'buy'), ('route_id', 'in', product.product_tmpl_id.route_ids.ids)])

        supplier_info = ""
        for i in range(0, len(sellers)):
            seller = sellers[i]
            supplier = suppliers[i]
            for rule in stock_rules:
                supplier_info += '\n'.join([
                    '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" cost="{:0.6f}">'.format(
                        seller.delay, seller.sequence, seller.price),
                    '<location name="{}"/>'.format(rule.location_id.complete_name),
                    '<supplier name="{} {}"/>'.format(supplier.id, supplier.name),
                    '</itemsupplier>\n'])
        supplier_info = supplier_info[:-1]  # Removing last \n
        return supplier_info

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_product_no_subcategory(self):
        """ Tests a product with no subcategories.
        """
        category_a = self._create_category('TC_Category_A')
        product_1 = self._create_product('TC_Product_1', category=category_a, price=5)
        product_1.default_code = 'DEFAULT_CODE'
        supplier_1, seller_1 = self._create_supplier_seller(
            'TC_Supplier_1', product=product_1, priority=1, price=7, delay=3)
        supplier_2, seller_2 = self._create_supplier_seller(
            'TC_Supplier_2', product=product_1, priority=2, price=13, delay=2)

        xml_str_actual = self.exporter.export_items(ctx={'test_export_items': True, 'test_prefix': 'TC_'})
        sellers = [seller_1, seller_2]
        suppliers = [supplier_1, supplier_2]
        supplier_info = self._get_supplier_info(sellers, suppliers, product_1)

        xml_str_expected = '\n'.join([
            '<!-- products -->',
            '<items>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a.name, category_a.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_1.name, product_1.list_price, self.kgm_uom.id, product_1.id),
            '<itemsuppliers>',
            supplier_info,
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '<stringproperty name="internalreference" value="{}"/>'.format(product_1.default_code),
            '</item>',
            '</members>',
            '</item>',
            '</items>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_product_with_subcategory_one_level(self):
        """ Tests a category with one level
        """
        category_a = self._create_category('TC_Category_A')
        product_a_1 = self._create_product('TC_Product_A_1', category=category_a, price=5)
        supplier_1, seller_1 = self._create_supplier_seller(
            'TC_Supplier_1', product=product_a_1, priority=1, price=7, delay=3)
        supplier_2, seller_2 = self._create_supplier_seller(
            'TC_Supplier_2', product=product_a_1, priority=2, price=13, delay=2)
        sellers_a = [seller_1, seller_2]
        suppliers_a = [supplier_1, supplier_2]
        supplier_info_a = self._get_supplier_info(sellers_a, suppliers_a, product_a_1)

        category_a_sub = self._create_category('TC_Category_A_Sub', parent=category_a)
        product_a_sub_1 = self._create_product('TC_Product_A_Sub_1', category=category_a_sub, price=5)
        supplier_3, seller_3 = self._create_supplier_seller(
            'TC_Supplier_3', product=product_a_sub_1, priority=10, price=70, delay=30)
        supplier_4, seller_4 = self._create_supplier_seller(
            'TC_Supplier_4', product=product_a_sub_1, priority=20, price=130, delay=20)
        sellers_a_sub = [seller_3, seller_4]
        suppliers_a_sub = [supplier_3, supplier_4]
        supplier_info_a_sub = self._get_supplier_info(sellers_a_sub, suppliers_a_sub, product_a_sub_1)

        xml_str_actual = self.exporter.export_items(ctx={'test_export_items': True, 'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- products -->',
            '<items>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a.name, category_a.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_1.name, product_a_1.list_price, self.kgm_uom.id, product_a_1.id),
            '<itemsuppliers>',
            supplier_info_a,
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a_sub.name, category_a_sub.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_sub_1.name, product_a_sub_1.list_price, self.kgm_uom.id, product_a_sub_1.id),
            '<itemsuppliers>',
            supplier_info_a_sub,
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '</members>',
            '</item>',
            '</members>',
            '</item>',
            '</items>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_product_with_subcategory_two_levels(self):
        """ Tests a product with two levels of subcategories.
        """
        category_a = self._create_category('TC_Category_A')
        product_a_1 = self._create_product('TC_Product_A_1', category=category_a, price=5)
        supplier_1, seller_1 = self._create_supplier_seller(
            'TC_Supplier_1', product=product_a_1, priority=1, price=7, delay=3)
        supplier_2, seller_2 = self._create_supplier_seller(
            'TC_Supplier_2', product=product_a_1, priority=2, price=13, delay=2)
        sellers_a_1 = [seller_1, seller_2]
        suppliers_a_1 = [supplier_1, supplier_2]
        supplier_info_a_1 = self._get_supplier_info(sellers_a_1, suppliers_a_1, product_a_1)

        category_a_sub = self._create_category('TC_Category_A_Sub', parent=category_a)
        product_a_sub_1 = self._create_product('TC_Product_A_Sub_1', category=category_a_sub, price=5)
        supplier_3, seller_3 = self._create_supplier_seller(
            'TC_Supplier_3', product=product_a_sub_1, priority=10, price=70, delay=30)
        supplier_4, seller_4 = self._create_supplier_seller(
            'TC_Supplier_4', product=product_a_sub_1, priority=20, price=130, delay=20)
        sellers_a_sub_1 = [seller_3, seller_4]
        suppliers_a_sub_1 = [supplier_3, supplier_4]
        supplier_info_a_sub_1 = self._get_supplier_info(sellers_a_sub_1, suppliers_a_sub_1, product_a_sub_1)

        category_a_sub_sub = self._create_category('TC_Category_A_Sub_Sub', parent=category_a_sub)
        product_a_sub_sub_1 = self._create_product('TC_Product_A_Sub_Sub_1', category=category_a_sub_sub, price=7)
        supplier_5, seller_5 = self._create_supplier_seller(
            'TC_Supplier_5', product=product_a_sub_sub_1, priority=10, price=70, delay=30)
        sellers_a_sub_sub_1 = [seller_5]
        suppliers_a_sub_sub_1 = [supplier_5]
        supplier_info_a_sub_sub_1 = self._get_supplier_info(sellers_a_sub_sub_1, suppliers_a_sub_sub_1,
                                                            product_a_sub_sub_1)

        product_a_sub_sub_2 = self._create_product('TC_Product_A_Sub_Sub_2', category=category_a_sub_sub, price=7)
        supplier_6, seller_6 = self._create_supplier_seller(
            'TC_Supplier_6', product=product_a_sub_sub_2, priority=20, price=130, delay=20)
        sellers_a_sub_sub_2 = [seller_6]
        suppliers_a_sub_sub_2 = [supplier_6]
        supplier_info_a_sub_sub_2 = self._get_supplier_info(sellers_a_sub_sub_2, suppliers_a_sub_sub_2,
                                                            product_a_sub_sub_2)

        category_b = self._create_category('TC_Category_B')
        product_b_1 = self._create_product('TC_Product_B_1', category=category_b, price=5)
        supplier_7, seller_7 = self._create_supplier_seller(
            'TC_Supplier_7', product=product_b_1, priority=1, price=7, delay=3)
        sellers_b_1 = [seller_7]
        suppliers_b_1 = [supplier_7]
        supplier_info_b_1 = self._get_supplier_info(sellers_b_1, suppliers_b_1, product_b_1)

        xml_str_actual = self.exporter.export_items(ctx={'test_export_items': True, 'test_prefix': 'TC_'})
        xml_str_expected = '\n'.join([
            '<!-- products -->',
            '<items>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a.name, category_a.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_1.name, product_a_1.list_price, self.kgm_uom.id, product_a_1.id),
            '<itemsuppliers>',
            supplier_info_a_1,
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a_sub.name, category_a_sub.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_sub_1.name, product_a_sub_1.list_price, self.kgm_uom.id, product_a_sub_1.id),
            '<itemsuppliers>',
            supplier_info_a_sub_1,
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a_sub_sub.name, category_a_sub_sub.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_sub_sub_1.name, product_a_sub_sub_1.list_price, self.kgm_uom.id, product_a_sub_sub_1.id),
            '<itemsuppliers>',
            supplier_info_a_sub_sub_1,
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_sub_sub_2.name, product_a_sub_sub_2.list_price, self.kgm_uom.id, product_a_sub_sub_2.id),
            '<itemsuppliers>',
            supplier_info_a_sub_sub_2,
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '</members>',
            '</item>',
            '</members>',
            '</item>',
            '</members>',
            '</item>',
            '<item name="{}" category="{}" description="category">'.format(
                category_b.name, category_b.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_b_1.name, product_b_1.list_price, self.kgm_uom.id, product_b_1.id),
            '<itemsuppliers>',
            supplier_info_b_1,
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '</members>',
            '</item>',
            '</items>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)

    @skipIf(UNDER_DEVELOPMENT, UNDER_DEVELOPMENT_MSG)
    def test_product_inactive(self):
        """ Tests that deactivated products are also processed.
        """
        category = self._create_category('TC_Category')
        product_active = self._create_product('TC_Product_Active', category=category, price=5)
        product_inactive = self._create_product('TC_Product_Inactive', category=category, price=5)
        product_inactive.active = False
        self.assertTrue(product_active.active)
        self.assertFalse(product_inactive.active)

        self.exporter.export_items(ctx={'test_export_items': True, 'test_prefix': 'TC_'})
        self.assertIn(product_active.id, self.exporter.product_product)
        self.assertIn(product_inactive.id, self.exporter.product_product)
