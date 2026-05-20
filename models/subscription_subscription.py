<<<<<<< HEAD
# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SubscriptionSubscription(models.Model):
    """Core Subscription Contract model tracking the full lifecycle of a recurring customer contract."""
=======
<<<<<<< HEAD
# -*- coding: utf-8 -*-
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
from odoo import models, fields, api, _
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError

class Subscription(models.Model):
<<<<<<< HEAD
    """Subscription model representing the active recurring client contract, managing billing dates and fulfillment metrics."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
    _name = 'subscription.subscription'
    _description = 'Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
<<<<<<< HEAD
    _rec_name = 'name'

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default='New', tracking=True
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, tracking=True
    )
    plan_id = fields.Many2one(
        'subscription.plan', string='Subscription Plan', required=True, tracking=True
    )
    sale_order_id = fields.Many2one(
        'sale.order', string='Sales Order', readonly=True, copy=False
    )
    coupon_id = fields.Many2one(
        'subscription.coupon', string='Applied Coupon'
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='company_id.currency_id', store=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_trial', 'In Trial'),
        ('in_progress', 'In Progress'),
=======

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
<<<<<<< HEAD
    partner_invoice_id = fields.Many2one('res.partner', string='Invoice Address', related='sale_order_id.partner_invoice_id', readonly=True)
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', related='sale_order_id.partner_shipping_id', readonly=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', related='sale_order_id.payment_term_id', readonly=True)
    referrer_id = fields.Many2one('res.partner', string='Referrer', related='sale_order_id.referrer_id', readonly=True)
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
    plan_id = fields.Many2one('subscription.plan', string='Subscription Plan', required=True, tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', related='plan_id.currency_id', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_trial', 'In Trial'),
<<<<<<< HEAD
        ('in_progress', 'In Progress'),
=======
        ('in_progress', 'Active'),
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        ('paused', 'Paused'),
        ('in_dunning', 'In Dunning'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('renewed', 'Renewed'),
        ('cancelled', 'Cancelled'),
<<<<<<< HEAD
        ('closed', 'Closed / Churned'),
    ], string='Status', default='draft', required=True, tracking=True)

    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date')
    trial_end_date = fields.Date(string='Trial End Date')
    cancel_date = fields.Date(string='Cancellation Date')
    next_invoice_date = fields.Date(string='Next Invoice Date')

    line_ids = fields.One2many(
        'subscription_line', 'subscription_id', string='Subscription Lines'
    )

    close_reason_id = fields.Many2one(
        'subscription.close.reason', string='Close Reason'
    )
    close_reason_notes = fields.Text(string='Close Notes')

    invoice_ids = fields.One2many(
        'account.move', 'subscription_id', string='Invoices'
    )
    invoice_count = fields.Integer(
        string='Invoice Count', compute='_compute_invoice_count'
    )
    picking_ids = fields.One2many(
        'stock.picking', 'subscription_id', string='Deliveries'
    )

    mrr = fields.Float(
        string='MRR', compute='_compute_mrr', store=True, digits='Product Price'
    )

    # ── Sequence ──────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('subscription.subscription')
                    or 'New'
                )
        return super().create(vals_list)

    # ── Computed fields ───────────────────────────────────────────────────────

    @api.depends('line_ids.price_subtotal', 'plan_id.billing_period', 'plan_id.custom_days')
    def _compute_mrr(self):
        for sub in self:
            period = sub.plan_id.billing_period if sub.plan_id else 'monthly'
            custom_days = sub.plan_id.custom_days if sub.plan_id else 0
            total = sum(sub.line_ids.mapped('price_subtotal'))
            if period == 'daily':
                sub.mrr = total * 30.0
            elif period == 'weekly':
                sub.mrr = total * 4.33
            elif period == 'monthly':
                sub.mrr = total
            elif period == 'quarterly':
                sub.mrr = total / 3.0
            elif period == 'semi_annually':
                sub.mrr = total / 6.0
            elif period == 'yearly':
                sub.mrr = total / 12.0
            elif period == 'custom' and custom_days:
                sub.mrr = total * (30.0 / custom_days)
            else:
                sub.mrr = total

    def _compute_invoice_count(self):
        for sub in self:
            sub.invoice_count = len(sub.invoice_ids)

    # ── Lifecycle actions ─────────────────────────────────────────────────────

    def action_start_trial(self):
        for sub in self:
            plan = sub.plan_id
            trial_days = plan.trial_period_days if plan else 0
            vals = {
                'state': 'in_trial',
                'start_date': fields.Date.today(),
            }
            if trial_days:
                vals['trial_end_date'] = (
                    fields.Date.today() + relativedelta(days=trial_days)
                )
            sub.write(vals)
            sub.message_post(body=_('Trial period started.'))

    def action_activate(self):
        for sub in self:
            sub.write({
                'state': 'in_progress',
                'start_date': sub.start_date or fields.Date.today(),
            })
            sub.message_post(body=_('Subscription activated.'))

    def action_pause(self):
        for sub in self:
            if sub.state not in ('in_progress', 'in_trial', 'in_dunning'):
                raise UserError(
                    _('Only active subscriptions can be paused.')
                )
            sub.write({'state': 'paused'})
            sub.message_post(body=_('Subscription paused.'))

    def action_resume(self):
        for sub in self:
            sub.write({'state': 'in_progress'})
            sub.message_post(body=_('Subscription resumed.'))

    def action_close(self, close_reason_id=None, notes=None):
        for sub in self:
            vals = {
                'state': 'closed',
                'cancel_date': fields.Date.today(),
            }
            if close_reason_id:
                vals['close_reason_id'] = close_reason_id
            if notes:
                vals['close_reason_notes'] = notes
            sub.write(vals)
            sub.message_post(body=_('Subscription closed.'))

    def action_cancel(self):
        for sub in self:
            sub.write({
                'state': 'cancelled',
                'cancel_date': fields.Date.today(),
            })
            sub.message_post(body=_('Subscription cancelled.'))

    # ── Button: open close wizard ─────────────────────────────────────────────

    def action_open_close_wizard(self):
        self.ensure_one()
        return {
            'name': _('Close Subscription'),
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_subscription_id': self.id},
        }

    # ── Button: open change plan wizard ──────────────────────────────────────

    def action_open_change_plan_wizard(self):
        self.ensure_one()
        return {
            'name': _('Change Subscription Plan'),
=======
<<<<<<< HEAD
        ('closed', 'Closed / Churned')
=======
        ('closed', 'Closed')
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
    ], string='Status', required=True, default='draft', tracking=True)

    start_date = fields.Date(string='Start Date', default=fields.Date.context_today, tracking=True)
    next_invoice_date = fields.Date(string='Next Invoice Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True, help='Date when the subscription expires if not renewed.')
    
    trial_end_date = fields.Date(string='Trial End Date', tracking=True)
    pause_date = fields.Date(string='Pause Date', tracking=True)
    resume_date = fields.Date(string='Expected Resume Date', tracking=True)
    cancel_date = fields.Date(string='Cancel Date', tracking=True)

    line_ids = fields.One2many('subscription.line', 'subscription_id', string='Subscription Lines')

    # New Relationships for integration
    sale_order_id = fields.Many2one('sale.order', string='Origin Sales Order', readonly=True, copy=False)
    invoice_ids = fields.One2many('account.move', 'subscription_id', string='Invoices', readonly=True)
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')
    
    picking_ids = fields.One2many('stock.picking', 'subscription_id', string='Deliveries', readonly=True)
    picking_count = fields.Integer(string='Delivery Count', compute='_compute_picking_count')
    
    close_reason_id = fields.Many2one('subscription.close.reason', string='Close/Cancel Reason', tracking=True)
    mrr_total = fields.Monetary(string='MRR', compute='_compute_mrr_total', store=True, currency_field='currency_id')
<<<<<<< HEAD
    
    # Coupons & Churn Prediction
    coupon_id = fields.Many2one('subscription.coupon', string='Applied Coupon', tracking=True)
    grandfathered = fields.Boolean(string='Grandfathered Price', default=True, help="If checked, historical line prices are frozen and protected against plan master updates.")
    ramp_ids = fields.One2many('subscription.line.ramp', 'subscription_id', string='Ramp Pricing Rules')
    churn_risk_score = fields.Float(string='Churn Risk Score (%)', readonly=True, tracking=True)
    churn_risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk')
    ], string='Churn Risk Level', compute='_compute_churn_risk_level', store=True)

    @api.depends('churn_risk_score')
    def _compute_churn_risk_level(self):
        """Compute the qualitative risk level based on the numerical churn risk score."""
        for rec in self:
            if rec.churn_risk_score >= 70:
                rec.churn_risk_level = 'high'
            elif rec.churn_risk_score >= 30:
                rec.churn_risk_level = 'medium'
            else:
                rec.churn_risk_level = 'low'

    @api.depends('line_ids.price_subtotal', 'plan_id')
    def _compute_mrr_total(self):
        """Compute the total Monthly Recurring Revenue (MRR) for this contract."""
=======

    @api.depends('line_ids.price_subtotal', 'plan_id')
    def _compute_mrr_total(self):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for sub in self:
            mrr_total = 0.0
            if sub.plan_id:
                period = sub.plan_id.billing_period
                for line in sub.line_ids:
                    subtotal = line.price_subtotal
                    if period == 'daily':
                        mrr = subtotal * 30.0
                    elif period == 'weekly':
                        mrr = subtotal * 4.33
                    elif period == 'monthly':
                        mrr = subtotal
                    elif period == 'quarterly':
                        mrr = subtotal / 3.0
                    elif period == 'semi_annually':
                        mrr = subtotal / 6.0
                    elif period == 'yearly':
                        mrr = subtotal / 12.0
                    elif period == 'custom' and sub.plan_id.custom_days:
                        mrr = subtotal * (30.0 / sub.plan_id.custom_days)
                    else:
                        mrr = subtotal
                    mrr_total += mrr
            sub.mrr_total = mrr_total

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
<<<<<<< HEAD
        """Compute the total count of invoices generated for this subscription."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    @api.depends('picking_ids')
    def _compute_picking_count(self):
