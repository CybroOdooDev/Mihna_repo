# -*- coding: utf-8 -*-
from odoo import models, fields, _
from markupsafe import Markup


class ProductTemplate(models.Model):
    """Inherited Product Template model to define if a product represents a recurring subscription plan."""
    _inherit = 'product.template'

    recurring_ok = fields.Boolean(
        string='Subscription Product', default=False,
        help='Check if this product is a recurring subscription plan.'
    )
    subscription_plan_id = fields.Many2one(
        'subscription.plan', string='Subscription Plan',
        help='Plan used when selling this product.'
    )

    def write(self, vals):
        """Detect list_price changes and fire the Grandfathering Engine.

        When ``list_price`` is updated:
        - **Price-locked** subscriptions: log the skipped update with
          ``is_protected=True`` and post a chatter warning.
        - **Unlocked** subscriptions: auto-apply the new price to
          subscription lines and log the change with ``is_protected=False``.
        """
        old_prices = {}
        if 'list_price' in vals:
            for tmpl in self:
                old_prices[tmpl.id] = tmpl.list_price

        result = super().write(vals)

        if old_prices:
            PriceLog = self.env['subscription.price.change.log']
            for tmpl in self:
                old_price = old_prices.get(tmpl.id)
                new_price = tmpl.list_price
                if old_price is None or old_price == new_price:
                    continue

                # Find all active subscription lines using any variant of this template
                variant_ids = tmpl.product_variant_ids.ids
                affected_lines = self.env['sale.order.line'].search([
                    ('product_id', 'in', variant_ids),
                    ('order_id.subscription_state', 'in', ['3_progress', '4_paused']),
                ])

                for line in affected_lines:
                    order = line.order_id
                    is_protected = order.is_price_locked

                    PriceLog.create({
                        'sale_order_id': order.id,
                        'product_id': line.product_id.id,
                        'old_price': old_price,
                        'new_price': new_price,
                        'changed_by': self.env.user.id,
                        'is_protected': is_protected,
                        'notes': _(
                            'Grandfathered – price locked' if is_protected
                            else 'Auto-updated from product price change'
                        ),
                    })

                    if is_protected:
                        order.message_post(body=Markup(_(
                            '<b>⚑ Price Change Blocked (Grandfathered)</b><br/>'
                            'Product <b>%s</b> price changed from <b>%.2f</b> → <b>%.2f</b>.<br/>'
                            'This subscription is price-locked. The old price has been retained.'
                        )) % (tmpl.name, old_price, new_price))
                    else:
                        line.with_context(_price_lock_bypass=True).write(
                            {'price_unit': new_price}
                        )
                        order.message_post(body=Markup(_(
                            '<b>Price Updated</b><br/>'
                            'Product <b>%s</b> price changed from <b>%.2f</b> → <b>%.2f</b>.<br/>'
                            'Subscription line has been updated automatically.'
                        )) % (tmpl.name, old_price, new_price))

        return result
