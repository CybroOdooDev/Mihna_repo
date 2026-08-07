/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
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

        onWillStart(() => this.loadHistory(this.props.record));

        // The pager (Next/Previous) swaps this.props.record for a new
        // employee without recreating this component, so the timeline
        // must explicitly refetch whenever the underlying record changes -
        // otherwise it keeps showing the previously viewed employee's data.
        onWillUpdateProps((nextProps) => {
            const currentId = this.props.record && this.props.record.resId;
            const nextId = nextProps.record && nextProps.record.resId;
            if (nextId !== currentId) {
                this.loadHistory(nextProps.record);
            }
        });
    }

    async loadHistory(record) {
        this.state.loading = true;
        const employeeId = record && record.resId;
        this.state.items = employeeId
            ? await this.orm.call("hr.employee", "get_employee_history_timeline", [employeeId])
            : [];
        this.state.loading = false;
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