<<<<<<< HEAD
        """Compute the total count of physical deliveries generated for this subscription."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.model_create_multi
    def create(self, vals_list):
<<<<<<< HEAD
        """Override create to automatically generate unique subscription contract serial references (SUB prefix)."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('subscription.subscription') or _('New')
        return super().create(vals_list)

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
<<<<<<< HEAD
        """Pre-populate fields automatically when linked sale_order_id changes."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        if self.sale_order_id:
            if self.sale_order_id.partner_id:
                self.partner_id = self.sale_order_id.partner_id.id
            if self.sale_order_id.plan_id:
                self.plan_id = self.sale_order_id.plan_id.id

    @api.onchange('plan_id')
    def _onchange_plan_id(self):
<<<<<<< HEAD
        """Pre-populate contract line items automatically when plan_id is changed."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        if self.plan_id:
            new_lines = []
            if self.plan_id.product_id:
                new_lines.append((0, 0, {
                    'product_id': self.plan_id.product_id.id,
                    'name': self.plan_id.product_id.name,
                    'quantity': 1.0,
                    'price_unit': self.plan_id.product_id.list_price,
                }))
            elif self.plan_id.pricing_ids:
                for line in self.plan_id.pricing_ids:
                    new_lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.product_id.name,
                        'quantity': 1.0,
                        'price_unit': line.price,
                    }))
            if new_lines:
                self.line_ids = [(5, 0, 0)] + new_lines

