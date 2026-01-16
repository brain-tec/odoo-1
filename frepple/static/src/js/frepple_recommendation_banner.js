/** @odoo-module **/
import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillDestroy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

export class FreppleRecommendationBanner extends Component {
  static template = "frepple.RecommendationBanner";

  setup() {
    this.orm = useService("orm");
    this.notification = useService("notification");

    this.state = useState({
      message: "Loading...",
      isRunning: false, // track if a job is running
    });

    this.timer = null;

    onWillStart(async () => {
      await this.fetchData();
      this.startTimer();
    });

    onWillDestroy(() => {
      clearInterval(this.timer);
    });
  }

  async fetchData() {
    try {
      // session.user_context contains the same info as the user service
      const userContext = this.env.services.user?.context || session.user_context || {};
      const companyId = userContext.allowed_company_ids ? userContext.allowed_company_ids[0] : (session.company_id || 1);

      const data = await this.orm.call("frepple.job", "get_status", [companyId]);
      this.state.message = data.message;
      this.state.isRunning = data.is_running;
    } catch (error) {
      this.state.message = error;
    }
  }

  startTimer() {
    this.timer = setInterval(() => this.fetchData(), 5000);
  }

  async onButtonClick() {
    const userContext = this.env.services.user?.context || session.user_context || {};
    const companyId = userContext.allowed_company_ids ? userContext.allowed_company_ids[0] : (session.company_id || 1);
    try {
      if (this.state.isRunning) {
        // Logic to cancel the job
        await this.orm.call("frepple.job", "action_cancel_all", [companyId]);
        this.notification.add("Stopping process...", { type: "warning" });
      } else {
        await this.orm.call("frepple.job", "action_launch", [companyId]);
        this.notification.add("Process started successfully!", {
          type: "success",
        });
      }
      // Refresh data immediately after click
      await this.fetchData();
    } catch (error) {
      this.notification.add("Action failed", { type: "danger" });
    }
  }

}

export class FreppleListController extends ListController {
  static template = "frepple.ListView";
  static components = { ...ListController.components, FreppleRecommendationBanner };
}

registry.category("views").add("frepple_recommendation_list", {
  ...registry.category("views").get("list"),
  Controller: FreppleListController,
});
