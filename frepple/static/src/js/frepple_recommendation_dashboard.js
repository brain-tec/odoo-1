/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class FreppleRecommendationDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = {
            purchase: [],
            mrp: [],
            sale: [],
            stock: [],
        };

        onWillStart(async () => {
            await this._load();
        });
    }

async _load() {
    const fields = [
        "product_id",
        "quantity",
        "startdate",
        "enddate",
        "description",
        "data",
    ];

    const purchase = await this.orm.searchRead(
        "frepple.recommendation",
        [["type", "=", "purchase"]],
        fields
    );

    // 🔹 Extract partner_ids
    const partnerIds = [];
    for (const r of purchase) {
        if (r.data) {
            try {
                const parsed = JSON.parse(r.data);
                if (parsed.partner_id) {
                    r.supplier_id = parsed.partner_id;
                    partnerIds.push(parsed.partner_id);
                }
            } catch (e) {
                // ignore invalid JSON
            }
        }
    }

    // 🔹 Fetch partner names
    let partnersById = {};
    if (partnerIds.length) {
        const partners = await this.orm.searchRead(
            "res.partner",
            [["id", "in", partnerIds]],
            ["name"]
        );
        for (const p of partners) {
            partnersById[p.id] = p.name;
        }
    }

    // 🔹 Attach supplier_name to records
    for (const r of purchase) {
        if (r.supplier_id) {
            r.supplier_name = partnersById[r.supplier_id] || "";
        }
    }

    // Assign to state
    this.state.purchase = purchase;

    // Other tabs unchanged
    this.state.mrp = await this.orm.searchRead(
        "frepple.recommendation",
        [["type", "=", "mrp"]],
        fields
    );
    this.state.sale = await this.orm.searchRead(
        "frepple.recommendation",
        [["type", "=", "sale"]],
        fields
    );
    this.state.stock = await this.orm.searchRead(
        "frepple.recommendation",
        [["type", "=", "stock"]],
        fields
    );
}


    openProduct(productId) {
    this.action.doAction({
        type: "ir.actions.act_window",
        res_model: "product.product",
        res_id: productId,
        views: [[false, "form"]],
        target: "current",
    });
}

openPartner(partnerId) {
    this.action.doAction({
        type: "ir.actions.act_window",
        res_model: "res.partner",
        res_id: partnerId,
        views: [[false, "form"]],
        target: "current",
    });
}



}

FreppleRecommendationDashboard.template = "frepple.RecommendationDashboard";

registry.category("actions").add(
    "frepple_recommendation_dashboard",
    FreppleRecommendationDashboard
);