<<<<<<< HEAD
    @api.onchange('grandfathered')
    def _onchange_grandfathered(self):
        """Immediately update subscription lines to latest master prices in the UI if grandfathering is deactivated."""
        if not self.grandfathered and self.plan_id:
            for line in self.line_ids:
                pricing = self.plan_id.pricing_ids.filtered(lambda p: p.product_id == line.product_id)
                if pricing:
                    if line.product_id.list_price != line.price_unit:
                        line.price_unit = line.product_id.list_price
                    else:
                        line.price_unit = pricing[0].price
                else:
                    line.price_unit = line.product_id.list_price

    def action_start_trial(self):
        """Start the free trial phase, computing starting and trial end dates."""
=======
    def action_start_trial(self):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for rec in self:
            if rec.state == 'draft' and rec.plan_id.trial_period_days > 0:
                rec.state = 'in_trial'
                rec.start_date = fields.Date.context_today(self)
                rec.trial_end_date = rec.start_date + timedelta(days=rec.plan_id.trial_period_days)
                rec.next_invoice_date = rec.trial_end_date
                rec.message_post(body=_("Trial started. End of trial: %s") % rec.trial_end_date)
    
    def action_activate(self):
<<<<<<< HEAD
        """Activate the subscription contract and set state to in progress."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for rec in self:
            if rec.state in ['draft', 'in_trial', 'paused']:
                rec.state = 'in_progress'
                if not rec.start_date:
                    rec.start_date = fields.Date.context_today(self)
                if not rec.next_invoice_date:
                    rec.next_invoice_date = fields.Date.context_today(self)
                rec.message_post(body=_("Subscription activated! Next renewal date set to: %s") % rec.next_invoice_date)

    def action_pause(self):
<<<<<<< HEAD
        """Pause the subscription contract, preserving dates while halting billing."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for rec in self:
            if rec.state == 'in_progress':
                rec.state = 'paused'
                rec.pause_date = fields.Date.context_today(self)
                rec.message_post(body=_("Subscription paused on %s.") % rec.pause_date)

    def action_resume(self):
