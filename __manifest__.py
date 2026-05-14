# -*- coding: utf-8 -*-
{
    'name': 'Delivery Map',
    'version': '19.0.1.0.1',
    'category': 'Inventory',
    'summary': 'Delivery map in stock picking',
    'author': 'Mihna',
    'depends': ['stock', 'sale_stock', 'web',],
    'data': [
        'views/stock_location_views.xml',
        'views/res_config_settings_views.xml',
        'views/stock_picking_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'delivery_map/static/src/js/delivery_map.js',
            'delivery_map/static/src/xml/delivery_map_template.xml',
            'https://unpkg.com/leaflet/dist/leaflet.css',
            'https://unpkg.com/leaflet/dist/leaflet.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3'
}
