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

class AnonymousServerInfo extends Component {
  static template = xml`
    <div class="o_action" style="display:flex;align-items:center;justify-content:center;height:100%;padding:2rem;">
      <div style="max-width:700px;text-align:center;">
        <div style="position:relative;display:inline-block;width:80px;height:80px;margin-bottom:1rem;">
          <img src="https://frepple.com/wp-content/uploads/frepple.svg" style="width:80px;height:80px;" alt="frePPLe logo"/>
          <svg viewBox="0 0 100 100" style="position:absolute;top:0;left:0;width:80px;height:80px;">
            <circle cx="50" cy="50" r="46" fill="none" stroke="#dc3545" stroke-width="6"/>
            <line x1="15" y1="85" x2="85" y2="15" stroke="#dc3545" stroke-width="6"/>
          </svg>
        </div>
        <h2 class="mb-4">Anonymous frePPLe Server</h2>
        <p class="mb-3" style="font-size:1.1rem;">
          This Odoo instance is connected to the anonymous frePPLe server
          (https://odoo.frepple.com), which is a shared environment computing recommendations
          for demonstration and evaluation purposes.
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
registry.category("actions").add('frepple.anonymous_server_info', AnonymousServerInfo);

