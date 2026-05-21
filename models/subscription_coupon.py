# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SubscriptionCoupon(models.Model):
    """Subscription Promo Coupon model to define percentage or fixed-amount
    discounts applied during subscription checkouts, with advanced validation
    rules for date ranges, usage limits, plan restrictions, and new customers."""

    _name = 'subscription.coupon'
    _description = 'Subscription Promo Coupon'

    name = fields.Char(string='Coupon Name', required=True)
    code = fields.Char(string='Coupon Code', required=True, copy=False)
    discount_type = fields.Selection([
        ('percentage', 'Percentage (%)'),
        ('fixed', 'Fixed Amount')
    ], string='Discount Type', required=True, default='percentage')
    discount_value = fields.Float(string='Discount Value', required=True, default=0.0)
    active = fields.Boolean(string='Active', default=True)

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    max_uses = fields.Integer(
        string='Max Global Uses', default=0,
        help="0 means unlimited."
    )
    current_uses = fields.Integer(string='Current Uses', compute='_compute_current_uses')
    max_uses_per_customer = fields.Integer(
        string='Max Uses Per Customer', default=1,
        help="0 means unlimited."
    )
    min_order_amount = fields.Float(string='Minimum Order Amount', default=0.0)
    plan_ids = fields.Many2many(
        'subscription.plan', string='Specific Plans',
        help="Leave empty to apply to all plans."
    )
    first_time_only = fields.Boolean(string='First-Time Customers Only', default=False)

    recurring_type = fields.Selection([
        ('first', 'First Invoice Only'),
        ('limited', 'Limited Invoices'),
        ('forever', 'Forever')
    ], string='Recurring Application', default='forever', required=True)
    recurring_invoices = fields.Integer(
        string='Number of Invoices', default=3,
        help="Number of invoices this coupon applies to, if Limited Invoices is selected."
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The coupon code must be unique!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Override creation to automatically sanitize and uppercase coupon codes."""
        for vals in vals_list:
            if 'code' in vals and vals['code']:
                vals['code'] = vals['code'].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        """Override write to automatically sanitize and uppercase coupon codes."""
        if 'code' in vals and vals['code']:
            vals['code'] = vals['code'].strip().upper()
        return super().write(vals)

    def _compute_current_uses(self):
        """Count the number of confirmed sales orders that have used this coupon."""
        for coupon in self:
            coupon.current_uses = self.env['sale.order'].search_count([
                ('coupon_id', '=', coupon.id),
                ('state', 'in', ['sale', 'done'])
            ])

    def _validate_coupon(self, partner=None, plan=None, amount=0.0):
        """Validate the coupon against all advanced business rules.

        Checks include: active status, date validity, global/per-customer usage
        limits, minimum order amount, plan restriction, and first-time customer
        constraint.

        :param partner: res.partner record of the subscribing customer (optional).
        :param plan: subscription.plan record being purchased (optional).
        :param amount: float order subtotal used for minimum amount validation.
        :returns: tuple (bool is_valid, str message)
        """
        self.ensure_one()
        if not self.active:
            return False, "This coupon is inactive."

        today = fields.Date.context_today(self)
        if self.start_date and today < self.start_date:
            return False, "This coupon is not valid yet."
        if self.end_date and today > self.end_date:
            return False, "This coupon has expired."

        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False, "This coupon has reached its maximum usage limit."

        if self.min_order_amount > 0 and amount < self.min_order_amount:
            currency_symbol = plan.currency_id.symbol if plan and plan.currency_id else '$'
            return False, (
                f"This coupon requires a minimum order amount of "
                f"{currency_symbol}{self.min_order_amount:.2f}."
            )

        if plan and self.plan_ids and plan.id not in self.plan_ids.ids:
            return False, "This coupon is not valid for the selected plan."

        if partner:
            if self.max_uses_per_customer > 0:
                customer_uses = self.env['sale.order'].search_count([
                    ('coupon_id', '=', self.id),
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['sale', 'done'])
                ])
                if customer_uses >= self.max_uses_per_customer:
                    return False, "You have reached the usage limit for this coupon."

            if self.first_time_only:
                past_subs = self.env['sale.order'].search_count([
                    ('partner_id', '=', partner.id),
                    ('subscription_state', 'not in', [False, '1_draft'])
                ])
                if past_subs > 0:
                    return False, "This coupon is only valid for first-time customers."

        return True, "Coupon applied successfully!"
