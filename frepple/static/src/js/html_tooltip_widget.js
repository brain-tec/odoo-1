/** @odoo-module **/
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class HtmlTooltipField extends Component {
    static template = xml`
        <div class="o_field_html_hover"
             t-on-mouseenter="onMouseEnter"
             t-on-mouseleave="onMouseLeave"
             style="cursor: pointer; display: inline-block; max-width: 100%; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
            <t t-out="props.record.data[props.name] || ''"/>
        </div>
    `;

    setup() {
        this.popoverService = useService("popover");
        this.removePopover = null;
        this.closeTimer = null;
    }

    onMouseEnter(ev) {
        // Clear any pending close timer
        if (this.closeTimer) {
            clearTimeout(this.closeTimer);
            this.closeTimer = null;
        }

        const content = this.props.record.data[this.props.name];

        if (content) {
            if (!this.removePopover) {
                this.removePopover = this.popoverService.add(
                    ev.currentTarget,
                    HtmlTooltipContent,
                    { htmlContent: content },
                    { position: "top" }
                );
            }
        }
    }

    onMouseLeave() {
        this.closeTimer = setTimeout(() => {
            if (this.removePopover) {
                this.removePopover();
                this.removePopover = null;
            }
        }, 100);
    }
}

class HtmlTooltipContent extends Component {
    static template = xml`
        <div class="p-3 shadow border bg-view o_html_popover" style="max-width: 450px; max-height: 350px; overflow-y: auto; font-size: 13px;">
            <t t-out="props.htmlContent"/>
        </div>
    `;
}
HtmlTooltipContent.props = ["htmlContent"];

HtmlTooltipField.props = { ...standardFieldProps };

registry.category("fields").add("html_hover", {
    component: HtmlTooltipField,
    supportedTypes: ["html", "text", "char"],
});
