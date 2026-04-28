/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class FreppleLaunchDialog extends Component {
  static template = "frepple.LaunchDialog";
  static components = { Dialog };
  static props = {
    companies: { type: Array },
    defaultCompanyId: { type: Number },
    close: { type: Function },
    onConfirm: { type: Function },
  };

  setup() {
    const initialCompanyId = this.props.companies.length === 1
      ? this.props.companies[0].id
      : this.props.defaultCompanyId;
    this.state = useState({
      capacity: true,
      mfgLeadTime: true,
      poLeadTime: true,
      companyId: initialCompanyId,
    });
  }

  get isAnonymousServer() {
    const company = this.props.companies.find(c => c.id === this.state.companyId);
    const server = (company && company.frepple_server || "").replace(/\/+$/, "").toLowerCase();
    return server === "https://odoo.frepple.com";
  }

  onConfirm() {
    this.props.onConfirm({
      capacity: this.state.capacity,
      mfgLeadTime: this.state.mfgLeadTime,
      poLeadTime: this.state.poLeadTime,
      companyId: this.state.companyId,
    });
    this.props.close();
  }

  onCancel() {
    this.props.close();
  }

  onCapacityChange(ev) {
    this.state.capacity = ev.target.checked;
  }

  onMfgLeadTimeChange(ev) {
    this.state.mfgLeadTime = ev.target.checked;
  }

  onPoLeadTimeChange(ev) {
    this.state.poLeadTime = ev.target.checked;
  }

  onCompanyChange(ev) {
    this.state.companyId = parseInt(ev.target.value);
  }
}
