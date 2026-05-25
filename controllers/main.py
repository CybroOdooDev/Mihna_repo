# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.payment.controllers.portal import PaymentPortal


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
        })

        product = plan.product_id or request.env['product.product'].sudo().search(
            [('recurring_ok', '=', True), ('subscription_plan_id', '=', plan.id)], limit=1
        )
        if not product:
            product = request.env['product.product'].sudo().search(
                [('recurring_ok', '=', True)], limit=1
            )

        if product:
            request.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'price_unit': plan.total_price,
            })

        order.action_confirm()

        return request.render('subscription_management.subscription_success_page', {
            'plan': plan,
            'subscription': order,
            'message': 'Your subscription has been successfully created and is waiting for activation.'
        })

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

            subtotal = plan.total_price or 0.0
            
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
        })

        product = plan.product_id or request.env['product.product'].sudo().search(
            [('recurring_ok', '=', True), ('subscription_plan_id', '=', plan.id)], limit=1
        )
        if not product:
            product = request.env['product.product'].sudo().search(
                [('recurring_ok', '=', True)], limit=1
            )

        if product:
            price = plan.total_price
            line = request.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
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

        if order_sudo.state not in ['sale', 'done']:
            order_sudo.action_confirm()

        return request.render('subscription_management.subscription_success_page', {
            'plan': order_sudo.plan_id,
            'subscription': order_sudo,
            'message': 'Your transaction was successful, and your subscription is now active!'
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
    def portal_my_subscriptions(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        """Render the listing page for all the customer's active subscription orders."""
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id

        domain = [
            ('partner_id', '=', partner.id),
            ('subscription_state', 'in', ['1_draft', '2_renewal', '3_progress', '4_paused', '5_renewed', '6_churn', '7_upsell', '8_blocked']),
        ]

        subscription_count = request.env['sale.order'].sudo().search_count(domain)
        pager = portal_pager(
            url="/my/subscriptions",
            total=subscription_count,
            page=page,
            step=10
        )
        subscriptions = request.env['sale.order'].sudo().search(domain, limit=10, offset=pager['offset'])

        values.update({
            'subscriptions': subscriptions,
            'page_name': 'subscription',
            'pager': pager,
            'default_url': '/my/subscriptions',
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
            subscription._action_close_confirm(
                close_reason_id=int(close_reason_id) if close_reason_id else None,
            )
        return request.redirect('/my/subscription/%s' % subscription_id)
