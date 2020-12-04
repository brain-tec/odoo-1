##############################################################################
# Copyright (c) 2020 brain-tec AG (https://bt-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from odoo.tests.common import TransactionCase
from odoo.addons.frepple.misc.tree import Node


class TestBase(TransactionCase):
    maxDiff = None

    def test_to_list_xml(self):
        """ Tests a tree encoding an XML-like structure.

            Structure to test is:
            <customers>
                <customer name="customer_1"/>
                <customer name="customer_2" owner="customer_1">
                    <attribute name="1"/>
                    <attribute name="2"/>
                </customer>
                <customer name="customer_3"/>
            </customers>
        """
        attr_1 = Node('attribute', attrs={'name': '1'})
        attr_2 = Node('attribute', attrs={'name': '2'})
        customer_2 = Node('customer', attrs={'name': 'customer_2', 'owner': 'customer_1'}, children=[attr_1, attr_2])
        customer_1 = Node('customer', attrs={'name': 'customer_1'})
        customer_3 = Node('customer', attrs={'name': 'customer_3'})
        customers = Node('customers', children=[customer_1, customer_2, customer_3])

        expected = [
            '<customers>',
            '<customer name="customer_1"/>',
            '<customer name="customer_2" owner="customer_1">',
            '<attribute name="1"/>',
            '<attribute name="2"/>',
            '</customer>',
            '<customer name="customer_3"/>',
            '</customers>',
        ]
        self.assertEqual(expected, customers.to_list_xml())

    def test_to_list_nodes(self):
        """ Tests that we can iterate over the nodes of a tree.

            Tree used here is:
                    A
                   / \
                  B   C
                     /|\
                    D E F
        """
        a = Node('a')
        b = Node('b')
        c = Node('c')
        d = Node('d')
        e = Node('e')
        f = Node('f')
        c.children.extend([d, e, f])
        a.children.extend([b, c])
        self.assertEqual([a, b, c, d, e, f], a.to_list_nodes())
