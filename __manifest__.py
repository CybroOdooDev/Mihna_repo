# -*- coding: utf-8 -*-
{
    'name': 'POS Refund Limit Days',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Restrict POS order refunds by enforcing a configurable return period in days.',
    'description': """
        This module allows users to set a return period for each Point of Sale.
        POS orders can only be refunded if they are within the specified return period.
    """,
    'author': 'Mihna',
    'depends': ['point_of_sale'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_refund_days/static/src/js/refund_limit.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}