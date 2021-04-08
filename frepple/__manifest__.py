# -*- coding: utf-8 -*-
{
    "name": "frepple",
    "version": "13.0.6.7.3",
    "category": "Manufacturing",
    "summary": "Advanced planning and scheduling",
    "author": "frePPLe, brain-tec AG",
    "website": "https://frepple.com",
    "license": "AGPL-3",
    "description": "Connector to frePPLe - finite capacity planning and scheduling",
    "depends": [
        "product",
        "purchase",
        "sale",
        "sale_stock",
        "resource",
        "mrp",
        'stock',
        "uom",
    ],
    "external_dependencies": {"python": ["pyjwt"]},
    "data": [
        "data/mrp_routing.xml",
        "security/frepple_security.xml",
        "security/ir.model.access.csv",
        "views/frepple_data.xml",
        "views/res_company.xml",
        "views/res_config_settings_views.xml",
        "views/mrp_skill.xml",
        "views/mrp_workcenter_inherit.xml",
        "views/mrp_workcenter_skill.xml",
        "views/mrp_routing_workcenter_inherit.xml",
        "views/mrp_production.xml",
        "views/stock_picking_views.xml",
        "views/purchase_order_views.xml",
    ],
    "demo": ["data/demo.xml"],
    "test": [],
    "installable": True,
    "auto_install": False,
}
