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
            ('subscription_state', 'in', ['1_draft', '3_progress', '4_paused'])
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
        plan = request.env['subscription.plan'].sudo().browse(int(plan_id))
        if not plan.exists():
            return {'valid': False, 'message': 'Plan not found'}

        coupon = request.env['subscription.coupon'].sudo().search([
            ('code', '=ilike', coupon_code.strip()),
            ('active', '=', True)
        ], limit=1)

        if not coupon:
            return {'valid': False, 'message': 'Invalid coupon code.'}

        subtotal = plan.total_price or 0.0
        partner = request.env.user.partner_id if not request.env.user._is_public() else None

        is_valid, msg = coupon._validate_coupon(partner=partner, plan=plan, amount=subtotal)
        if not is_valid:
            return {'valid': False, 'message': msg}

        discount_amount = 0.0
        if coupon.discount_type == 'percentage':
            discount_amount = subtotal * (coupon.discount_value / 100.0)
        elif coupon.discount_type == 'fixed':
            discount_amount = min(coupon.discount_value, subtotal)

        new_total = max(0.0, subtotal - discount_amount)
        currency = plan.currency_id
        formatted_discount = f"{currency.symbol or ''}{discount_amount:.2f}" if currency else f"${discount_amount:.2f}"
        formatted_total = f"{currency.symbol or ''}{new_total:.2f}" if currency else f"${new_total:.2f}"

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
            ('subscription_state', 'in', ['1_draft', '3_progress', '4_paused'])
        ], limit=1)

        if existing:
            return request.render('subscription_management.subscription_success_page', {
                'plan': plan,
                'subscription': existing,
                'message': 'You already have an active or pending subscription for this plan.'
            })

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

        order = request.env['sale.order'].sudo().create({
            'partner_id': partner.id,
            'plan_id': plan.id,
            'coupon_id': coupon_id,
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
            discount_pct = 0.0

            if coupon_id:
                coupon = request.env['subscription.coupon'].sudo().browse(coupon_id)
                is_valid, _msg = coupon._validate_coupon(partner=partner, plan=plan, amount=price)
                if not is_valid:
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
            line.sudo().write({
                'price_unit': price,
                'discount': discount_pct,
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
            ('subscription_state', 'in', ['1_draft', '2_renewal', '3_progress', '4_paused', '5_renewed', '6_churn']),
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
