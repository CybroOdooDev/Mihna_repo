from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

class SubscriptionController(http.Controller):

    @http.route(['/subscriptions'], type='http', auth="public", website=True)
    def subscription_plans(self, **kw):
        plans = request.env['subscription.plan'].sudo().search([('active', '=', True)])
        return request.render('subscription_management.subscription_plans_page', {
            'plans': plans
        })

    @http.route(['/subscriptions/subscribe/<model("subscription.plan"):plan>'], type='http', auth="user", website=True)
    def subscription_subscribe(self, plan, **kw):
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
            
        # Create a new draft subscription
        subscription = request.env['subscription.subscription'].sudo().create({
            'partner_id': partner.id,
            'plan_id': plan.id,
            'state': 'draft'
        })
        # Trigger the onchange manually to populate lines since we are in backend code
        subscription._onchange_plan_id()
        
        return request.render('subscription_management.subscription_success_page', {
            'plan': plan,
            'subscription': subscription,
            'message': 'Your subscription has been successfully created and is waiting for activation.'
        })

class CustomerPortalSubscription(CustomerPortal):

    def _prepare_home_portal_values(self, selectors=None):
        values = super()._prepare_home_portal_values(selectors)
        partner = request.env.user.partner_id
        subscription_count = request.env['subscription.subscription'].sudo().search_count([
            ('partner_id', '=', partner.id)
        ])
        values['subscription_count'] = subscription_count
        return values

    @http.route(['/my/subscriptions', '/my/subscriptions/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_subscriptions(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
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
        subscription = request.env['subscription.subscription'].sudo().browse(subscription_id)
        if not subscription.exists() or subscription.partner_id != request.env.user.partner_id:
            return request.redirect('/my/subscriptions')
            
        close_reasons = request.env['subscription.close.reason'].sudo().search([])
        
        return request.render("subscription_management.portal_my_subscription_detail", {
            'subscription': subscription,
            'close_reasons': close_reasons,
            'page_name': 'subscription_detail',
        })

    @http.route(['/my/subscription/<int:subscription_id>/pause'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_pause(self, subscription_id, **kw):
        subscription = request.env['subscription.subscription'].sudo().browse(subscription_id)
        if subscription.exists() and subscription.partner_id == request.env.user.partner_id and subscription.plan_id.is_pausable:
            subscription.action_pause()
        return request.redirect('/my/subscription/%s' % subscription_id)

    @http.route(['/my/subscription/<int:subscription_id>/resume'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_resume(self, subscription_id, **kw):
        subscription = request.env['subscription.subscription'].sudo().browse(subscription_id)
        if subscription.exists() and subscription.partner_id == request.env.user.partner_id and subscription.plan_id.is_pausable:
            subscription.action_resume()
        return request.redirect('/my/subscription/%s' % subscription_id)

    @http.route(['/my/subscription/<int:subscription_id>/cancel'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def portal_my_subscription_cancel(self, subscription_id, **kw):
        subscription = request.env['subscription.subscription'].sudo().browse(subscription_id)
        if subscription.exists() and subscription.partner_id == request.env.user.partner_id and subscription.plan_id.is_closable:
            close_reason_id = kw.get('close_reason_id')
            vals = {
                'close_reason_id': int(close_reason_id) if close_reason_id else False,
            }
            subscription.write(vals)
            subscription.action_cancel()
        return request.redirect('/my/subscription/%s' % subscription_id)
