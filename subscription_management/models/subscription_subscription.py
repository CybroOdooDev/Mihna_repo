from odoo import models, fields, api, _
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError

class Subscription(models.Model):
    _name = 'subscription.subscription'
    _description = 'Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    plan_id = fields.Many2one('subscription.plan', string='Subscription Plan', required=True, tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', related='plan_id.currency_id', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_trial', 'In Trial'),
        ('in_progress', 'Active'),
        ('paused', 'Paused'),
        ('in_dunning', 'In Dunning'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('renewed', 'Renewed'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed')
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

    @api.depends('line_ids.price_subtotal', 'plan_id')
    def _compute_mrr_total(self):
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
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('subscription.subscription') or _('New')
        return super().create(vals_list)

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            if self.sale_order_id.partner_id:
                self.partner_id = self.sale_order_id.partner_id.id
            if self.sale_order_id.plan_id:
                self.plan_id = self.sale_order_id.plan_id.id

    @api.onchange('plan_id')
    def _onchange_plan_id(self):
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

    def action_start_trial(self):
        for rec in self:
            if rec.state == 'draft' and rec.plan_id.trial_period_days > 0:
                rec.state = 'in_trial'
                rec.start_date = fields.Date.context_today(self)
                rec.trial_end_date = rec.start_date + timedelta(days=rec.plan_id.trial_period_days)
                rec.next_invoice_date = rec.trial_end_date
                rec.message_post(body=_("Trial started. End of trial: %s") % rec.trial_end_date)
    
    def action_activate(self):
        for rec in self:
            if rec.state in ['draft', 'in_trial', 'paused']:
                rec.state = 'in_progress'
                if not rec.start_date:
                    rec.start_date = fields.Date.context_today(self)
                if not rec.next_invoice_date:
                    rec.next_invoice_date = fields.Date.context_today(self)
                rec.message_post(body=_("Subscription activated! Next renewal date set to: %s") % rec.next_invoice_date)

    def action_pause(self):
        for rec in self:
            if rec.state == 'in_progress':
                rec.state = 'paused'
                rec.pause_date = fields.Date.context_today(self)
                rec.message_post(body=_("Subscription paused on %s.") % rec.pause_date)

    def action_resume(self):
        for rec in self:
            if rec.state == 'paused':
                rec.state = 'in_progress'
                rec.resume_date = fields.Date.context_today(self)
                # If next invoice date was during pause, set it to today so billing catch up occurs
                if rec.next_invoice_date and rec.next_invoice_date < fields.Date.context_today(self):
                    rec.next_invoice_date = fields.Date.context_today(self)
                rec.message_post(body=_("Subscription resumed! Next renewal date: %s") % rec.next_invoice_date)

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'
            rec.cancel_date = fields.Date.context_today(self)
            rec.message_post(body=_("Subscription cancelled on %s.") % rec.cancel_date)

    def action_close(self):
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
            'invoice_line_ids': [],
        }

        for line in self.line_ids:
            invoice_vals['invoice_line_ids'].append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
            }))

        invoice = self.env['account.move'].create(invoice_vals)
        
        # Post the invoice automatically
        try:
            invoice.action_post()
            self.message_post(body=_("Auto-generated and posted Invoice %s.") % invoice.name)
        except Exception as e:
            self.message_post(body=_("Created draft Invoice %s. Auto-post failed: %s") % (invoice.name, str(e)))

        # Update Next Invoice Date
        self._increment_next_invoice_date()
        return invoice

    def _increment_next_invoice_date(self):
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
            'move_ids_without_package': []
        }

        for line in physical_lines:
            picking_vals['move_ids_without_package'].append((0, 0, {
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'location_id': source_loc,
                'location_dest_id': dest_loc,
            }))

        picking = self.env['stock.picking'].create(picking_vals)
        picking.action_confirm()
        self.message_post(body=_("Auto-created Delivery Order %s.") % picking.name)
        return picking

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
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        action['domain'] = [('subscription_id', '=', self.id)]
        action['context'] = {'default_move_type': 'out_invoice', 'default_subscription_id': self.id}
        return action

    def action_view_pickings(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        action['domain'] = [('subscription_id', '=', self.id)]
        action['context'] = {'default_subscription_id': self.id}
        return action

    def action_view_sales_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
        action['domain'] = [('id', '=', self.sale_order_id.id)]
        action['res_id'] = self.sale_order_id.id
        action['view_mode'] = 'form'
        action['views'] = [(False, 'form')]
        return action

    def action_preview_subscription(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/my/subscription/%s' % self.id,
            'target': 'new',
        }

class SubscriptionCloseWizard(models.TransientModel):
    _name = 'subscription.close.wizard'
    _description = 'Subscription Close Wizard'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', required=True)
    close_reason_id = fields.Many2one('subscription.close.reason', string='Close Reason', required=True)
    description = fields.Text(string='Details')

    def action_close_subscription(self):
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
