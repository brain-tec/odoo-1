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
          purchase: { page: 1, pageSize: 100, total: 0, sortField: 'id', sortAsc: true },
          mrp: { page: 1, pageSize: 100, total: 0, sortField: 'id', sortAsc: true },
          sale: { page: 1, pageSize: 100, total: 0, sortField: 'id', sortAsc: true },
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
        const order = `${pageInfo.sortField} ${pageInfo.sortAsc ? 'asc' : 'desc'}`;

        // Get total count for pagination
        const total = await this.orm.searchCount("frepple.recommendation", [
            ["tab", "=", tabName],
            ["company_id", "in", activeCompanyIds],
        ]);

        this.state.pagination[tabName].total = total;

        return await this.orm.searchRead(
            "frepple.recommendation",
            [["tab", "=", tabName], ["company_id", "in", activeCompanyIds]],
            fields,
            { offset: offset, limit: pageInfo.pageSize, order: order }
        );
    };

    // Load each tab
    this.state.purchase = await loadTab("purchase", ["product_id", "res_partner_id", "quantity", "startdate", "enddate", "description"]);
    this.state.mrp = await loadTab("mrp", ["mrp_production_id", "product_id", "quantity", "startdate", "enddate", "description"]);
    this.state.sale = await loadTab("sale", ["product_id", "sale_order_id", "quantity", "startdate", "enddate", "description"]);

    // Clear selections on reload
    this.state.selected.clear();

    // ------------------------------------------------------------
    // LAST FREPPLE RUN DATE
    // ------------------------------------------------------------

    const jobs = await this.orm.searchRead("frepple.job", [["status", "=", "done"], ["company_id", "in", activeCompanyIds]], ["finished"], { order: "finished desc", limit: 1 });
    this.state.lastRunDate = jobs.length ? jobs[0].finished : null;
    // Check for running jobs
    await this._checkRunningJobs();
  }

// Read running jobs for the Refresh button
async _checkRunningJobs() {
    const activeCompanyIds = user.activeCompanies.map((c) => c.id);
    if (!activeCompanyIds.length) { this.state.hasRunningJob = false; return; }
    const jobs = await this.orm.searchRead("frepple.job", [["status", "=", "Waiting for results"], ["company_id", "in", activeCompanyIds]], ["id"], { limit: 1 });
    this.state.hasRunningJob = jobs.length > 0;
  }

  // NAVIGATION
  openProduct(id) { this.action.doAction({ type: "ir.actions.act_window", res_model: "product.product", res_id: id, views: [[false, "form"]], target: "current" }); }
  openSaleOrder(id) { this.action.doAction({ type: "ir.actions.act_window", res_model: "sale.order", res_id: id, views: [[false, "form"]], target: "current" }); }
  openPartner(id) { this.action.doAction({ type: "ir.actions.act_window", res_model: "res.partner", res_id: id, views: [[false, "form"]], target: "current" }); }
  openManufacturingOrder(id) { this.action.doAction({ type: "ir.actions.act_window", res_model: "mrp.production", res_id: id, views: [[false, "form"]], target: "current" }); }

  // PAGING & SORTING
  prevPage(tab) { if (this.state.pagination[tab].page > 1) { this.state.pagination[tab].page -= 1; this._load(); } }
  nextPage(tab) { const p = this.state.pagination[tab]; if (p.page < Math.ceil(p.total / p.pageSize)) { p.page += 1; this._load(); } }

  setSort(tabName, fieldName) {
    const tab = this.state.pagination[tabName];
    if (tab.sortField === fieldName) { tab.sortAsc = !tab.sortAsc; }
    else { tab.sortField = fieldName; tab.sortAsc = true; }
    this._load();
  }

  // SELECTION
  toggleSelection(id) { if (this.state.selected.has(id)) this.state.selected.delete(id); else this.state.selected.add(id); }
  isSelected(id) { return this.state.selected.has(id); }
  toggleSelectAll(recs) {
    const all = recs.every(r => this.state.selected.has(r.id));
    recs.forEach(r => all ? this.state.selected.delete(r.id) : this.state.selected.add(r.id));
  }
  areAllSelected(recs) { return recs.length > 0 && recs.every(r => this.state.selected.has(r.id)); }

  // ACTIONS
  async approveRecommendation(id) { this._removeFromState(id); await this.orm.call("frepple.recommendation", "action_approve", [[id]]); this.state.selected.delete(id); }
  async bulkApprove() {
    const ids = Array.from(this.state.selected);
    ids.forEach(id => this._removeFromState(id));
    await this.orm.call("frepple.recommendation", "action_approve", [ids]);
    this.state.selected.clear();
  }
  _removeFromState(id) {
    this.state.purchase = this.state.purchase.filter(r => r.id !== id);
    this.state.mrp = this.state.mrp.filter(r => r.id !== id);
    this.state.sale = this.state.sale.filter(r => r.id !== id);
  }

  async refreshRecommendations() {
    const activeCompanyIds = user.activeCompanies.map((c) => c.id);
    if (activeCompanyIds.length !== 1) {
      this.action.doAction({ type: "ir.actions.client", tag: "display_notification", params: { title: "Invalid selection", message: "Select exactly one company.", type: "danger" } });
      return;
    }
    try {
      await this.orm.call("frepple.job", this.state.hasRunningJob ? "action_cancel_all" : "action_launch", [activeCompanyIds[0]]);
      await this._load();
    } catch (err) { this.notification.add("Action failed.", { type: "danger" }); }
  }
}

FreppleRecommendationDashboard.template = "frepple.RecommendationDashboard";
registry.category("actions").add("frepple_recommendation_dashboard", FreppleRecommendationDashboard);
