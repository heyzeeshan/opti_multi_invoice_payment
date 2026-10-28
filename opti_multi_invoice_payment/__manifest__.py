# -*- coding: utf-8 -*-
# Copyright 2026 optiOdoo Solutions
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    'name': 'Portal Multi Invoice Payment with Card Surcharge',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Pay several customer invoices from the portal, and add a surcharge line from the payment method.',
    'description': """
Portal Multi Invoice Payment with Card Surcharge
=================================================

Customers select open invoices on the portal and pay them together.
Each payment method can carry its own surcharge percent. When the
customer pays, that percent of the untaxed amount is added as an
invoice line and included in the amount sent to the provider.
    """,
    'author': 'optiOdoo Solutions',
    'support': 'optiodoosolutions@gmail.com',
    'website': 'https://www.optiodoo.com',
    'license': 'LGPL-3',
    'depends': ['account_payment'],
    'data': [
        'views/payment_method_views.xml',
        'views/payment_form_templates.xml',
        'views/report_invoice.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'opti_multi_invoice_payment/static/src/components/tax_totals/tax_totals.xml',
        ],
        'web.assets_frontend': [
            'opti_multi_invoice_payment/static/src/scss/portal_multi_invoice.scss',
            'opti_multi_invoice_payment/static/src/js/portal_multi_invoice.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'price': 75.00,
    'currency': 'USD',
    'installable': True,
    'application': False,
    'auto_install': False,
}
