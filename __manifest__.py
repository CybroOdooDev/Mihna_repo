# -*- coding: utf-8 -*-
{
    'name': 'Subscription Management',
    'version': '19.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Manage recurring billing, subscriptions, and customer lifecycle.',
    'description': """
Subscription Management System
==============================
A commercial-grade Subscription Management application that provides feature parity with Odoo Enterprise Subscriptions.
Features include:
- Subscription plans and pricing tiers
- Recurring invoicing
- Dunning management
- Customer self-service portal
- MRR, Churn, and KPI dashboards
    """,
    'author': 'Cybrosys Technologies',
    'company': 'Cybrosys Technologies',
    'maintainer': 'Cybrosys Technologies',
    'website': 'https://www.cybrosys.com',
    'depends': ['sale_management', 'account', 'mail', 'portal', 'website', 'website_sale', 'payment', 'stock', 'delivery', 'sale_project', 'sale_timesheet'],
    'data': [
        'security/subscription_security.xml',
        'security/ir.model.access.csv',
        'data/subscription_sequence.xml',
        'data/subscription_cron.xml',
        'views/subscription_dashboard_views.xml',
        'views/subscription_coupon_views.xml',
        'views/subscription_plan_views.xml',
        'views/sale_order_views.xml',
        'views/subscription_subscription_views.xml',
        'views/subscription_price_lock_views.xml',
        'views/subscription_menus.xml',
        'views/subscription_reporting_views.xml',
        'views/sale_order_template_views.xml',
        'views/subscription_templates.xml',
        'views/subscription_close_reason_views.xml',
        'views/subscription_change_plan_wizard_views.xml',
        'views/product_template_views.xml',
    ],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            'subscription_management/static/src/css/dashboard.scss',
            'subscription_management/static/src/js/dashboard.js',
            'subscription_management/static/src/xml/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
