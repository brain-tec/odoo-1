/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";


class FreppleRecommendationDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            purchase: [],
            mrp: [],
            sale: [],
            stock: [],
            selected: new Set(),
            lastRunDate: null,
        });

        onWillStart(async () => {
            await this._load();
        });

        hasRunningJob: false
    }

    formatDate(dateStr) {
        if (!dateStr) return "";
        const d = new Date(dateStr);
        return d.toLocaleString(); // user locale
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

      // Read the active companies, used to filter data in the orm calls
      const activeCompanyIds = user.activeCompanies.map((c) => c.id);

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
            [["type", "=", "purchase"],
             ["company_id", "in", activeCompanyIds]],
             fields
        );

        //split description and assign to state
        for (const r of purchase) {
            const d = splitDescription(r.description);
            r.desc_first = d.first;
            r.desc_rest = d.rest;
        }
        this.state.purchase = purchase;


        // Extract partner from JSON
        const partnerIds = [];
        for (const r of purchase) {
            if (r.data) {
                try {

                        r.partner_id = r.data.partner_id;
                        partnerIds.push(r.data.partner_id);

                } catch(e) {
                    // ignore invalid JSON
                    console.error('Invalid JSON:', e);
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
            if (r.partner_id) {
                r.partner_name = partnersById[r.partner_id] || "";
            }
        }

        this.state.purchase = purchase;

        // OTHER TABS
        this.state.mrp = await this.orm.searchRead(
            "frepple.recommendation",
            [["type", "=", "mrp"],
             ["company_id", "in", activeCompanyIds]],
            fields
        );
        this.state.sale = await this.orm.searchRead(
            "frepple.recommendation",
            [["type", "=", "sale"],
             ["company_id", "in", activeCompanyIds]],
            fields
        );
        this.state.stock = await this.orm.searchRead(
            "frepple.recommendation",
            [["type", "=", "stock"],
             ["company_id", "in", activeCompanyIds]],
            fields
        );

        this.state.selected.clear();


        // ------------------------------------------------------------
        // LAST FREPPLE RUN DATE
        // ------------------------------------------------------------

        const jobs = await this.orm.searchRead(
            "frepple.job",
            [["status", "=", "done"],
             ["company_id", "in", activeCompanyIds]],
            ["finished"],
            {
                order: "finished desc",
                limit: 1,
            }
        );

        this.state.lastRunDate = jobs.length ? jobs[0].finished : null;

        await this._checkRunningJobs();
    }

    // Read running jobs for the Refresh button
    async _checkRunningJobs() {
        const activeCompanyIds = user.activeCompanies.map((c) => c.id);

        if (!activeCompanyIds.length) {
            this.state.hasRunningJob = false;
            return;
        }

        const jobs = await this.orm.searchRead(
            "frepple.job",
            [
                ["status", "=", "Waiting for results"],
                ["company_id", "in", activeCompanyIds],
            ],
            ["id"],
            { limit: 1 }
        );

        this.state.hasRunningJob = jobs.length > 0;
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

    // Refresh recommendations
    async refreshRecommendations() {
      const activeCompanyIds = user.activeCompanies.map((c) => c.id);

      if (activeCompanyIds.length !== 1) {
          this.action.doAction({
            type: "ir.actions.client",
            tag: "display_notification",
            params: {
                title: "Invalid company selection",
                message: "Please select exactly one company to refresh or cancel recommendations.",
                type: "danger",
            },
        });
        return;
      }

      const companyId = activeCompanyIds[0];

      try {

          if (this.state.hasRunningJob) {
            // CANCEL JOB
            await this.orm.call(
                "frepple.job",
                "action_cancel_all",
                [companyId]
            );
        } else {

          await fetch("/frepple/submit", {
              method: "POST",
              headers: {
                  "Content-Type": "application/json",
                  "X-Openerp-CSRFToken": odoo.csrf_token,
              },
              body: JSON.stringify({
                  "company_id": companyId,
              }),
          });

        }

          // Reload dashboard data
          await this._load();

      } catch (err) {
          this.notification.add(
              "Failed to refresh recommendations.",
              { type: "danger" }
          );
          console.error(err);
      }
  }

}

FreppleRecommendationDashboard.template = "frepple.RecommendationDashboard";

registry.category("actions").add(
    "frepple_recommendation_dashboard",
    FreppleRecommendationDashboard
);
