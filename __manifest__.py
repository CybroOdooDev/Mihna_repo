{
    'name': 'Braintree Payment Gateway',
    'version': '19.0.1.0.0',
    'summary': 'Safe and reliable Braintree payment gateway for Odoo',
    'description': """
        Odoo Website Braintree Payment Acquirer
        ========================================
        Integrates Braintree payment gateway with Odoo.
    """,
    'category': 'Accounting/Payment Acquirers',
    'author': 'Mihna',
    'depends': ['payment', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'data/payment_provider_method.xml',
        'data/payment_provider_data.xml',
        'views/payment_provider_views.xml',
        'views/payment_braintree_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'https://js.braintreegateway.com/web/dropin/1.43.0/js/dropin.min.js',
            'payment_braintree/static/src/interactions/payment_form.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}