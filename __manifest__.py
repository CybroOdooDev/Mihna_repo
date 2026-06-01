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
    'depends': ['sale_management', 'account', 'mail', 'portal', 'website', 'website_sale', 'payment', 'stock', 'delivery', 'sale_project', 'sale_timesheet', 'loyalty', 'sale_loyalty'],
    'data': [
        'security/subscription_security.xml',
        'security/ir.model.access.csv',
        'views/subscription_menu_roots.xml',
        'data/subscription_sequence.xml',
        'data/subscription_cron.xml',
        'data/dunning_cron.xml',
        'data/dunning_mail_templates.xml',
        'data/whatsapp_templates_data.xml',
        'data/close_signature_mail_template.xml',
        'views/subscription_dashboard_views.xml',
        'views/loyalty_program_views.xml',
        'views/subscription_plan_views.xml',
        'views/sale_order_views.xml',
        'views/subscription_price_lock_views.xml',
        'views/subscription_dunning_views.xml',
        'views/subscription_whatsapp_template_views.xml',
        'views/subscription_reporting_views.xml',
        'views/sale_order_template_views.xml',
        'views/subscription_templates.xml',
        'views/subscription_close_reason_views.xml',
        'views/subscription_change_plan_wizard_views.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/subscription_menus.xml',
    ],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            'subscription_management/static/src/css/dashboard.scss',
            'subscription_management/static/src/js/dashboard.js',
            'subscription_management/static/src/xml/dashboard.xml',
        ],
        'web.assets_frontend': [
            'subscription_management/static/src/css/hide_sidebar.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
