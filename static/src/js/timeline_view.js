/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class HistoryTimeline extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            items: [],
            filter: "All",
            loading: true,
        });

        onWillStart(async () => {
            let employeeId = false;
            if (this.props.record && this.props.record.resId) {
                employeeId = this.props.record.resId;
            }
            
            if (employeeId) {
                const data = await this.orm.call("hr.employee", "get_employee_history_timeline", [employeeId]);
                this.state.items = data;
            }
            this.state.loading = false;
        });
    }

    get filteredItems() {
        if (this.state.filter === "All") {
            return this.state.items;
        }
        return this.state.items.filter(item => item.category === this.state.filter);
    }
}

HistoryTimeline.template = "history_employee.TimelineView";
registry.category("view_widgets").add("history_employee_timeline", {
    component: HistoryTimeline,
});
