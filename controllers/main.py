<<<<<<< HEAD
# -*- coding: utf-8 -*-
=======
<<<<<<< HEAD
# -*- coding: utf-8 -*-
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

class SubscriptionController(http.Controller):
<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
    """Subscription Controller managing the public frontend website plans, subscribe routes, checkouts, and coupon validation endpoints."""

    @http.route(['/subscriptions'], type='http', auth="public", website=True)
    def subscription_plans(self, **kw):
        """Render the public subscription plans landing page listing all active plans."""
<<<<<<< HEAD
=======
=======

    @http.route(['/subscriptions'], type='http', auth="public", website=True)
    def subscription_plans(self, **kw):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        plans = request.env['subscription.plan'].sudo().search([('active', '=', True)])
        return request.render('subscription_management.subscription_plans_page', {
            'plans': plans
        })

    @http.route(['/subscriptions/subscribe/<model("subscription.plan"):plan>'], type='http', auth="user", website=True)
    def subscription_subscribe(self, plan, **kw):
<<<<<<< HEAD
        """Handle direct 1-click subscription registration, creating a sales order and contract."""
=======
<<<<<<< HEAD
        """Handle direct 1-click subscription registration, creating a sales order and contract."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        partner = request.env.user.partner_id
        
        # Check if already has a draft/active subscription for this plan
        existing = request.env['subscription.subscription'].sudo().search([
            ('partner_id', '=', partner.id),
            ('plan_id', '=', plan.id),
            ('state', 'in', ['draft', 'in_trial', 'in_progress', 'paused'])
        ], limit=1)
        
        if existing:
            return request.render('subscription_management.subscription_success_page', {
                'plan': plan,
                'subscription': existing,
                'message': 'You already have an active or pending subscription for this plan.'
            })
            
<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        # Create a new draft sales order
        order = request.env['sale.order'].sudo().create({
            'partner_id': partner.id,
            'plan_id': plan.id,
            'state': 'draft',
        })
        
        # Find product
        product = plan.product_id or request.env['product.product'].sudo().search([('recurring_ok', '=', True), ('subscription_plan_id', '=', plan.id)], limit=1)
        if not product:
            product = request.env['product.product'].sudo().search([('recurring_ok', '=', True)], limit=1)
            
        if product:
            request.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'price_unit': plan.total_price,
            })
            
        # Confirm the sales order
        order.action_confirm()
        
        # Find the created subscription
        subscription = request.env['subscription.subscription'].sudo().search([('sale_order_id', '=', order.id)], limit=1)
        if not subscription:
            subscription = request.env['subscription.subscription'].sudo().create({
                'partner_id': partner.id,
                'plan_id': plan.id,
                'sale_order_id': order.id,
                'state': 'draft'
            })
            subscription._onchange_plan_id()
<<<<<<< HEAD
=======
=======
        # Create a new draft subscription
        subscription = request.env['subscription.subscription'].sudo().create({
            'partner_id': partner.id,
            'plan_id': plan.id,
            'state': 'draft'
        })
        # Trigger the onchange manually to populate lines since we are in backend code
        subscription._onchange_plan_id()
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        
        return request.render('subscription_management.subscription_success_page', {
            'plan': plan,
            'subscription': subscription,
            'message': 'Your subscription has been successfully created and is waiting for activation.'
        })

<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
    @http.route(['/subscriptions/checkout/<model("subscription.plan"):plan>'], type='http', auth="public", website=True)
    def subscription_checkout(self, plan, **kw):
        """Render the custom subscription checkout page with billing, coupon, and payment provider options."""
        partner = request.env.user.partner_id if not request.env.user._is_public() else request.env['res.partner']
        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([])
        providers = request.env['payment.provider'].sudo().search([('state', 'in', ['test', 'enabled'])])
        
        return request.render('subscription_management.subscription_checkout_page', {
            'plan': plan,
            'partner': partner,
            'countries': countries,
            'states': states,
            'providers': providers,
            'kw': kw
        })

    @http.route(['/subscriptions/checkout/validate_coupon'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def validate_coupon(self, coupon_code, plan_id, **kw):
        """Validate the applied coupon code asynchronously via JSON-RPC endpoint."""
        plan = request.env['subscription.plan'].sudo().browse(int(plan_id))
        if not plan.exists():
            return {'valid': False, 'message': 'Plan not found'}
            
        coupon = request.env['subscription.coupon'].sudo().search([
            ('code', '=ilike', coupon_code.strip()),
            ('active', '=', True)
        ], limit=1)
        
        if not coupon:
<<<<<<< HEAD
            return {'valid': False, 'message': 'Invalid coupon code.'}
            
        subtotal = plan.total_price or 0.0
        partner = request.env.user.partner_id if not request.env.user._is_public() else None
        
        is_valid, msg = coupon._validate_coupon(partner=partner, plan=plan, amount=subtotal)
        if not is_valid:
            return {'valid': False, 'message': msg}
            
=======
            return {'valid': False, 'message': 'Invalid or expired coupon code.'}
            
        subtotal = plan.total_price or 0.0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        discount_amount = 0.0
        if coupon.discount_type == 'percentage':
            discount_amount = subtotal * (coupon.discount_value / 100.0)
        elif coupon.discount_type == 'fixed':
            discount_amount = min(coupon.discount_value, subtotal)
            
        new_total = max(0.0, subtotal - discount_amount)
        
        # Format with currency symbol
        currency = plan.currency_id
        if currency:
            formatted_discount = f"{currency.symbol or ''}{discount_amount:.2f}"
            formatted_total = f"{currency.symbol or ''}{new_total:.2f}"
        else:
            formatted_discount = f"${discount_amount:.2f}"
            formatted_total = f"${new_total:.2f}"
            
        return {
            'valid': True,
            'coupon_id': coupon.id,
            'name': coupon.name,
            'code': coupon.code,
            'discount_type': coupon.discount_type,
            'discount_value': coupon.discount_value,
            'discount_amount': formatted_discount,
            'discount_amount_raw': discount_amount,
            'new_total': formatted_total,
            'new_total_raw': new_total,
            'message': 'Coupon applied successfully!'
        }

    @http.route(['/subscriptions/checkout/<model("subscription.plan"):plan>/confirm'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def subscription_checkout_confirm(self, plan, **kw):
        """Confirm checkout details, process payment, and activate the Sales Order & contract."""
        name = kw.get('name')
        email = kw.get('email')
        street = kw.get('street')
        city = kw.get('city')
        zip_code = kw.get('zip')
        country_id = kw.get('country_id')
        state_id = kw.get('state_id')
        
        if not request.env.user._is_public():
            partner = request.env.user.partner_id
            partner_vals = {}
            if not partner.street and street: partner_vals['street'] = street
            if not partner.city and city: partner_vals['city'] = city
            if not partner.zip and zip_code: partner_vals['zip'] = zip_code
            if not partner.country_id and country_id: partner_vals['country_id'] = int(country_id)
            if not partner.state_id and state_id: partner_vals['state_id'] = int(state_id)
            if partner_vals:
                partner.sudo().write(partner_vals)
        else:
            partner = request.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': name,
                    'email': email,
                    'street': street,
                    'city': city,
                    'zip': zip_code,
                    'country_id': int(country_id) if country_id else False,
                    'state_id': int(state_id) if state_id else False,
                })
        
        existing = request.env['subscription.subscription'].sudo().search([
            ('partner_id', '=', partner.id),
            ('plan_id', '=', plan.id),
            ('state', 'in', ['draft', 'in_trial', 'in_progress', 'paused'])
        ], limit=1)
        
        if existing:
            return request.render('subscription_management.subscription_success_page', {
                'plan': plan,
                'subscription': existing,
                'message': 'You already have an active or pending subscription for this plan.'
            })
            
        # Check for Coupon Code
        coupon_id = False
        coupon_code = kw.get('coupon_code')
        if coupon_code:
            coupon = request.env['subscription.coupon'].sudo().search([
                ('code', '=ilike', coupon_code.strip()),
                ('active', '=', True)
            ], limit=1)
            if coupon:
                coupon_id = coupon.id
            else:
                countries = request.env['res.country'].sudo().search([])
                states = request.env['res.country.state'].sudo().search([])
                providers = request.env['payment.provider'].sudo().search([('state', 'in', ['test', 'enabled'])])
                return request.render('subscription_management.subscription_checkout_page', {
                    'plan': plan,
                    'partner': partner,
                    'countries': countries,
                    'states': states,
                    'providers': providers,
                    'coupon_error': 'Invalid or expired coupon code. Please try again.',
                    'kw': kw
                })

        # Create a new draft sales order
        order = request.env['sale.order'].sudo().create({
            'partner_id': partner.id,
            'plan_id': plan.id,
            'coupon_id': coupon_id,
            'state': 'draft',
        })
        
        # Find product
        product = plan.product_id or request.env['product.product'].sudo().search([('recurring_ok', '=', True), ('subscription_plan_id', '=', plan.id)], limit=1)
        if not product:
            product = request.env['product.product'].sudo().search([('recurring_ok', '=', True)], limit=1)
            
        if product:
            price = plan.total_price
<<<<<<< HEAD
            discount_pct = 0.0
            
            if coupon_id:
                coupon = request.env['subscription.coupon'].sudo().browse(coupon_id)
                
                # Server-side enforcement of coupon rules
                is_valid, _msg = coupon._validate_coupon(partner=partner, plan=plan, amount=price)
                
                if not is_valid:
                    # Strip the coupon if it violates rules (e.g. usage limit exceeded right as they click pay)
                    coupon_id = None
                    order.sudo().write({'coupon_id': False})
                else:
                    if coupon.discount_type == 'percentage':
                        discount_pct = coupon.discount_value
                    elif coupon.discount_type == 'fixed':
                        if price > 0:
                            discount_pct = (coupon.discount_value / price) * 100.0
                            if discount_pct > 100.0:
                                discount_pct = 100.0
                            
            line = request.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
                'product_uom_qty': 1.0,
            })
            
            # Explicitly write price and discount after creation to bypass auto-computes!
            line.sudo().write({
                'price_unit': price,
                'discount': discount_pct,
            })
            
        # Confirm the sales order (leave it in draft/sent for payment processing if needed, but standard Odoo payment flow works with draft orders. We will leave it in draft for the payment gateway to process).
        
        # We redirect to the native payment step
        return request.redirect(f'/subscriptions/payment/{order.id}')

    @http.route(['/subscriptions/payment/<int:order_id>'], type='http', auth="public", website=True)
    def subscription_payment(self, order_id, **kw):
        """Render the native Odoo payment form for the draft subscription order."""
        order_sudo = request.env['sale.order'].sudo().browse(order_id)
        if not order_sudo.exists() or order_sudo.state not in ['draft', 'sent']:
            return request.redirect('/subscriptions')
            
        plan = order_sudo.plan_id
        if not plan:
            return request.redirect('/subscriptions')

        logged_in = not request.env.user._is_public()
        partner_sudo = request.env.user.partner_id if logged_in else order_sudo.partner_id
        company = order_sudo.company_id
        currency = order_sudo.currency_id
        amount = order_sudo.amount_total

        # Generate payment context native to Odoo 19
        availability_report = {}
        providers_sudo = request.env['payment.provider'].sudo()._get_compatible_providers(
            company.id, partner_sudo.id, amount, currency_id=currency.id,
            sale_order_id=order_sudo.id, report=availability_report
        )
        payment_methods_sudo = request.env['payment.method'].sudo()._get_compatible_payment_methods(
            providers_sudo.ids, partner_sudo.id, currency_id=currency.id,
            sale_order_id=order_sudo.id, report=availability_report
        )
        tokens_sudo = request.env['payment.token'].sudo()._get_available_tokens(
            providers_sudo.ids, partner_sudo.id
        )

        from odoo.addons.payment.controllers.portal import PaymentPortal
        
        payment_context = {
            'amount': amount,
            'currency': currency,
            'partner_id': partner_sudo.id,
            'providers_sudo': providers_sudo,
            'payment_methods_sudo': payment_methods_sudo,
            'tokens_sudo': tokens_sudo,
            'availability_report': availability_report,
            'transaction_route': f'/my/orders/{order_sudo.id}/transaction',
            'landing_route': f'/subscriptions/success/{order_sudo.id}',
            'access_token': order_sudo._portal_ensure_token(),
            'show_tokenize_input_mapping': PaymentPortal._compute_show_tokenize_input_mapping(
                providers_sudo, sale_order_id=order_sudo.id
            ),
            'company_mismatch': False,
            'expected_company': company,
        }

        render_values = {
            'plan': plan,
            'order': order_sudo,
        }
        render_values.update(payment_context)

        return request.render('subscription_management.subscription_payment_page', render_values)
        
    @http.route(['/subscriptions/success/<int:order_id>'], type='http', auth="public", website=True)
    def subscription_success(self, order_id, **kw):
        """Landing route after successful payment transaction."""
        order_sudo = request.env['sale.order'].sudo().browse(order_id)
        if not order_sudo.exists():
            return request.redirect('/subscriptions')
            
        # Ensure subscription is linked and active
        subscription = request.env['subscription.subscription'].sudo().search([('sale_order_id', '=', order_sudo.id)], limit=1)
        
        if not subscription and order_sudo.state in ['sale', 'done']:
            # The transaction callback confirmed the order, so we generate the subscription manually if it failed
            order_sudo.action_confirm()
            subscription = request.env['subscription.subscription'].sudo().search([('sale_order_id', '=', order_sudo.id)], limit=1)
            
        # In trial cases, we might bypass payment
        if subscription and subscription.plan_id.trial_period_days > 0 and subscription.state == 'draft':
            subscription.action_start_trial()

        return request.render('subscription_management.subscription_success_page', {
            'plan': order_sudo.plan_id,
            'subscription': subscription,
            'message': 'Your transaction was successful, and your subscription is now active!'
=======
            if coupon_id:
                coupon = request.env['subscription.coupon'].sudo().browse(coupon_id)
                if coupon.discount_type == 'percentage':
                    price = price * (1.0 - (coupon.discount_value / 100.0))
                elif coupon.discount_type == 'fixed':
                    price = max(0.0, price - coupon.discount_value)
                    
            request.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'price_unit': price,
            })
            
        # Confirm the sales order
        order.action_confirm()
        
        # Find the created subscription
        subscription = request.env['subscription.subscription'].sudo().search([('sale_order_id', '=', order.id)], limit=1)
        if not subscription:
            subscription = request.env['subscription.subscription'].sudo().create({
                'partner_id': partner.id,
                'plan_id': plan.id,
                'coupon_id': coupon_id,
                'sale_order_id': order.id,
                'state': 'draft',
            })
            subscription._onchange_plan_id()
            
        if plan.trial_period_days > 0:
            subscription.action_start_trial()
            msg = 'Your subscription has been successfully started with a free trial!'
        else:
            invoice = subscription.action_create_invoice()
            provider_id = kw.get('payment_provider_id')
            provider_name = ""
            if provider_id:
                provider = request.env['payment.provider'].sudo().browse(int(provider_id))
                if provider:
                    provider_name = provider.name
            subscription.action_pay_and_reconcile(invoice, provider_name=provider_name)
            subscription.action_activate()
            msg = 'Your payment was processed successfully, and your subscription is now active!'
            
        return request.render('subscription_management.subscription_success_page', {
            'plan': plan,
            'subscription': subscription,
            'message': msg
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        })

class CustomerPortalSubscription(CustomerPortal):
    """Customer Portal Subscription controller inheriting portal structures to expose self-service subscription listings and management features."""

    def _prepare_home_portal_values(self, selectors=None):
        """Inject the active subscription count into the customer portal home values."""
<<<<<<< HEAD
=======
=======
class CustomerPortalSubscription(CustomerPortal):

    def _prepare_home_portal_values(self, selectors=None):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        values = super()._prepare_home_portal_values(selectors)
        partner = request.env.user.partner_id
        subscription_count = request.env['subscription.subscription'].sudo().search_count([
            ('partner_id', '=', partner.id)
        ])
        values['subscription_count'] = subscription_count
        return values

    @http.route(['/my/subscriptions', '/my/subscriptions/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_subscriptions(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
<<<<<<< HEAD
        """Render the listing page for all the customer's active and historical subscription contracts."""
