# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.payment.controllers.portal import PaymentPortal
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

class SubscriptionController(http.Controller):
    """Subscription Controller managing the public frontend website plans,
    subscribe routes, checkouts, coupon validation, and payment endpoints."""


    @http.route(['/subscriptions'], type='http', auth="public", website=True)
    def subscription_plans(self, **kw):
        """Render the public subscription plans landing page listing all active plans."""
        plans = request.env['subscription.plan'].sudo().search([('active', '=', True)])
        return request.render('subscription_management.subscription_plans_page', {
            'plans': plans
        })

    @http.route(['/subscriptions/subscribe/<model("subscription.plan"):plan>'], type='http', auth="user", website=True)
    def subscription_subscribe(self, plan, **kw):
        """Handle direct 1-click subscription registration, creating a sales order."""
        partner = request.env.user.partner_id

        # Check if user already has an active subscription (sale.order in progress)
        existing = request.env['sale.order'].sudo().search([
            ('partner_id', '=', partner.id),
            ('plan_id', '=', plan.id),
            ('subscription_state', 'in', ['1_draft', '3_progress', '4_paused', '8_blocked'])
        ], limit=1)

        if existing:
            return request.render('subscription_management.subscription_success_page', {
                'plan': plan,
                'subscription': existing,
                'message': 'You already have an active or pending subscription for this plan.'
            })

        order = request.env['sale.order'].sudo().create({
            'partner_id': partner.id,
            'plan_id': plan.id,
            'state': 'draft',
            'is_price_locked': True,
        })

        product = plan.product_id or request.env['product.product'].sudo().search(
            [('recurring_ok', '=', True), ('subscription_plan_id', '=', plan.id)], limit=1
        )
        if not product:
            product = request.env['product.product'].sudo().search(
                [('recurring_ok', '=', True)], limit=1
            )
        if not product:
            product = request.env['product.product'].sudo().create({
                'name': f"{plan.name} Subscription",
                'type': 'service',
                'recurring_ok': True,
                'list_price': 0.0,
            })

        if product:
            sudo_plan = request.env['subscription.plan'].sudo().browse(plan.id)
            price = sudo_plan.total_price
            line = request.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
                'name': f"Subscription: {plan.name}",
                'product_uom_qty': 1.0,
                'price_unit': price,
                'discount': 100.0 if sudo_plan.trial_period_days > 0 else 0.0,
            })

        if order.state == 'draft':
            try:
                order.action_confirm()
            except Exception:
                pass  # Order may already be confirmed via payment flow

        return request.render('subscription_management.subscription_success_page', {
            'plan': plan,
            'subscription': order,
            'message': 'Your subscription has been successfully created and is waiting for activation.'
        })

    @http.route(['/subscriptions/checkout/<model("subscription.plan"):plan>'], type='http', auth="public", website=True)
    def subscription_checkout(self, plan, **kw):
        """Render the custom subscription checkout page with billing, coupon, and payment provider options."""
        partner = request.env.user.partner_id if not request.env.user._is_public() else request.env['res.partner']
        if not partner:
            partner_id = request.session.get('subscription_guest_partner_id')
            if partner_id:
                partner = request.env['res.partner'].sudo().browse(partner_id)
            else:
                partner = request.env['res.partner'].sudo().create({'name': 'Guest Customer'})
                request.session['subscription_guest_partner_id'] = partner.id

        # --- Guard: check for an existing active subscription for this plan ---
        if partner and not request.env.user._is_public():
            active_sub = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner.id),
                ('plan_id', '=', plan.id),
                ('subscription_state', 'in', ['3_progress', '4_paused']),
                ('state', 'in', ['sale', 'done']),
            ], limit=1)
            if active_sub:
                return request.render('subscription_management.subscription_already_subscribed', {
                    'plan': plan,
                    'subscription': active_sub,
                })

        # --- Reuse or create a single draft order per partner+plan ---
        session_key = f'subscription_order_{plan.id}'
        order_id = request.session.get(session_key)
        order = request.env['sale.order'].sudo().browse(order_id) if order_id else request.env['sale.order']

        # Validate the session order is still usable
        if order.exists() and (order.state != 'draft' or order.partner_id.id != partner.id):
            # Session order is stale – clear it and look in DB
            order = request.env['sale.order']
            request.session.pop(session_key, None)

        if not order.exists():
            # Try to find an existing unused draft in the database before creating a new one
            existing_draft = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner.id),
                ('plan_id', '=', plan.id),
                ('state', '=', 'draft'),
                ('subscription_state', '=', '1_draft'),
            ], order='id desc', limit=1)

            if existing_draft:
                order = existing_draft
                request.session[session_key] = order.id
            else:
                # Create a fresh draft order
                order = request.env['sale.order'].sudo().create({
                    'partner_id': partner.id,
                    'plan_id': plan.id,
                    'state': 'draft',
                })
                product = plan.product_id or request.env['product.product'].sudo().search(
                    [('recurring_ok', '=', True), ('subscription_plan_id', '=', plan.id)], limit=1
                )
                if not product:
                    product = request.env['product.product'].sudo().create({
                        'name': f"{plan.name} Subscription",
                        'type': 'service',
                        'recurring_ok': True,
                        'list_price': 0.0,
                    })
                request.env['sale.order.line'].sudo().create({
                    'order_id': order.id,
                    'product_id': product.id,
                    'name': f"Subscription: {plan.name}",
                    'product_uom_qty': 1.0,
                    'price_unit': product.list_price if plan.product_id else plan.total_price,
                    'discount': 100.0 if plan.trial_period_days > 0 else 0.0,
                })
                request.session[session_key] = order.id

        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([])
        
        availability_report = {}
        providers_sudo = request.env['payment.provider'].sudo()._get_compatible_providers(
            order.company_id.id, partner.id, order.amount_total, currency_id=order.currency_id.id,
            sale_order_id=order.id, report=availability_report
        )
        payment_methods_sudo = request.env['payment.method'].sudo()._get_compatible_payment_methods(
            providers_sudo.ids, partner.id, currency_id=order.currency_id.id,
            sale_order_id=order.id, report=availability_report
        )
        tokens_sudo = request.env['payment.token'].sudo()._get_available_tokens(
            providers_sudo.ids, partner.id
        )

        payment_context = {
            'amount': order.amount_total,
            'currency': order.currency_id,
            'partner_id': partner.id,
            'providers_sudo': providers_sudo,
            'payment_methods_sudo': payment_methods_sudo,
            'tokens_sudo': tokens_sudo,
            'availability_report': availability_report,
            'transaction_route': f'/my/orders/{order.id}/transaction',
            'landing_route': f'/subscriptions/success/{order.id}',
            'access_token': order._portal_ensure_token(),
            'show_tokenize_input_mapping': PaymentPortal._compute_show_tokenize_input_mapping(
                providers_sudo, sale_order_id=order.id
            ),
            'company_mismatch': False,
            'expected_company': order.company_id,
        }

        render_values = {
            'plan': plan,
            'order': order,
            'partner': partner if partner.name != 'Guest Customer' else request.env['res.partner'],
            'countries': countries,
            'states': states,
            'kw': kw
        }
        render_values.update(payment_context)

        return request.render('subscription_management.subscription_checkout_page', render_values)

    @http.route(['/subscriptions/checkout/save_address'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def save_address(self, name, email, street, city, zip_code, country_id, state_id, **kw):
        """AJAX endpoint to save the billing address of the current user or guest
        during the subscription checkout process."""
        partner = request.env.user.partner_id if not request.env.user._is_public() else False
        if not partner:
            partner_id = request.session.get('subscription_guest_partner_id')
            if partner_id:
                partner = request.env['res.partner'].sudo().browse(partner_id)
                
        if partner:
            partner.sudo().write({
                'name': name or partner.name,
                'email': email or partner.email,
                'street': street or partner.street,
                'city': city or partner.city,
                'zip': zip_code or partner.zip,
                'country_id': int(country_id) if country_id else partner.country_id.id,
                'state_id': int(state_id) if state_id else partner.state_id.id,
            })
        return {'success': True}

    @http.route(['/subscriptions/checkout/update_config'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def update_config(self, plan_id, seats=None, cycle=None, **kw):
        """AJAX endpoint to dynamically update seat count or billing cycle
        on the active draft sales order before finalizing checkout."""
        session_key = f'subscription_order_{plan_id}'
        order_id = request.session.get(session_key)
        
        if not order_id:
            return {'success': False, 'error': 'Session expired. Please refresh the page.'}
            
        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists() or order.state != 'draft':
            return {'success': False, 'error': 'Invalid order state.'}

        # Update seats
        if seats is not None:
            for line in order.order_line:
                line.product_uom_qty = max(1.0, float(seats))
                
        # Handle billing cycle switch
        if cycle:
            current_plan = request.env['subscription.plan'].sudo().browse(int(plan_id))
            if current_plan.billing_period != cycle:
                # Find matching plan with the requested cycle
                new_plan = request.env['subscription.plan'].sudo().search([
                    ('name', '=', current_plan.name),
                    ('billing_period', '=', cycle),
                    ('active', '=', True)
                ], limit=1)
                
                if new_plan:
                    return {'success': True, 'redirect': f'/subscriptions/checkout/{new_plan.id}'}
                else:
                    return {'success': False, 'error': f'The {cycle} variant for this plan is not currently available.'}
                
        return {'success': True}

    @http.route(['/subscriptions/checkout/validate_coupon'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def validate_coupon(self, coupon_code, plan_id, **kw):
        """Validate the applied coupon code asynchronously via JSON-RPC endpoint."""
        try:
            plan = request.env['subscription.plan'].sudo().browse(int(plan_id))
            if not plan.exists():
                return {'valid': False, 'message': 'Plan not found'}

            clean_code = coupon_code.strip() if coupon_code else ""
            if not clean_code:
                return {'valid': False, 'message': 'Please enter a coupon code.'}


            # 1. Search in loyalty.rule (for promo codes)
            rule = request.env['loyalty.rule'].sudo().search([('code', '=ilike', clean_code)], limit=1)
            program = False
            card = False
            
            if rule:
                program = rule.program_id
            else:
                # 2. Search in loyalty.card (for coupon codes)
                card = request.env['loyalty.card'].sudo().search([('code', '=ilike', clean_code)], limit=1)
                if card:
                    program = card.program_id

            # 3. Backup search for inactive/archived coupons to provide a helpful error message
            if not program:
                inactive_card = request.env['loyalty.card'].sudo().with_context(active_test=False).search([('code', '=ilike', clean_code)], limit=1)
                if inactive_card:
                    return {'valid': False, 'message': 'This coupon code is inactive or archived.'}
                return {'valid': False, 'message': 'Invalid coupon code.'}

            if not program.active:
                return {'valid': False, 'message': 'This coupon program is inactive.'}

            # 4. Expiration check
            if card and card.expiration_date and card.expiration_date < fields.Date.today():
                return {'valid': False, 'message': 'This coupon has expired.'}

            # 5. Points / usage check for loyalty cards
            if card:
                min_points = min(program.reward_ids.mapped('required_points')) if program.reward_ids else 1
                if card.points < min_points:
                    return {'valid': False, 'message': 'This coupon has already been used.'}

            # 6. Enforce Subscription Plan Constraints
            if program.plan_ids and plan.id not in program.plan_ids.ids:
                return {'valid': False, 'message': 'This promo code is not valid for the selected plan.'}

            # 7. Customer constraints (if logged in)
            if not request.env.user._is_public():
                partner = request.env.user.partner_id
                
                if program.first_time_only:
                    past_subs = request.env['sale.order'].sudo().search_count([
                        ('partner_id', '=', partner.id),
                        ('subscription_state', 'not in', [False, '1_draft'])
                    ])
                    if past_subs > 0:
                        return {'valid': False, 'message': 'This promotion is only valid for first-time customers.'}
                        
                if program.max_uses_per_customer > 0:
                    customer_uses = request.env['sale.order'].sudo().search_count([
                        ('partner_id', '=', partner.id),
                        ('state', 'in', ['sale', 'done']),
                        ('order_line.reward_id.program_id', '=', program.id)
                    ])
                    if customer_uses >= program.max_uses_per_customer:
                        return {'valid': False, 'message': 'You have reached the usage limit for this promotion.'}

            sudo_plan = request.env['subscription.plan'].sudo().browse(plan.id)
            subtotal = sudo_plan.total_price or 0.0
            
            # Approximate discount for UI preview (Odoo native will calculate exactly on SO creation)
            discount_amount = 0.0
            reward = program.reward_ids[0] if program.reward_ids else False
            if reward:
                if reward.discount_mode == 'percent':
                    discount_amount = subtotal * (reward.discount / 100.0)
                elif reward.discount_mode == 'per_order':
                    discount_amount = min(reward.discount, subtotal)

            new_total = max(0.0, subtotal - discount_amount)
            currency = plan.currency_id
            formatted_discount = f"{currency.symbol or ''}{discount_amount:.2f}" if currency else f"${discount_amount:.2f}"
            formatted_total = f"{currency.symbol or ''}{new_total:.2f}" if currency else f"${new_total:.2f}"

            return {
                'valid': True,
                'coupon_id': program.id,
                'name': program.name,
                'code': clean_code,
                'discount_type': reward.discount_mode if reward else 'percent',
                'discount_value': reward.discount if reward else 0.0,
                'discount_amount': formatted_discount,
                'discount_amount_raw': discount_amount,
                'new_total': formatted_total,
                'new_total_raw': new_total,
                'message': 'Coupon applied successfully!'
            }
        except Exception as e:
            return {'valid': False, 'message': f'Python Error: {str(e)}'}

    @http.route(['/subscriptions/checkout/<model("subscription.plan"):plan>/confirm'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def subscription_checkout_confirm(self, plan, **kw):
        """Confirm checkout details, apply coupon, and redirect to the payment step."""
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
            if not partner.street and street:
                partner_vals['street'] = street
            if not partner.city and city:
                partner_vals['city'] = city
            if not partner.zip and zip_code:
                partner_vals['zip'] = zip_code
            if not partner.country_id and country_id:
                partner_vals['country_id'] = int(country_id)
            if not partner.state_id and state_id:
                partner_vals['state_id'] = int(state_id)
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

        existing = request.env['sale.order'].sudo().search([
            ('partner_id', '=', partner.id),
            ('plan_id', '=', plan.id),
            ('subscription_state', 'in', ['1_draft', '3_progress', '4_paused', '8_blocked'])
        ], limit=1)

        if existing:
            return request.render('subscription_management.subscription_success_page', {
                'plan': plan,
                'subscription': existing,
                'message': 'You already have an active or pending subscription for this plan.'
            })

        order = request.env['sale.order'].sudo().create({
            'partner_id': partner.id,
            'partner_invoice_id': partner.id,
            'partner_shipping_id': partner.id,
            'plan_id': plan.id,
            'state': 'draft',
            'is_price_locked': True,
        })

        product = plan.product_id or request.env['product.product'].sudo().search(
            [('recurring_ok', '=', True), ('subscription_plan_id', '=', plan.id)], limit=1
        )
        if not product:
            product = request.env['product.product'].sudo().search(
                [('recurring_ok', '=', True)], limit=1
            )
        if not product:
            product = request.env['product.product'].sudo().create({
                'name': f"{plan.name} Subscription",
                'type': 'service',
                'recurring_ok': True,
                'list_price': 0.0,
            })

        if product:
            sudo_plan = request.env['subscription.plan'].sudo().browse(plan.id)
            price = sudo_plan.product_id.list_price if sudo_plan.product_id else sudo_plan.total_price
            line = request.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
                'name': f"Subscription: {plan.name}",
                'product_uom_qty': 1.0,
                'price_unit': price,
                'discount': 100.0 if sudo_plan.trial_period_days > 0 else 0.0,
            })
            
        coupon_code = kw.get('coupon_code')
        if coupon_code:
            # Enforce custom subscription constraints before native application
            rule = request.env['loyalty.rule'].sudo().search([('code', '=ilike', coupon_code.strip())], limit=1)
            program = rule.program_id if rule else False
            if not program:
                card = request.env['loyalty.card'].sudo().search([('code', '=ilike', coupon_code.strip())], limit=1)
                program = card.program_id if card else False
                
            coupon_error = False
            if program:
                if program.plan_ids and plan.id not in program.plan_ids.ids:
                    coupon_error = 'This promo code is not valid for the selected plan.'
                elif program.first_time_only:
                    past_subs = request.env['sale.order'].sudo().search_count([
                        ('partner_id', '=', partner.id),
                        ('subscription_state', 'not in', [False, '1_draft'])
                    ])
                    if past_subs > 0:
                        coupon_error = 'This promotion is only valid for first-time customers.'
                elif program.max_uses_per_customer > 0:
                    customer_uses = request.env['sale.order'].sudo().search_count([
                        ('partner_id', '=', partner.id),
                        ('state', 'in', ['sale', 'done']),
                        ('order_line.reward_id.program_id', '=', program.id)
                    ])
                    if customer_uses >= program.max_uses_per_customer:
                        coupon_error = 'You have reached the usage limit for this promotion.'

            if not coupon_error:
                status = order.sudo()._try_apply_code(coupon_code.strip())
                if 'error' in status:
                    coupon_error = status['error']

            if coupon_error:
                # Rollback or handle error
                countries = request.env['res.country'].sudo().search([])
                states = request.env['res.country.state'].sudo().search([])
                providers = request.env['payment.provider'].sudo().search([('state', 'in', ['test', 'enabled'])])
                return request.render('subscription_management.subscription_checkout_page', {
                    'plan': plan,
                    'partner': partner,
                    'countries': countries,
                    'states': states,
                    'providers': providers,
                    'coupon_error': coupon_error,
                    'kw': kw
                })

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

        render_values = {'plan': plan, 'order': order_sudo}
        render_values.update(payment_context)
        return request.render('subscription_management.subscription_payment_page', render_values)

    @http.route(['/subscriptions/success/<int:order_id>'], type='http', auth="public", website=True)
    def subscription_success(self, order_id, **kw):
        """Landing route after successful payment transaction."""
        order_sudo = request.env['sale.order'].sudo().browse(order_id)
        if not order_sudo.exists():
            return request.redirect('/subscriptions')

        if order_sudo.state == 'draft':
            try:
                order_sudo.action_confirm()
            except Exception:
                pass  # Already confirmed or payment gateway handled it
                
        # Instantly generate the first invoice if it hasn't been generated yet
        # (This catches orders confirmed by the payment gateway before reaching this page)
        if not order_sudo.invoice_ids and order_sudo.state in ('sale', 'done'):
            try:
                order_sudo._generate_recurring_invoice()
            except Exception:
                pass

        # Get last invoice directly linked to this order
        invoices = order_sudo.invoice_ids.filtered(lambda i: i.move_type == 'out_invoice')
        invoice = invoices.sorted(key=lambda i: i.id, reverse=True)[0] if invoices else request.env['account.move']

        # Calculate next billing date
        from datetime import date
        from dateutil.relativedelta import relativedelta
        today = date.today()
        next_billing = order_sudo.next_invoice_date
        
        if not next_billing:
            period = order_sudo.plan_id.billing_period if order_sudo.plan_id else 'month'
            if period == 'month':
                next_billing = today + relativedelta(months=1)
            elif period == 'year':
                next_billing = today + relativedelta(years=1)
            elif period == 'week':
                next_billing = today + relativedelta(weeks=1)
            else:
                next_billing = today + relativedelta(months=1)

        return request.render('subscription_management.subscription_success_page', {
            'plan': order_sudo.plan_id,
            'subscription': order_sudo,
            'invoice': invoice,
            'next_billing': next_billing,
            'partner': order_sudo.partner_id,
            'message': 'Your transaction was successful, and your subscription is now active!',
        })

    @http.route(['/subscriptions/api/trigger_emails/<int:order_id>'], type='http', auth="public", website=True, csrf=False)
    def trigger_subscription_emails(self, order_id, **kw):
        """API endpoint to trigger welcome and receipt emails asynchronously."""
        import json
        
        order_sudo = request.env['sale.order'].sudo().browse(order_id)
        if not order_sudo.exists():
            return request.make_response(json.dumps({'status': 'error', 'message': 'Order not found'}), headers=[('Content-Type', 'application/json')])
            
        # Security Validation
        access_token = kw.get('access_token')
        if not request.env.user._is_public():
            if order_sudo.partner_id != request.env.user.partner_id and not request.env.user.has_group('base.group_user'):
                return request.make_response(json.dumps({'status': 'error', 'message': 'Access denied'}), headers=[('Content-Type', 'application/json')])
        else:
            if order_sudo.access_token and order_sudo.access_token != access_token:
                return request.make_response(json.dumps({'status': 'error', 'message': 'Access denied'}), headers=[('Content-Type', 'application/json')])

        if order_sudo.state not in ['sale', 'done']:
            return request.make_response(json.dumps({'status': 'error', 'message': 'Invalid order state'}), headers=[('Content-Type', 'application/json')])

        if not order_sudo.partner_id.email:
            return request.make_response(json.dumps({'status': 'error', 'message': 'Missing customer email'}), headers=[('Content-Type', 'application/json')])
            
        welcome_queued = False
        receipt_queued = False
        # Trigger Welcome Email synchronously
        try:
            sale_template = request.env.ref('sale.mail_template_sale_confirmation', raise_if_not_found=False)
            if sale_template:
                # Force send_mail to bypass follower preferences and guarantee a mail.mail record
                sale_template.sudo().send_mail(order_sudo.id, force_send=True)
        except Exception as e:
            order_sudo.message_post(body="Failed to trigger Welcome Email: %s" % str(e))
            
        # Trigger Receipt/Invoice Email synchronously
        try:
            invoice = request.env['account.move'].sudo().search([
                ('invoice_origin', '=', order_sudo.name),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted')
            ], order='id desc', limit=1)
            if invoice:
                inv_template = request.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
                if inv_template:
                    inv_template.sudo().send_mail(invoice.id, force_send=True)
        except Exception as e:
            order_sudo.message_post(body="Failed to trigger Receipt Email: %s" % str(e))

        return request.make_response(json.dumps({
            'status': 'success',
            'email': order_sudo.partner_id.email,
        }), headers=[('Content-Type', 'application/json')])


from odoo.addons.account.controllers.portal import PortalAccount

class CustomerPortalSubscription(CustomerPortal):
    """Customer Portal Subscription controller."""

    @http.route([
        '/my/subscription/<int:order_id>/close_signature',
        '/my/orders/<int:order_id>/close_signature'
    ], type='http', auth="public", website=True)
    def portal_subscription_close_signature(self, order_id, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        except Exception:
            return request.redirect('/my/subscriptions')

        if order_sudo.subscription_state != '6_churn' or order_sudo.close_signature:
            return request.redirect(order_sudo.get_portal_url())

        values = {
            'sale_order': order_sudo,
            'page_name': 'subscription_close_signature',
        }
        return request.render('subscription_management.subscription_close_signature_page', values)

    @http.route([
        '/my/subscription/<int:order_id>/close_signature/accept',
        '/my/orders/<int:order_id>/close_signature/accept'
    ], type='jsonrpc', auth="public", website=True)
    def portal_subscription_close_signature_accept(self, order_id, access_token=None, name=None, signature=None):
        import binascii
        from odoo import fields
        
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        except Exception:
            return {'error': _('Invalid order.')}

        if order_sudo.subscription_state != '6_churn':
            return {'error': _('The subscription is not closed yet.')}
        if not signature:
            return {'error': _('Signature is missing.')}

        try:
            order_sudo.write({
                'close_signed_by': name,
                'close_signed_on': fields.Datetime.now(),
                'close_signature': signature,
            })
            request.env.cr.flush()
        except (TypeError, binascii.Error) as e:
            return {'error': _('Invalid signature data.')}

        order_sudo.message_post(
            author_id=(
                order_sudo.partner_id.id
                if request.env.user._is_public()
                else request.env.user.partner_id.id
            ),
            body=_('Subscription close accepted and signed by %s', name),
            message_type='comment',
        )

        return {
            'force_refresh': True,
            'redirect_url': order_sudo.get_portal_url(),
        }

class CustomPortalAccount(PortalAccount):
    """Extend default account portal to support custom invoice tabs."""

    def _get_account_searchbar_filters(self):
        filters = super()._get_account_searchbar_filters()
        
        from odoo import fields
        
        filters.update({
            'paid': {'label': 'Paid', 'domain': [('payment_state', 'in', ('paid', 'in_payment', 'reversed'))]},
            'awaiting': {'label': 'Awaiting Payment', 'domain': [
                ('state', 'not in', ('cancel', 'draft')),
                ('payment_state', 'in', ('not_paid', 'partial')),
                '|', ('invoice_date_due', '>=', fields.Date.today()), ('invoice_date_due', '=', False)
            ]},
            'overdue_invoices': {'label': 'Overdue', 'domain': [
                ('state', 'not in', ('cancel', 'draft')),
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('invoice_date_due', '<', fields.Date.today())
            ]},
        })
        return filters

    def _prepare_home_portal_values(self, counters):
        """Inject the active subscription count into the customer portal home values."""
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        subscription_count = request.env['sale.order'].sudo().search_count([
            ('partner_id', '=', partner.id),
            ('plan_id', '!=', False),
            ('state', 'in', ['sale', 'done'])
        ])
        values['subscription_count'] = subscription_count

        # Override native Odoo limit=1 optimization so the sidebar badges show exact counts
        if 'invoice_count' in counters:
            values['invoice_count'] = request.env['account.move'].search_count(self._get_invoices_domain('out')) if request.env['account.move'].has_access('read') else 0
        if 'order_count' in counters:
            values['order_count'] = request.env['sale.order'].search_count(self._prepare_orders_domain(partner)) if hasattr(self, '_prepare_orders_domain') and request.env['sale.order'].has_access('read') else 0
        if 'quotation_count' in counters:
            values['quotation_count'] = request.env['sale.order'].search_count(self._prepare_quotations_domain(partner)) if hasattr(self, '_prepare_quotations_domain') and request.env['sale.order'].has_access('read') else 0

        return values

    @http.route(['/my/subscriptions', '/my/subscriptions/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_subscriptions(self, page=1, filterby=None, **kw):
        """Render the listing page for all the customer's active subscription orders."""
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id

        if not filterby:
            filterby = 'all'

        searchbar_filters = {
            'all': {'domain': [('plan_id', '!=', False), ('state', 'in', ['sale', 'done'])]},
            'in_progress': {'domain': [('plan_id', '!=', False), ('state', 'in', ['sale', 'done']), ('subscription_state', 'in', ['3_progress', '5_renewed'])]},
            'to_renew': {'domain': [('plan_id', '!=', False), ('state', 'in', ['sale', 'done']), ('subscription_state', 'in', ['2_renewal', '7_upsell', '4_paused'])]},
            'closed': {'domain': [('plan_id', '!=', False), ('state', 'in', ['sale', 'done']), ('subscription_state', 'in', ['6_churn', '8_blocked'])]},
        }

        base_domain = [('partner_id', '=', partner.id)]
        
        SaleOrder = request.env['sale.order'].sudo()
        subscription_counts = {
            'all': SaleOrder.search_count(base_domain + searchbar_filters['all']['domain']),
            'in_progress': SaleOrder.search_count(base_domain + searchbar_filters['in_progress']['domain']),
            'to_renew': SaleOrder.search_count(base_domain + searchbar_filters['to_renew']['domain']),
            'closed': SaleOrder.search_count(base_domain + searchbar_filters['closed']['domain']),
        }

        domain = base_domain + searchbar_filters.get(filterby, searchbar_filters['all'])['domain']

        subscription_count = SaleOrder.search_count(domain)
        pager = portal_pager(
            url="/my/subscriptions",
            url_args={'filterby': filterby},
            total=subscription_count,
            page=page,
            step=10
        )
        subscriptions = SaleOrder.search(domain, limit=10, offset=pager['offset'])

        # --- Metrics Calculation ---
        from odoo import fields
        AccountMove = request.env['account.move'].sudo()
        today = fields.Date.today()
        
        # Outstanding & Overdue Invoices
        unpaid_invoices = AccountMove.search([
            ('commercial_partner_id', '=', partner.commercial_partner_id.id),
            ('state', 'not in', ('cancel', 'draft')),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('move_type', '=', 'out_invoice')
        ])
        portal_outstanding_amount = sum(unpaid_invoices.mapped('amount_residual'))
        portal_overdue_count = sum(1 for inv in unpaid_invoices if inv.invoice_date_due and inv.invoice_date_due < today)

        # Global MRR & Next Invoice
        all_active_subs = SaleOrder.search(base_domain + searchbar_filters['in_progress']['domain'])
        portal_mrr = 0.0
        portal_next_invoice_date = False
        portal_next_invoice_amount = 0.0
        portal_next_invoice_plan = ""

        subs_with_next_date = all_active_subs.filtered(lambda s: s.next_invoice_date).sorted(key=lambda s: s.next_invoice_date)
        if subs_with_next_date:
            first_sub = subs_with_next_date[0]
            portal_next_invoice_date = first_sub.next_invoice_date
            portal_next_invoice_plan = first_sub.plan_id.name
            portal_next_invoice_amount = sum(l.price_subtotal for l in first_sub.order_line if (l.product_template_id.recurring_ok or l.product_id.recurring_ok))

        for sub in all_active_subs:
            sub_total = sum(l.price_subtotal for l in sub.order_line if (l.product_template_id.recurring_ok or l.product_id.recurring_ok))
            period = sub.plan_id.billing_period or 'monthly'
            if period == 'weekly':
                portal_mrr += sub_total * 4.333
            elif period == 'monthly':
                portal_mrr += sub_total
            elif period == 'yearly':
                portal_mrr += sub_total / 12.0

        values.update({
            'subscriptions': subscriptions,
            'page_name': 'subscription',
            'pager': pager,
            'default_url': '/my/subscriptions',
            'filterby': filterby,
            'subscription_counts': subscription_counts,
            'portal_outstanding_amount': portal_outstanding_amount,
            'portal_overdue_count': portal_overdue_count,
            'portal_mrr': portal_mrr,
            'portal_next_invoice_date': portal_next_invoice_date,
            'portal_next_invoice_amount': portal_next_invoice_amount,
            'portal_next_invoice_plan': portal_next_invoice_plan,
        })
        return request.render("subscription_management.portal_my_subscriptions", values)

    @http.route(['/my/subscription/<int:subscription_id>'], type='http', auth="user", website=True)
    def portal_my_subscription_detail(self, subscription_id, **kw):
        """Render the detailed view page for a specific subscription order."""
        subscription = request.env['sale.order'].sudo().browse(subscription_id)
        if not subscription.exists() or subscription.partner_id != request.env.user.partner_id:
            return request.redirect('/my/subscriptions')

        close_reasons = request.env['subscription.close.reason'].sudo().search([])
        preview = subscription.sudo()._preview_next_invoice()

        return request.render("subscription_management.portal_my_subscription_detail", {
            'subscription': subscription,
            'close_reasons': close_reasons,
            'preview': preview,
            'page_name': 'subscription_detail',
        })

    @http.route(['/my/subscription/<int:subscription_id>/change_seats'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_change_seats(self, subscription_id, **kw):
        """Update subscription quantity (seats) from portal."""
        subscription = request.env['sale.order'].sudo().browse(subscription_id)
        if (
            subscription.exists()
            and subscription.partner_id == request.env.user.partner_id
            and subscription.subscription_state == '3_progress'
        ):
            line_id = int(kw.get('line_id'))
            new_qty = float(kw.get('new_quantity'))
            if new_qty > 0:
                subscription.action_change_seats(line_id, new_qty)
        return request.redirect('/my/subscription/%s' % subscription_id)

    @http.route(['/my/subscription/<int:subscription_id>/pause'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_pause(self, subscription_id, **kw):
        """Pause the customer's subscription via portal."""
        subscription = request.env['sale.order'].sudo().browse(subscription_id)
        if (
            subscription.exists()
            and subscription.partner_id == request.env.user.partner_id
            and subscription.plan_id.is_pausable
        ):
            subscription.action_pause()
        return request.redirect('/my/subscription/%s' % subscription_id)

    @http.route(['/my/subscription/<int:subscription_id>/resume'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_resume(self, subscription_id, **kw):
        """Resume the customer's subscription via portal."""
        subscription = request.env['sale.order'].sudo().browse(subscription_id)
        if (
            subscription.exists()
            and subscription.partner_id == request.env.user.partner_id
            and subscription.plan_id.is_pausable
        ):
            subscription.action_resume()
        return request.redirect('/my/subscription/%s' % subscription_id)

    @http.route(['/my/subscription/<int:subscription_id>/cancel'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_cancel(self, subscription_id, **kw):
        """Cancel the customer's subscription via portal."""
        subscription = request.env['sale.order'].sudo().browse(subscription_id)
        if (
            subscription.exists()
            and subscription.partner_id == request.env.user.partner_id
            and subscription.plan_id.is_closable
        ):
            close_reason_id = kw.get('close_reason_id')
            customer_signature = kw.get('customer_signature')
            
            if customer_signature:
                subscription.message_post(body=f"Subscription cancelled by customer. Electronic Signature: <b>{customer_signature}</b>")
                
            subscription._action_close_confirm(
                close_reason_id=int(close_reason_id) if close_reason_id else None,
            )
        return request.redirect('/my/subscription/%s' % subscription_id)

class SubscriptionPaymentPostProcessing(PaymentPostProcessing):
    @http.route('/payment/status', type='http', auth='public', website=True, sitemap=False)
    def display_status(self, **kwargs):
        monitored_tx = self._get_monitored_transaction()
        if monitored_tx and monitored_tx.landing_route and monitored_tx.landing_route.startswith('/subscriptions/success'):
            if not monitored_tx.is_post_processed:
                try:
                    monitored_tx._post_process()
                except Exception:
                    request.env.cr.rollback()
            return request.redirect(monitored_tx.landing_route)
        return super().display_status(**kwargs)
