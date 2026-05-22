# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from markupsafe import Markup
from odoo.exceptions import UserError


class SubscriptionSubscription(models.Model):
    """Core Subscription Contract model tracking the full lifecycle of a
    recurring customer contract from draft through trial, active billing,
    dunning, and final cancellation or closure."""

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

    # ── Grandfathering / Price Lock ───────────────────────────────────────────

    is_price_locked = fields.Boolean(
        string='Price Locked', default=False, tracking=True,
        help="When enabled, no automatic price updates from product price changes "
             "will be applied to this subscription. Existing prices are grandfathered."
    )
    price_lock_date = fields.Datetime(
        string='Locked On', readonly=True, copy=False
    )
    price_locked_by = fields.Many2one(
        'res.users', string='Locked By', readonly=True, copy=False
    )
    price_change_log_ids = fields.One2many(
        'subscription.price.change.log', 'subscription_id',
        string='Price Change History'
    )
    price_change_count = fields.Integer(
        string='Price Changes', compute='_compute_price_change_count'
    )

    # ── Sequence ──────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-assign a unique sequence reference on creation if none provided."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('subscription.subscription')
                    or 'New'
                )
        return super().create(vals_list)

    # ── Computed fields ───────────────────────────────────────────────────────

    def _compute_price_change_count(self):
        """Count all price change log entries linked to this subscription."""
        for sub in self:
            sub.price_change_count = len(sub.price_change_log_ids)

    @api.depends('line_ids.price_subtotal', 'plan_id.billing_period', 'plan_id.custom_days')
    def _compute_mrr(self):
        """Normalize the subscription's total revenue to a monthly figure (MRR)
        based on the plan's billing period."""
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
        """Count the number of invoices linked to this subscription contract."""
        for sub in self:
            sub.invoice_count = len(sub.invoice_ids)

    # ── Lifecycle actions ─────────────────────────────────────────────────────

    def action_start_trial(self):
        """Transition the subscription to 'In Trial' state and set the trial end
        date according to the plan's configured trial period days."""
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
        """Activate the subscription by transitioning it to 'In Progress' state
        and recording the start date if not already set."""
        for sub in self:
            sub.write({
                'state': 'in_progress',
                'start_date': sub.start_date or fields.Date.today(),
            })
            sub.message_post(body=_('Subscription activated.'))

    def action_pause(self):
        """Pause an active subscription contract. Only subscriptions in
        'in_progress', 'in_trial', or 'in_dunning' state can be paused."""
        for sub in self:
            if sub.state not in ('in_progress', 'in_trial', 'in_dunning'):
                raise UserError(
                    _('Only active subscriptions can be paused.')
                )
            sub.write({'state': 'paused'})
            sub.message_post(body=_('Subscription paused.'))

    def action_resume(self):
        """Resume a paused subscription contract, returning it to 'In Progress'."""
        for sub in self:
            sub.write({'state': 'in_progress'})
            sub.message_post(body=_('Subscription resumed.'))

    def action_close(self, close_reason_id=None, notes=None):
        """Close and churn the subscription contract. Optionally records
        a close reason and freeform notes for retention analysis."""
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
        """Cancel the subscription contract and record today as the cancellation date."""
        for sub in self:
            sub.write({
                'state': 'cancelled',
                'cancel_date': fields.Date.today(),
            })
            sub.message_post(body=_('Subscription cancelled.'))

    # ── Button: open close wizard ─────────────────────────────────────────────

    def action_open_close_wizard(self):
        """Open the Close Subscription wizard dialog to capture a churn reason
        before terminating the contract."""
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
        """Open the Change Subscription Plan wizard to allow mid-cycle plan
        upgrades or downgrades."""
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
        """Open the list of all invoices generated for this subscription contract."""
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

    # ── Smart button: price change history ───────────────────────────────────

    def action_view_price_history(self):
        """Open the price change history log for this subscription."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Price Change History'),
            'res_model': 'subscription.price.change.log',
            'view_mode': 'list,form',
            'domain': [('subscription_id', '=', self.id)],
            'context': {'default_subscription_id': self.id},
        }

    # ── Smart button: source sale order ──────────────────────────────────────

    def action_view_sale_order(self):
        """Navigate to the originating Sales Order that created this subscription."""
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

    # ── Grandfathering / Price Lock actions ──────────────────────────────────

    def action_lock_prices(self):
        """Lock the current prices on all subscription lines, preventing any
        automatic price updates when product prices change (grandfathering)."""
        for sub in self:
            sub.write({
                'is_price_locked': True,
                'price_lock_date': fields.Datetime.now(),
                'price_locked_by': self.env.user.id,
            })
            sub.message_post(
                body=Markup(_(
                    '<b>Prices Grandfathered</b> by %s on %s. '
                    'This subscription is now protected from automatic price updates.'
                )) % (
                    self.env.user.name,
                    fields.Datetime.now().strftime('%Y-%m-%d %H:%M'),
                )
            )

    def action_unlock_prices(self):
        """Remove the price lock, allowing future product price changes to
        automatically update this subscription's line prices."""
        for sub in self:
            sub.write({
                'is_price_locked': False,
                'price_lock_date': False,
                'price_locked_by': False,
            })
            sub.message_post(
                body=Markup(_(
                    '<b>Price Lock Removed</b> by %s. '
                    'This subscription will now receive automatic price updates.'
                )) % self.env.user.name
            )

    def action_apply_latest_prices(self):
        """Pull the current product list_price into all unlocked subscription lines.
        Useful to manually roll out a price increase to a previously locked subscription."""
        self.ensure_one()
        if self.is_price_locked:
            raise UserError(_(
                "This subscription is price-locked (grandfathered). "
                "Please unlock it first before applying new prices."
            ))
        updated = 0
        for line in self.line_ids:
            new_price = line.product_id.list_price
            if new_price != line.price_unit:
                self.env['subscription.price.change.log'].create({
                    'subscription_id': self.id,
                    'product_id': line.product_id.id,
                    'old_price': line.price_unit,
                    'new_price': new_price,
                    'changed_by': self.env.user.id,
                    'is_protected': False,
                    'notes': _('Manually applied via Apply Latest Prices'),
                })
                line.with_context(_price_lock_bypass=True).write({'price_unit': new_price})
                updated += 1
        if updated:
            self.message_post(
                body=Markup(_('<b>%d line(s)</b> updated to latest product prices by %s.')) % (
                    updated, self.env.user.name
                )
            )
        else:
            self.message_post(body=_('All line prices are already up to date.'))
        return True

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
            # Handle coupon limitations dynamically on each invoice run
            discount = line.discount
            if self.coupon_id:
                if self.coupon_id.recurring_type == 'first' and self.invoice_count > 0:
                    discount = 0.0
                elif self.coupon_id.recurring_type == 'limited' and self.invoice_count >= self.coupon_id.recurring_invoices:
                    discount = 0.0

            invoice_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name or line.product_id.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': discount,
                'tax_ids': [(6, 0, line.tax_ids.ids)] if line.tax_ids else False,
            }))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'subscription_id': self.id,
            'invoice_line_ids': invoice_lines,
        })

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
                # Use a savepoint to prevent the entire cron transaction from rolling back
                with self.env.cr.savepoint():
                    sub._generate_invoice()
            except Exception as e:
                # Log error and advance date by 1 day to prevent infinite failure loops blocking the queue
                sub.message_post(body=_('Invoice generation failed: %s. Retrying tomorrow.') % str(e))
                sub.next_invoice_date = sub.next_invoice_date + relativedelta(days=1)

    def action_generate_invoice_manually(self):
        """Manually trigger invoice generation for this subscription and open the created invoice."""
        self.ensure_one()
        invoice = self._generate_invoice()
        if not invoice:
            raise UserError(_(
                "Could not generate invoice. "
                "Make sure subscription is active and has line items."
            ))
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
        """Apply the selected close reason and permanently close the subscription."""
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
        """Update the subscription's plan and post a chatter message with the change."""
        self.ensure_one()
        self.subscription_id.write({'plan_id': self.plan_id.id})
        self.subscription_id.message_post(
            body=Markup(_('Subscription plan changed to <b>%s</b>.')) % self.plan_id.name
        )
        return {'type': 'ir.actions.act_window_close'}
