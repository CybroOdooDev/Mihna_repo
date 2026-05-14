/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

const { DateTime } = luxon;

patch(TicketScreen.prototype, {
    async onDoRefund() {
        const order = this.getSelectedOrder();
        if (order) {
            const returnPeriod = this.pos.config.return_period;
            if (returnPeriod && returnPeriod > 0) {
                const orderDate = order.date_order.startOf('day');
                const today = DateTime.now().startOf('day');
                const diffDays = today.diff(orderDate, 'days').days;
                if (diffDays > returnPeriod) {
                    this.dialog.add(AlertDialog, {
                        title: _t("Refund Limit Exceeded"),
                        body: _t(
                            "This order cannot be refunded as it exceeds the allowed return period of %s days.",
                            returnPeriod
                        ),
                    });
                    return;
                }
            }
        }
        return super.onDoRefund();
    }
});
