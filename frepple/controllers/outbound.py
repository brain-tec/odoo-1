# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 by frePPLe bv
# Copyright (c) 2022 brain-tec AG (https://braintec-group.com)
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
import json
import logging
import pytz
import xmlrpc.client
from xml.sax.saxutils import quoteattr
from datetime import datetime, timedelta
import odoo
from odoo import fields as odoo_fields
from odoo.tools import frozendict
from odoo.osv import expression
from pytz import timezone
import ssl
from .. import with_mrp

import ast

logger = logging.getLogger(__name__)


class Odoo_generator:
    def __init__(self, env):
        self.env = env

    def setContext(self, **kwargs):
        t = dict(self.env.context)
        t.update(kwargs)
        self.env = self.env(
            user=self.env.user,
            context=t,
        )

    def callMethod(self, model, id, method, args=[]):
        for obj in self.env[model].browse(id):
            return getattr(obj, method)(*args)
        return None

    def getData(self, model, search=[], order=None, fields=[], ids=None):
        if ids is not None:
            return self.env[model].browse(ids).read(fields) if ids else []
        if order:
            return self.env[model].search(search, order=order).read(fields)
        else:
            return self.env[model].search(search).read(fields)


class XMLRPC_generator:

    pagesize = 5000

    def __init__(self, url, db, username, password):
        self.db = db
        self.password = password
        self.env = xmlrpc.client.ServerProxy(
            "{}/xmlrpc/2/common".format(url),
            context=ssl._create_unverified_context(),
        )
        self.uid = self.env.authenticate(db, username, password, {})
        self.env = xmlrpc.client.ServerProxy(
            "{}/xmlrpc/2/object".format(url),
            context=ssl._create_unverified_context(),
            use_builtin_types=True,
            headers={"Connection": "keep-alive"}.items(),
        )
        self.context = {}

    def setContext(self, **kwargs):
        self.context.update(kwargs)

    def callMethod(self, model, id, method, args):
        return self.env.execute_kw(
            self.db, self.uid, self.password, model, method, [id], []
        )

    def getData(self, model, search=None, order="id asc", fields=[], ids=[]):
        if ids:
            page_ids = [ids]
        else:
            page_ids = []
            offset = 0
            msg = {
                "limit": self.pagesize,
                "offset": offset,
                "context": self.context,
                "order": order,
            }
            while True:
                extra_ids = self.env.execute_kw(
                    self.db,
                    self.uid,
                    self.password,
                    model,
                    "search",
                    [search] if search else [[]],
                    msg,
                )
                if not extra_ids:
                    break
                page_ids.append(extra_ids)
                offset += self.pagesize
                msg["offset"] = offset
        if page_ids and page_ids != [[]]:
            data = []
            for page in page_ids:
                data.extend(
                    self.env.execute_kw(
                        self.db,
                        self.uid,
                        self.password,
                        model,
                        "read",
                        [page],
                        {"fields": fields, "context": self.context},
                    )
                )
            return data
        else:
            return []