=======
<<<<<<< HEAD
        """Render the listing page for all the customer's active and historical subscription contracts."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Subscription = request.env['subscription.subscription'].sudo()
        
        domain = [('partner_id', '=', partner.id)]
        
        # count for pager
        subscription_count = Subscription.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/subscriptions",
            total=subscription_count,
            page=page,
            step=10
        )
        # content
        subscriptions = Subscription.search(domain, limit=10, offset=pager['offset'])
        
        values.update({
            'subscriptions': subscriptions,
            'page_name': 'subscription',
            'pager': pager,
            'default_url': '/my/subscriptions',
        })
        return request.render("subscription_management.portal_my_subscriptions", values)

    @http.route(['/my/subscription/<int:subscription_id>'], type='http', auth="user", website=True)
    def portal_my_subscription_detail(self, subscription_id, **kw):
<<<<<<< HEAD
        """Render the detailed view page for a specific subscription contract."""
=======
<<<<<<< HEAD
        """Render the detailed view page for a specific subscription contract."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        subscription = request.env['subscription.subscription'].sudo().browse(subscription_id)
        if not subscription.exists() or subscription.partner_id != request.env.user.partner_id:
            return request.redirect('/my/subscriptions')
            
        close_reasons = request.env['subscription.close.reason'].sudo().search([])
        
