# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import models

class PaymentTransaction(models.Model):
    """Extension of Payment Transaction to auto-link saved payment tokens
    to subscription sales orders for future automated billing."""
    _inherit = 'payment.transaction'
    _description = 'Payment Transaction'

    def _post_process(self):
        """Hook into the transaction post-processing flow to grab successful
        payment tokens and assign them to the originating subscription order."""
        super()._post_process()
        # Automatically assign the saved payment token to the subscription order
        # so that future recurring invoices can be charged automatically without manual intervention.
        for tx in self.filtered(lambda t: t.state in ['done', 'authorized'] and t.token_id):
            for order in tx.sale_order_ids.filtered(lambda o: o.plan_id):
                if not order.payment_token_id:
                    order.payment_token_id = tx.token_id.id
