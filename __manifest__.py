# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
{
    'name': 'Advanced Subscription Management',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Manage recurring billing, subscriptions, and customer lifecycle.',
    'description': """
Advanced Subscription Management System
==============================
A commercial-grade Advanced Subscription Management application that provides feature parity with Odoo Enterprise Subscriptions.
Features include:
- Subscription plans and pricing tiers
- Recurring invoicing
- Dunning management
- Customer self-service portal
- MRR, Churn, and KPI dashboards
""",
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['sale_management', 'account', 'mail', 'portal', 'website', 'website_sale', 'payment', 'stock',
                'delivery', 'sale_project', 'sale_timesheet', 'loyalty', 'sale_loyalty'],
    'data': [
        'security/advanced_subscription_management_security.xml',
        'security/ir.model.access.csv',
        'views/subscription_menu_roots.xml',
        'data/subscription_close_reason_data.xml',
        'data/ir_cron_data.xml',
        'data/mail_template_data.xml',
        'data/whatsapp_template_data.xml',
        'views/subscription_dashboard_views.xml',
        'views/loyalty_program_views.xml',
        'views/subscription_plan_views.xml',
        'views/sale_order_views.xml',
        'views/subscription_dunning_views.xml',
        'views/subscription_whatsapp_template_views.xml',
        'report/subscription_report_views.xml',
        'views/sale_order_template_views.xml',
        'views/subscription_templates.xml',
        'views/subscription_close_reason_views.xml',
        'wizard/subscription_close_views.xml',
        'wizard/subscription_change_plan_views.xml',
        'views/product_template_views.xml',
        'views/product_pricelist_views.xml',
        'views/res_config_settings_views.xml',
        'views/subscription_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'advanced_subscription_management/static/src/css/dashboard.scss',
            'advanced_subscription_management/static/src/js/dashboard.js',
            'advanced_subscription_management/static/src/xml/dashboard.xml',
        ],
        'web.assets_frontend': [
            'advanced_subscription_management/static/src/css/hide_sidebar.css',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