<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        # Calculate dynamic next invoice preview
        try:
            preview = subscription.action_preview_next_invoice()
        except Exception:
            preview = None
        
        return request.render("subscription_management.portal_my_subscription_detail", {
            'subscription': subscription,
            'close_reasons': close_reasons,
            'preview': preview,
<<<<<<< HEAD
=======
=======
        return request.render("subscription_management.portal_my_subscription_detail", {
            'subscription': subscription,
            'close_reasons': close_reasons,
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
            'page_name': 'subscription_detail',
        })

    @http.route(['/my/subscription/<int:subscription_id>/pause'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_pause(self, subscription_id, **kw):
<<<<<<< HEAD
        """Pause the customer's subscription contract via portal interaction."""
=======
<<<<<<< HEAD
        """Pause the customer's subscription contract via portal interaction."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        subscription = request.env['subscription.subscription'].sudo().browse(subscription_id)
        if subscription.exists() and subscription.partner_id == request.env.user.partner_id and subscription.plan_id.is_pausable:
            subscription.action_pause()
        return request.redirect('/my/subscription/%s' % subscription_id)

    @http.route(['/my/subscription/<int:subscription_id>/resume'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_resume(self, subscription_id, **kw):
<<<<<<< HEAD
        """Resume the customer's paused subscription contract via portal interaction."""
=======
<<<<<<< HEAD
        """Resume the customer's paused subscription contract via portal interaction."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        subscription = request.env['subscription.subscription'].sudo().browse(subscription_id)
        if subscription.exists() and subscription.partner_id == request.env.user.partner_id and subscription.plan_id.is_pausable:
            subscription.action_resume()
        return request.redirect('/my/subscription/%s' % subscription_id)

    @http.route(['/my/subscription/<int:subscription_id>/cancel'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_cancel(self, subscription_id, **kw):
<<<<<<< HEAD
        """Cancel and churn the customer's subscription contract via portal interaction with close reasons."""
=======
<<<<<<< HEAD
        """Cancel and churn the customer's subscription contract via portal interaction with close reasons."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        subscription = request.env['subscription.subscription'].sudo().browse(subscription_id)
        if subscription.exists() and subscription.partner_id == request.env.user.partner_id and subscription.plan_id.is_closable:
            close_reason_id = kw.get('close_reason_id')
            vals = {
                'close_reason_id': int(close_reason_id) if close_reason_id else False,
            }
            subscription.write(vals)
            subscription.action_cancel()
        return request.redirect('/my/subscription/%s' % subscription_id)
