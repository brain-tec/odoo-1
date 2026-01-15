/** @odoo-module **/
import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillDestroy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class FreppleRecommendationBanner extends Component {
  static template = "frepple.RecommendationBanner";

  setup() {
    this.orm = useService("orm");
    this.notification = useService("notification");

    this.state = useState({
      message: "Loading...",
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
      // TODO avoid hardcoded company id
      const data = await this.orm.call("frepple.job", "get_status", [1]);
      this.state.message = data.message;
    } catch (error) {
      this.state.message = "Connection lost...";
    }
  }

  startTimer() {
    this.timer = setInterval(() => this.fetchData(), 5000);
  }

  async onButtonClick() {
    try {
      // TODO avoid hardcoded company id
      await this.orm.call("frepple.job", "action_launch", [1]);
      this.notification.add("Process started successfully!", {
        type: "success",
      });
    } catch (error) {
      this.notification.add("Action failed", { type: "danger" });
    }
  }

}

export class FreppleListController extends ListController {
  static components = { ...ListController.components, FreppleRecommendationBanner };
}

registry.category("views").add("frepple_recommendation_list", {
  ...registry.category("views").get("list"),
  Controller: FreppleListController,
});
