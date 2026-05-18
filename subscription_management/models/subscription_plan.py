from odoo import models, fields, api

class SubscriptionPlan(models.Model):
    _name = 'subscription.plan'
    _description = 'Subscription Plan'
    _order = 'name'

    name = fields.Char(string='Plan Name', required=True, translate=True)
    code = fields.Char(string='Code', help='Unique code for this plan')
    description = fields.Text(string='Description', translate=True)
    active = fields.Boolean(default=True)
    
    product_id = fields.Many2one('product.product', string='Linked Product', 
                                 help='The core product representing this subscription plan.')
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id', store=True)

    # Legacy field kept for backward-compatibility
    billing_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annually', 'Semi-Annually'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Days')
    ], string='Billing Period', required=True, default='monthly')
    
    custom_days = fields.Integer(string='Custom Days', help='Used only if Billing Period is set to Custom Days')
    
    trial_period_days = fields.Integer(string='Trial Period (Days)', default=0, help='Number of days for the trial period.')
    trial_type = fields.Selection([
        ('free', 'Free Trial'),
        ('paid', 'Paid Trial')
    ], string='Trial Type', default='free')

    # Premium Enterprise fields from mockup
    billing_period_value = fields.Integer(string='Billing Period Value', default=1)
    billing_period_unit = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
        ('years', 'Years')
    ], string='Billing Period Unit', default='months')

    align_to_period_start = fields.Boolean(string='Align to Period Start')
    automatic_closing_days = fields.Integer(string='Automatic Closing', default=15)
    invoice_mail_template_id = fields.Many2one('mail.template', string='Invoice Email Template')

    is_closable = fields.Boolean(string='Closable')
    is_pausable = fields.Boolean(string='Pausable')
    is_add_products = fields.Boolean(string='Add Products')
    is_renew = fields.Boolean(string='Renew')
    
    optional_plan_ids = fields.Many2many(
        'subscription.plan',
        'subscription_plan_optional_rel',
        'plan_id',
        'optional_plan_id',
        string='Optional Plans'
    )

    pricing_ids = fields.One2many('subscription.plan.pricing', 'plan_id', string='Pricing')

    # Dynamic Stat Count fields
    subscription_count = fields.Integer(string='Subscriptions', compute='_compute_counts')
    item_count = fields.Integer(string='Subscription Items', compute='_compute_counts')
    total_price = fields.Float(string='Total Price', compute='_compute_total_price')

    @api.depends('product_id', 'product_id.list_price', 'pricing_ids.price')
    def _compute_total_price(self):
        for plan in self:
            if plan.product_id:
                plan.total_price = plan.product_id.list_price
            elif plan.pricing_ids:
                plan.total_price = sum(line.price for line in plan.pricing_ids)
            else:
                plan.total_price = 0.0

    @api.depends('name')
    def _compute_counts(self):
        for plan in self:
            plan.subscription_count = self.env['sale.order'].search_count([('plan_id', '=', plan.id), ('state', '=', 'sale')])
            plan.item_count = self.env['sale.order.line'].search_count([('order_id.plan_id', '=', plan.id), ('order_id.state', '=', 'sale')])

    def action_view_subscriptions(self):
        self.ensure_one()
        return {
            'name': 'Subscriptions',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('plan_id', '=', self.id), ('state', '=', 'sale')],
            'context': {'default_plan_id': self.id},
            'target': 'current',
        }

    def action_view_subscription_items(self):
        self.ensure_one()
        return {
            'name': 'Subscription Items',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.line',
            'view_mode': 'list,form',
            'domain': [('order_id.plan_id', '=', self.id), ('order_id.state', '=', 'sale')],
            'target': 'current',
        }


class SubscriptionPlanPricing(models.Model):
    _name = 'subscription.plan.pricing'
    _description = 'Subscription Plan Pricing'

    plan_id = fields.Many2one('subscription.plan', string='Subscription Plan', ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    variant_id = fields.Many2one('product.attribute.value', string='Variant')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    price = fields.Float(string='Unit Price', required=True)