<<<<<<< HEAD
        """Resume the paused subscription contract, setting next invoice date to resume date."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for rec in self:
            if rec.state == 'paused':
                rec.state = 'in_progress'
                rec.resume_date = fields.Date.context_today(self)
                # If next invoice date was during pause, set it to today so billing catch up occurs
                if rec.next_invoice_date and rec.next_invoice_date < fields.Date.context_today(self):
                    rec.next_invoice_date = fields.Date.context_today(self)
<<<<<<< HEAD
                rec.message_post(body=_("Subscription resumed! Next billing cycle: %s") % rec.next_invoice_date)

    def action_change_plan_wizard(self):
        """Open the subscription plan change and proration wizard in a modal view."""
        self.ensure_one()
        return {
            'name': _('Upgrade / Change Plan'),
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.change.plan.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_subscription_id': self.id,
<<<<<<< HEAD
                'default_plan_id': self.plan_id.id,
            },
        }

    # ── Smart button: invoices ────────────────────────────────────────────────

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('subscription_id', '=', self.id)],
            'context': {
                'default_subscription_id': self.id,
                'default_move_type': 'out_invoice',
            },
        }

    # ── Smart button: source sale order ──────────────────────────────────────

    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
        }

    # ── Recurring invoice generation ──────────────────────────────────────────

    def _get_billing_delta(self):
        """Return the relativedelta corresponding to the plan billing period."""
        self.ensure_one()
        plan = self.plan_id
        if not plan:
            return relativedelta(months=1)
        period_map = {
            'daily': relativedelta(days=1),
            'weekly': relativedelta(weeks=1),
            'monthly': relativedelta(months=1),
            'quarterly': relativedelta(months=3),
            'semi_annually': relativedelta(months=6),
            'yearly': relativedelta(years=1),
        }
        if plan.billing_period == 'custom' and plan.custom_days:
            return relativedelta(days=plan.custom_days)
        return period_map.get(plan.billing_period, relativedelta(months=1))

    def _generate_invoice(self):
        """Generate a recurring invoice for this subscription and advance the next_invoice_date."""
        self.ensure_one()
        if self.state not in ('in_progress', 'in_trial'):
            return False
        if not self.line_ids:
            return False

        invoice_lines = []
        for line in self.line_ids:
            invoice_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name or line.product_id.name,
=======
            }
        }

    def action_preview_next_invoice(self):
        """Calculate and return a dynamic forecast/preview of the next cycle's invoice details."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        next_invoice = self.next_invoice_date or today
        current_cycle = len(self.invoice_ids) + 1

        lines_preview = []
        for line in self.line_ids:
            # 1. Seat-based prediction
            quantity = line.quantity
            if line.billing_type == 'seat':
                partner_ids = [self.partner_id.id]
                if self.partner_id.commercial_partner_id:
                    partner_ids.append(self.partner_id.commercial_partner_id.id)
                child_partners = self.env['res.partner'].search([('parent_id', '=', self.partner_id.commercial_partner_id.id)])
                partner_ids.extend(child_partners.ids)
                user_count = self.env['res.users'].search_count([
                    ('active', '=', True),
                    ('partner_id', 'in', partner_ids)
                ])
                quantity = max(1, user_count)
            elif line.billing_type == 'usage':
                usages = self.env['subscription.usage'].search([
                    ('subscription_id', '=', self.id),
                    ('product_id', '=', line.product_id.id),
                    ('billed', '=', False)
                ])
                quantity = sum(usages.mapped('quantity'))

            # 2. Grandfathering
            price_unit = line.price_unit
            if not self.grandfathered:
                pricing = self.plan_id.pricing_ids.filtered(lambda p: p.product_id == line.product_id)
                if pricing:
                    if line.product_id.list_price != line.price_unit:
                        price_unit = line.product_id.list_price
                    else:
                        price_unit = pricing[0].price
                else:
                    price_unit = line.product_id.list_price

            # 3. Ramp Pricing
            ramp_rule = self.ramp_ids.filtered(lambda r: r.start_cycle <= current_cycle <= r.end_cycle)
            if not ramp_rule:
                ramp_rule = self.plan_id.ramp_ids.filtered(lambda r: r.start_cycle <= current_cycle <= r.end_cycle)
            if ramp_rule:
                price_unit = ramp_rule[0].price_unit

            subtotal = quantity * price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            lines_preview.append({
                'product_id': line.product_id.id,
                'product_name': line.product_id.display_name or line.name,
                'quantity': quantity,
                'price_unit': price_unit,
                'discount': line.discount,
                'subtotal': subtotal
            })

        # Calculate Coupon discounts
        total_before_discount = sum(l['subtotal'] for l in lines_preview)
        discount_amount = 0.0
        if self.coupon_id:
            coupon = self.coupon_id
            if coupon.discount_type == 'percentage':
                discount_amount = total_before_discount * (coupon.discount_value / 100.0)
            elif coupon.discount_type == 'fixed':
                discount_amount = min(total_before_discount, coupon.discount_value)

        total_after_discount = max(0.0, total_before_discount - discount_amount)
        tax_amount = total_after_discount * 0.18
        grand_total = total_after_discount + tax_amount

        return {
            'next_invoice_date': next_invoice,
            'lines': lines_preview,
            'total_before_discount': total_before_discount,
            'coupon_code': self.coupon_id.code if self.coupon_id else None,
            'discount_amount': discount_amount,
            'subtotal': total_after_discount,
            'tax_amount': tax_amount,
            'grand_total': grand_total,
            'currency_symbol': self.currency_id.symbol or '$'
        }

    def action_cancel(self):
        """Cancel and terminate the subscription contract."""
