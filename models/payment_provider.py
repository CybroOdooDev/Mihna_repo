# -*- coding: utf-8 -*-
import braintree

from odoo import fields, models


class PaymentProviderBraintree(models.Model):
    """ Braintree Payment Provider """
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('braintree', 'Braintree')],
        ondelete={'braintree': 'set default'}
    )
    braintree_merchant_id = fields.Char(string='Merchant ID')
    braintree_public_key = fields.Char(string='Public Key')
    braintree_private_key = fields.Char(string='Private Key')
    braintree_use_sandbox = fields.Boolean(
        string='Sandbox',
        default=True
    )

    def _get_default_payment_method_codes(self):
        """
        Override of payment to return the default payment method codes.
        """
        self.ensure_one()
        if self.code != 'braintree':
            return []
        return ['braintree']

    def _braintree_get_inline_form_values(self):
        """
        Generate and return the Braintree client token for the inline form.
        """
        self.ensure_one()
        gateway = self._get_braintree_gateway()
        client_token = gateway.client_token.generate()
        return client_token

    def _get_braintree_gateway(self):
        """
        Instantiate and return the Braintree gateway using provider credentials.
        """
        self.ensure_one()
        environment = (
            braintree.Environment.Sandbox
            if self.braintree_use_sandbox
            else braintree.Environment.Production
        )
        gateway = braintree.BraintreeGateway(
            braintree.Configuration(
                environment=environment,
                merchant_id=self.braintree_merchant_id or '',
                public_key=self.braintree_public_key or '',
                private_key=self.braintree_private_key or '',
            )
        )
        return gateway
