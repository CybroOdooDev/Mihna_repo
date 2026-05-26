# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from markupsafe import Markup
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import requests



class SaleOrder(models.Model):
    """Inherited Sale Order model representing customer quotation and order
    pipeline linked to active subscription contracts."""

    _inherit = 'sale.order'

    def _default_plan_id(self):
        """Return the default monthly billing plan for new Sales Orders,
        falling back to any available plan if no monthly plan exists."""
        plan = self.env['subscription.plan'].search(
            [('billing_period', '=', 'monthly')], limit=1
        )
        if not plan:
            plan = self.env['subscription.plan'].search([], limit=1)
        return plan.id if plan else False

    plan_id = fields.Many2one(
        'subscription.plan', string='Recurring Plan',
        default=_default_plan_id,
        help="Select the recurring billing plan for this quotation."
    )
    subscription_end_date = fields.Date(
        string='Until', help="End date of the subscription."
    )
    next_invoice_date = fields.Date(
        string='Next Invoice Date',
        help="Date for the next recurring billing cycle."
    )
    mrr_total = fields.Monetary(
        string='MRR Total', compute='_compute_mrr_totals',
        currency_field='currency_id'
    )
    non_recurring_total = fields.Monetary(
        string='Non Recurring Total', compute='_compute_mrr_totals',
        currency_field='currency_id'
    )

    referrer_id = fields.Many2one(
        'res.partner', string='Referrer',
        help="Select referring partner for this order."
    )

    is_price_locked = fields.Boolean(
        string='Price Locked', default=False,
        help="If checked, the unit prices on recurring lines are grandfathered and locked."
    )
    close_reason_id = fields.Many2one(
        'subscription.close.reason', string='Close Reason'
    )
    close_reason_notes = fields.Text(string='Close Notes')

    subscription_cycle = fields.Integer(
        string='Current Cycle', default=1, copy=False,
        help="Tracks the number of billing cycles completed plus the current one."
    )

    subscription_state = fields.Selection([
        ('1_draft', 'Draft'),
        ('2_renewal', 'Renewal'),
        ('3_progress', 'In Progress'),
        ('4_paused', 'Paused'),
        ('5_renewed', 'Renewed'),
        ('6_churn', 'Churned'),
        ('7_upsell', 'Upsell'),
        ('8_blocked', 'Blocked'),
    ], string='Subscription Status', default='1_draft', copy=False, tracking=True)

    dunning_plan_id = fields.Many2one(
        'subscription.dunning.plan', string='Dunning Plan',
        help="Dunning plan to apply if a payment fails."
    )
    payment_token_id = fields.Many2one(
        'payment.token', string='Payment Token',
        domain="[('partner_id', '=', partner_id)]",
        help="Saved payment method used for automatic billing."
    )
    is_in_dunning = fields.Boolean(string='In Dunning', default=False)
    next_dunning_date = fields.Date(string='Next Dunning Date')
    dunning_stage_id = fields.Many2one(
        'subscription.dunning.plan.line', string='Current Dunning Stage'
    )

    @api.depends(
        'order_line.price_subtotal', 'plan_id',
        'order_line.product_id.recurring_ok',
        'order_line.product_id.subscription_plan_id'
    )
    def _compute_mrr_totals(self):
        """Compute the Monthly Recurring Revenue (MRR) and non-recurring revenue
        totals from order lines, normalizing each recurring line to a monthly figure."""
        for order in self:
            mrr_total = 0.0
            non_recurring_total = 0.0
            for line in order.order_line:
                if line.product_id.recurring_ok:
                    plan = line.product_id.subscription_plan_id or order.plan_id
                    subtotal = line.price_subtotal
                    if plan:
                        period = plan.billing_period
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
                        elif period == 'custom' and plan.custom_days:
                            mrr = subtotal * (30.0 / plan.custom_days)
                        else:
                            mrr = subtotal
                        mrr_total += mrr
                    else:
                        mrr_total += subtotal
                else:
                    non_recurring_total += line.price_subtotal
            order.mrr_total = mrr_total
            order.non_recurring_total = non_recurring_total

    def _action_cancel(self):
        """Override standard cancel to mark active subscriptions as churned."""
        res = super()._action_cancel()
        for order in self:
            if order.plan_id and order.subscription_state not in ('1_draft', '6_churn'):
                order.subscription_state = '6_churn'
        return res

    def action_confirm(self):
        """Override standard action_confirm to auto-activate and set next invoice date."""
        res = super().action_confirm()
        for order in self:
            if order.plan_id:
                vals = {
                    'subscription_state': '3_progress',
                }
                if not order.next_invoice_date:
                    vals['next_invoice_date'] = fields.Date.today()
                order.write(vals)
        return res

    def action_upsell(self):
        """Create a new draft Sales Order quotation pre-filled with existing
        subscription lines for upselling additional items."""
        self.ensure_one()
        upsell_order = self.copy({
            'origin': _("Upsell of %s") % self.name,
            'state': 'draft',
            'client_order_ref': False,
            'subscription_state': '7_upsell',
        })
        return {
            'name': _('Upsell Quotation'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': upsell_order.id,
            'views': [(self.env.ref('subscription_management.view_subscription_order_form').id, 'form')],
            'target': 'current',
        }

    def action_renew(self):
        """Create a new draft Sales Order copying all lines from this order
        to initiate a subscription renewal."""
        self.ensure_one()
        renew_order = self.copy({
            'origin': _("Renewal of %s") % self.name,
            'state': 'draft',
            'client_order_ref': False,
            'subscription_state': '2_renewal',
        })

        return {
            'name': _('Renewal Quotation'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': renew_order.id,
            'views': [(self.env.ref('subscription_management.view_subscription_order_form').id, 'form')],
            'target': 'current',
        }

    def action_close(self):
        """Open the Close Subscription wizard to select a churn reason and
        gracefully terminate the active subscription order."""
        self.ensure_one()
        return {
            'name': _('Close Subscription Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            }
        }

    def _action_close_confirm(self, close_reason_id=None, notes=None):
        """Apply the selected close reason and permanently close/churn the subscription."""
        for order in self:
            vals = {
                'subscription_state': '6_churn',
                'state': 'cancel',
            }
            if close_reason_id:
                vals['close_reason_id'] = close_reason_id
            if notes:
                vals['close_reason_notes'] = notes
            order.write(vals)
            order.message_post(body=_("Subscription closed/churned."))

    def action_mrr_smart_button(self):
        """Returns the window action details to navigate to and display MRR breakdown analysis records linked to this subscription."""
        self.ensure_one()
        return {
            'name': _('MRR Analysis'),
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.mrr.breakdown',
            'view_mode': 'list,pivot,graph',
            'domain': [('sale_order_id', '=', self.id)],
        }

    def action_lock_prices(self):
        """Locks the unit prices of recurring items (grandfathering) on this subscription to protect them from future automatic pricelist updates."""
        self.write({'is_price_locked': True})
        self.message_post(body=_("Subscription prices have been locked (grandfathered)."))

    def action_unlock_prices(self):
        """Unlocks unit prices on this subscription to allow automated pricelist updates or manual reapplications to modify them."""
        self.write({'is_price_locked': False})
        self.message_post(body=_("Subscription prices have been unlocked."))

    def action_apply_latest_prices(self):
        """Compares and overrides unit prices on all recurring lines of this subscription with the latest product template list prices, logging price change actions."""
        updated = 0
        for line in self.order_line.filtered(lambda l: l.product_id.recurring_ok):
            new_price = line.product_id.list_price
            if new_price != line.price_unit:
                self.env['subscription.price.change.log'].create({
                    'sale_order_id': self.id,
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
            self.message_post(body=Markup(_('<b>%d line(s)</b> updated to latest product prices.')) % updated)
        else:
            self.message_post(body=_('All line prices are already up to date.'))
        return True

    def action_view_price_history(self):
        """Returns the window action to display price changes and logs linked to this subscription."""
        self.ensure_one()
        return {
            'name': _('Price History'),
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.price.change.log',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
        }

    def action_pause(self):
        """Pauses billing cycle processing and places the subscription in paused state."""
        self.write({'subscription_state': '4_paused'})
        self.message_post(body=_("Subscription has been paused."))

    def action_resume(self):
        """Resumes active recurring billing cycle processing on this paused subscription."""
        self.write({'subscription_state': '3_progress'})
        self.message_post(body=_("Subscription has been resumed."))

    def action_change_seats(self, line_id, new_quantity):
        """Modifies recurring line quantities (seats) dynamically, applying proration rules for remaining days in cycle."""
        self.ensure_one()
        line = self.env['sale.order.line'].browse(line_id)
        if not line or line.order_id.id != self.id:
            return False
        
        old_qty = line.product_uom_qty
        qty_diff = new_quantity - old_qty
        if qty_diff <= 0:
            line.with_context(_price_lock_bypass=True).write({'product_uom_qty': new_quantity})
            return True
            
        # Proration logic
        today = fields.Date.today()
        next_date = self.next_invoice_date
        
        if next_date and next_date > today:
            days_remaining = (next_date - today).days
            # Calculate total cycle days based on billing period
            delta = self._get_billing_delta()
            cycle_start = next_date - delta
            total_days = (next_date - cycle_start).days
            if total_days <= 0:
                total_days = 30
            
            proration_ratio = max(0, min(1, days_remaining / total_days))
            prorated_amount = (qty_diff * line.price_unit) * proration_ratio
            
            if prorated_amount > 0:
                self.env['subscription.proration'].create({
                    'subscription_order_id': self.id,
                    'product_id': line.product_id.id,
                    'description': _('Prorated charge for %s added seats (%s days remaining)') % (qty_diff, days_remaining),
                    'quantity': qty_diff,
                    'amount': prorated_amount,
                })
        
        line.with_context(_price_lock_bypass=True).write({'product_uom_qty': new_quantity})
        self.message_post(body=Markup(_('Quantity of <b>%s</b> updated from %s to %s. Prorated charges applied if applicable.')) % (line.product_id.display_name, old_qty, new_quantity))
        return True

    def _preview_next_invoice(self):
        """Generates a complete, structured dictionary preview of lines, taxes, and totals for the next scheduled invoice cycle."""
        self.ensure_one()
        preview = {
            'next_invoice_date': self.next_invoice_date or fields.Date.today(),
            'lines': [],
            'discount_amount': 0.0,
            'coupon_code': False,
            'tax_amount': 0.0,
            'grand_total': 0.0,
        }
        
        subtotal_before_discount = 0.0
        tax_total = 0.0
        
        # 1. Base Recurring Lines
        recurring_lines = self.order_line.filtered(lambda l: l.product_id.recurring_ok and not l.is_reward_line)
        for line in recurring_lines:
            price_unit = line.price_unit
            if self.plan_id and self.plan_id.ramp_ids:
                for ramp in self.plan_id.ramp_ids.sorted('start_cycle'):
                    if ramp.start_cycle <= self.subscription_cycle <= ramp.end_cycle:
                        price_unit = ramp.price_unit
                        break

            subtotal = price_unit * line.product_uom_qty
            discount_amount = subtotal * (line.discount / 100.0) if line.discount else 0.0
            
            tax_amt = 0.0
            if line.tax_ids:
                taxes = line.tax_ids.compute_all(price_unit, self.currency_id, line.product_uom_qty, line.product_id, self.partner_id)
                tax_amt = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
            
            preview['lines'].append({
                'product_name': line.product_id.display_name,
                'quantity': line.product_uom_qty,
                'price_unit': price_unit,
                'subtotal': subtotal,
            })
            
            subtotal_before_discount += subtotal
            tax_total += tax_amt
            preview['discount_amount'] += discount_amount

        # 1.5 Native Loyalty Reward Lines
        reward_lines = self.order_line.filtered(lambda l: l.is_reward_line)
        for line in reward_lines:
            # Reward lines typically have negative price_unit
            subtotal = line.price_unit * line.product_uom_qty
            preview['lines'].append({
                'product_name': line.name or line.product_id.display_name,
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
                'subtotal': subtotal,
            })
            preview['discount_amount'] += abs(subtotal)
            
            if line.tax_ids:
                taxes = line.tax_ids.compute_all(line.price_unit, self.currency_id, line.product_uom_qty, line.product_id, self.partner_id)
                tax_amt = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                tax_total += tax_amt

        # 2. Unbilled Usage
        usages = self.env['subscription.usage'].search([
            ('subscription_order_id', '=', self.id),
            ('billed', '=', False)
        ])
        for usage in usages:
            price_unit = usage.product_id.list_price
            subtotal = price_unit * usage.quantity
            preview['lines'].append({
                'product_name': f"Usage: {usage.description or usage.product_id.display_name}",
                'quantity': usage.quantity,
                'price_unit': price_unit,
                'subtotal': subtotal,
            })
            subtotal_before_discount += subtotal
            if usage.product_id.taxes_id:
                taxes = usage.product_id.taxes_id.compute_all(price_unit, self.currency_id, usage.quantity, usage.product_id, self.partner_id)
                tax_total += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))

        # 3. Unbilled Prorations
        prorations = self.env['subscription.proration'].search([
            ('subscription_order_id', '=', self.id),
            ('invoiced', '=', False)
        ])
        for proro in prorations:
            subtotal = proro.amount
            price_unit = subtotal / proro.quantity if proro.quantity else subtotal
            preview['lines'].append({
                'product_name': proro.description,
                'quantity': proro.quantity,
                'price_unit': price_unit,
                'subtotal': subtotal,
            })
            subtotal_before_discount += subtotal
            if proro.product_id.taxes_id:
                taxes = proro.product_id.taxes_id.compute_all(price_unit, self.currency_id, proro.quantity, proro.product_id, self.partner_id)
                tax_total += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))

        preview['tax_amount'] = tax_total
        preview['grand_total'] = subtotal_before_discount - preview['discount_amount'] + tax_total
        return preview

    # ── Invoicing ─────────────────────────────────────────────────────────────

    def _get_billing_delta(self):
        """Calculates and returns the python dateutil relativedelta duration representing the active subscription plan's billing period."""
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

    def _generate_recurring_invoice(self):
        """Generates, posts, and attempts automatic payment collection for the next recurring cycle invoice, initiating dunning if the payment fails."""
        self.ensure_one()
        if self.subscription_state not in ('3_progress',):
            return False
        recurring_lines = self.order_line.filtered(lambda l: l.product_id.recurring_ok and not l.is_reward_line)
        reward_lines = self.order_line.filtered(lambda l: l.is_reward_line)
        
        if not recurring_lines:
            return False

        invoice_lines = []
        for line in recurring_lines:
            # Check for Ramp Pricing overrides based on the current subscription cycle
            price_unit = line.price_unit
            if self.plan_id and self.plan_id.ramp_ids:
                for ramp in self.plan_id.ramp_ids.sorted('start_cycle'):
                    if ramp.start_cycle <= self.subscription_cycle <= ramp.end_cycle:
                        price_unit = ramp.price_unit
                        # Update the sale order line so the UI reflects the current cycle's price.
                        # Bypassing the lock so the contract explicitly ramps up/down as planned.
                        if line.price_unit != price_unit:
                            line.with_context(_price_lock_bypass=True).write({'price_unit': price_unit})
                            self.message_post(body=Markup(_(
                                '<b>Ramp Pricing Applied:</b> Cycle %s reached.<br/>'
                                'Unit price for <b>%s</b> updated to <b>%.2f</b>.'
                            )) % (self.subscription_cycle, line.product_id.display_name, price_unit))
                        break # First matching ramp applies

            invoice_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name or line.product_id.name,
                'quantity': line.product_uom_qty,
                'price_unit': price_unit,
                'discount': line.discount,
                'tax_ids': [(6, 0, line.tax_ids.ids)] if line.tax_ids else False,
                'sale_line_ids': [(4, line.id)],
            }))

        for r_line in reward_lines:
            # Check if reward is still applicable based on custom recurring logic
            program = r_line.reward_id.program_id if hasattr(r_line, 'reward_id') and r_line.reward_id else False
            if program:
                if program.recurring_type == 'first' and self.subscription_cycle > 1:
                    continue
                if program.recurring_type == 'limited' and self.subscription_cycle > program.recurring_invoices:
                    continue

            invoice_lines.append((0, 0, {
                'product_id': r_line.product_id.id,
                'name': r_line.name or r_line.product_id.name,
                'quantity': r_line.product_uom_qty,
                'price_unit': r_line.price_unit,
                'discount': r_line.discount,
                'tax_ids': [(6, 0, r_line.tax_ids.ids)] if r_line.tax_ids else False,
                'sale_line_ids': [(4, r_line.id)],
            }))

        # Add unbilled usage
        usages = self.env['subscription.usage'].search([
            ('subscription_order_id', '=', self.id),
            ('billed', '=', False)
        ])
        for usage in usages:
            invoice_lines.append((0, 0, {
                'product_id': usage.product_id.id,
                'name': usage.description or usage.product_id.display_name,
                'quantity': usage.quantity,
                'price_unit': usage.product_id.list_price,
                'tax_ids': [(6, 0, usage.product_id.taxes_id.ids)] if usage.product_id.taxes_id else False,
            }))
            usage.write({'billed': True})

        # Add unbilled proration
        prorations = self.env['subscription.proration'].search([
            ('subscription_order_id', '=', self.id),
            ('invoiced', '=', False)
        ])
        for proro in prorations:
            invoice_lines.append((0, 0, {
                'product_id': proro.product_id.id,
                'name': proro.description,
                'quantity': proro.quantity,
                'price_unit': proro.amount / proro.quantity if proro.quantity else proro.amount,
                'tax_ids': [(6, 0, proro.product_id.taxes_id.ids)] if proro.product_id.taxes_id else False,
            }))
            proro.write({'invoiced': True})

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': invoice_lines,
        })

        for line in recurring_lines:
            line.invoice_lines = [(4, il.id) for il in invoice.invoice_line_ids if il.product_id == line.product_id]

        invoice.action_post()
        payment_success = False
        if self.payment_token_id:
            try:
                with self.env.cr.savepoint():
                    tx = self.env['payment.transaction'].create({
                        'amount': invoice.amount_total,
                        'currency_id': invoice.currency_id.id,
                        'partner_id': invoice.partner_id.id,
                        'token_id': self.payment_token_id.id,
                        'provider_id': self.payment_token_id.provider_id.id,
                        'payment_method_id': self.payment_token_id.payment_method_id.id,
                        'operation': 'offline',
                    })
                    tx._send_payment_request()
                    if tx.state in ('done', 'authorized'):
                        payment_success = True
                        tx.invoice_ids = [(6, 0, invoice.ids)]
            except Exception as e:
                self.message_post(body=Markup(_("Payment attempt failed: %s")) % str(e))

        delta = self._get_billing_delta()
        next_date = (self.next_invoice_date or fields.Date.today()) + delta
        
        vals = {
            'next_invoice_date': next_date,
            'subscription_cycle': self.subscription_cycle + 1,
        }
        if not payment_success and self.dunning_plan_id:
            vals['is_in_dunning'] = True
            vals['next_dunning_date'] = fields.Date.today()
            if not self.payment_token_id:
                self.message_post(body=Markup(_("Invoice %s generated, but no payment token is on file. Subscription placed in Dunning." % invoice.name)))
            
        self.write(vals)
        return invoice

    @api.model
    def _cron_generate_invoices(self):
        """Automated scheduled action running daily to identify active subscriptions due for recurring billing and generate their next cycle invoices."""
        today = fields.Date.today()
        due_subs = self.search([
            ('subscription_state', 'in', ['3_progress']),
            ('next_invoice_date', '<=', today),
        ])
        for sub in due_subs:
            try:
                with self.env.cr.savepoint():
                    sub._generate_recurring_invoice()
            except Exception as e:
                sub.message_post(body=Markup(_('Invoice generation failed: %s. Retrying tomorrow.')) % str(e))
                sub.next_invoice_date = sub.next_invoice_date + relativedelta(days=1)

    @api.model
    def _cron_dunning_and_retry(self):
        """Automated scheduled action running daily to process payment-failed active subscriptions in dunning, executing stage level actions and dispatching WhatsApp alerts."""
        today = fields.Date.today()
        dunning_subs = self.search([
            ('is_in_dunning', '=', True),
            ('subscription_state', 'in', ['3_progress', '4_paused', '8_blocked']),
            ('next_dunning_date', '<=', today)
        ])
        for sub in dunning_subs:
            # Find unpaid invoice
            unpaid_invoices = sub.invoice_ids.filtered(lambda inv: inv.state == 'posted' and inv.payment_state in ('not_paid', 'partial'))
            if not unpaid_invoices:
                sub.write({'is_in_dunning': False, 'dunning_stage_id': False})
                continue
            
            invoice = unpaid_invoices[0]
            
            # Determine stage
            days_overdue = (today - (invoice.invoice_date_due or invoice.date or today)).days
            stages = sub.dunning_plan_id.line_ids.filtered(lambda s: s.delay_days <= days_overdue).sorted('delay_days')
            current_stage = stages[-1] if stages else False
            
            if current_stage and sub.dunning_stage_id != current_stage:
                sub.dunning_stage_id = current_stage.id
                
                # Retry Payment
                payment_success = False
                if sub.payment_token_id:
                    try:
                        tx = self.env['payment.transaction'].create({
                            'amount': invoice.amount_residual,
                            'currency_id': invoice.currency_id.id,
                            'partner_id': invoice.partner_id.id,
                            'token_id': sub.payment_token_id.id,
                            'provider_id': sub.payment_token_id.provider_id.id,
                            'payment_method_id': sub.payment_token_id.payment_method_id.id,
                            'operation': 'offline',
                        })
                        tx._send_payment_request()
                        if tx.state in ('done', 'authorized'):
                            payment_success = True
                            tx.invoice_ids = [(6, 0, invoice.ids)]
                    except Exception as e:
                        sub.message_post(body=Markup(_("Smart Retry failed: %s")) % str(e))
                        
                if payment_success:
                    sub.write({'is_in_dunning': False, 'dunning_stage_id': False})
                    sub.message_post(body=_("Smart Retry successful. Subscription active."))
                    
                    # Send successful payment WhatsApp notification
                    msg = _("Dear Customer, your subscription payment of %s %s was successful. Your subscription %s is now active. Thank you!") % (invoice.amount_residual, invoice.currency_id.name, sub.name)
                    sub._send_whatsapp_notification(msg)
                    continue
                else:
                    if current_stage.mail_template_id:
                        current_stage.mail_template_id.send_mail(sub.id, force_send=True)
                        
                    # Send failed payment/retry WhatsApp notification
                    if current_stage.send_whatsapp:
                        status_lbl = _("Pending")
                        if current_stage.action_type == 'pause':
                            status_lbl = _("Paused")
                        elif current_stage.action_type == 'close':
                            status_lbl = _("Cancelled")
                        elif current_stage.action_type == 'block':
                            status_lbl = _("Blocked")
                            
                        from odoo.tools import html2plaintext
                        template_text = current_stage.whatsapp_template_id.body if current_stage.whatsapp_template_id else False
                        if template_text:
                            template_text = html2plaintext(template_text)
                            try:
                                msg = template_text.format(
                                    customer_name=sub.partner_id.name or '',
                                    subscription_name=sub.name or '',
                                    invoice_amount=invoice.amount_residual or 0.0,
                                    invoice_currency=invoice.currency_id.name or '',
                                    status_label=status_lbl
                                )
                            except Exception:
                                # Fallback if customer entered invalid brackets/placeholder syntax
                                msg = template_text
                        else:
                            msg = _("Dear %s, we tried to process the payment of %s %s for your subscription %s, but it failed. Please update your payment method. Current Status: %s") % (sub.partner_id.name, invoice.amount_residual, invoice.currency_id.name, sub.name, status_lbl)
                            
                        sub._send_whatsapp_notification(msg)

                    if current_stage.action_type == 'pause':
                        sub.action_pause()
                        sub.message_post(body=_("Subscription paused due to failed payment."))
                    elif current_stage.action_type == 'close':
                        sub.write({'subscription_state': '6_churn'})
                        sub.message_post(body=_("Subscription cancelled due to failed payment."))
                    elif current_stage.action_type == 'block':
                        sub.write({'subscription_state': '8_blocked'})
                        sub.message_post(body=_("Subscription blocked due to failed payment."))
            
            # Calculate next dunning date
            next_stages = sub.dunning_plan_id.line_ids.filtered(lambda s: s.delay_days > days_overdue).sorted('delay_days')
            if next_stages:
                next_delay = next_stages[0].delay_days - days_overdue
                sub.next_dunning_date = today + relativedelta(days=next_delay)
            else:
                sub.next_dunning_date = today + relativedelta(days=1) # Fallback

    def _send_whatsapp_notification(self, message):
        """Dispatches an automated WhatsApp notification text message via the UltraMsg Gateway api
        to the customer phone or mobile contact, and logs the API response state back to chatter logs."""
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return

        phone_number = False
        if 'mobile' in partner._fields and partner.mobile:
            phone_number = partner.mobile
        elif partner.phone:
            phone_number = partner.phone

        if not phone_number:
            return

        # Strip all non-numeric characters except digits
        clean_phone = "".join(c for c in phone_number if c.isdigit())

        # Retrieve UltraMsg Settings from subscription.whatsapp.config
        config = self.env['subscription.whatsapp.config'].get_config()

        if not config or not config.instance_id or not config.token:
            # Fallback / Log if not configured yet
            self.message_post(body=_("[WhatsApp Simulation - UltraMsg Not Configured] To: %s | Message: %s") % (clean_phone, message))
            return

        instance_id = config.instance_id
        token = config.token

        url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
        payload = {
            "token": token,
            "to": clean_phone,
            "body": message
        }
        headers = {
            "content-type": "application/x-www-form-urlencoded"
        }
        
        try:
            # Make the UltraMsg POST request synchronously but safely caught
            response = requests.post(url, data=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get('sent') == 'true' or res_data.get('id'):
                    self.message_post(body=_("WhatsApp message successfully sent via UltraMsg to %s.") % clean_phone)
                else:
                    self.message_post(body=_("UltraMsg responded with error: %s") % response.text)
            else:
                self.message_post(body=_("Failed to send WhatsApp message via UltraMsg. HTTP Status: %s. Response: %s") % (response.status_code, response.text))
        except Exception as e:
            self.message_post(body=_("Error sending WhatsApp message via UltraMsg: %s") % str(e))

    @api.model
    def _cron_recurring_billing(self):
        """Fallback for older databases where the cron job was registered with the previous method name."""
        return self._cron_generate_invoices()


class SaleOrderLine(models.Model):
    """Inherited Sale Order Line to track specific physical or human resources
    associated with service subscription line items."""

    _inherit = 'sale.order.line'

    resource_id = fields.Many2one(
        'res.partner', string='Resource',
        help="Select resource associated with this line."
    )

    def write(self, vals):
        # Block price_unit changes on lines belonging to a price-locked subscription.
        if 'price_unit' in vals and not self.env.context.get('_price_lock_bypass'):
            locked_lines = self.filtered(lambda l: l.order_id.is_price_locked and l.product_id.recurring_ok)
            if locked_lines:
                product_names = ', '.join(locked_lines.mapped('product_id.name'))
                raise UserError(_(
                    "Cannot modify unit price for the following products because "
                    "this subscription has grandfathered (price-locked) pricing:\n%s\n\n"
                    "To update prices, first unlock the subscription via "
                    "'Unlock Prices' or use 'Apply Latest Prices'."
                ) % product_names)
        return super().write(vals)


# ── Wizards ───────────────────────────────────────────────────────────────────

class SubscriptionCloseWizard(models.TransientModel):
    """Wizard allowing users to select a close reason before terminating a subscription."""

    _name = 'subscription.close.wizard'
    _description = 'Close Subscription Wizard'

    sale_order_id = fields.Many2one(
        'sale.order', string='Subscription (Sale Order)', required=True
    )
    close_reason_id = fields.Many2one(
        'subscription.close.reason', string='Close Reason'
    )
    notes = fields.Text(string='Notes')

    def action_close(self):
        """Apply the selected close reason and permanently close the subscription."""
        self.ensure_one()
        self.sale_order_id._action_close_confirm(
            close_reason_id=self.close_reason_id.id if self.close_reason_id else None,
            notes=self.notes,
        )
        return {'type': 'ir.actions.act_window_close'}


class SubscriptionChangePlanWizard(models.TransientModel):
    """Wizard for changing the subscription plan on an active contract."""

    _name = 'subscription.change.plan.wizard'
    _description = 'Change Subscription Plan Wizard'

    sale_order_id = fields.Many2one(
        'sale.order', string='Subscription (Sale Order)', required=True
    )
    plan_id = fields.Many2one(
        'subscription.plan', string='New Plan', required=True
    )

    def action_change_plan(self):
        """Update the subscription's plan and post a chatter message with the change."""
        self.ensure_one()
        self.sale_order_id.write({'plan_id': self.plan_id.id})
        self.sale_order_id.message_post(
            body=Markup(_('Subscription plan changed to <b>%s</b>.')) % self.plan_id.name
        )
        return {'type': 'ir.actions.act_window_close'}