=======
                rec.message_post(body=_("Subscription resumed! Next renewal date: %s") % rec.next_invoice_date)

    def action_cancel(self):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for rec in self:
            rec.state = 'cancelled'
            rec.cancel_date = fields.Date.context_today(self)
            rec.message_post(body=_("Subscription cancelled on %s.") % rec.cancel_date)

    def action_close(self):
<<<<<<< HEAD
        """Trigger the backend close reason wizard to terminate the active subscription."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        self.ensure_one()
        return {
            'name': _('Close Subscription Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_subscription_id': self.id,
            }
        }

    def action_create_invoice(self):
        """Generates a recurring invoice for this subscription."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Cannot generate invoice for subscription with no lines."))

        # Create Invoice
        invoice_vals = {
            'partner_id': self.partner_id.id,
            'move_type': 'out_invoice',
            'subscription_id': self.id,
            'invoice_date': fields.Date.context_today(self),
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
<<<<<<< HEAD
            'ref': f"Subscription Invoice - {self.name}",
            'invoice_line_ids': [],
        }

        # Determine the current billing cycle number
        current_cycle = len(self.invoice_ids) + 1

        for line in self.line_ids:
            # 1. Seat-Based Recalculation
            if line.billing_type == 'seat':
                partner_ids = [self.partner_id.id]
                if self.partner_id.commercial_partner_id:
                    partner_ids.append(self.partner_id.commercial_partner_id.id)
                child_partners = self.env['res.partner'].search([('parent_id', '=', self.partner_id.commercial_partner_id.id)])
                partner_ids.extend(child_partners.ids)
                
                user_count = self.env['res.users'].search_count([
                    ('active', '=', True),
                    ('partner_id', 'in', partner_ids)
                ])
                line.quantity = max(1, user_count)

            quantity = line.quantity
            if line.billing_type == 'usage':
                # Sum all unbilled usage for this subscription and product
                usages = self.env['subscription.usage'].search([
                    ('subscription_id', '=', self.id),
                    ('product_id', '=', line.product_id.id),
                    ('billed', '=', False)
                ])
                quantity = sum(usages.mapped('quantity'))
                usages.write({'billed': True})
            
            # 2. Grandfathering Pricing Lock vs Dynamic Master Update
            price_unit = line.price_unit
            if not self.grandfathered:
                pricing = self.plan_id.pricing_ids.filtered(lambda p: p.product_id == line.product_id)
                if pricing:
                    if line.product_id.list_price != line.price_unit:
                        price_unit = line.product_id.list_price
                    else:
                        price_unit = pricing[0].price
                else:
                    price_unit = line.product_id.list_price
                line.price_unit = price_unit

            # 3. Ramp Pricing Engine check
            ramp_rule = self.ramp_ids.filtered(lambda r: r.start_cycle <= current_cycle <= r.end_cycle)
            if not ramp_rule:
                ramp_rule = self.plan_id.ramp_ids.filtered(lambda r: r.start_cycle <= current_cycle <= r.end_cycle)
            
            if ramp_rule:
                price_unit = ramp_rule[0].price_unit

            if quantity > 0 or line.billing_type != 'usage':
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'quantity': quantity,
                    'price_unit': price_unit,
                    'discount': line.discount,
                }))

        invoice = self.env['account.move'].create(invoice_vals)

        # Apply Coupon Discount
        if self.coupon_id and invoice.invoice_line_ids:
            coupon = self.coupon_id
            
            # Manually sum line subtotals to avoid Odoo lazy-load compute gotcha
            total_before_discount = sum(l.quantity * l.price_unit * (1.0 - l.discount / 100.0) for l in invoice.invoice_line_ids)
            
            discount_amount = 0.0
            if coupon.discount_type == 'percentage':
                discount_amount = total_before_discount * (coupon.discount_value / 100.0)
            elif coupon.discount_type == 'fixed':
                discount_amount = min(coupon.discount_value, total_before_discount)
                
            if discount_amount > 0:
                first_line = invoice.invoice_line_ids[0]
                invoice.write({
                    'invoice_line_ids': [(0, 0, {
                        'name': f"Coupon Discount - {coupon.name} ({coupon.code})",
                        'quantity': 1.0,
                        'price_unit': -discount_amount,
                        'account_id': first_line.account_id.id,
                        'tax_ids': [(6, 0, first_line.tax_ids.ids)],
                    })]
                })
=======
            'invoice_line_ids': [],
        }

        for line in self.line_ids:
            invoice_vals['invoice_line_ids'].append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name,
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
            }))

