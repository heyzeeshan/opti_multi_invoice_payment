# -*- coding: utf-8 -*-
# Copyright 2026 optiOdoo Solutions
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    opti_is_surcharge = fields.Boolean(
        string='Payment Method Surcharge',
        copy=True,
        help='Line added from the surcharge percent of the payment method used on the portal.',
    )
