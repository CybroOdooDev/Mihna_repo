/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";

export class PayslipListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    async onClickPayRun() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Payslips Batches',
            res_model: 'hr.payslip.run',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new'
        });
    }
}

export const payslipListView = {
    ...listView,
    Controller: PayslipListController,
    buttonTemplate: "hr_payroll_community.ListView.Buttons",
};

registry.category("views").add("hr_payslip_list", payslipListView);