<<<<<<< HEAD
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'subscription_id': self.id,
            'invoice_line_ids': invoice_lines,
        })

        # Advance next invoice date
        delta = self._get_billing_delta()
        next_date = (self.next_invoice_date or fields.Date.today()) + delta
        self.write({'next_invoice_date': next_date})
        return invoice

    @api.model
    def _cron_generate_invoices(self):
        """Cron job: generate invoices for all subscriptions with an overdue next_invoice_date."""
        today = fields.Date.today()
        due_subs = self.search([
            ('state', 'in', ['in_progress']),
            ('next_invoice_date', '<=', today),
        ])
        for sub in due_subs:
            try:
                sub._generate_invoice()
            except Exception as e:
                sub.message_post(body=_('Invoice generation failed: %s') % str(e))

    def action_generate_invoice_manually(self):
        """Manually trigger invoice generation for this subscription and view the created invoice."""
        self.ensure_one()
        invoice = self._generate_invoice()
        if not invoice:
            from odoo.exceptions import UserError
            raise UserError(_("Could not generate invoice. Make sure subscription is active and has line items."))
        return {
            'name': _('Generated Invoice'),
=======
        invoice = self.env['account.move'].create(invoice_vals)
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        
        # Post the invoice automatically
        try:
            invoice.action_post()
            self.message_post(body=_("Auto-generated and posted Invoice %s.") % invoice.name)
        except Exception as e:
            self.message_post(body=_("Created draft Invoice %s. Auto-post failed: %s") % (invoice.name, str(e)))

        # Update Next Invoice Date
        self._increment_next_invoice_date()
<<<<<<< HEAD
        return {
            'name': _('Customer Invoice'),
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

<<<<<<< HEAD

# ── Wizards ───────────────────────────────────────────────────────────────────

class SubscriptionCloseWizard(models.TransientModel):
    """Wizard allowing users to select a close reason before terminating a subscription."""
    _name = 'subscription.close.wizard'
    _description = 'Close Subscription Wizard'

    subscription_id = fields.Many2one(
        'subscription.subscription', string='Subscription', required=True
    )
    close_reason_id = fields.Many2one(
        'subscription.close.reason', string='Close Reason'
    )
    notes = fields.Text(string='Notes')

    def action_close(self):
        self.ensure_one()
        self.subscription_id.action_close(
            close_reason_id=self.close_reason_id.id if self.close_reason_id else None,
            notes=self.notes,
        )
        return {'type': 'ir.actions.act_window_close'}


class SubscriptionChangePlanWizard(models.TransientModel):
    """Wizard for changing the subscription plan on an active contract."""
    _name = 'subscription.change.plan.wizard'
    _description = 'Change Subscription Plan Wizard'

    subscription_id = fields.Many2one(
        'subscription.subscription', string='Subscription', required=True
    )
    plan_id = fields.Many2one(
        'subscription.plan', string='New Plan', required=True
    )

    def action_change_plan(self):
        self.ensure_one()
        self.subscription_id.write({'plan_id': self.plan_id.id})
        self.subscription_id.message_post(
            body=_('Subscription plan changed to <b>%s</b>.') % self.plan_id.name
        )
        return {'type': 'ir.actions.act_window_close'}
=======
    def action_pay_and_reconcile(self, invoice, provider_name=""):
        """Programmatically pay and reconcile the given invoice with a transaction memo."""
        self.ensure_one()
        if invoice.payment_state == 'paid':
            return True
            
        # Create payment record
        memo = f"Payment for Subscription {self.name} via {provider_name}" if provider_name else f"Payment for Subscription {self.name}"
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_id.id,
            'amount': invoice.amount_total,
            'currency_id': invoice.currency_id.id,
            'journal_id': self.env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', self.company_id.id)
            ], limit=1).id or self.env['account.journal'].search([('type', '=', 'bank')], limit=1).id,
            'memo': memo,
        }
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        
        # Reconcile invoice line with payment line
        receivable_line = invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        payment_receivable_line = payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        
        if receivable_line and payment_receivable_line:
            (receivable_line + payment_receivable_line).reconcile()
            self.message_post(body=_("Payment reconciled successfully for Invoice %s. Memo: %s") % (invoice.name, payment.memo))
        return True

    def _increment_next_invoice_date(self):
        """Increment the contract billing next_invoice_date forward based on the selected plan interval."""
