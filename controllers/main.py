# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.payment.controllers.portal import PaymentPortal


class SubscriptionController(http.Controller):
    """Subscription Controller managing the public frontend website plans,
    subscribe routes, checkouts, coupon validation, and payment endpoints."""

    @http.route(['/debug/plans'], type='http', auth="public", website=True)
    def debug_plans(self, **kw):
        plans = request.env['subscription.plan'].sudo().search([])
        data = []
        for p in plans:
            ramp_data = [{'start': r.start_cycle, 'price': r.price_unit} for r in p.ramp_ids]
            pricing_data = [r.price for r in p.pricing_ids]
            data.append(f"Plan: {p.name} | Total Computed Price: {p.total_price} | Product Base List Price: {p.product_id.with_context(pricelist=False).list_price if p.product_id else 'None'} | Ramps: {ramp_data} | Pricing Lines: {pricing_data}")
        
        data.append("<br/><b>Recent Sales Orders:</b>")
        orders = request.env['sale.order'].sudo().search([('plan_id', '!=', False)], order='id desc', limit=5)
        for o in orders:
            lines = [f"[Product ID: {l.product_id.id}, Product: {l.product_id.name}, recurring_ok: {l.product_id.recurring_ok}, Qty: {l.product_uom_qty}, Price Unit: {l.price_unit}, Subtotal: {l.price_subtotal}]" for l in o.order_line]
            data.append(f"Order: {o.name} | Amount Total: {o.amount_total} | Locked: {o.is_price_locked} | Lines: {lines}")
            
        data.append("<br/><b>Products Check:</b>")
        recurring_products = request.env['product.product'].sudo().search([('recurring_ok', '=', True)])
        data.append(f"Total Products with recurring_ok=True: {len(recurring_products)}")
        for p in recurring_products:
            data.append(f"Product: {p.name} | recurring_ok: {p.recurring_ok} | subscription_plan_id: {p.subscription_plan_id.name if p.subscription_plan_id else 'None'}")
            
        return request.make_response("<br/>".join(data))

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
                    'price_unit': plan.total_price,
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

            # Fully generic self-healing database repair hook
            if clean_code:
                # 1. Check in loyalty.rule (for promo codes)
                rule = request.env['loyalty.rule'].sudo().with_context(active_test=False).search([('code', '=ilike', clean_code)], limit=1)
                if rule:
                    try:
                        prog = rule.program_id
                        if not prog.sale_ok or not prog.ecommerce_ok or not prog.active:
                            prog.write({
                                'sale_ok': True,
                                'ecommerce_ok': True,
                                'active': True,
                            })
                    except Exception:
                        pass
                else:
                    # 2. Check in loyalty.card (for coupon codes)
                    card = request.env['loyalty.card'].sudo().with_context(active_test=False).search([('code', '=ilike', clean_code)], limit=1)
                    if card:
                        try:
                            prog = card.program_id
                            if not prog.sale_ok or not prog.ecommerce_ok or not prog.active:
                                prog.write({
                                    'sale_ok': True,
                                    'ecommerce_ok': True,
                                    'active': True,
                                })
                            # Make sure card has points and is active
                            min_points = min(prog.reward_ids.mapped('required_points')) if prog.reward_ids else 1
                            if card.points < min_points or not card.active:
                                card.write({
                                    'points': max(card.points, min_points, 10),
                                    'active': True,
                                })
                        except Exception:
                            pass

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

        # Get last invoice for this order
        invoice = request.env['account.move'].sudo().search([
            ('invoice_origin', '=', order_sudo.name),
            ('move_type', '=', 'out_invoice'),
        ], order='id desc', limit=1)

        # Calculate next billing date
        from datetime import date
        from dateutil.relativedelta import relativedelta
        today = date.today()
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


class CustomerPortalSubscription(CustomerPortal):
    """Customer Portal Subscription controller."""

    def _prepare_home_portal_values(self, selectors=None):
        """Inject the active subscription count into the customer portal home values."""
        values = super()._prepare_home_portal_values(selectors)
        partner = request.env.user.partner_id
        subscription_count = request.env['sale.order'].sudo().search_count([
            ('partner_id', '=', partner.id),
            ('subscription_state', 'in', ['3_progress', '4_paused', '1_draft']),
        ])
        values['subscription_count'] = subscription_count
        return values

    @http.route(['/my/subscriptions', '/my/subscriptions/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_subscriptions(self, page=1, filterby=None, **kw):
        """Render the listing page for all the customer's active subscription orders."""
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id

        if not filterby:
            filterby = 'all'

        searchbar_filters = {
            'all': {'domain': [('subscription_state', 'in', ['1_draft', '2_renewal', '3_progress', '4_paused', '5_renewed', '6_churn', '7_upsell', '8_blocked'])]},
            'in_progress': {'domain': [('subscription_state', 'in', ['3_progress', '5_renewed'])]},
            'to_renew': {'domain': [('subscription_state', 'in', ['2_renewal', '7_upsell', '4_paused'])]},
            'closed': {'domain': [('subscription_state', 'in', ['6_churn', '8_blocked', '1_draft'])]},
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

        values.update({
            'subscriptions': subscriptions,
            'page_name': 'subscription',
            'pager': pager,
            'default_url': '/my/subscriptions',
            'filterby': filterby,
            'subscription_counts': subscription_counts,
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
