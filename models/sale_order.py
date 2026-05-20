# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    """Inherited Sale Order model representing customer quotation and order pipeline linked to active subscription contracts."""
    _inherit = 'sale.order'

    subscription_ids = fields.One2many('subscription.subscription', 'sale_order_id', string='Subscriptions', readonly=True)
    subscription_count = fields.Integer(string='Subscription Count', compute='_compute_subscription_count')
    
    def _default_plan_id(self):
        """Retrieve the default recurring billing plan for new Sales Orders."""
        plan = self.env['subscription.plan'].search([('billing_period', '=', 'monthly')], limit=1)
        if not plan:
            plan = self.env['subscription.plan'].search([], limit=1)
        return plan.id if plan else False

    plan_id = fields.Many2one('subscription.plan', string='Recurring Plan', default=_default_plan_id, help="Select the recurring billing plan for this quotation.")
    subscription_end_date = fields.Date(string='Until', help="End date of the subscription.")
    next_invoice_date = fields.Date(string='Next Invoice Date', help="Date for the next recurring billing cycle.")
    mrr_total = fields.Monetary(string='MRR Total', compute='_compute_mrr_totals', currency_field='currency_id')
    non_recurring_total = fields.Monetary(string='Non Recurring Total', compute='_compute_mrr_totals', currency_field='currency_id')
    
    referrer_id = fields.Many2one('res.partner', string='Referrer', help="Select referring partner for this order.")
    coupon_id = fields.Many2one('subscription.coupon', string='Applied Coupon', help="Applied coupon for discounts.")
 
    subscription_state = fields.Selection([
        ('1_draft', 'Draft'),
        ('2_renewal', 'Renewal'),
        ('3_progress', 'In Progress'),
        ('4_paused', 'Paused'),
        ('5_renewed', 'Renewed'),
        ('6_churn', 'Churned'),
        ('7_upsell', 'Upsell'),
    ], string='Subscription Status', compute='_compute_subscription_state', store=True)
 
    @api.depends('state', 'plan_id', 'subscription_ids.state', 'origin')
    def _compute_subscription_state(self):
        """Compute the current subscription status based on order status and contract states."""
        for order in self:
            if not order.plan_id:
                order.subscription_state = False
            elif order.state in ('draft', 'sent'):
                if order.origin and "Renewal of" in order.origin:
                    order.subscription_state = '2_renewal'
                elif order.origin and "Upsell of" in order.origin:
                    order.subscription_state = '7_upsell'
                else:
                    order.subscription_state = '1_draft'
            elif order.state == 'cancel':
                order.subscription_state = '6_churn'
            elif order.subscription_ids:
                # If all subscriptions are closed/cancelled, order is churned
                if all(s.state in ('closed', 'cancelled') for s in order.subscription_ids):
                    order.subscription_state = '6_churn'
                # If all non-closed subscriptions are paused, order status is paused
                elif all(s.state == 'paused' for s in order.subscription_ids.filtered(lambda x: x.state not in ('closed', 'cancelled'))):
                    order.subscription_state = '4_paused'
                else:
                    order.subscription_state = '3_progress'
            elif order.state == 'sale':
                order.subscription_state = '3_progress'
            else:
                order.subscription_state = False
 
    @api.depends('subscription_ids')
    def _compute_subscription_count(self):
        """Compute the total count of active subscription contracts linked to this Sales Order."""
        for order in self:
            order.subscription_count = len(order.subscription_ids)
 
    @api.depends('order_line.price_subtotal', 'plan_id', 'order_line.product_id.recurring_ok', 'order_line.product_id.subscription_plan_id')
    def _compute_mrr_totals(self):
        """Compute the Monthly Recurring Revenue (MRR) and non-recurring revenue totals from order lines."""
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

    def action_confirm(self):
        """Override standard action_confirm to auto-generate corresponding subscription contract records."""
        res = super().action_confirm()
        for order in self:
            order._create_subscriptions_from_order()
        return res

    def _create_subscriptions_from_order(self):
        """Find all recurring line items, group them by plan, and create the matching contracts."""
        self.ensure_one()
        # Find lines that contain a product set as recurring_ok
        recurring_lines = self.order_line.filtered(lambda l: l.product_id.recurring_ok)
        if not recurring_lines:
            return

        # Group lines by plan
        lines_by_plan = {}
        for line in recurring_lines:
            plan = line.product_id.subscription_plan_id or self.plan_id
            if plan:
                lines_by_plan.setdefault(plan, []).append(line)

        for plan, lines in lines_by_plan.items():
            # Create subscription
            sub = self.env['subscription.subscription'].create({
                'partner_id': self.partner_id.id,
                'plan_id': plan.id,
                'sale_order_id': self.id,
                'coupon_id': self.coupon_id.id,
                'next_invoice_date': self.next_invoice_date or fields.Date.today(),
                'state': 'draft',
            })
            # Clear default lines that might have been added by _onchange_plan_id
            sub.line_ids.unlink()
            
            # Copy lines from sales order
            sub_lines = []
            for line in lines:
                sub_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'discount': 0.0 if self.coupon_id else line.discount,
                }))
            sub.write({'line_ids': sub_lines})
            # If trial period exists, start trial, else activate
            if plan.trial_period_days > 0:
                sub.action_start_trial()
            else:
                sub.action_activate()

    def action_upsell(self):
        """Create a new draft Sales Order quotation specifically for upselling and adding items to this contract."""
        self.ensure_one()
        # Create a new draft quotation for upsell
        upsell_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'plan_id': self.plan_id.id,
            'partner_invoice_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'payment_term_id': self.payment_term_id.id,
            'origin': _("Upsell of %s") % self.name,
            'state': 'draft',
        })
        # Redirect to the new quotation form view using the subscription form layout
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
        """Create a new draft Sales Order quotation copying lines to renew the subscription contract."""
        self.ensure_one()
        # Create a new draft quotation for renewal
        renew_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'plan_id': self.plan_id.id,
            'partner_invoice_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'payment_term_id': self.payment_term_id.id,
            'origin': _("Renewal of %s") % self.name,
            'state': 'draft',
        })
        
        # Copy all subscription order lines from the original order
        for line in self.order_line:
            self.env['sale.order.line'].create({
                'order_id': renew_order.id,
                'product_id': line.product_id.id,
                'name': line.name,
                'product_uom_qty': line.product_uom_qty,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'resource_id': line.resource_id.id if hasattr(line, 'resource_id') and line.resource_id else False,
            })
            
        # Redirect to the new quotation form view using the subscription form layout
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
        """Trigger the close wizard to select a close reason and gracefully terminate active contracts."""
        self.ensure_one()
        active_subs = self.subscription_ids.filtered(lambda s: s.state not in ('closed', 'cancelled', 'expired'))
        if not active_subs:
            raise UserError(_("There are no active subscriptions associated with this sales order to close."))
        
        # Return the window action to open our beautiful close reason wizard!
        return {
            'name': _('Close Subscription Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_subscription_id': active_subs[0].id,
            }
        }


class SaleOrderLine(models.Model):
    """Inherited Sale Order Line to track specific physical or human resources associated with service items."""
    _inherit = 'sale.order.line'

    resource_id = fields.Many2one('res.partner', string='Resource', help="Select resource associated with this line.")