=======
        return invoice

    def _increment_next_invoice_date(self):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        self.ensure_one()
        current_date = self.next_invoice_date or fields.Date.context_today(self)
        period = self.plan_id.billing_period
        custom_days = self.plan_id.custom_days or 1

        if period == 'daily':
            next_date = current_date + timedelta(days=1)
        elif period == 'weekly':
            next_date = current_date + timedelta(weeks=1)
        elif period == 'monthly':
            next_date = current_date + relativedelta(months=1)
        elif period == 'quarterly':
            next_date = current_date + relativedelta(months=3)
        elif period == 'semi_annually':
            next_date = current_date + relativedelta(months=6)
        elif period == 'yearly':
            next_date = current_date + relativedelta(years=1)
        elif period == 'custom':
            next_date = current_date + timedelta(days=custom_days)
        else:
            next_date = current_date + relativedelta(months=1)

        self.next_invoice_date = next_date

    def action_create_delivery(self):
        """Generates a stock picking for physical subscription lines."""
        self.ensure_one()
        physical_lines = self.line_ids.filtered(lambda l: l.product_id.type == 'consu')
        if not physical_lines:
            return False

        # Find picking type outgoing
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        if not picking_type:
            raise UserError(_("No outgoing picking type found for company."))

        # Find default source and destination locations
        source_loc = picking_type.default_location_src_id.id
        dest_loc = self.partner_id.property_stock_customer.id

        picking_vals = {
            'partner_id': self.partner_id.id,
            'picking_type_id': picking_type.id,
            'subscription_id': self.id,
            'location_id': source_loc,
            'location_dest_id': dest_loc,
            'origin': self.name,
<<<<<<< HEAD
            'move_ids': []
        }

        for line in physical_lines:
            picking_vals['move_ids'].append((0, 0, {
                'description_picking': line.product_id.display_name,
=======
            'move_ids_without_package': []
        }

        for line in physical_lines:
            picking_vals['move_ids_without_package'].append((0, 0, {
                'name': line.product_id.display_name,
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'location_id': source_loc,
                'location_dest_id': dest_loc,
            }))

        picking = self.env['stock.picking'].create(picking_vals)
        picking.action_confirm()
        self.message_post(body=_("Auto-created Delivery Order %s.") % picking.name)
<<<<<<< HEAD
        return {
            'name': _('Delivery Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }
=======
        return picking
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0

    @api.model
    def _cron_recurring_billing(self):
        """Daily Cron method to identify subscriptions due for billing and process them."""
        today = fields.Date.context_today(self)
        # Find active subscriptions that are due
        due_subs = self.search([
            ('state', 'in', ['in_progress', 'in_trial']),
            ('next_invoice_date', '<=', today)
        ])

        for sub in due_subs:
            try:
                # Generate Invoice
                invoice = sub.action_create_invoice()
                # Generate physical delivery if physical items exist
                sub.action_create_delivery()
            except Exception as e:
                # Log any errors to chatter to make it visible to admins
                sub.message_post(body=_("Cron recurring billing failed: %s") % str(e))

    # Smart Buttons Actions
    def action_view_invoices(self):
<<<<<<< HEAD
        """Return a window action showing all customer invoices generated for this subscription."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        action['domain'] = [('subscription_id', '=', self.id)]
        action['context'] = {'default_move_type': 'out_invoice', 'default_subscription_id': self.id}
        return action

    def action_view_pickings(self):
<<<<<<< HEAD
        """Return a window action showing all stock pickings generated for this subscription."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        action['domain'] = [('subscription_id', '=', self.id)]
        action['context'] = {'default_subscription_id': self.id}
        return action

    def action_view_sales_orders(self):
<<<<<<< HEAD
        """Return a window action displaying the linked Sales Order for this subscription."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
        action['domain'] = [('id', '=', self.sale_order_id.id)]
        action['res_id'] = self.sale_order_id.id
        action['view_mode'] = 'form'
        action['views'] = [(False, 'form')]
        return action

    def action_preview_subscription(self):
<<<<<<< HEAD
        """Open a new browser tab redirecting to the customer portal preview of this subscription."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/my/subscription/%s' % self.id,
            'target': 'new',
        }

<<<<<<< HEAD
    def action_calculate_churn_risk(self):
        """AI churn risk heuristic analyzer."""
        for rec in self:
            score = 0.0
            # 1. Unpaid invoices factor
            unpaid_invoices = rec.invoice_ids.filtered(lambda inv: inv.payment_state in ['not_paid', 'partial'])
            if unpaid_invoices:
                score += min(len(unpaid_invoices) * 25.0, 50.0)
                
            # 2. Trial state factor
            if rec.state == 'in_trial':
                score += 15.0
                
            # 3. New contract factor
            total_days = (fields.Date.context_today(self) - rec.start_date).days
            if total_days < 30 and rec.state != 'in_trial':
                score += 10.0
                
            # 4. Support and pauses history factor
            if rec.state == 'paused':
                score += 20.0
                
            rec.churn_risk_score = min(score, 100.0)
            rec.message_post(body=_("AI Churn Risk Analyzed. Score: %s%%. Level: %s.") % (rec.churn_risk_score, rec.churn_risk_level.upper()))
        return True

class SubscriptionCloseWizard(models.TransientModel):
    """Subscription Close Wizard transient model assisting users in selecting a termination reason and churning contracts."""
=======
class SubscriptionCloseWizard(models.TransientModel):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
    _name = 'subscription.close.wizard'
    _description = 'Subscription Close Wizard'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', required=True)
    close_reason_id = fields.Many2one('subscription.close.reason', string='Close Reason', required=True)
    description = fields.Text(string='Details')

    def action_close_subscription(self):
<<<<<<< HEAD
        """Process subscription termination within the close reason wizard, updating the parent contract."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        self.ensure_one()
        sub = self.subscription_id
        sub.write({
            'state': 'closed',
            'close_reason_id': self.close_reason_id.id,
            'end_date': fields.Date.context_today(self),
        })
        # Post a message inside subscription chatter
        msg = _("Subscription closed. Reason: %s") % self.close_reason_id.name
        if self.description:
            msg += "<br/><b>Details:</b> %s" % self.description
        sub.message_post(body=msg)

        # Also cancel/close the linked Sales Order state if it's active
        if sub.sale_order_id:
            sub.sale_order_id.message_post(body=_("Linked subscription was closed. Reason: %s") % self.close_reason_id.name)
        return {'type': 'ir.actions.act_window_close'}
<<<<<<< HEAD


class SubscriptionLineRamp(models.Model):
    """Subscription Line Ramp model defining graduated pricing cycles for active contracts."""
    _name = 'subscription.line.ramp'
    _description = 'Subscription Line Pricing Ramp'
    _order = 'sequence, id'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', ondelete='cascade', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    start_cycle = fields.Integer(string='Start Cycle', default=1, required=True, help="Billing cycle sequence number where this price begins (1-indexed).")
    end_cycle = fields.Integer(string='End Cycle', required=True, help="Billing cycle sequence number where this price ends.")
    price_unit = fields.Float(string='Ramp Price', required=True, help="The unit price charged during this ramp interval.")


class SubscriptionChangePlanWizard(models.TransientModel):
    """Subscription Change Plan Wizard transient model managing mid-cycle proration, delta pricing calculation, and upgrade/downgrade invoicing."""
    _name = 'subscription.change.plan.wizard'
    _description = 'Subscription Change Plan Wizard'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', required=True)
    new_plan_id = fields.Many2one('subscription.plan', string='New Plan', required=True)
    prorate = fields.Boolean(string='Prorate Changes', default=True, help="If checked, calculate the delta price for remaining days in the active cycle.")

    def action_change_plan(self):
        """Execute the plan migration, calculate delta balances, and post prorated adjustment invoices/credits."""
        self.ensure_one()
        sub = self.subscription_id
        old_plan = sub.plan_id
        new_plan = self.new_plan_id

        if old_plan == new_plan:
            raise UserError(_("The selected plan is already active on this subscription."))

        # 1. Gather baseline pricing info
        old_price = old_plan.total_price or (old_plan.product_id.list_price if old_plan.product_id else 0.0)
        new_price = new_plan.total_price or (new_plan.product_id.list_price if new_plan.product_id else 0.0)

        # 2. Date calculations
        today = fields.Date.context_today(self)
        start_date = sub.start_date or today
        next_invoice = sub.next_invoice_date or today

        # Compute total days in current cycle (approximate to 30 days if not set, or compute using interval)
        total_days = 30
        if next_invoice > start_date:
            total_days = (next_invoice - start_date).days or 30

        remaining_days = max(0, (next_invoice - today).days)

        # 3. Calculate proration value
        if self.prorate and remaining_days > 0 and total_days > 0:
            ratio = float(remaining_days) / float(total_days)
            unused_value = old_price * ratio
            new_plan_cost = new_price * ratio
            delta_price = new_plan_cost - unused_value
        else:
            delta_price = new_price - old_price

        # 4. Apply plan change
        sub.write({
            'plan_id': new_plan.id,
        })
        # Reset contract lines to match new plan
        sub._onchange_plan_id()

        # 5. Generate adjustment Invoice / Credit Note immediately
        if delta_price != 0.0:
            invoice_vals = {
                'partner_id': sub.partner_id.id,
                'move_type': 'out_invoice' if delta_price > 0 else 'out_refund',
                'subscription_id': sub.id,
                'invoice_date': today,
                'currency_id': sub.currency_id.id,
                'company_id': sub.company_id.id,
                'ref': f"Plan Migration Adjustment: {old_plan.name} -> {new_plan.name}",
                'invoice_line_ids': [(0, 0, {
                    'product_id': new_plan.product_id.id or old_plan.product_id.id,
                    'name': _("Prorated Plan Adjustment: %s to %s (%s remaining days)") % (old_plan.name, new_plan.name, remaining_days),
                    'quantity': 1.0,
                    'price_unit': abs(delta_price),
                })],
            }
            invoice = self.env['account.move'].create(invoice_vals)
            try:
                invoice.action_post()
            except Exception:
                pass
            
            msg = _("Prorated plan changed to <b>%s</b>. Prorated adjustment invoice %s created.") % (new_plan.name, invoice.name)
        else:
            msg = _("Plan changed to <b>%s</b> with no proration delta.") % new_plan.name

        sub.message_post(body=msg)
        return {'type': 'ir.actions.act_window_close'}
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