class exporter(object):
    def __init__(
        self,
        generator,
        req,
        uid,
        database=None,
        company=None,
        mode=1,
        timezone=None,
        singlecompany=False,
        version="0.0.0.unknown",
    ):
        self.database = database
        self.company = company
        self.generator = generator
        self.version = version
        self.timezone = timezone
        if timezone:
            if timezone not in pytz.all_timezones:
                logger.warning("Invalid timezone URL argument: %s." % (timezone,))
                self.timezone = None
            else:
                # Valid timezone override in the url
                self.timezone = timezone
        if not self.timezone:
            # Default timezone: use the timezone of the connector user (or UTC if not set)
            for i in self.generator.getData(
                "res.users",
                ids=[
                    uid,
                ],
                fields=["tz"],
            ):
                self.timezone = i["tz"] or "UTC"
        self.timeformat = "%Y-%m-%dT%H:%M:%S"
        self.singlecompany = singlecompany

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

        # Map: location.id -> 'complete name for the stock location of the warehouse the location belongs to'.
        self.map_locations = {}

    def run(self):
        # Check if we manage by work orders or manufacturing orders.
        self.manage_work_orders = False
        for rec in self.generator.getData(
            "ir.model", search=[("model", "=", "mrp.workorder")], fields=["name"]
        ):
            self.manage_work_orders = True

        # Load some auxiliary data in memory
        self.load_company()
        self.load_uom()

        # Header.
        # The source attribute is set to 'odoo_<mode>', such that all objects created or
        # updated from the data are also marked as from originating from odoo.
        yield '<?xml version="1.0" encoding="UTF-8" ?>\n'
        yield '<plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" source="odoo_%s">\n' % self.mode
        yield "<description>Generated by odoo %s</description>\n" % odoo.release.version

        # Synchronize users
        for i in self.export_users():
            yield i

        # Main content.
        # The order of the entities is important. First one needs to create the
        # objects before they are referenced by other objects.
        # If multiple types of an entity exists (eg operation_time_per,
        # operation_alternate, operation_alternate, etc) the reference would
        # automatically create an object, potentially of the wrong type.
        if with_mrp:
            logger.debug("Exporting calendars.")
            if self.mode == 1:
                for i in self.export_calendar():
                    yield i
        logger.debug("Exporting locations.")
        for i in self.export_locations():
            yield i
        logger.debug("Exporting customers.")
        for i in self.export_customers():
            yield i
        if self.mode == 1:
            logger.debug("Exporting suppliers.")
            for i in self.export_suppliers():
                yield i
            if with_mrp:
                logger.debug("Exporting skills.")
                for i in self.export_skills():
                    yield i
                logger.debug("Exporting workcenters.")
                for i in self.export_workcenters():
                    yield i
        logger.debug("Exporting products.")
        for i in self.export_items():
            yield i
        if with_mrp:
            logger.debug("Exporting BOMs.")
            if self.mode == 1:
                for i in self.export_boms():
                    yield i
        logger.debug("Exporting sales orders.")
        for i in self.export_salesorders():
            yield i
        # Uncomment the following lines to create forecast models in frepple
        # logger.debug("Exporting forecast.")
        # for i in self.export_forecasts():
        #     yield i
        if self.mode == 1:
            logger.debug("Exporting purchase orders.")
            for i in self.export_purchaseorders():
                yield i
            if with_mrp:
                logger.debug("Exporting manufacturing orders.")
                for i in self.export_manufacturingorders():
                    yield i
            logger.debug("Exporting reordering rules.")
            for i in self.export_orderpoints():
                yield i
            logger.debug("Exporting quantities on-hand.")
            for i in self.export_onhand():
                yield i
            yield self.export_moves()
            yield self.export_stock_rules()

        # Footer
        yield "</plan>\n"

    def load_company(self):
        self.company_id = 0
        for i in self.generator.getData(
            "res.company",
            search=[("name", "=", self.company)],
            fields=[
                "security_lead",
                "po_lead",
                "manufacturing_lead",
                "calendar",
                "manufacturing_warehouse",
                "respect_reservations",
                "tz_for_exporting",
                "frepple_export_language",
            ],
        ):
            self.company_id = i["id"]
            self.security_lead = int(
                i["security_lead"]
            )  # TODO NOT USED RIGHT NOW - add parameter in frepple for this
            self.po_lead = i["po_lead"]
            self.manufacturing_lead = i["manufacturing_lead"]
            self.respect_reservations = i["respect_reservations"]
            try:
                self.calendar = i["calendar"] and i["calendar"][1] or "Working hours"
                self.mfg_location = (
                    i["manufacturing_warehouse"]
                    and i["manufacturing_warehouse"][1]
                    or self.company
                )
                self.stock_location = (
                    i["manufacturing_warehouse"]
                    and self.env["stock.warehouse"].browse(i["manufacturing_warehouse"][0]).lot_stock_id
                    or self.company
                )
            except Exception:
                self.calendar = None
                self.mfg_location = None
                self.stock_location = None
            if self.singlecompany:
                # Create a new context to limit the data to the selected company
                self.generator.setContext(allowed_company_ids=[i["id"]])
            ctx = self.env.context.copy()
            ctx['tz'] = i["tz_for_exporting"]
            if i["frepple_export_language"]:
                ctx['lang'] = self.env['res.lang'].browse(i["frepple_export_language"][0]).code
            self.env.context = frozendict(ctx)
        if not self.company_id:
            logger.warning("Can't find company '%s'" % self.company)
            self.company_id = None
            self.security_lead = 0
            self.po_lead = 0
            self.manufacturing_lead = 0
            self.calendar = None
            self.mfg_location = self.company

    def load_uom(self):
        """
        Loading units of measures into a dictionary for fast lookups.

        All quantities are sent to frePPLe as numbers, expressed in the default
        unit of measure of the uom dimension.
        """
        self.uom = {}
        self.uom_categories = {}
        for i in self.generator.getData(
            "uom.uom",
            # We also need to load INactive UOMs, because there still might be records
            # using the inactive UOM. Questionable practice, but can happen...
            search=["|", ("active", "=", 1), ("active", "=", 0)],
            fields=["factor", "uom_type", "category_id", "name"],
        ):
            if i["uom_type"] == "reference":
                self.uom_categories[i["category_id"][0]] = i["id"]
            self.uom[i["id"]] = {
                "factor": i["factor"],
                "category": i["category_id"][0],
                "name": i["name"],
            }

    def convert_qty_uom(self, qty, uom_id, product_id=None):
        """
        Convert a quantity to the reference uom of the product.
        """
        try:
            uom_id = uom_id[0]
        except Exception:
            pass
        if not uom_id:
            return qty
        if not product_id:
            return qty * self.uom[uom_id]["factor"]
        else:
            product = self.env['product.template'].browse(product_id)
            uom = self.env['uom.uom'].browse(uom_id)

            # I use the normal Odoo's conversion.
            # If it fails, I return what the original frePPLe code returns.
            try:
                return uom._compute_quantity(qty, product.uom_id, raise_if_failure=True)
            except Exception as e:
                logger.warning(
                    "Can't convert from %s for product %s. With error: %s"
                    % (self.uom[uom_id]["name"], product_id, str(e))
                )
                return qty * self.uom[uom_id]["factor"]

    def convert_float_time(self, float_time, units="days"):
        """
        Convert Odoo float time to ISO 8601 duration.
        """
        d = timedelta(**{units: float_time})
        return "P%dDT%dH%dM%dS" % (
            d.days,  # duration: days
            int(d.seconds / 3600),  # duration: hours
            int((d.seconds % 3600) / 60),  # duration: minutes
            int(d.seconds % 60),  # duration: seconds
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

    def formatDateTime(self, d, tmzone=None):
        if not isinstance(d, datetime):
            d = datetime.fromisoformat(d)
        return d.astimezone(timezone(tmzone or self.timezone)).strftime(self.timeformat)

    def export_users(self):
        users = []
        for grp in self.generator.getData(
            "res.groups",
            search=[("name", "=", "frePPLe user")],
            fields=[
                "users",
            ],
        ):
            for usr in self.generator.getData(
                "res.users",
                ids=grp["users"],
                fields=["name", "login"],
            ):
                users.append(
                    (
                        usr["name"],
                        usr["login"],
                    )
                )
        yield '<stringproperty name="users" value=%s/>\n' % quoteattr(json.dumps(users))

    def export_calendar(self):
        """
        Reads all calendars from resource.calendar model and creates a calendar in frePPLe.
        Attendance times are read from resource.calendar.attendance
        Leave times are read from resource.calendar.leaves

        resource.calendar.name -> calendar.name (default value is 0)
        resource.calendar.attendance.date_from -> calendar bucket start date (or 2000-01-01 if unspecified)
        resource.calendar.attendance.date_to -> calendar bucket end date (or 2030-01-01 if unspecified)
        resource.calendar.attendance.hour_from -> calendar bucket start time
        resource.calendar.attendance.hour_to -> calendar bucket end time
        resource.calendar.attendance.dayofweek -> calendar bucket day

        resource.calendar.leaves.date_from -> calendar bucket start date
        resource.calendar.leaves.date_to -> calendar bucket end date

        """
        yield "<!-- calendar -->\n"
        yield "<calendars>\n"

        calendars = {}
        cal_tz = {}
        cal_ids = set()
        try:

            # Read the timezone
            for i in self.generator.getData(
                "resource.calendar",
                fields=[
                    "name",
                    "tz",
                ],
            ):
                cal_tz[i["name"]] = i["tz"]
                cal_ids.add(i["id"])

            # Read the attendance for all calendars
            for i in self.generator.getData(
                "resource.calendar.attendance",
                fields=[
                    "dayofweek",
                    "date_from",
                    "date_to",
                    "hour_from",
                    "hour_to",
                    "calendar_id",
                ],
            ):
                if i["calendar_id"] and i["calendar_id"][0] in cal_ids:
                    if i["calendar_id"][1] not in calendars:
                        calendars[i["calendar_id"][1]] = []
                    i["attendance"] = True
                    calendars[i["calendar_id"][1]].append(i)

            # Read the leaves for all calendars
            for i in self.generator.getData(
                "resource.calendar.leaves",
                search=[("time_type", "=", "leave")],
                fields=[
                    "date_from",
                    "date_to",
                    "calendar_id",
                ],
            ):
                if i["calendar_id"] and i["calendar_id"][0] in cal_ids:
                    if i["calendar_id"][1] not in calendars:
                        calendars[i["calendar_id"][1]] = []
                    i["attendance"] = False
                    calendars[i["calendar_id"][1]].append(i)

            # Iterate over the results:
            for i in calendars:
                priority_attendance = 1000
                priority_leave = 10
                if cal_tz[i] != self.timezone:
                    logger.warning(
                        "timezone is different on workcenter %s and connector user. "
                        "Working hours will not be synced correctly to frepple."
                        % i
                    )
                yield '<calendar name=%s default="0"><buckets>\n' % quoteattr(i)
                for j in calendars[i]:
                    yield '''<bucket start="%s" end="%s" value="%s" days="%s" priority="%s"
                     starttime="%s" endtime="%s"/>\n''' % (
                        self.formatDateTime(j["date_from"], cal_tz[i])
                        if not j["attendance"]
                        else (
                            j["date_from"].strftime("%Y-%m-%dT00:00:00")
                            if j["date_from"]
                            else "2000-01-01T00:00:00"
                        ),
                        self.formatDateTime(j["date_to"], cal_tz[i])
                        if not j["attendance"]
                        else (
                            j["date_to"].strftime("%Y-%m-%dT00:00:00")
                            if j["date_to"]
                            else "2030-01-01T00:00:00"
                        ),
                        "1" if j["attendance"] else "0",
                        (2 ** ((int(j["dayofweek"]) + 1) % 7))
                        if "dayofweek" in j
                        else (2 ** 7) - 1,
                        priority_attendance if j["attendance"] else priority_leave,
                        # In odoo, monday = 0. In frePPLe, sunday = 0.
                        ("PT%dM" % round(j["hour_from"] * 60))
                        if "hour_from" in j
                        else "PT0M",
                        ("PT%dM" % round(j["hour_to"] * 60))
                        if "hour_to" in j
                        else "PT1440M",
                    )
                    if j["attendance"]:
                        priority_attendance += 1
                    else:
                        priority_leave += 1
                yield "</buckets></calendar>\n"

            yield "</calendars>\n"
        except Exception as e:
            logger.info(e)
            yield "</calendars>\n"

    def export_locations(self, ctx=None):
        """
        Generate a list of warehouse locations to frePPLe, based on the
        stock.warehouse model.

        We assume the location name to be unique. This is NOT guaranteed by Odoo.

        The field subcategory is used to store the id of the warehouse. This makes
        it easier for frePPLe to send back planning results directly with an
        odoo location identifier.

        frePPLe is not interested in the locations odoo defines with a warehouse.
        This methods also populates a map dictionary between these locations and
        warehouse they belong to.

        The optional context (ctx) is to test easily.

        Mapping:
        stock.warehouse.name -> location.name
        stock.warehouse.id -> location.subcategory
        """
        ctx = ctx if ctx else {}

        for loc in self.env['stock.location'].with_context(active_test=False).search([]):
            self.map_locations[loc.id] = loc.get_warehouse_stock_location().complete_name

        warehouses = self.env['stock.warehouse'].with_context(active_test=False).search([]).filtered(
            lambda warehouse: warehouse.name.startswith(ctx.get('test_prefix', '')))
        stock_locations = warehouses.mapped('lot_stock_id').filtered(
            lambda location: location.name.startswith(ctx.get('test_prefix', '')))

        xml_str = ['<locations>']
        for loc in stock_locations:
            xml_str.append('<location name="{}" subcategory="{}"/>'.format(loc.complete_name, loc.id))
        xml_str.append('</locations>')
        return '\n'.join(xml_str)

    def export_customers(self, ctx=None):
        """ Generate a list of customers to frePPLe, based on the res.partner model.
            We filter on res.partner where customer = True.
        """
        ctx = ctx if ctx else {}
        return self.env['res.partner'].with_context(**ctx)._frepple_export_customers()

    def export_suppliers(self):
        """
        Generate a list of suppliers for frePPLe, based on the res.partner model.
        We filter on res.supplier where supplier = True.

        Mapping:
        res.partner.id res.partner.name -> supplier.name
        """
        first = True
        for i in self.generator.getData(
            "res.partner",
            search=[("is_company", "=", True)],
            fields=["name"],
        ):
            if first:
                yield "<!-- suppliers -->\n"
                yield "<suppliers>\n"
                first = False
            yield "<supplier name=%s/>\n" % quoteattr("%d %s" % (i["id"], i["name"]))
        if not first:
            yield "</suppliers>\n"

    def export_skills(self):
        first = True
        for i in self.generator.getData(
            "mrp.skill",
            fields=["name"],
        ):
            if first:
                yield "<!-- skills -->\n"
                yield "<skills>\n"
                first = False
            name = i["name"]
            yield "<skill name=%s/>\n" % (quoteattr(name),)
        if not first:
            yield "</skills>\n"

    def export_workcenterskills(self):
        first = True
        for i in self.generator.getData(
            "mrp.workcenter.skill",
            fields=["workcenter", "skill", "priority"],
        ):
            if not i["workcenter"] or i["workcenter"][0] not in self.map_workcenters:
                continue
            if first:
                yield "<!-- resourceskills -->\n"
                yield "<skills>\n"
                first = False
            yield "<skill name=%s>\n" % quoteattr(i["skill"][1])
            yield "<resourceskills>"
            yield '<resourceskill priority="%d"><resource name=%s/></resourceskill>' % (
                i["priority"],
                quoteattr(self.map_workcenters[i["workcenter"][0]]),
            )
            yield "</resourceskills>"
            yield "</skill>"
        if not first:
            yield "</skills>"

    def export_workcenters(self):
        """
        Send the workcenter list to frePPLe, based one the mrp.workcenter model.

        We assume the workcenter name is unique. Odoo does NOT guarantuee that.

        Mapping:
        mrp.workcenter.name -> resource.name
        mrp.workcenter.owner -> resource.owner
        mrp.workcenter.resource_calendar_id -> resource.available
        mrp.workcenter.capacity -> resource.maximum
        mrp.workcenter.time_efficiency -> resource.efficiency

        company.mfg_location -> resource.location
        """
        self.map_workcenters = {}
        first = True
        for i in self.generator.getData(
            "mrp.workcenter",
            fields=[
                "name",
                "owner",
                "resource_calendar_id",
                "time_efficiency",
                "capacity",
            ],
        ):
            if first:
                yield "<!-- workcenters -->\n"
                yield "<resources>\n"
                first = False
            name = i["name"]
            owner = i["owner"]
            available = i["resource_calendar_id"]
            self.map_workcenters[i["id"]] = name
            yield '<resource name=%s maximum="%s" efficiency="%s"><location name=%s/>%s%s</resource>\n' % (
                quoteattr(name),
                i["capacity"],
                i["time_efficiency"],
                quoteattr(self.mfg_location),
                ("<owner name=%s/>" % quoteattr(owner[1])) if owner else "",
                ("<available name=%s/>" % quoteattr(available[1])) if available else "",
            )
        if not first:
            yield "</resources>\n"

    def export_items(self, ctx=None):
        """
        Send the list of products to frePPLe, based on the product.product model.
        For purchased items we also create a procurement buffer in each warehouse.

        Mapping:
        [product.product.code] product.product.name -> item.name
        product.product.product_tmpl_id.list_price or standard_price -> item.cost
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

        # Read the product templates
        self.product_product = {}
        self.product_template_product = {}
        self.product_templates = {}
        for i in self.generator.getData(
            "product.template",
            search=[("type", "not in", ("service", "consu"))],
            fields=[
                "sale_ok",
                "purchase_ok",
                "produce_delay",
                "list_price",
                "standard_price",
                "uom_id",
                "categ_id",
                "product_variant_ids",
            ],
        ):
            self.product_templates[i["id"]] = i

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

        self._fill_in_product_related_variables(
            search_domain_products, search_domain_suppliers, search_domain_templates)

        # Now we generate the XML.
        xml_str.append('<!-- products -->')
        xml_str.append('<items>')

        top_categories = self.env['product.category'].search(
            [('parent_id', '=', False)] + search_domain_product_categories, order='name,id')
        for top_category in top_categories:
            xml_str.extend(self._generate_category_xml(
                top_category, search_domain_product_categories, search_domain_products, search_domain_suppliers,
                ctx))

        xml_str.append('</items>')
        return '\n'.join(xml_str)

    def _fill_in_product_related_variables(
            self, search_domain_products, search_domain_suppliers, search_domain_templates):
        """ We fill in the attributes the original method export_items filled in.
            I keep them here because the original code defines and fills them ─ only because of that.
            The original code also loaded the location routes, that used for nothing, thus
            I don't load them...
        """
        self.product_product = dict()
        self.product_template_product = dict()
        self.product_supplier = dict()
        for product in self.env['product.product'].with_context(active_test=False).search(search_domain_products):
            product_template_id = product.product_tmpl_id.id
            product_data = {'name': product.name, 'template': product_template_id}
            self.product_product[product.id] = product_data
            self.product_template_product[product.product_tmpl_id.id] = product_data
        for supplier in self.env['product.supplierinfo'].with_context(active_test=False).search(
                search_domain_suppliers
        ):
            self.product_supplier.setdefault(supplier.product_tmpl_id.id, []).append(
                (supplier.name, supplier.delay, supplier.min_qty, supplier.date_end,
                 supplier.date_start, supplier.price, supplier.sequence))

    def _generate_category_xml(
            self, category, search_domain_categories, search_domain_products, search_domain_suppliers, ctx=None):
        ctx = ctx if ctx else {}

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
                    product, search_domain_suppliers, ctx))
            for subcategory in subcategories:
                xml_str.extend(self._generate_category_xml(
                    subcategory, search_domain_categories, search_domain_products, search_domain_suppliers, ctx))
            xml_str.append('</members>')

        xml_str.append('</item>')
        return xml_str

    def _generate_product_xml(self, product, search_domain_suppliers, ctx=None):
        ctx = ctx if ctx else {}

        # The subcategory attribute in an <item> stores, separated by a comma, the ID of the
        # UOM used as the reference for the category of the UOM set on the product's template,
        # and then the product's ID. ò_Ó
        ref_uom_for_uom_category_id = self.uom_categories[self.uom[product.product_tmpl_id.uom_id.id]['category']]
        xml_str = ['<item name={} cost="{:0.6f}" subcategory="{},{}" description="product">'.format(
            quoteattr(product.name), product.list_price, ref_uom_for_uom_category_id, product.id)]

        warehouse_domain = []
        if 'test_prefix' in ctx:
            warehouse_domain.append(('code', '=like', '{}%'.format(ctx['test_prefix'])))

        weight = product._get_weight()
        if weight:
            xml_str.append('<weight>%f</weight>' % weight)

        # in the export of product master data the supplierinfo is also exported. to make sure frepple has all
        # the right routes to source the products, we were exporting each supplierinfo once for each warehouse.
        # Here we changed the implementation as not all products can be purchased for every warehouse.
        # Hence we use routes to determine for which warehouses the sourcing should be done.
        # Instead of just using all warehouses, only warehouses for which the product in question has a route
        # are used
        stock_rules = self.env['stock.rule'].search(
            [('action', '=', 'buy'), ('route_id', 'in', product.product_tmpl_id.route_ids.ids)])

        suppliers = self.env['product.supplierinfo'].search(expression.AND([[
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
        ], search_domain_suppliers]), order='id')
        for supplier_no, supplier in enumerate(suppliers):
            if supplier_no == 0:
                xml_str.append('<itemsuppliers>')

            for rule in stock_rules:
                seller = supplier.name
                supplier_name = "{} {}".format(seller.id, seller.name)
                effective_end_str = ' effective_end="{}T00:00:00"'.format(
                    odoo_fields.Date.to_string(supplier.date_end)) if supplier.date_end else ''
                effective_start_str = ' effective_start="{}T00:00:00"'.format(
                    odoo_fields.Date.to_string(supplier.date_start)) if supplier.date_start else ''
                xml_str.extend([
                    '<itemsupplier leadtime="P{}D" priority="{}" size_minimum="{:.6f}" '
                    'cost="{:0.6f}"{}{}>'.format(
                        supplier.delay, supplier.sequence or 1, supplier.min_qty or 0, supplier.price,
                        effective_end_str, effective_start_str),
                    '<location name="{}"/>'.format(rule.location_id.complete_name),
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

        # dictionary used to divide the confirmed MO quantities
        # key is tuple (operation name, produced item)
        # value is quantity in Operation Materials.
        self.bom_producedQty = {}

        # Read all active manufacturing routings
        mrp_routings = {}
        # m = self.env["mrp.routing"]
        # recs = m.search([])
        # fields = ["location_id"]
        # for i in recs.read(fields):
        #    mrp_routings[i["id"]] = i["location_id"]

        # Read all workcenters of all routings
        mrp_routing_workcenters = {}
        for i in self.generator.getData(
            "mrp.routing.workcenter",
            order="bom_id, sequence, id asc",
            fields=[
                "name",
                "bom_id",
                "workcenter_id",
                "sequence",
                "time_cycle",
                "skill",
                "search_mode",
            ],
        ):
            if not i["bom_id"]:
                continue

            if i["bom_id"][0] in mrp_routing_workcenters:
                # If the same workcenter is used multiple times in a routing,
                # we add the times together.
                exists = False
                if not self.manage_work_orders:
                    for r in mrp_routing_workcenters[i["bom_id"][0]]:
                        if r["workcenter_id"][1] == i["workcenter_id"][1]:
                            r["time_cycle"] += i["time_cycle"]
                            exists = True
                            break
                if not exists:
                    mrp_routing_workcenters[i["bom_id"][0]].append(i)
            else:
                mrp_routing_workcenters[i["bom_id"][0]] = [i]

        # Loop over all bom records
        for i in self.generator.getData(
            "mrp.bom",
            fields=[
                "product_qty",
                "product_uom_id",
                "product_tmpl_id",
                "type",
                "bom_line_ids",
                "sequence",
                "picking_type_id"
            ],
        ):
            # if not i['routing_id']:
            #     i['routing_id'] = dummy_mrp_route_m2o_read

            # Determine the location
            warehouse = False
            if i and i["picking_type_id"]:
                warehouse = self.env['stock.picking.type'].browse(i["picking_type_id"][0]).warehouse_id

            location = warehouse.lot_stock_id if warehouse else self.stock_location
            location_name = location.display_name

            product_template = self.product_templates.get(i["product_tmpl_id"][0], None)
            if not product_template:
                continue
            uom_factor = self.convert_qty_uom(
                1.0, i["product_uom_id"], i["product_tmpl_id"][0]
            )

            # Loop over all subcontractors
            if i["type"] == "subcontract":
                subcontractors = self.product_templates[i["product_tmpl_id"][0]].get(
                    "subcontractors", None
                )
                if not subcontractors:
                    continue
            else:
                subcontractors = [{}]

            for product_id in product_template["product_variant_ids"]:

                # Determine operation name and item
                product_buf = self.product_product.get(product_id, None)
                if not product_buf:
                    logger.warning("Skipping %s" % i["product_tmpl_id"][0])
                    continue

                for subcontractor in subcontractors:
                    # Build operation. The operation can either be a summary operation or a detailed
                    # routing.
                    operation = "%s @ %s %d" % (
                        product_buf["name"],
                        subcontractor.get("name", location_name),
                        i["id"],
                    )
                    if len(operation) > 300:
                        suffix = " @ %s %d" % (
                            subcontractor.get("name", location_name),
                            i["id"],
                        )
                        operation = "%s%s" % (
                            product_buf["name"][: 300 - len(suffix)],
                            suffix,
                        )
                    self.operations.add(operation)
                    if (
                        not self.manage_work_orders
                        or subcontractor
                        or not mrp_routing_workcenters.get(i["id"], [])
                    ):
                        #
                        # CASE 1: A single operation used for the BOM
                        # All routing steps are collapsed in a single operation.
                        #
                        if subcontractor:
                            yield '<operation name=%s size_multiple="1" category="subcontractor" subcategory=%s duration="P%dD" posttime="P%dD" xsi:type="operation_fixed_time" priority="%s" size_minimum="%s">\n' "<item name=%s/><location name=%s/>\n" % (
                                quoteattr(operation),
                                quoteattr(subcontractor["name"]),
                                subcontractor.get("delay", 0),
                                self.po_lead,
                                subcontractor.get("priority", 1),
                                subcontractor.get("size_minimum", 0),
                                quoteattr(product_buf["name"]),
                                quoteattr(location_name),
                            )
                        else:
                            duration_per = (
                                self.product_templates[i["product_tmpl_id"][0]][
                                    "produce_delay"
                                ]
                                / 1440.0
                            )
                            yield '<operation name=%s size_multiple="1" duration_per="%s" posttime="P%dD" priority="%s" xsi:type="operation_time_per">\n' "<item name=%s/><location name=%s/>\n" % (
                                quoteattr(operation),
                                self.convert_float_time(duration_per)
                                if duration_per and duration_per > 0
                                else "P0D",
                                self.manufacturing_lead,
                                i["sequence"] or 1,
                                quoteattr(product_buf["name"]),
                                quoteattr(location_name),
                            )

                        convertedQty = self.convert_qty_uom(
                            i["product_qty"],
                            i["product_uom_id"],
                            i["product_tmpl_id"][0],
                        )
                        yield '<flows>\n<flow xsi:type="flow_end" quantity="%f"><item name=%s/></flow>\n' % (
                            convertedQty,
                            quoteattr(product_buf["name"]),
                        )
                        self.bom_producedQty[
                            (operation, product_buf["name"])
                        ] = convertedQty

                        # Build consuming flows.
                        # If the same component is consumed multiple times in the same BOM
                        # we sum up all quantities in a single flow. We assume all of them
                        # have the same effectivity.
                        fl = {}
                        for j in self.generator.getData(
                            "mrp.bom.line",
                            ids=i["bom_line_ids"],
                            fields=[
                                "product_qty",
                                "product_uom_id",
                                "product_id",
                                "operation_id",
                                "bom_product_template_attribute_value_ids",
                            ],
                        ):
                            # check if this BOM line applies to this variant
                            if len(
                                j["bom_product_template_attribute_value_ids"]
                            ) > 0 and not all(
                                elem
                                in product_buf["product_template_attribute_value_ids"]
                                for elem in j[
                                    "bom_product_template_attribute_value_ids"
                                ]
                            ):
                                continue
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
                                    k["product_qty"],
                                    k["product_uom_id"],
                                    self.product_product[k["product_id"][0]][
                                        "template"
                                    ],
                                )
                                for k in fl[j]
                            )
                            if qty > 0:
                                yield '<flow xsi:type="flow_start" quantity="-%f"><item name=%s/></flow>\n' % (
                                    qty,
                                    quoteattr(product["name"]),
                                )

                        # Build byproduct flows
                        if i.get("sub_products", None):
                            for j in self.generator.getData(
                                "mrp.subproduct",
                                ids=i["sub_products"],
                                fields=[
                                    "product_id",
                                    "product_qty",
                                    "product_uom",
                                    "subproduct_type",
                                ],
                            ):
                                product = self.product_product.get(
                                    j["product_id"][0], None
                                )
                                if not product:
                                    continue
                                yield '<flow xsi:type="%s" quantity="%f"><item name=%s/></flow>\n' % (
                                    "flow_fixed_end"
                                    if j["subproduct_type"] == "fixed"
                                    else "flow_end",
                                    self.convert_qty_uom(
                                        j["product_qty"],
                                        j["product_uom"],
                                        j["product_id"][0],
                                    ),
                                    quoteattr(product["name"]),
                                )
                        yield "</flows>\n"

                        # Create loads
                        if i["id"] and not subcontractor:
                            exists = False
                            for j in mrp_routing_workcenters.get(i["id"], []):
                                if (
                                    not j["workcenter_id"]
                                    or j["workcenter_id"][0] not in self.map_workcenters
                                ):
                                    continue
                                if not exists:
                                    exists = True
                                    yield "<loads>\n"
                                yield '<load quantity="%f" search=%s><resource name=%s/>%s</load>\n' % (
                                    j["time_cycle"],
                                    quoteattr(j["search_mode"]),
                                    quoteattr(
                                        self.map_workcenters[j["workcenter_id"][0]]
                                    ),
                                    ("<skill name=%s/>" % quoteattr(j["skill"][1]))
                                    if j["skill"]
                                    else "",
                                )
                            if exists:
                                yield "</loads>\n"
                    else:
                        #
                        # CASE 2: A routing operation is created with a suboperation for each
                        # routing step.
                        #
                        yield '<operation name=%s size_multiple="1" posttime="P%dD" priority="%s" xsi:type="operation_routing">' "<item name=%s/><location name=%s/>\n" % (
                            quoteattr(operation),
                            self.manufacturing_lead,
                            i["sequence"] or 1,
                            quoteattr(product_buf["name"]),
                            quoteattr(location),
                        )

                        yield "<suboperations>"

                        fl = {}
                        for j in self.generator.getData(
                            "mrp.bom.line",
                            ids=i["bom_line_ids"],
                            fields=[
                                "product_qty",
                                "product_uom_id",
                                "product_id",
                                "operation_id",
                                "bom_product_template_attribute_value_ids",
                            ],
                        ):
                            # check if this BOM line applies to this variant
                            if len(
                                j["bom_product_template_attribute_value_ids"]
                            ) > 0 and not all(
                                elem
                                in product_buf["product_template_attribute_value_ids"]
                                for elem in j[
                                    "bom_product_template_attribute_value_ids"
                                ]
                            ):
                                continue
                            product = self.product_product.get(j["product_id"][0], None)
                            if not product:
                                continue
                            qty = self.convert_qty_uom(
                                j["product_qty"],
                                j["product_uom_id"],
                                self.product_product[j["product_id"][0]]["template"],
                            )
                            if j["product_id"][0] in fl:
                                # If the same component is consumed multiple times in the same BOM
                                # we sum up all quantities in a single flow. We assume all of them
                                # have the same effectivity.
                                fl[j["product_id"][0]]["qty"] += qty
                            else:
                                j["qty"] = qty
                                fl[j["product_id"][0]] = j

                        steplist = mrp_routing_workcenters[i["id"]]
                        counter = 0
                        for step in steplist:
                            counter = counter + 1
                            suboperation = step["name"]
                            name = "%s - %s - %s" % (
                                operation,
                                suboperation,
                                step["id"],
                            )
                            if len(name) > 300:
                                suffix = " - %s - %s" % (
                                    suboperation,
                                    step["id"],
                                )
                                name = "%s%s" % (
                                    operation[: 300 - len(suffix)],
                                    suffix,
                                )
                            if (
                                not step["workcenter_id"]
                                or step["workcenter_id"][0] not in self.map_workcenters
                            ):
                                continue
                            yield "<suboperation>" '<operation name=%s priority="%s" duration_per="%s" xsi:type="operation_time_per">\n' "<location name=%s/>\n" '<loads><load quantity="%f" search=%s><resource name=%s/>%s</load></loads>\n' % (
                                quoteattr(name),
                                counter * 10,
                                self.convert_float_time(step["time_cycle"] / 1440.0)
                                if step["time_cycle"] and step["time_cycle"] > 0
                                else "P0D",
                                quoteattr(location),
                                1,
                                quoteattr(step["search_mode"]),
                                quoteattr(
                                    self.map_workcenters[step["workcenter_id"][0]]
                                ),
                                ("<skill name=%s/>" % quoteattr(step["skill"][1]))
                                if step["skill"]
                                else "",
                            )
                            first_flow = True
                            if counter == len(steplist):
                                # Add producing flows on the last routing step
                                first_flow = False
                                yield '<flows>\n<flow xsi:type="flow_end" quantity="%f"><item name=%s/></flow>\n' % (
                                    i["product_qty"]
                                    * getattr(i, "product_efficiency", 1.0)
                                    * uom_factor,
                                    quoteattr(product_buf["name"]),
                                )
                                self.bom_producedQty[(name, product_buf["name"],)] = (
                                    i["product_qty"]
                                    * getattr(i, "product_efficiency", 1.0)
                                    * uom_factor
                                )
                            for j in fl.values():
                                if j["qty"] > 0 and (
                                    (
                                        j["operation_id"]
                                        and j["operation_id"][0] == step["id"]
                                    )
                                    or (not j["operation_id"] and step == steplist[0])
                                ):
                                    if first_flow:
                                        first_flow = False
                                        yield "<flows>\n"
                                    yield '<flow xsi:type="flow_start" quantity="-%f"><item name=%s/></flow>\n' % (
                                        j["qty"],
                                        quoteattr(
                                            self.product_product[j["product_id"][0]][
                                                "name"
                                            ]
                                        ),
                                    )
                            if not first_flow:
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

        Send confirmed sales order lines as demand to frePPLe, using the
        sale.order and sale.order.line models.

        Each order is linked to a warehouse, which is used as the location in
        frePPLe.

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
        ctx = ctx if ctx else {}
        return self.env['sale.order.line'].with_context(**ctx)._frepple_export()

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
        convert purchase.order.line.product_uom_qty - purchase.order.line.qty_received and
        purchase.order.line.product_uom -> operationplan.quantity
        purchase.order.date_planned -> operationplan.end
        purchase.order.date_planned -> operationplan.start
        'PO' -> operationplan.ordertype
        'confirmed' -> operationplan.status
        """
        po_line = {
            i["id"]: i
            for i in self.generator.getData(
                "purchase.order.line",
                search=[
                    "|",
                    (
                        "order_id.state",
                        "not in",
                        # Comment out on of the following alternative approaches:
                        # Alternative I: don't send RFQs to frepple because that supply isn't
                        # certain to be available yet.
                        ("draft", "sent", "bid", "confirmed", "cancel"),
                        # Alternative II: send RFQs to frepple to avoid that the same
                        # purchasing proposal is generated again by frepple.
                        # ("bid", "confirmed", "cancel"),
                    ),
                    ("order_id.state", "=", False),
                ],
                fields=[
                    "name",
                    "date_planned",
                    "product_id",
                    "product_qty",
                    "qty_received",
                    "product_uom",
                    "order_id",
                    "state",
                    "move_ids",
                ],
            )
        }

        # Get all purchase orders
        m = self.env["purchase.order"]
        po = {
            i["id"]: i
            for i in self.generator.getData(
                "purchase.order",
                ids=[j["order_id"][0] for j in po_line.values()],
                fields=["name", "company_id", "partner_id", "state", "date_order"],
            )
        }

        # Create purchasing operations from PO lines
        stock_move_ids = []
        yield "<!-- open purchase orders from PO lines -->\n"
        yield "<operationplans>\n"
        for i in po_line.values():
            if i["move_ids"]:
                # Use the stock move information rather than the po line
                stock_move_ids.extend(i["move_ids"])
                continue
            if not i["product_id"] or i["state"] == "cancel":
                continue
            item = self.product_product.get(i["product_id"][0], None)
            j = po[i["order_id"][0]]
            # if PO status is done, we should ignore this PO line
            if j["state"] == "done" or not item:
                continue

            location_name = \
                self.env['purchase.order'].browse(
                    j["id"]
                ).picking_type_id.warehouse_id.lot_stock_id.get_warehouse_stock_location().complete_name
            # location = self.mfg_location  # Original frePPLe code.
            if location_name and item and i["product_qty"] > i["qty_received"]:
                start = odoo_fields.Datetime.context_timestamp(m, j["date_order"]).strftime("%Y-%m-%dT%H:%M:%S")
                end = odoo_fields.Datetime.context_timestamp(m, i["date_planned"]).strftime("%Y-%m-%dT%H:%M:%S")

                qty = self.convert_qty_uom(
                    i["product_qty"] - i["qty_received"],
                    i["product_uom"][0],
                    i["product_id"][0],
                )
                yield '<operationplan reference=%s ordertype="PO" start="%s" end="%s"' \
                      ' quantity="%f" status="confirmed">' "<item name=%s/><location name=%s/>" \
                      "<supplier name=%s/></operationplan>\n" % (
                            quoteattr("%s - %s" % (j["name"], i["id"])),
                            start,
                            end,
                            qty,
                            quoteattr(item["name"]),
                            quoteattr(location_name),
                            quoteattr("%d %s" % (j["partner_id"][0], j["partner_id"][1])),
                        )
        yield "</operationplans>\n"

        # Create purchasing operations from stock moves
        if stock_move_ids:
            yield "<!-- open purchase orders from PO receipts-->\n"
            yield "<operationplans>\n"
            for i in self.generator.getData(
                "stock.move",
                ids=stock_move_ids,
                fields=[
                    "state",
                    "product_id",
                    "product_qty",
                    "quantity_done",
                    "reference",
                    "product_uom",
                    "location_dest_id",
                    "origin",
                    "picking_id",
                    "date",
                    "purchase_line_id",
                ],
            ):
                if (
                    not i["product_id"]
                    or not i["purchase_line_id"]
                    or not i["location_dest_id"]
                    or i["state"] in ("draft", "cancel", "done")
                ):
                    continue
                item = self.product_product.get(i["product_id"][0], None)
                if not item:
                    continue
                j = po[po_line[i["purchase_line_id"][0]]["order_id"][0]]
                # if PO status is done, we should ignore this receipt
                if j["state"] == "done":
                    continue
                location = self.env['purchase.order'].browse(
                    j["id"]
                ).picking_type_id.warehouse_id.lot_stock_id.get_warehouse_stock_location().complete_name
                if not location:
                    continue
                start = self.formatDateTime(j["date_order"])
                end = self.formatDateTime(i["date"])
                qty = i["quantity_done"] or i["product_qty"]
                if qty >= 0:
                    yield '<operationplan reference=%s ordertype="PO" start="%s" end="%s" quantity="%f"' \
                          ' status="confirmed">' "<item name=%s/><location name=%s/><supplier name=%s/>" \
                          "</operationplan>\n" % (
                                quoteattr(
                                    "%s - %s - %s" % (j["name"], i["picking_id"][1], i["id"])
                                ),
                                start,
                                end,
                                qty,
                                quoteattr(item["name"]),
                                quoteattr(location),
                                quoteattr("%d %s" % (j["partner_id"][0], j["partner_id"][1])),
                            )
            yield "</operationplans>\n"

    def export_manufacturingorders(self):
        """
        Extracting work in progress to frePPLe, using the mrp.production model.

        We extract workorders in the states 'in_production' and 'confirmed', and
        which have a bom specified.

        Mapping:
        mrp.production.bom_id mrp.production.bom_id.name @ mrp.production.location_dest_id ->
        operationplan.operation
        convert mrp.production.product_qty and mrp.production.product_uom -> operationplan.quantity
        mrp.production.date_planned -> operationplan.start
        '1' -> operationplan.status = "confirmed"
        """
        yield "<!-- manufacturing orders in progress -->\n"
        yield "<operationplans>\n"
        m = self.env["mrp.production"]
        sml = self.env["stock.move.line"]
        for i in self.generator.getData(
            "mrp.production",
            search=[("state", "not in", ["draft", "done", "cancel"])],
            fields=[
                "bom_id",
                "date_start",
                "date_planned_start",
                "date_planned_finished",
                "name",
                "state",
                "product_qty",
                "product_uom_id",
                "location_dest_id",
                "product_id",
                "move_raw_ids",
                "finished_move_line_ids",
            ],
        ):
            if i["bom_id"]:
                # Open orders
                location = self.map_locations.get(i["location_dest_id"][0], None)
                item = (
                    self.product_product[i["product_id"][0]]
                    if i["product_id"][0] in self.product_product
                    else None
                )
                if not item or not location:
                    continue

                operation_ids = [int(x.split(' ')[-1]) for x in self.operations]
                # Working with ids for bom_ids instead of with text, as it might lead to problems
                # due to changes in name_get for instance
                bom_id = i["bom_id"][0]
                if bom_id not in operation_ids:
                    continue
                operation_index = operation_ids.index(bom_id)
                operation = list(self.operations)[operation_index]

                startdate = i["date_start"] or i["date_planned_start"] or None
                if not startdate:
                    continue


                factor = (
                    self.bom_producedQty[(operation, item["name"])]
                    if (operation, i["name"]) in self.bom_producedQty
                    else 1
                )
                qty = (
                        self.convert_qty_uom(
                            i["product_qty"],
                            i["product_uom_id"][0],
                            self.product_product[i["product_id"][0]]["template"],
                        )
                        / factor
                )
                # qty would be here the qty to be produced. In case we already produced a part,
                # we should rather decrease it with the qty already produced
                if i["finished_move_line_ids"]:
                    move_lines = sml.browse(i["finished_move_line_ids"])
                    product_uom_qty = 0
                    for ml in move_lines:
                        product_uom_qty += (self.convert_qty_uom(ml.product_uom_qty, ml.product_uom_id.id,
                                                                 ml.product_id.id) / factor)
                    qty -= product_uom_qty
                    # in case qty <= 0 we should not output that MO at all
                    if qty <= 0:
                        continue

                location_dest = self.env['stock.location'].browse(i['location_dest_id'][0])
                # Option 1: compute MO end date based on the start date
                yield '''<operationplan type="MO" reference=%s start="%s" quantity="%s" status="confirmed">
                <operation name=%s/><location name=%s/>\n''' % (
                    quoteattr(i["name"]),
                    odoo_fields.Datetime.context_timestamp(m, startdate).strftime("%Y-%m-%dT%H:%M:%S"),
                    qty,
                    # "approved",  # In the "approved" status, frepple can still
                    # reschedule the MO in function of material and capacity
                    # "confirmed",  # In the "confirmed" status, frepple sees the MO as frozen and unchangeable
                    quoteattr(operation),
                    quoteattr(location_dest.get_warehouse_stock_location().complete_name)
                )
                # Option 2: compute MO start date based on the end date
                # yield '<operationplan type="MO" reference=%s end="%s" quantity="%s" status="%s">
                # <operation name=%s/><flowplans>\n' % (
                #     quoteattr(i["name"]),
                #     enddate,
                #     qty,
                #     # "approved",  # In the "approved" status, frepple can still
                #     reschedule the MO in function of material and capacity
                #     "confirmed",  # In the "confirmed" status, frepple sees the MO as frozen and unchangeable
                #     quoteattr(operation),
                # )
                yield "<flowplans>\n"
                for mv in self.generator.getData(
                        "stock.move",
                        ids=i["move_raw_ids"],
                        fields=[
                            "product_id",
                            "product_qty",
                            "product_uom",
                            "date",
                            "reference",
                            "move_line_ids",
                            "workorder_id",
                            "should_consume_qty",
                            "reserved_availability",
                        ],
                ):
                    item = (
                        self.product_product[mv["product_id"][0]]
                        if mv["product_id"][0] in self.product_product
                        else None
                    )
                    if not item:
                        continue

                    qty = mv["product_qty"] - ( mv["reserved_availability"] if self.respect_reservations else 0 )

                    yield '<flowplan status="confirmed" quantity="%s"><item name=%s/></flowplan>\n' % (
                        -qty,
                        quoteattr(item["name"]),
                    )
                yield "</flowplans></operationplan>\n"
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
        first = True
        for i in self.generator.getData(
            "stock.warehouse.orderpoint",
            fields=[
                "warehouse_id",
                "product_id",
                "product_min_qty",
                "product_max_qty",
                "product_uom",
                "qty_multiple",
            ],
        ):
            if first:
                yield "<!-- order points -->\n"
                yield "<calendars>\n"
                first = False
            item = self.product_product.get(
                i["product_id"] and i["product_id"][0] or 0, None
            )
            if not item:
                continue
            uom_factor = self.convert_qty_uom(
                1.0,
                i["product_uom"][0],
                self.product_product[i["product_id"][0]]["template"],
            )
            name = u"%s @ %s" % (item["name"], i["warehouse_id"][1])
            if i["product_min_qty"]:
                yield """
                <calendar name=%s default="0"><buckets>
                <bucket start="2000-01-01T00:00:00" end="2030-01-01T00:00:00" value="%s" days="127" priority="998"
                 starttime="PT0M" endtime="PT1440M"/>
                </buckets>
                </calendar>\n
                """ % (
                    (quoteattr("SS for %s" % (name,))),
                    (i["product_min_qty"] * uom_factor),
                )
            if i["product_max_qty"] - i["product_min_qty"] > 0:
                yield """
                <calendar name=%s default="0"><buckets>
                <bucket start="2000-01-01T00:00:00" end="2030-01-01T00:00:00" value="%s" days="127" priority="998"
                 starttime="PT0M" endtime="PT1440M"/>
                </buckets>
                </calendar>\n
                """ % (
                    (quoteattr("ROQ for %s" % (name,))),
                    ((i["product_max_qty"] - i["product_min_qty"]) * uom_factor),
                )
        if not first:
            yield "</calendars>\n"

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
        if isinstance(self.generator, Odoo_generator):
            # SQL query gives much better performance
            self.generator.env.cr.execute(
                "SELECT product_id, location_id, sum(quantity), sum(reserved_quantity) "
                "FROM stock_quant "
                "WHERE quantity > 0 "
                "GROUP BY product_id, location_id "
                "ORDER BY location_id ASC"
            )
            data = self.generator.env.cr.fetchall()
        else:
            data = [
                (i["product_id"][0], i["location_id"][0], i["quantity"])
                for i in self.generator.getData(
                    "stock.quant",
                    search=[("quantity", ">", 0)],
                    fields=[
                        "product_id",
                        "location_id",
                        "quantity",
                        "reserved_quantity",
                    ],
                )
                if i["product_id"] and i["location_id"]
            ]
        inventory = {}
        for i in data:
            item = self.product_product.get(i[0], None)
            location = self.map_locations.get(i[1], None)
            if item and location:
                inventory[(item["name"], location)] = (
                    inventory.get((item["name"], location), 0)
                    + i[2]
                    - (i[3] if self.respect_reservations else 0)
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
            if rule.route_id.warehouse_selectable:
                xml_str.append('<item name="All"/>')
            if rule.location_src_id:
                xml_str.append('<origin name={loc_name} subcategory="{loc_id}" description="location"/>'.format(
                    loc_name=quoteattr(rule.location_src_id.complete_name),
                    loc_id=rule.location_src_id.id))
            xml_str.append('<destination name={loc_name} subcategory="{loc_id}" description="location"/>'.format(
                loc_name=quoteattr(rule.location_id.complete_name),
                loc_id=rule.location_id.id))
            xml_str.append('<leadtime>P{}D</leadtime>'.format(rule.delay or 0))
            xml_str.append('</itemdistribution>')

        xml_str.append('</itemdistributions>')
        return '\n'.join(xml_str)

    def export_moves(self, ctx=None):
        """ Extracts the moves, according to the domain set on the res.company.
            Domains having the same location as From & To are discarded always.
        """
        if ctx is None:
            ctx = {}

        xml_str = [
            '<!-- Stock Moves -->',
            '<operationplans>',
        ]

        moves = self.env['stock.move'].search(
            ast.literal_eval(self.env.user.company_id.internal_moves_domain),
            order='id').filtered(lambda move: move.location_id != move.location_dest_id)
        if 'test_export_moves' in ctx:
            moves = moves.filtered(lambda move_line: move_line.reference.startswith(ctx['test_prefix']))

        # Status between stock.move in Odoo and in frePPLe differ.
        # The following dictionary maps Odoo's status into frePPLe's status.
        status_mapping = {
            'draft': 'proposed',
            'waiting': 'confirmed',
            'confirmed': 'confirmed',
            'partially_available': 'confirmed',
            'assigned': 'confirmed',
            'done': 'completed',
            'cancel': 'closed',
        }

        for move in moves:
            product = move.product_id
            ref_uom_for_uom_category_id = self.uom_categories[
                self.uom[product.product_tmpl_id.uom_id.id]['category']]
            location_origin = move.location_id.get_warehouse_stock_location()
            location_dest = move.location_dest_id.get_warehouse_stock_location()

            # frepple cannot work with DOs having the same origin and destination, so skip those
            if location_origin == location_dest:
                continue

            # We do this to ensure a matching between the outgoing and the incoming software.
            if not move.frepple_reference:
                move.frepple_reference = move.id

            xml_str.append(
                '<operationplan '
                'ordertype="DO" '
                'reference="{reference}" '
                'start="{start}" '
                'quantity="{quantity}" '
                'status="{status}">'.format(
                    reference=move.frepple_reference,
                    start=odoo_fields.Datetime.context_timestamp(
                        move, move.date
                    ).strftime("%Y-%m-%dT%H:%M:%S"),
                    quantity=move.product_uom_qty,
                    status=status_mapping.get(move.state, 'closed')))
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


if __name__ == "__main__":
    #
    # When calling this script directly as a Python file, the connector uses XMLRPC
    # to connect to odoo and download all data.
    #
    # This is useful for debugging connector updates remotely, when you don't have
    # direct access to the odoo server itself.
    # This mode of working is not recommended for production use because of performance
    # considerations.
    #
    #  EXPERIMENTAL FEATURE!!!
    #
    import argparse

    parser = argparse.ArgumentParser(description="Debug frepple odoo connector")
    parser.add_argument(
        "--url", help="URL of the odoo server", default="http://localhost:8069"
    )
    parser.add_argument("--db", help="Odoo database to connect to", default="odoo14")
    parser.add_argument(
        "--username", help="User name for the odoo connection", default="admin"
    )
    parser.add_argument(
        "--password", help="User password for the odoo connection", default="admin"
    )
    parser.add_argument(
        "--company", help="Odoo company to use", default="My Company (Chicago)"
    )
    parser.add_argument(
        "--timezone", help="Time zone to convert odoo datetime fields to", default="UTC"
    )
    parser.add_argument(
        "--singlecompany",
        default=False,
        help="Limit the data to a single company only.",
        action="store_true",
    )
    args = parser.parse_args()

    generator = XMLRPC_generator(args.url, args.db, args.username, args.password)
    xp = exporter(
        generator,
        None,
        uid=generator.uid,
        database=generator.db,
        company=args.company,
        mode=1,
        timezone=args.timezone,
        singlecompany=True,
    )
    for i in xp.run():
        print(i, end="")
