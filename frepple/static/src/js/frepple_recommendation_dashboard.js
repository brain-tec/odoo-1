/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class FreppleRecommendationDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            purchase: [],
            mrp: [],
            sale: [],
            stock: [],
            selected: new Set(),
        });

        onWillStart(async () => {
            await this._load();
        });
    }

    // ------------------------------------------------------------
    // DATA LOADING
    // ------------------------------------------------------------
    async _load() {

      // smaller font for the second line
      function splitDescription(desc) {
        if (!desc) {
            return { first: "", rest: "" };
        }

        // IMPORTANT: split on literal "\n"
        const lines = desc.split("\\n");

        return {
            first: lines[0],
            rest: lines.slice(1).join("\n"),
        };
}



      const fields = [
            "product_id",
            "quantity",
            "startdate",
            "enddate",
            "description",
            "data",
        ];

        // PURCHASE
        const purchase = await this.orm.searchRead(
            "frepple.recommendation",
            [["type", "=", "purchase"]],
            fields
        );

        //split description and assign to state
        for (const r of purchase) {
            const d = splitDescription(r.description);
            r.desc_first = d.first;
            r.desc_rest = d.rest;
        }
        this.state.purchase = purchase;


        // Extract supplier from JSON
        const partnerIds = [];
        for (const r of purchase) {
            if (r.data) {
                try {
                    const parsed = JSON.parse(r.data);
                    if (parsed.partner_id) {
                        r.supplier_id = parsed.partner_id;
                        partnerIds.push(parsed.partner_id);
                    }
                } catch {
                    // ignore invalid JSON
                }
            }
        }

        // Fetch partner names
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

        for (const r of purchase) {
            if (r.supplier_id) {
                r.supplier_name = partnersById[r.supplier_id] || "";
            }
        }

        this.state.purchase = purchase;

        // OTHER TABS
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

        this.state.selected.clear();
    }

    // ------------------------------------------------------------
    // NAVIGATION
    // ------------------------------------------------------------
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

    // ------------------------------------------------------------
    // SELECTION LOGIC
    // ------------------------------------------------------------
    toggleSelection(recId) {
        if (this.state.selected.has(recId)) {
            this.state.selected.delete(recId);
        } else {
            this.state.selected.add(recId);
        }
    }

    isSelected(recId) {
        return this.state.selected.has(recId);
    }

    toggleSelectAll(records) {
        const allSelected = records.every(r =>
            this.state.selected.has(r.id)
        );

        for (const r of records) {
            if (allSelected) {
                this.state.selected.delete(r.id);
            } else {
                this.state.selected.add(r.id);
            }
        }
    }

    areAllSelected(records) {
    if (!records.length) {
        return false;
    }
    return records.every(r => this.state.selected.has(r.id));
}

    clearSelection() {
        this.state.selected.clear();
    }

    // ------------------------------------------------------------
    // APPROVAL
    // ------------------------------------------------------------
    async approveRecommendation(recId) {
        this._removeFromState(recId);
        await this.orm.call(
            "frepple.recommendation",
            "action_approve",
            [[recId]]
        );
        this.state.selected.delete(recId);
    }

    async bulkApprove() {
        const ids = Array.from(this.state.selected);
        if (!ids.length) return;

        for (const id of ids) {
            this._removeFromState(id);
        }

        await this.orm.call(
            "frepple.recommendation",
            "action_approve",
            [ids]
        );

        this.clearSelection();
    }

    _removeFromState(recId) {
        this.state.purchase = this.state.purchase.filter(r => r.id !== recId);
        this.state.mrp = this.state.mrp.filter(r => r.id !== recId);
        this.state.sale = this.state.sale.filter(r => r.id !== recId);
        this.state.stock = this.state.stock.filter(r => r.id !== recId);
    }
}

FreppleRecommendationDashboard.template = "frepple.RecommendationDashboard";

registry.category("actions").add(
    "frepple_recommendation_dashboard",
    FreppleRecommendationDashboard
);
