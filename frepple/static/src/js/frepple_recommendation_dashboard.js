/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { markup } from "@odoo/owl";

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
      hasRunningJob: false,
       // Pagination per tab
      pagination: {
          purchase: { page: 1, pageSize: 100, total: 0 },
          mrp: { page: 1, pageSize: 100, total: 0 },
          sale: { page: 1, pageSize: 100, total: 0 },
      },
    });

    onWillStart(async () => {
      await this._load();
    });
  }

  formatDate(dateStr) {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    return d.toLocaleString(); // user locale
  }

  formatDescription(desc) {
    if (!desc) return { first: "", rest: "" };

    // IMPORTANT: split on literal "\n"
    const lines = desc.split("\\n");
    const firstline = lines[0];
    const restlines = lines.slice(1).join("\n");
    return markup(
      `<div class="o_reco_desc_first">${firstline}</div>` +
      (restlines ? `<div class="o_reco_desc_rest">${restlines}</div>` : ""));
  }

  // ------------------------------------------------------------
  // DATA LOADING
  // ------------------------------------------------------------
  async _load() {

    // Read the active companies, used to filter data in the orm calls
    const activeCompanyIds = user.activeCompanies.map((c) => c.id);

    const loadTab = async (tabName, fields) => {
        const pageInfo = this.state.pagination[tabName];
        const offset = (pageInfo.page - 1) * pageInfo.pageSize;

        // Get total count for pagination
        const total = await this.orm.searchCount("frepple.recommendation", [
            ["tab", "=", tabName],
            ["company_id", "in", activeCompanyIds],
        ]);

        this.state.pagination[tabName] = {
        ...pageInfo,
        total: total,
        };

        // Fetch only current page
        return await this.orm.searchRead(
            "frepple.recommendation",
            [
                ["tab", "=", tabName],
                ["company_id", "in", activeCompanyIds],
            ],
            fields,
            {
                offset: offset,
                limit: pageInfo.pageSize,
                order: undefined, // you can add sorting later
            }
        );
    };

    // Load each tab
    this.state.purchase = await loadTab("purchase", [
        "product_id",
        "res_partner_id",
        "quantity",
        "startdate",
        "enddate",
        "description",
    ]);

    this.state.mrp = await loadTab("mrp", [
        "mrp_production_id",
        "product_id",
        "quantity",
        "startdate",
        "enddate",
        "description",
    ]);

    this.state.sale = await loadTab("sale", [
        "product_id",
        "sale_order_id",
        "quantity",
        "startdate",
        "enddate",
        "description",
    ]);

    // Clear selections on reload
    this.state.selected.clear();

    // ------------------------------------------------------------
    // LAST FREPPLE RUN DATE
    // ------------------------------------------------------------
    const jobs = await this.orm.searchRead(
        "frepple.job",
        [
            ["status", "=", "done"],
            ["company_id", "in", activeCompanyIds],
        ],
        ["finished"],
        {
            order: "finished desc",
            limit: 1,
        }
    );

    this.state.lastRunDate = jobs.length ? jobs[0].finished : null;

    // Check for running jobs
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
  openProduct(theId) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "product.product",
      res_id: theId,
      views: [[false, "form"]],
      target: "current",
    });
  }

  openSaleOrder(theId) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "sale.order",
      res_id: theId,
      views: [[false, "form"]],
      target: "current",
    });
  }

  openPartner(theId) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "res.partner",
      res_id: theId,
      views: [[false, "form"]],
      target: "current",
    });
  }

  openManufacturingOrder(theId) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "mrp.production",
      res_id: theId,
      views: [[false, "form"]],
      target: "current",
    });
  }

  prevPage(tabName) {
    if (this.state.pagination[tabName].page > 1) {
        this.state.pagination[tabName].page -= 1;
        this._load();
    }
  }

  nextPage(tabName) {
      const pageInfo = this.state.pagination[tabName];
      const maxPage = Math.ceil(pageInfo.total / pageInfo.pageSize);
      if (pageInfo.page < maxPage) {
          pageInfo.page += 1;
          this._load();
      }
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
