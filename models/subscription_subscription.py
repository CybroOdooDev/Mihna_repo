# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SubscriptionSubscription(models.Model):
    """Core Subscription Contract model tracking the full lifecycle of a recurring customer contract."""
    _name = 'subscription.subscription'
    _description = 'Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
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
        ('paused', 'Paused'),
        ('in_dunning', 'In Dunning'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('renewed', 'Renewed'),
        ('cancelled', 'Cancelled'),
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
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.change.plan.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_subscription_id': self.id,
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
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
            }))

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
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }


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
