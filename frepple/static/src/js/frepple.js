/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, xml, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class Quotes extends Component {
  setup() {
    this.orm = useService("orm");
    onWillStart(async () => {
      this.freppleURL = await this.orm.call(
        "res.company", "getFreppleURL", [false, '/quote/']
      );
    });
  }

  static template = xml`<iframe t-att-src="freppleURL" width="100%"
     height="100%" marginwidth="0" marginheight="0" frameborder="no"
     scrolling="yes" style="border-width:0px;"/>`;
}
registry.category("actions").add('frepple.quotes', Quotes);

class ApsServiceInfo extends Component {
  static template = xml`
    <div class="o_action" style="display:flex;align-items:center;justify-content:center;height:100%;padding:2rem;">
      <div style="max-width:900px;text-align:center;">
        <div style="margin-bottom:1rem;">
          <img src="https://frepple.com/docs/current/_images/aps_service.png" style="width:100%;height:auto;" alt="APS service"/>
        </div>
        <h2 class="mb-4">Advanced Planning and Scheduling Service</h2>
        <p class="mb-3" style="font-size:1.1rem;">
          This Odoo instance is connected to the Advanced Planning and Scheduling (APS) cloud service provided by frePPLe. It
          computes planning recommendations but has no user interface.
        </p>
        <p class="mb-3" style="font-size:1.1rem;">
          If you want the complete APS experience (with more detailed reports, plan analysis screens, interactive planning capabilities, etc...), you need a
          dedicated frePPLe instance, either:
        </p>
        <ul class="text-start mb-4" style="font-size:1.05rem;display:inline-block;">
          <li class="mb-2">frePPLe Community Edition — a free, self-hosted open-source option.</li>
          <li class="mb-2">frePPLe Enterprise / Cloud Edition — a fully managed instance with advanced features and support.</li>
        </ul>
        <p style="font-size:1.05rem;">
          Visit <a href="https://frepple.com" target="_blank" rel="noopener noreferrer">frepple.com</a>
          for more information.
        </p>
      </div>
    </div>`;
}
registry.category("actions").add('frepple.aps_service_info', ApsServiceInfo);

