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
from odoo import models, fields, api, _
from markupsafe import Markup
from odoo.exceptions import UserError


class SubscriptionPlan(models.Model):
    """Subscription Plan model containing contract configurations, pricing,
    trial definitions, portal settings, and optional add-on plans."""

    _name = 'subscription.plan'
    _description = 'Subscription Plan'
    _order = 'name'

    name = fields.Char(string='Plan Name', required=True, translate=True)
    code = fields.Char(string='Code', help='Unique code for this plan.')
    description = fields.Text(string='Description', translate=True)
    active = fields.Boolean(default=True)
    product_id = fields.Many2one(
        'product.product', string='Website Linked Product', required=True,
        help='The core product representing this subscription plan on the website.'
    )
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='company_id.currency_id', store=True
    )
    billing_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annually', 'Semi-Annually'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Days')
    ], string='Billing Period', required=True, default='monthly',
        compute='_compute_billing_period',
        store=True, readonly=False)
    custom_days = fields.Integer(
        string='Custom Days',
        help='Used only if Billing Period is set to Custom Days.',
        compute='_compute_billing_period', store=True, readonly=False
    )
    trial_period_days = fields.Integer(
        string='Trial Period (Days)', default=0,
        help='Number of days for the trial period.'
    )
    trial_type = fields.Selection([
        ('free', 'Free Trial'),
        ('paid', 'Paid Trial')
    ], string='Trial Type', default='free')
    billing_period_value = fields.Integer(string='Billing Period Value', default=1)
    billing_period_unit = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
        ('years', 'Years')
    ], string='Billing Period Unit', default='months')
    align_to_period_start = fields.Boolean(string='Align To Period Start')
    automatic_closing_days = fields.Integer(string='Automatic Closing Days', default=15)
    invoice_mail_template_id = fields.Many2one(
        'mail.template', string='Invoice Email Template'
    )
    is_closable = fields.Boolean(string='Closable')
    is_pausable = fields.Boolean(string='Pausable')
    is_add_products = fields.Boolean(string='Add Products')
    is_renew = fields.Boolean(string='Renew')
    is_popular = fields.Boolean(string='Most Popular')
    optional_plan_ids = fields.Many2many(
        'subscription.plan',
        'subscription_plan_optional_rel',
        'plan_id',
        'optional_plan_id',
        string='Optional Plans'
    )
    remark_ids = fields.One2many('subscription.plan.remark', 'plan_id', string='Remarks')
    pricing_ids = fields.One2many('subscription.plan.pricing', 'plan_id', string='Pricing')
    ramp_ids = fields.One2many('subscription.plan.ramp', 'plan_id', string='Ramp Pricing Rules')
    subscription_count = fields.Integer(string='Subscriptions', compute='_compute_counts')
    item_count = fields.Integer(string='Subscription Items', compute='_compute_counts')
    total_price = fields.Float(string='Total Price', compute='_compute_total_price')

    @api.depends('product_id', 'product_id.list_price', 'pricing_ids.price', 'ramp_ids.price_unit', 'ramp_ids.start_cycle')
    def _compute_total_price(self):
        """Compute the total price of the subscription plan based on pricing lines, ramp rules, or product list price."""
        for plan in self:
            if plan.pricing_ids:
                plan.total_price = sum(line.price for line in plan.pricing_ids)
            elif plan.ramp_ids:
                first_ramp = min(plan.ramp_ids, key=lambda r: r.start_cycle)
                plan.total_price = first_ramp.price_unit
            elif plan.product_id:
                plan.total_price = plan.product_id.with_context(pricelist=False).list_price
            else:
                plan.total_price = 0.0

    @api.depends('billing_period_value', 'billing_period_unit')
    def _compute_billing_period(self):
        """Automatically sync the internal backend 'billing_period' field with the user-facing
         'billing_period_value' and 'billing_period_unit' fields."""
        for plan in self:
            val = plan.billing_period_value
            unit = plan.billing_period_unit
            if not val or not unit:
                continue
            if unit == 'days':
                if val == 1:
                    plan.billing_period = 'daily'
                else:
                    plan.billing_period = 'custom'
                    plan.custom_days = val
            elif unit == 'weeks':
                if val == 1:
                    plan.billing_period = 'weekly'
                else:
                    plan.billing_period = 'custom'
                    plan.custom_days = val * 7
            elif unit == 'months':
                if val == 1:
                    plan.billing_period = 'monthly'
                elif val == 3:
                    plan.billing_period = 'quarterly'
                elif val == 6:
                    plan.billing_period = 'semi_annually'
                elif val == 12:
                    plan.billing_period = 'yearly'
                else:
                    plan.billing_period = 'custom'
                    plan.custom_days = val * 30
            elif unit == 'years':
                if val == 1:
                    plan.billing_period = 'yearly'
                else:
                    plan.billing_period = 'custom'
                    plan.custom_days = val * 365

    @api.depends('name')
    def _compute_counts(self):
        """Compute stats for linked subscription sales orders and subscription line items."""
        for plan in self:
            plan.subscription_count = self.env['sale.order'].search_count(
                [('plan_id', '=', plan.id), ('state', '=', 'sale')]
            )
            plan.item_count = self.env['sale.order.line'].search_count(
                [('order_id.plan_id', '=', plan.id), ('order_id.state', '=', 'sale')]
            )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used(self):
        """Prevent deletion of plans that are already referenced in a sale order. Suggest archiving instead."""
        for plan in self:
            if self.env['sale.order'].search_count([('plan_id', '=', plan.id)], limit=1):
                raise UserError(_(
                    "You cannot delete the subscription plan '%s' because it is already in use by a quotation or subscription.\n\n"
                    "Please archive the plan instead if you no longer wish to use it."
                ) % plan.name)

    def action_view_subscriptions(self):
        """Return an action displaying all confirmed subscription sales orders for this plan."""
        self.ensure_one()
        return {
            'name': _('Subscriptions'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('plan_id', '=', self.id), ('state', '=', 'sale')],
            'context': {'default_plan_id': self.id},
            'target': 'current',
        }

    def action_view_subscription_items(self):
        """Return an action displaying all confirmed subscription sales order line items for this plan."""
        self.ensure_one()
        return {
            'name': _('Subscription Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.line',
            'view_mode': 'list,form',
            'domain': [('order_id.plan_id', '=', self.id), ('order_id.state', '=', 'sale')],
            'target': 'current',
        }


class SubscriptionPlanPricing(models.Model):
    """Subscription Plan Pricing model mapping optional pricelists, product
    variants, and unit price values to subscription plans."""

    _name = 'subscription.plan.pricing'
    _description = 'Subscription Plan Pricing'

    plan_id = fields.Many2one(
        'subscription.plan', string='Subscription Plan',
        ondelete='cascade', required=True
    )
    product_template_id = fields.Many2one(
        'product.template', string='Product Template', 
        required=True, domain="[('recurring_ok', '=', True)]"
    )
    variant_id = fields.Many2one('product.attribute.value', string='Variant')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    currency_id = fields.Many2one('res.currency', string='Currency', related='pricelist_id.currency_id',
                                  store=True)
    price = fields.Float(string='Unit Price', required=True)

class SubscriptionPlanRamp(models.Model):
    """Subscription Plan Ramp model defining graduated pricing cycles for
    subscription plans."""

    _name = 'subscription.plan.ramp'
    _description = 'Subscription Plan Pricing Ramp'
    _order = 'start_cycle, id'

    plan_id = fields.Many2one(
        'subscription.plan', string='Subscription Plan',
        ondelete='cascade', required=True
    )
    name = fields.Char(string='Description', compute='_compute_name', store=True)
    start_cycle = fields.Integer(
        string='Start Cycle', default=1, required=True,
        help="Billing cycle sequence number where this price begins (1-indexed)."
    )
    end_cycle = fields.Integer(
        string='End Cycle', required=True,
        help="Billing cycle sequence number where this price ends."
    )
    price_unit = fields.Float(
        string='Ramp Price', required=True,
        help="The unit price charged during this ramp interval."
    )

    @api.depends('start_cycle', 'end_cycle')
    def _compute_name(self):
        """Compute the display name for the ramp rule."""
        for rec in self:
            if rec.start_cycle and rec.end_cycle:
                rec.name = "Cycle {} to {}".format(rec.start_cycle, rec.end_cycle)
            else:
                rec.name = "New Ramp Rule"


class SubscriptionPlanRemark(models.Model):
    """Subscription Plan Remark model for defining bullet points on the pricing card."""

    _name = 'subscription.plan.remark'
    _description = 'Subscription Plan Remark'
    _order = 'sequence, id'

    plan_id = fields.Many2one(
        'subscription.plan', string='Subscription Plan',
        ondelete='cascade', required=True
    )
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Remark', required=True, translate=True)
