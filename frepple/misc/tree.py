##############################################################################
# Copyright (c) 2020 brain-tec AG (https://bt-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from xml.sax.saxutils import quoteattr
from collections import deque


class Node:
    """ This implements an easy tree-like structure with n-children
        Will be used as an auxiliary class to craft some hierarchies in frePPLe,
        so a node represents an XML entity (see details in the constructor).
    """
    def __init__(self, name, attrs=None, children=None, odoo_record=None, owner=None):
        """
        :param name: The name of the XML-tag, e.g. <customer>, <product>, etc.
        :param attrs: A dictionary storing the attributes of the XML-tag.
        :param children: The deque of Nodes that are children of this Node.
        :param odoo_record: Odoo's record (just one) which is represented by the XML-tag.
        :param owner: An owner is a node that is inside a tag <owner> and that only prints
                      its attribute 'name', not any other attribute, e.g.

                          n1 = Node('n', attrs={'name': 'n1', 'a': 1})
                          n2 = Node('n', attrs='{'name': 'n2', 'b': 2}, owner=n1)

                      '\n'.join(n2.to_list_xml()) will render as

                          <n2 name="n2" b="2">
                          <owner name="n1"/>
                          </n2>
        """
        self.name = name
        self.attrs = attrs if attrs else {}
        self.children = children if children else deque()
        self.odoo_record = odoo_record if odoo_record else None
        self.owner = owner if owner else None

        if self.owner and 'name' not in self.owner.attrs:
            raise ValueError('A tree that is set as owner must have an attribute "name"')

    def __str__(self):
        attrs_str = ' '.join(['{}={};'.format(k, v) for k, v in self.attrs.items()])
        children_str = '' if not self.children else '(children: {})'.format(len(self.children))
        return '<{}> {}{}'.format(self.name, attrs_str, children_str)

    def to_list_nodes(self):
        _list = []
        self.__to_list_nodes(_list)
        return _list

    def __to_list_nodes(self, _list):
        if self:
            _list.append(self)
            for node in self.children:
                node.__to_list_nodes(_list)

    def to_list_xml(self):
        _list = []
        self.__to_list_xml(_list)
        return _list

    def __to_list_xml(self, _list):
        if self:
            # Prints the start of the entity.
            tag = ['<{}'.format(self.name)]
            if self.attrs:
                tag.append(' '.join(['{}={}'.format(k, quoteattr(v)) for k, v in sorted(self.attrs.items())]))
            tag[-1] += '>' if (self.children or self.owner) else '/>'
            _list.append(' '.join(tag))

            # Prints the owner, if any.
            if self.owner:
                _list.append('<owner name={}/>'.format(quoteattr(self.owner.attrs.get('name', ''))))

            # Prints the entities that are children of this one.
            for node in self.children:
                node.__to_list_xml(_list)

            # Prints the end of the entity.
            if self.children or self.owner:
                _list.append('</{}>'.format(self.name))
