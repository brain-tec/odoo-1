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
        xml_str_expected = '\n'.join([
            '<!-- products -->',
            '<items>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a.name, category_a.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_1.name, product_1.list_price, self.kgm_uom.id, product_1.id),
            '<itemsuppliers>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_1.delay, seller_1.sequence, seller_1.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_1.id, supplier_1.name),
            '</itemsupplier>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_2.delay, seller_2.sequence, seller_2.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_2.id, supplier_2.name),
            '</itemsupplier>',
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

        category_a_sub = self._create_category('TC_Category_A_Sub', parent=category_a)
        product_a_sub_1 = self._create_product('TC_Product_A_Sub_1', category=category_a_sub, price=5)
        supplier_3, seller_3 = self._create_supplier_seller(
            'TC_Supplier_3', product=product_a_sub_1, priority=10, price=70, delay=30)
        supplier_4, seller_4 = self._create_supplier_seller(
            'TC_Supplier_4', product=product_a_sub_1, priority=20, price=130, delay=20)

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
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_1.delay, seller_1.sequence, seller_1.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_1.id, supplier_1.name),
            '</itemsupplier>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_2.delay, seller_2.sequence, seller_2.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_2.id, supplier_2.name),
            '</itemsupplier>',
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a_sub.name, category_a_sub.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_sub_1.name, product_a_sub_1.list_price, self.kgm_uom.id, product_a_sub_1.id),
            '<itemsuppliers>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_3.delay, seller_3.sequence, seller_3.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_3.id, supplier_3.name),
            '</itemsupplier>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_4.delay, seller_4.sequence, seller_4.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_4.id, supplier_4.name),
            '</itemsupplier>',
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
        self.assertTrue(True)

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

        category_a_sub = self._create_category('TC_Category_A_Sub', parent=category_a)
        product_a_sub_1 = self._create_product('TC_Product_A_Sub_1', category=category_a_sub, price=5)
        supplier_3, seller_3 = self._create_supplier_seller(
            'TC_Supplier_3', product=product_a_sub_1, priority=10, price=70, delay=30)
        supplier_4, seller_4 = self._create_supplier_seller(
            'TC_Supplier_4', product=product_a_sub_1, priority=20, price=130, delay=20)

        category_a_sub_sub = self._create_category('TC_Category_A_Sub_Sub', parent=category_a_sub)
        product_a_sub_sub_1 = self._create_product('TC_Product_A_Sub_Sub_1', category=category_a_sub_sub, price=7)
        supplier_5, seller_5 = self._create_supplier_seller(
            'TC_Supplier_5', product=product_a_sub_sub_1, priority=10, price=70, delay=30)
        product_a_sub_sub_2 = self._create_product('TC_Product_A_Sub_Sub_2', category=category_a_sub_sub, price=7)
        supplier_6, seller_6 = self._create_supplier_seller(
            'TC_Supplier_6', product=product_a_sub_sub_2, priority=20, price=130, delay=20)

        category_b = self._create_category('TC_Category_B')
        product_b_1 = self._create_product('TC_Product_B_1', category=category_b, price=5)
        supplier_7, seller_7 = self._create_supplier_seller(
            'TC_Supplier_7', product=product_b_1, priority=1, price=7, delay=3)

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
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_1.delay, seller_1.sequence, seller_1.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_1.id, supplier_1.name),
            '</itemsupplier>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_2.delay, seller_2.sequence, seller_2.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_2.id, supplier_2.name),
            '</itemsupplier>',
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a_sub.name, category_a_sub.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_sub_1.name, product_a_sub_1.list_price, self.kgm_uom.id, product_a_sub_1.id),
            '<itemsuppliers>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_3.delay, seller_3.sequence, seller_3.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_3.id, supplier_3.name),
            '</itemsupplier>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_4.delay, seller_4.sequence, seller_4.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_4.id, supplier_4.name),
            '</itemsupplier>',
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '<item name="{}" category="{}" description="category">'.format(
                category_a_sub_sub.name, category_a_sub_sub.id),
            '<members>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_sub_sub_1.name, product_a_sub_sub_1.list_price, self.kgm_uom.id, product_a_sub_sub_1.id),
            '<itemsuppliers>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_5.delay, seller_5.sequence, seller_5.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_5.id, supplier_5.name),
            '</itemsupplier>',
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '<item name="{}" cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
                product_a_sub_sub_2.name, product_a_sub_sub_2.list_price, self.kgm_uom.id, product_a_sub_sub_2.id),
            '<itemsuppliers>',
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_6.delay, seller_6.sequence, seller_6.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_6.id, supplier_6.name),
            '</itemsupplier>',
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
            '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
            'cost="{:0.6f}" location="{}">'.format(
                seller_7.delay, seller_7.sequence, seller_7.price, self.stock_location.complete_name),
            '<supplier name="{} {}"/>'.format(supplier_7.id, supplier_7.name),
            '</itemsupplier>',
            '</itemsuppliers>',
            '<stringproperty name="itemstatus" value="active"/>',
            '</item>',
            '</members>',
            '</item>',
            '</items>',
        ])
        self.assertEqual(xml_str_actual, xml_str_expected)
        self.assertTrue(True)

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
