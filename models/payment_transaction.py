# -*- coding: utf-8 -*-
from odoo import models

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _post_process(self):
        super()._post_process()
        # Automatically assign the saved payment token to the subscription order
        # so that future recurring invoices can be charged automatically without manual intervention.
        for tx in self.filtered(lambda t: t.state in ['done', 'authorized'] and t.token_id):
            for order in tx.sale_order_ids.filtered(lambda o: o.plan_id):
                if not order.payment_token_id:
                    order.payment_token_id = tx.token_id.id
