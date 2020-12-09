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
        Will be used as an auxiliary class to craft some hierarchies in frePPLe.
    """
    def __init__(self, name, attrs=None, children=None, odoo_record=None):
        self.name = name
        self.attrs = attrs if attrs else {}
        self.children = children if children else deque()
        self.odoo_record = odoo_record if odoo_record else None

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
            tag[-1] += '>' if self.children else '/>'
            _list.append(' '.join(tag))

            # Prints the entities that are children of this one.
            for node in self.children:
                node.__to_list_xml(_list)

            # Prints the end of the entity.
            if self.children:
                _list.append('</{}>'.format(self.name))
