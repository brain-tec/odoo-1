# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 by frePPLe bv
# Copyright (c) 2020 brain-tec AG (https://braintec-group.com)
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import logging
from xml.sax.saxutils import quoteattr
from datetime import datetime, timedelta
from operator import itemgetter

import ast

logger = logging.getLogger(__name__)


class exporter(object):
    def __init__(self, req, uid, database=None, company=None, mode=1):
        self.database = database
        self.company = company

        # The mode argument defines different types of runs:
        #  - Mode 1:
        #    This mode returns all data that is loaded with every planning run.
        #    Currently this mode transfers all objects, except closed sales orders.
        #  - Mode 2:
        #    This mode returns data that is loaded that changes infrequently and
        #    can be transferred during automated scheduled runs at a quiet moment.
        #    Currently this mode transfers only closed sales orders.
        #
        # Normally an Odoo object should be exported by only a single mode.
        # Exporting a certain object with BOTH modes 1 and 2 will only create extra
        # processing time for the connector without adding any benefits. On the other
        # hand it won't break things either.
        #
        # Which data elements belong to each mode can vary between implementations.
        self.mode = mode

        # Initialize an environment
        self.env = req.env

    def run(self):
        # Check if we manage by work orders or manufacturing orders.
        self.manage_work_orders = False
        m = self.env["ir.model"]
        recs = m.search([("model", "=", "mrp.workorder")])
        for rec in recs:
            self.manage_work_orders = True

        # Load some auxiliary data in memory
        self.load_company()
        self.load_uom()

        # Header.
        # The source attribute is set to 'odoo_<mode>', such that all objects created or
        # updated from the data are also marked as from originating from odoo.
        yield '<?xml version="1.0" encoding="UTF-8" ?>\n'
        yield '<plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" source="odoo_%s">\n' % self.mode

        # Main content.
        # The order of the entities is important. First one needs to create the
        # objects before they are referenced by other objects.
        # If multiple types of an entity exists (eg operation_time_per,
        # operation_alternate, operation_alternate, etc) the reference would
        # automatically create an object, potentially of the wrong type.
        if self.mode == 1:
            for i in self.export_calendar():
                yield i
        for i in self.export_locations():
            yield i
        for i in self.export_customers():
            yield i
        if self.mode == 1:
            for i in self.export_suppliers():
                yield i
            for i in self.export_workcenters():
                yield i
        for i in self.export_items():
            yield i
        if self.mode == 1:
            for i in self.export_boms():
                yield i
        for i in self.export_salesorders():
            yield i
        if self.mode == 1:
            for i in self.export_purchaseorders():
                yield i
            for i in self.export_manufacturingorders():
                yield i
            for i in self.export_orderpoints():
                yield i
            for i in self.export_onhand():
                yield i
            yield self.export_move_lines()
            yield self.export_stock_rules()

        # Footer
        yield "</plan>\n"

    def load_company(self):
        m = self.env["res.company"]
        recs = m.search([("name", "=", self.company)])
        fields = [
            "security_lead",
            "po_lead",
            "manufacturing_lead",
            "calendar",
            "manufacturing_warehouse",
        ]
        self.company_id = 0
        for i in recs.read(fields):
            self.company_id = i["id"]
            self.security_lead = int(
                i["security_lead"]
            )  # TODO NOT USED RIGHT NOW - add parameter in frepple for this
            self.po_lead = i["po_lead"]
            self.manufacturing_lead = i["manufacturing_lead"]
            self.calendar = i["calendar"] and i["calendar"][1] or "Working hours"
            self.mfg_location = (
                i["manufacturing_warehouse"]
                and i["manufacturing_warehouse"][1]
                or self.company
            )
        if not self.company_id:
            logger.warning("Can't find company '%s'" % self.company)
            self.company_id = None
            self.security_lead = 0
            self.po_lead = 0
            self.manufacturing_lead = 0
            self.calendar = "Working hours"
            self.mfg_location = self.company

    def load_uom(self):
        """
        Loading units of measures into a dictinary for fast lookups.

        All quantities are sent to frePPLe as numbers, expressed in the default
        unit of measure of the uom dimension.
        """
        m = self.env["uom.uom"]
        # We also need to load INactive UOMs, because there still might be records
        # using the inactive UOM. Questionable practice, but can happen...
        recs = m.search(["|", ("active", "=", 1), ("active", "=", 0)])
        fields = ["factor", "uom_type", "category_id", "name"]
        self.uom = {}
        self.uom_categories = {}
        for i in recs.read(fields):
            if i["uom_type"] == "reference":
                f = 1.0
                self.uom_categories[i["category_id"][0]] = i["id"]
            elif i["uom_type"] == "bigger":
                f = i["factor"]
            else:
                if i["factor"] > 0:
                    f = 1 / i["factor"]
                else:
                    f = 1.0
            self.uom[i["id"]] = {
                "factor": f,
                "category": i["category_id"][0],
                "name": i["name"],
            }

    def convert_qty_uom(self, qty, uom_id, product_id=None):
        """
        Convert a quantity to the reference uom of the product.
        The default implementation doesn't consider the product at all, and just
        converts to the reference unit of the uom category.
        """
        if not uom_id:
            return qty
        return qty * self.uom[uom_id]["factor"]

    def convert_float_time(self, float_time):
        """
        Convert Odoo float time to ISO 8601 duration.
        """
        return "PT%dH%dM%dS" % (
            int(float_time),  # duration: hours
            int((float_time*60) % 60),  # duration: minutes
            int((float_time*3600) % 60 % 60),  # duration: seconds
        )

    def _frepple_generate_common_fields_xml(self, odoo_record):
        """ Calls a method from the ORM that returns triplets used to create
            the XML for the common_fields. This is a Python class, that had to
            be monkey-patched; we call the method in the ORM to allow a regular
            Odoo-inheritance from other modules, while keeping the generation
            of the XML untouched.
        """
        xml_str = []
        for field_type, field_name, field_value in odoo_record._frepple_get_common_fields():
            xml_str.append('<{} name="{}" value={}/>'.format(
                field_type, field_name, quoteattr(field_value)))
        return xml_str

    def export_calendar(self):
        """
        Build a calendar with a) holidays and b) working hours.

        The holidays are obtained from the hr.holidays.public.line model.
        If the hr module isn't installed, no public holidays will be defined.

        The working hours are extracted from a resource.calendar model.
        The calendar to use is configured with the company parameter "calendar".
        If left unspecified we assume 24*7 working hours.

        The odoo model is not ideal and nice for frePPLe, and the current mapping
        is an as-good-as-it-gets workaround.

        Mapping:
        res.company.calendar  -> calendar.name
        (if no working hours are defined then 1 else 0) -> calendar.default_value

        resource.calendar.attendance.date_from -> calendar_bucket.start
        '1' -> calendar_bucket.value
        resource.calendar.attendance.dayofweek -> calendar_bucket.days
        resource.calendar.attendance.hour_from -> calendar_bucket.startime
        resource.calendar.attendance.hour_to -> calendar_bucket.endtime
        computed -> calendar_bucket.priority

        hr.holidays.public.line.start -> calendar_bucket.start
        hr.holidays.public.line.start + 1 day -> calendar_bucket.end
        '0' -> calendar_bucket.value
        '1' -> calendar_bucket.priority
        """
        yield "<!-- calendar -->\n"
        yield "<calendars>\n"
        try:
            m = self.env["resource.calendar"]
            recs = m.search([("name", "=", self.calendar)])
            rec = recs.read(["attendance_ids"], limit=1)
            fields = ["dayofweek", "date_from", "hour_from", "hour_to"]
            buckets = []
            for i in rec["attendance_ids"].read(fields):
                strt = datetime.strptime(i["date_from"] or "2000-01-01", "%Y-%m-%d")
                buckets.append(
                    (
                        strt,
                        '<bucket start="%sT00:00:00" value="1" days="%s" priority="%%s" starttime="%s" endtime="%s"/>\n'
                        % (
                            strt.strftime("%Y-%m-%d"),
                            2 ** ((int(i["dayofweek"]) + 1) % 7),
                            # In odoo, monday = 0. In frePPLe, sunday = 0.
                            "PT%dM" % round(i["hour_from"] * 60),
                            "PT%dM" % round(i["hour_to"] * 60),
                        ),
                    )
                )
            if len(buckets) > 0:
                # Sort by start date.
                # Required to assure that records with a later start date get a
                # lower priority in frePPLe.
                buckets.sort(key=itemgetter(0))
                priority = 1000
                yield '<calendar name=%s default="0"><buckets>\n' % quoteattr(
                    self.calendar
                )
                for i in buckets:
                    yield i[1] % priority
                    priority -= 1
            else:
                # No entries. We'll assume 24*7 availability.
                yield '<calendar name=%s default="1"><buckets>\n' % quoteattr(
                    self.calendar
                )
        except Exception:
            # Exception happens if the resource module isn't installed.
            yield "<!-- Working hours are assumed to be 24*7. -->\n"
            yield '<calendar name=%s default="1"><buckets>\n' % quoteattr(self.calendar)
        try:
            m = self.env["hr.holidays.public.line"]
            recs = m.search([])
            fields = ["date"]
            for i in recs.read(fields):
                nd = datetime.strptime(i["date"], "%Y-%m-%d") + timedelta(days=1)
                yield '<bucket start="%sT00:00:00" end="%sT00:00:00" value="0" priority="1"/>\n' % (
                    i["date"],
                    nd.strftime("%Y-%m-%d"),
                )
        except Exception:
            # Exception happens if the hr module is not installed
            yield "<!-- No holidays since the HR module is not installed -->\n"
        yield "</buckets></calendar></calendars>\n"

    def _generate_locations_from_location_xml(self, warehouse, location, ctx=None):
        ctx = ctx if ctx else {}
        prefix_location = ctx.get('test_prefix', '') if 'test_export_locations' in ctx else ''

        xml_str = []
        if location and location.name.startswith(prefix_location):
            # Original frePPLe stored the warehouse's name, we store the location's complete name
            self.map_locations[location.id] = location.complete_name
            xml_str.extend([
                '<location name={} subcategory="{}" description="location">'.format(
                    quoteattr(location.complete_name), location.id),
                '<available name={}/>'.format(quoteattr(self.calendar)),
            ])

            children_locations = self.env['stock.location'].search([
                ('location_id', '=', location.id),  # The 'parent_id' field, named here 'location_id'.
            ])
            if 'test_export_locations' in ctx:
                children_locations = children_locations.filtered(
                    lambda warehouse: warehouse.name.startswith(ctx['test_prefix']))

            if children_locations:
                xml_str.append('<members>')
                for child_location in children_locations:
                    xml_str.extend(self._generate_locations_from_location_xml(warehouse, child_location, ctx=ctx))
                xml_str.append('</members>')

            xml_str.append('</location>')
        return xml_str

    def _generate_locations_from_warehouse_xml(self, warehouse, ctx=None):
        """ This assumes a location belongs to only one warehouse.
            Returns the hierarchical xml structure for it.
        """
        ctx = ctx if ctx else {}

        xml_str = ['<members>']

        for location in [
            warehouse.wh_input_stock_loc_id,
            warehouse.wh_output_stock_loc_id,
            warehouse.wh_pack_stock_loc_id,
            warehouse.wh_qc_stock_loc_id,
            warehouse.view_location_id,
        ]:
            xml_str.extend(self._generate_locations_from_location_xml(warehouse, location, ctx=ctx))

        xml_str.append('</members>')
        return xml_str

    def _export_warehouses(self, warehouses, ctx=None):
        ctx = ctx if ctx else {}

        xml_str = []

        for warehouse in warehouses:
            self.warehouses.add(warehouse.name)

            xml_str.extend([
                '<location name={} subcategory="{}" description="warehouse">'.format(
                    quoteattr(warehouse.name), warehouse.id),
                '<available name={}/>'.format(quoteattr(self.calendar)),
            ])
            xml_str.extend(self._generate_locations_from_warehouse_xml(warehouse, ctx=ctx))
            xml_str.append('</location>')

        return xml_str

    def export_locations(self, ctx=None):
        """
        Generate a list of warehouse locations to frePPLe, based on the
        stock.warehouse model.

        We assume the location name to be unique. This is NOT guarantueed by Odoo.

        The field subategory is used to store the id of the warehouse. This makes
        it easier for frePPLe to send back planning results directly with an
        odoo location identifier.

        FrePPLe is not interested in the locations odoo defines with a warehouse.
        This methods also populates a map dictionary between these locations and
        warehouse they belong to.

        Mapping:
        stock.warehouse.name -> location.name
        stock.warehouse.id -> location.subcategory

        Provides a hierarchy of locations using the <members>. Other consideration is:
        locations were used for warehouses, not for locations. To differentiate,
        The common_attributes/description is used, with either 'warehouse' or 'location'.

        The optional context (ctx) is to test easily.
        """
        ctx = ctx if ctx else {}
        self.map_locations = {}
        self.warehouses = set()

        warehouses = self.env['stock.warehouse'].search([], order='id')
        if 'test_export_locations' in ctx:
            warehouses = warehouses.filtered(lambda warehouse: warehouse.name.startswith(ctx['test_prefix']))

        xml_str = [
            '<!-- warehouses -->',
            '<locations>',
        ]
        xml_str.extend(self._export_warehouses(warehouses, ctx=ctx))
        xml_str.append('</locations>')
        return '\n'.join(xml_str)

    def _export_customers(self, customers):
        """ Auxiliary method to export the customers.
            If partner_affiliates is installed, the field affiliate_ids will be
            inside the res.partner, so we use it.
        """
        xml_str = []
        if customers:
            for customer in customers:
                customer_name = '{} {}'.format(customer.id, customer.name)
                common_fields = self._frepple_generate_common_fields_xml(customer)
                if common_fields:
                    xml_str.append('<customer name={}>'.format(quoteattr(customer_name)))
                    xml_str.extend(common_fields)
                    xml_str.append('</customer>')
                else:
                    xml_str.append('<customer name={}/>'.format(quoteattr(customer_name)))
        return xml_str

    def export_customers(self, ctx=None):
        """
        Generate a list of customers to frePPLe, based on the res.partner model.
        We filter on res.partner where customer = True.

        Mapping:
        res.partner.id res.partner.name -> customer.name

        Implements a hierarchy for customers using <members>.

        The optional context (ctx) is to test easily.
        """
        if ctx is None:
            ctx = {}

        customers = self.env['res.partner'].search([
            ('customer_rank', '>', 0),
            ('parent_id', '=', False),
        ], order='id')
        if 'test_export_customers' in ctx:
            customers = customers.filtered(lambda customer: customer.name.startswith(ctx['test_prefix']))

        xml_str = [
            '<!-- customers -->',
            '<customers>',
        ]
        xml_str.extend(self._export_customers(customers))
        xml_str.append('</customers>')
        return '\n'.join(xml_str)

    def export_suppliers(self):
        """
        Generate a list of suppliers for frePPLe, based on the res.partner model.
        We filter on res.supplier where supplier = True.

        Mapping:
        res.partner.id res.partner.name -> supplier.name
        """
        m = self.env["res.partner"]
        recs = m.search([("is_company", "=", True), ("supplier_rank", ">", 0)])
        if recs:
            yield "<!-- suppliers -->\n"
            yield "<suppliers>\n"
            fields = ["name"]
            for i in recs.read(fields):
                yield "<supplier name=%s/>\n" % quoteattr(
                    "%d %s" % (i["id"], i["name"])
                )
            yield "</suppliers>\n"

    def export_workcenters(self):
        """
        Send the workcenter list to frePPLe, based one the mrp.workcenter model.

        We assume the workcenter name is unique. Odoo does NOT guarantuee that.

        Mapping:
        mrp.workcenter.name -> resource.name
        mrp.workcenter.costs_hour -> resource.cost
        mrp.workcenter.capacity_per_cycle / mrp.workcenter.time_cycle -> resource.maximum
        company.mfg_location -> resource.location
        """
        self.map_workcenters = {}
        m = self.env["mrp.workcenter"]
        recs = m.search([])
        fields = ["name"]
        if recs:
            yield "<!-- workcenters -->\n"
            yield "<resources>\n"
            for i in recs.read(fields):
                name = i["name"]
                self.map_workcenters[i["id"]] = name
                yield '<resource name=%s maximum="%s"><location name=%s/></resource>\n' % (
                    quoteattr(name),
                    1,
                    quoteattr(self.mfg_location),
                )
            yield "</resources>\n"

    def export_items(self, ctx=None):
        """
        Send the list of products to frePPLe, based on the product.product model.
        For purchased items we also create a procurement buffer in each warehouse.

        Mapping:
        [product.product.code] product.product.name -> item.name
        product.product.product_tmpl_id.list_price -> item.cost
        product.product.id , product.product.product_tmpl_id.uom_id -> item.subcategory

        If product.product.product_tmpl_id.purchase_ok
        and product.product.product_tmpl_id.routes contains the buy route
        we collect the suppliers as product.product.product_tmpl_id.seller_ids
        [product.product.code] product.product.name -> itemsupplier.item
        res.partner.id res.partner.name -> itemsupplier.supplier.name
        supplierinfo.delay -> itemsupplier.leadtime
        supplierinfo.min_qty -> itemsupplier.size_minimum
        supplierinfo.date_start -> itemsupplier.effective_start
        supplierinfo.date_end -> itemsupplier.effective_end
        product.product.product_tmpl_id.delay -> itemsupplier.leadtime
        '1' -> itemsupplier.priority

        Using the <members> I create a hierarchy of categories/products, first the
        products of the parent category, then their sub-categories.
        """
        ctx = ctx if ctx else {}

        xml_str = []

        # To ease testing, we alter the domain of the records we retrieve
        # depending on a flag set in the context.
        if 'test_export_items' in ctx:
            search_domain_products = [('name', 'like', '{}%'.format(ctx['test_prefix']))]
            search_domain_templates = [('name', 'like', '{}%'.format(ctx['test_prefix']))]
            search_domain_suppliers = [('name.name', 'like', '{}%'.format(ctx['test_prefix']))]
            search_domain_product_categories = [('name', 'like', '{}%'.format(ctx['test_prefix']))]
        else:
            search_domain_products = []
            search_domain_templates = []
            search_domain_suppliers = []
            search_domain_product_categories = []

        # We fill in the attributes the original method filled in.
        # I keep them here because the original code defines and fills them ─ only because of that.
        # The original code also loaded the location routes, that used for nothing, thus
        # I don't load them...
        self.product_product = dict()
        self.product_template_product = dict()
        self.product_supplier = dict()
        self.product_templates = dict()
        for product in self.env['product.product'].with_context(active_test=False).search(search_domain_products):
            product_template_id = product.product_tmpl_id.id
            product_data = {'name': product.name, 'template': product_template_id}
            self.product_product[product.id] = product_data
            self.product_template_product[product.product_tmpl_id.id] = product_data
        for supplier in self.env['product.supplierinfo'].with_context(active_test=False).search(search_domain_suppliers):
            self.product_supplier.setdefault(supplier.product_tmpl_id.id, []).append(
                (supplier.name, supplier.delay, supplier.min_qty, supplier.date_end,
                 supplier.date_start, supplier.price, supplier.sequence))
        for product_template in self.env['product.template'].with_context(active_test=False).search_read(
                search_domain_templates, ['purchase_ok', 'route_ids', 'bom_ids', 'produce_delay',
                                          'list_price', 'uom_id', 'seller_ids', 'standard_price']):
            self.product_templates[product_template['id']] = product_template

        # Now we generate the XML.
        xml_str.append('<!-- products -->')
        xml_str.append('<items>')

        top_categories = self.env['product.category'].search(
            [('parent_id', '=', False)] + search_domain_product_categories, order='name,id')
        for top_category in top_categories:
            xml_str.extend(self._generate_category_xml(
                top_category, search_domain_product_categories, search_domain_products, search_domain_suppliers))

        xml_str.append('</items>')
        return '\n'.join(xml_str)

    def _generate_category_xml(
            self, category, search_domain_categories, search_domain_products, search_domain_suppliers):
        xml_str = ['<item name={} category="{}" description="category">'.format(
            quoteattr(category.name), category.id)]
        products = self.env['product.product'].with_context(active_test=False).search(
            [('product_tmpl_id.categ_id', '=', category.id)] + search_domain_products, order='id')
        subcategories = self.env['product.category'].search(
            [('parent_id', '=', category.id)] + search_domain_categories, order='name, id')

        if products or subcategories:
            xml_str.append('<members>')
            for product in products:
                xml_str.extend(self._generate_product_xml(
                    product, search_domain_suppliers))
            for subcategory in subcategories:
                xml_str.extend(self._generate_category_xml(
                    subcategory, search_domain_categories, search_domain_products, search_domain_suppliers))
            xml_str.append('</members>')

        xml_str.append('</item>')
        return xml_str

    def _generate_product_xml(self, product, search_domain_suppliers):
        # The subcategory attribute in an <item> stores, separated by a comma, the ID of the
        # UOM used as the reference for the category of the UOM set on the product's template,
        # and then the product's ID. ò_Ó
        ref_uom_for_uom_category_id = self.uom_categories[self.uom[product.product_tmpl_id.uom_id.id]['category']]
        xml_str = ['<item name={} cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
            quoteattr(product.name), product.list_price, ref_uom_for_uom_category_id, product.id)]

        suppliers = self.env['product.supplierinfo'].search([
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
        ] + search_domain_suppliers, order='id')
        for supplier_no, supplier in enumerate(suppliers):
            if supplier_no == 0:
                xml_str.append('<itemsuppliers>')

            seller = supplier.name
            supplier_name = "{} {}".format(seller.id, seller.name)
            xml_str.extend([
                '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="0.000000" '
                'cost="{:0.6f}">'.format(
                    supplier.delay, supplier.sequence, supplier.price),
                '<supplier name={}/>'.format(quoteattr(supplier_name)),
                '</itemsupplier>',
            ])

            if supplier_no == len(suppliers) - 1:
                xml_str.append('</itemsuppliers>')

        xml_str.extend(self._frepple_generate_common_fields_xml(product))
        xml_str.append('</item>')
        return xml_str

    def export_boms(self):
        """
        Exports mrp.routings, mrp.routing.workcenter and mrp.bom records into
        frePPLe operations, flows and loads.

        Not supported yet: a) parent boms, b) phantom boms.
        """
        yield "<!-- bills of material -->\n"
        yield "<operations>\n"
        self.operations = set()

        # Read all active manufacturing routings
        mrp_routings = {}
        # m = self.env["mrp.routing"]
        # recs = m.search([])
        # fields = ["location_id"]
        # for i in recs.read(fields):
        #    mrp_routings[i["id"]] = i["location_id"]

        # Read all workcenters of all routings
        mrp_routing_workcenters = {}
        m = self.env["mrp.routing.workcenter"]
        recs = m.search([], order="routing_id, sequence asc")
        fields = ["name", "routing_id", "workcenter_id", "sequence", "time_cycle"]
        for i in recs.read(fields):
            if i["routing_id"][0] in mrp_routing_workcenters:
                # If the same workcenter is used multiple times in a routing,
                # we add the times together.
                exists = False
                if not self.manage_work_orders:
                    for r in mrp_routing_workcenters[i["routing_id"][0]]:
                        if r[0] == i["workcenter_id"][1]:
                            r[1] += i["time_cycle"]
                            exists = True
                            break
                if not exists:
                    mrp_routing_workcenters[i["routing_id"][0]].append(
                        [
                            i["workcenter_id"][1],
                            i["time_cycle"],
                            i["sequence"],
                            i["name"],
                        ]
                    )
            else:
                mrp_routing_workcenters[i["routing_id"][0]] = [
                    [i["workcenter_id"][1], i["time_cycle"], i["sequence"], i["name"]]
                ]

        # Models used in the bom-loop below
        bom_lines_model = self.env["mrp.bom.line"]
        bom_lines_fields = ["product_qty", "product_uom_id", "product_id", "routing_id"]
        try:
            subproduct_model = self.env["mrp.subproduct"]
            subproduct_fields = [
                "product_id",
                "product_qty",
                "product_uom",
                "subproduct_type",
            ]
        except Exception:
            subproduct_model = None

        # The mrp.routing is not mandatory in Odoo for an mrp.bom,
        # but is required by frePPLe when exporting an mrp.bom, thus
        # we use the dummy one defined in the company if none is
        # indicated.
        company = self.env['res.company'].browse(self.company_id)
        dummy_mrp_route = company.frepple_bom_dummy_route_id
        dummy_mrp_route_m2o_read = (dummy_mrp_route.id, dummy_mrp_route.name)

        # Loop over all bom records
        bom_recs = self.env["mrp.bom"].search([])
        bom_fields = [
            "product_qty",
            "product_uom_id",
            "product_tmpl_id",
            "routing_id",
            "type",
            "bom_line_ids",
        ]
        for i in bom_recs.read(bom_fields):
            if not i['routing_id']:
                i['routing_id'] = dummy_mrp_route_m2o_read

            # Determine the location
            if i["routing_id"]:
                location = mrp_routings.get(i["routing_id"][0], None)
                if not location:
                    location = self.mfg_location
                else:
                    location = location[1]
            else:
                location = self.mfg_location

            # Determine operation name and item
            product_buf = self.product_template_product.get(
                i["product_tmpl_id"][0], None
            )  # TODO avoid multiple bom on single template
            if not product_buf:
                logger.warn(
                    "skipping %s %s" % (i["product_tmpl_id"][0], i["routing_id"])
                )
                continue
            uom_factor = self.convert_qty_uom(
                1.0, i["product_uom_id"][0], i["product_tmpl_id"][0]
            )
            operation = u"%d %s @ %s" % (i["id"], product_buf["name"], location)
            self.operations.add(operation)

            # Build operation. The operation can either be a summary operation or a detailed
            # routing.
            if (
                not self.manage_work_orders
                or not i["routing_id"]
                or not mrp_routing_workcenters.get(i["routing_id"][0], [])
            ):
                #
                # CASE 1: A single operation used for the BOM
                # All routing steps are collapsed in a single operation.
                #
                yield '<operation name=%s size_multiple="1" duration="%s" posttime="P%dD" xsi:type="operation_fixed_time">\n' "<item name=%s/><location name=%s/>\n" % (
                    quoteattr(operation),
                    self.convert_float_time(
                        self.product_templates[i["product_tmpl_id"][0]]["produce_delay"]
                    ),
                    self.manufacturing_lead,
                    quoteattr(product_buf["name"]),
                    quoteattr(location),
                )
                yield '<flows>\n<flow xsi:type="flow_end" quantity="%f"><item name=%s/></flow>\n' % (
                    i["product_qty"] * uom_factor,
                    quoteattr(product_buf["name"]),
                )

                # Build consuming flows.
                # If the same component is consumed multiple times in the same BOM
                # we sum up all quantities in a single flow. We assume all of them
                # have the same effectivity.
                fl = {}
                for j in bom_lines_model.browse(i["bom_line_ids"]).read(
                    bom_lines_fields
                ):
                    product = self.product_product.get(j["product_id"][0], None)
                    if not product:
                        continue
                    if j["product_id"][0] in fl:
                        fl[j["product_id"][0]].append(j)
                    else:
                        fl[j["product_id"][0]] = [j]
                for j in fl:
                    product = self.product_product[j]
                    qty = sum(
                        self.convert_qty_uom(
                            k["product_qty"], k["product_uom_id"][0], k["product_id"][0]
                        )
                        for k in fl[j]
                    )
                    yield '<flow xsi:type="flow_start" quantity="-%f"><item name=%s/></flow>\n' % (
                        qty,
                        quoteattr(product["name"]),
                    )

                # Build byproduct flows
                if i.get("sub_products", None) and subproduct_model:
                    for j in subproduct_model.browse(i["sub_products"]).read(
                        subproduct_fields
                    ):
                        product = self.product_product.get(j["product_id"][0], None)
                        if not product:
                            continue
                        yield '<flow xsi:type="%s" quantity="%f"><item name=%s/></flow>\n' % (
                            "flow_fixed_end"
                            if j["subproduct_type"] == "fixed"
                            else "flow_end",
                            self.convert_qty_uom(
                                j["product_qty"],
                                j["product_uom"][0],
                                j["product_id"][0],
                            ),
                            quoteattr(product["name"]),
                        )
                yield "</flows>\n"

                # Create loads
                if i["routing_id"]:
                    yield "<loads>\n"
                    for j in mrp_routing_workcenters.get(i["routing_id"][0], []):
                        yield '<load quantity="%f"><resource name=%s/></load>\n' % (
                            j[1],
                            quoteattr(j[0]),
                        )
                    yield "</loads>\n"
            else:
                #
                # CASE 2: A routing operation is created with a suboperation for each
                # routing step.
                #
                yield '<operation name=%s size_multiple="1" posttime="P%dD" xsi:type="operation_routing">' "<item name=%s/><location name=%s/>\n" % (
                    quoteattr(operation),
                    self.manufacturing_lead,
                    quoteattr(product_buf["name"]),
                    quoteattr(location),
                )

                yield "<suboperations>"
                steplist = mrp_routing_workcenters[i["routing_id"][0]]
                # sequence cannot be trusted in odoo12
                counter = 0
                for step in steplist:
                    counter = counter + 1
                    suboperation = step[3]
                    yield "<suboperation>" '<operation name=%s priority="%s" duration="%s" xsi:type="operation_fixed_time">\n' "<location name=%s/>\n" '<loads><load quantity="%f"><resource name=%s/></load></loads>\n' % (
                        quoteattr(
                            "%s - %s - %s" % (operation, suboperation, (counter * 100))
                        ),
                        counter * 10,
                        self.convert_float_time(step[1]),
                        quoteattr(location),
                        1,
                        quoteattr(step[0]),
                    )
                    if step[2] == steplist[-1][2]:
                        # Add producing flows on the last routing step
                        yield '<flows>\n<flow xsi:type="flow_end" quantity="%f"><item name=%s/></flow>\n' % (
                            i["product_qty"]
                            * getattr(i, "product_efficiency", 1.0)
                            * uom_factor,
                            quoteattr(product_buf["name"]),
                        )
                        yield "</flows>\n"
                    if step[2] == steplist[0][2]:
                        # All consuming flows on the first routing step.
                        # If the same component is consumed multiple times in the same BOM
                        # we sum up all quantities in a single flow. We assume all of them
                        # have the same effectivity.
                        fl = {}
                        for j in bom_lines_model.browse(i["bom_line_ids"]).read(
                            bom_lines_fields
                        ):
                            product = self.product_product.get(j["product_id"][0], None)
                            if not product:
                                continue
                            if j["product_id"][0] in fl:
                                fl[j["product_id"][0]].append(j)
                            else:
                                fl[j["product_id"][0]] = [j]
                        yield "<flows>\n"
                        for j in fl:
                            product = self.product_product[j]
                            qty = sum(
                                self.convert_qty_uom(
                                    k["product_qty"],
                                    k["product_uom_id"][0],
                                    k["product_id"][0],
                                )
                                for k in fl[j]
                            )
                            yield '<flow xsi:type="flow_start" quantity="-%f"><item name=%s/></flow>\n' % (
                                qty,
                                quoteattr(product["name"]),
                            )
                        yield "</flows>\n"
                    yield "</operation></suboperation>\n"
                yield "</suboperations>\n"
            yield "</operation>\n"
        yield "</operations>\n"

    def export_salesorders(self, ctx=None):
        """
        if ctx is None:
            ctx = {}

        xml_str = []

        Only orders in the status 'draft' and 'sale' are extracted.

        The picking policy 'complete' is supported at the sales order line
        level only in frePPLe. FrePPLe doesn't allow yet to coordinate the
        delivery of multiple lines in a sales order (except with hacky
        modeling construct).
        The field requested_date is only available when sale_order_dates is
        installed.

        Mapping:
        sale.order.name ' ' sale.order.line.id -> demand.name
        sales.order.requested_date -> demand.due
        '1' -> demand.priority
        [product.product.code] product.product.name -> demand.item
        sale.order.partner_id.name -> demand.customer
        convert sale.order.line.product_uom_qty and sale.order.line.product_uom  -> demand.quantity
        stock.warehouse.name -> demand->location
        (if sale.order.picking_policy = 'one' then same as demand.quantity else 1) -> demand.minshipment
        """
        if ctx is None:
            ctx = {}

        xml_str = []

        # Get all sales order lines
        so_lines_datas = self.env['sale.order.line'].search_read(
            ast.literal_eval(self.env.user.company_id.sol_domain),
            ['qty_delivered', 'state', 'product_id', 'product_uom_qty', 'product_uom', 'order_id'],
            order='order_id, id')

        if 'test_export_salesorders' in ctx:
            filtered_so_lines_datas = []
            for so_line_data in so_lines_datas:
                sale_order = self.env['sale.order'].browse(so_line_data['order_id'][0])
                if sale_order.partner_id.name.startswith(ctx['test_prefix']):
                    filtered_so_lines_datas.append(so_line_data)
            so_lines_datas = filtered_so_lines_datas

        # Generate the demand records
        xml_str.append('<!-- sales order lines -->')
        xml_str.append('<demands>')

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

            qty = self.convert_qty_uom(
                product_uom_qty,
                so_line_data['product_uom'][0],
                so_line_data['product_id'][0]
            )

            name = '%s %d' % (sale_order.name, so_line_data['id'])
            product = self.product_product.get(so_line_data['product_id'][0], None)
            location = sale_order.warehouse_id.name
            customer_name = self._get_customer_name_for_demands(sale_order)
            due = getattr(sale_order, 'requested_date', False) or sale_order.date_order

            xml_str.extend([
                '<demand name={} quantity="{}" due="{}" priority="1" '
                'minshipment="{}" description="status={}">'.format(
                    quoteattr(name), qty, due.strftime('%Y-%m-%dT%H:%M:%S'),
                    sale_order.picking_policy == 'one' and qty or 1.0, frepple_status,
                ),
                '<item name={}/>'.format(quoteattr(product['name'])),
                '<customer name={}/>'.format(quoteattr(customer_name)),
                '<location name={}/>'.format(quoteattr(location)),
            ])
            xml_str.extend(self._frepple_generate_common_fields_xml(so_line))
            xml_str.append('</demand>')

        xml_str.append('</demands>')
        return '\n'.join(xml_str)

    def _get_customer_name_for_demands(self, sale_order):
        """ Returns the name of a customer in a <demand> item.
        """
        return '{} {}'.format(sale_order.partner_id.id, sale_order.partner_id.name)

    def export_purchaseorders(self):
        """
        Send all open purchase orders to frePPLe, using the purchase.order and
        purchase.order.line models.

        Only purchase order lines in state 'confirmed' are extracted. The state of the
        purchase order header must be "approved".

        Mapping:
        purchase.order.line.product_id -> operationplan.item
        purchase.order.company.mfg_location -> operationplan.location
        purchase.order.partner_id -> operationplan.supplier
        convert purchase.order.line.product_uom_qty - purchase.order.line.qty_received and purchase.order.line.product_uom -> operationplan.quantity
        purchase.order.date_planned -> operationplan.end
        purchase.order.date_planned -> operationplan.start
        'PO' -> operationplan.ordertype
        'confirmed' -> operationplan.status
        """
        m = self.env["purchase.order.line"]
        recs = m.search(
            [
                "|",
                ("order_id.state", "not in", ("draft", "sent", "bid", "confirmed")),
                ("order_id.state", "=", False),
            ]
        )
        fields = [
            "name",
            "date_planned",
            "product_id",
            "product_qty",
            "qty_received",
            "product_uom",
            "order_id",
        ]
        po_line = [i for i in recs.read(fields)]

        # Get all purchase orders
        m = self.env["purchase.order"]
        ids = [i["order_id"][0] for i in po_line]
        fields = ["name", "company_id", "partner_id", "state", "date_order"]
        po = {}
        for i in m.browse(ids).read(fields):
            po[i["id"]] = i

        # Create purchasing operations
        yield "<!-- open purchase orders -->\n"
        yield "<operationplans>\n"
        for i in po_line:
            if not i["product_id"]:
                continue
            item = self.product_product.get(i["product_id"][0], None)
            j = po[i["order_id"][0]]
            #
            location = self.mfg_location
            if location and item and i["product_qty"] > i["qty_received"]:
                start = j["date_order"].strftime("%Y-%m-%dT%H:%M:%S")
                end = i["date_planned"].strftime("%Y-%m-%dT%H:%M:%S")
                qty = self.convert_qty_uom(
                    i["product_qty"] - i["qty_received"],
                    i["product_uom"][0],
                    i["product_id"][0],
                )
                yield '<operationplan reference=%s ordertype="PO" start="%s" end="%s" quantity="%f" status="confirmed">' "<item name=%s/><location name=%s/><supplier name=%s/>" % (
                    quoteattr(j["name"]),
                    start,
                    end,
                    qty,
                    quoteattr(item["name"]),
                    quoteattr(location),
                    quoteattr("%d %s" % (j["partner_id"][0], j["partner_id"][1])),
                )
                yield "</operationplan>\n"
        yield "</operationplans>\n"

    def export_manufacturingorders(self):
        """
        Extracting work in progress to frePPLe, using the mrp.production model.

        We extract workorders in the states 'in_production' and 'confirmed', and
        which have a bom specified.

        Mapping:
        mrp.production.bom_id mrp.production.bom_id.name @ mrp.production.location_dest_id -> operationplan.operation
        convert mrp.production.product_qty and mrp.production.product_uom -> operationplan.quantity
        mrp.production.date_planned -> operationplan.end
        mrp.production.date_planned -> operationplan.start
        '1' -> operationplan.locked
        """
        yield "<!-- manufacturing orders in progress -->\n"
        yield "<operationplans>\n"
        m = self.env["mrp.production"]
        recs = m.search([("state", "in", ["in_production", "ready", "confirmed"])])
        fields = [
            "bom_id",
            "date_start",
            "date_planned_start",
            "name",
            "state",
            "product_qty",
            "product_uom_id",
            "location_dest_id",
            "product_id",
        ]
        for i in recs.read(fields):
            if i["state"] in ("in_production", "confirmed", "ready") and i["bom_id"]:
                # Open orders
                location = self.map_locations.get(i["location_dest_id"][0], None)
                operation = u"%d %s @ %s" % (i["bom_id"][0], i["bom_id"][1], location)
                startdate = i["date_start"] or i["date_planned_start"] or None
                if not startdate:
                    continue
                if not location or operation not in self.operations:
                    continue
                qty = self.convert_qty_uom(
                    i["product_qty"], i["product_uom_id"][0], i["product_id"][0]
                )
                yield '<operationplan reference=%s start="%s" end="%s" quantity="%s"><operation name=%s/></operationplan>\n' % (
                    quoteattr(i["name"]),
                    startdate.strftime('%Y-%m-%dT%H:%M:%S'),
                    startdate.strftime('%Y-%m-%dT%H:%M:%S'),
                    qty,
                    quoteattr(operation),
                )
        yield "</operationplans>\n"

    def export_orderpoints(self):
        """
        Defining order points for frePPLe, based on the stock.warehouse.orderpoint
        model.

        Mapping:
        stock.warehouse.orderpoint.product.name ' @ ' stock.warehouse.orderpoint.location_id.name -> buffer.name
        stock.warehouse.orderpoint.location_id.name -> buffer.location
        stock.warehouse.orderpoint.product.name -> buffer.item
        convert stock.warehouse.orderpoint.product_min_qty -> buffer.mininventory
        convert stock.warehouse.orderpoint.product_max_qty -> buffer.maxinventory
        convert stock.warehouse.orderpoint.qty_multiple -> buffer->size_multiple
        """
        m = self.env["stock.warehouse.orderpoint"]
        recs = m.search([])
        fields = [
            "warehouse_id",
            "product_id",
            "product_min_qty",
            "product_max_qty",
            "product_uom",
            "qty_multiple",
        ]
        if recs:
            yield "<!-- order points -->\n"
            yield "<buffers>\n"
            for i in recs.read(fields):
                item = self.product_product.get(
                    i["product_id"] and i["product_id"][0] or 0, None
                )
                if not item:
                    continue
                uom_factor = self.convert_qty_uom(
                    1.0, i["product_uom"][0], i["product_id"][0]
                )
                name = u"%s @ %s" % (item["name"], i["warehouse_id"][1])
                yield "<buffer name=%s><item name=%s/><location name=%s/>\n" '%s%s%s<booleanproperty name="ip_flag" value="true"/>\n' '<stringproperty name="roq_type" value="quantity"/>\n<stringproperty name="ss_type" value="quantity"/>\n' "</buffer>\n" % (
                    quoteattr(name),
                    quoteattr(item["name"]),
                    quoteattr(i["warehouse_id"][1]),
                    '<doubleproperty name="ss_min_qty" value="%s"/>\n'
                    % (i["product_min_qty"] * uom_factor)
                    if i["product_min_qty"]
                    else "",
                    '<doubleproperty name="roq_min_qty" value="%s"/>\n'
                    % ((i["product_max_qty"] - i["product_min_qty"]) * uom_factor)
                    if (i["product_max_qty"] - i["product_min_qty"])
                    else "",
                    '<doubleproperty name="roq_multiple_qty" value="%s"/>\n'
                    % (i["qty_multiple"] * uom_factor)
                    if i["qty_multiple"]
                    else "",
                )
            yield "</buffers>\n"

    def export_onhand(self, ctx=None):
        """
        Extracting all on hand inventories to frePPLe.

        We're bypassing the ORM for performance reasons.

        Mapping:
        stock.report.prodlots.product_id.name @ stock.report.prodlots.location_id.name -> buffer.name
        stock.report.prodlots.product_id.name -> buffer.item
        stock.report.prodlots.location_id.name -> buffer.location
        sum(stock.report.prodlots.qty) -> buffer.onhand
        """
        ctx = ctx if ctx else {}
        yield "<!-- inventory -->\n"
        yield "<buffers>\n"
        self.env.cr.execute(
            "SELECT product_id, location_id, sum(quantity) "
            "FROM stock_quant "
            "WHERE quantity > 0 "
            "GROUP BY product_id, location_id "
            "ORDER BY location_id ASC"
        )
        inventory = {}
        for i in self.env.cr.fetchall():
            item = self.product_product.get(i[0], None)
            location = self.map_locations.get(i[1], None)
            if item and location:
                inventory[(item["name"], location)] = i[2] + inventory.get(
                    (item["name"], location), 0
                )
        for key, val in inventory.items():
            buf = "%s @ %s" % (key[0], key[1])
            yield '<buffer name=%s onhand="%f"><item name=%s/><location name=%s/></buffer>\n' % (
                quoteattr(buf),
                val,
                quoteattr(key[0]),
                quoteattr(key[1]),
            )
        yield "</buffers>\n"

    def export_stock_rules(self, ctx=None):
        """ Exports the selected stock.rules, according to the domain set on the res.company.
        """
        if ctx is None:
            ctx = {}

        xml_str = [
            '<!-- Stock Rules -->',
            '<itemdistributions>',
        ]

        stock_rules = self.env['stock.rule'].search(
            ast.literal_eval(self.env.user.company_id.stock_rules_domain),
            order='location_src_id, location_id, delay DESC')
        if 'test_export_stock_rules' in ctx:
            stock_rules = stock_rules.filtered(lambda rule: rule.route_id.name.startswith(ctx['test_prefix']))

        # We show all the stock.rules, without considering the stock.location.route
        # they come from. Thus, it may be that we have duplicates for the same combination
        # of origin & destination. In this case, we choose the one with the higher delay.
        unique_rules = []
        for rule_no, rule in enumerate(stock_rules):
            if rule_no == 0:
                unique_rules.append(rule)
            else:
                # We check if the current one has the same combination of locations than the
                # the last one; in that case, since we order descending delay, we know the
                # current one has a lower delay, thus we skip it because of being duplicated
                # *and* having a lower delay (we want to keep the highest delay here, to
                # be on the safe side).
                last = unique_rules[-1]
                if rule.location_src_id != last.location_src_id or rule.location_id != last.location_id:
                    unique_rules.append(rule)
        unique_rules = self.env['stock.rule'].browse([rule.id for rule in unique_rules])

        for rule in unique_rules:
            xml_str.append('<itemdistribution>')
            if rule.location_src_id:
                xml_str.append('<origin name={loc_name} subcategory="{loc_id}" description="location"/>'.format(
                    loc_name=quoteattr(rule.location_src_id.name),
                    loc_id=rule.location_src_id.id))
            xml_str.append('<destination name={loc_name} subcategory="{loc_id}" description="location"/>'.format(
                loc_name=quoteattr(rule.location_id.name),
                loc_id=rule.location_id.id))
            if rule.delay:
                xml_str.append('<leadtime>P{}D</leadtime>'.format(rule.delay or 0))
            xml_str.append('</itemdistribution>')

        xml_str.append('</itemdistributions>')
        return '\n'.join(xml_str)

    def export_move_lines(self, ctx=None):
        """ Extracts the move lines, according to the domain set on the res.company.
            Domains having the same location as From & To are discarded always.
        """
        if ctx is None:
            ctx = {}

        xml_str = [
            '<!-- Stock Move Lines -->',
            '<operationplans>',
        ]

        move_lines = self.env['stock.move.line'].search(
            ast.literal_eval(self.env.user.company_id.internal_moves_domain),
            order='id').filtered(lambda move: move.location_id != move.location_dest_id)
        if 'test_export_move_lines' in ctx:
            move_lines = move_lines.filtered(lambda move_line: move_line.reference.startswith(ctx['test_prefix']))

        # Status between stock.move.line in Odoo and in frePPLe differ.
        # The following dictionary maps Odoo's status into frePPLe's status.
        status_mapping = {
            'draft': 'proposed',
            'waiting': 'approved',
            'confirmed': 'approved',
            'partially_available': 'approved',
            'assigned': 'confirmed',
            'done': 'completed',
            'cancel': 'closed',
        }

        for move_line in move_lines:
            product = move_line.product_id
            ref_uom_for_uom_category_id = self.uom_categories[
                self.uom[product.product_tmpl_id.uom_id.id]['category']]
            location_origin = move_line.location_id
            location_dest = move_line.location_dest_id

            xml_str.append(
                '<operationplan '
                'ordertype="DO" '
                'reference="{reference}" '
                'start="{start}" '
                'quantity="{quantity}" '
                'status="{status}">'.format(
                    reference=move_line.id,
                    start=move_line.date.strftime("%Y-%m-%dT%H:%M:%S"),
                    quantity=move_line.qty_done,
                    status=status_mapping.get(move_line.state, 'closed')))
            xml_str.extend([
                '<item name={product_name} subcategory="{subcategory}" description="Product"/>'.format(
                    product_name=quoteattr(product.name), subcategory='{},{}'.format(
                        ref_uom_for_uom_category_id, product.id)),
                '<location name={location_name} subcategory="{location_id}" description="Dest. location"/>'.format(
                    location_name=quoteattr(location_dest.complete_name), location_id=location_dest.id),
                '<origin name={location_name} subcategory="{location_id}" description="Origin location"/>'.format(
                    location_name=quoteattr(location_origin.complete_name), location_id=location_origin.id),
            ])
            xml_str.append('</operationplan>')

        xml_str.append('</operationplans>')
        return '\n'.join(xml_str)
