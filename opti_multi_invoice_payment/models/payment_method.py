# -*- coding: utf-8 -*-
# Copyright 2026 optiOdoo Solutions
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models


class PaymentMethod(models.Model):
    _inherit = 'payment.method'

    opti_surcharge = fields.Float(
        string='Invoice payment surcharge (%)',
        help='Percent of the invoice untaxed amount added as a line when the customer pays with this method.',
    )
    opti_surcharge_label = fields.Char(compute='_compute_opti_surcharge_label')
    opti_surcharge_custom = fields.Boolean(compute='_compute_opti_surcharge_custom')

    def _opti_effective_surcharge(self):
        """Percent used for the fee. An existing surcharge on the method is kept as-is."""
        self.ensure_one()
        if 'surcharge' in self._fields and self.surcharge:
            return self.surcharge
        return self.opti_surcharge or 0.0

    def _opti_surcharge_percent_label(self):
        self.ensure_one()
        percent = self._opti_effective_surcharge()
        if float(percent).is_integer():
            return str(int(percent))
        return f'{percent:.2f}'.rstrip('0').rstrip('.')

    def _opti_show_surcharge_note(self, invoices, multi_pay=False):
        self.ensure_one()
        if not invoices or not self._opti_effective_surcharge():
            return False
        if multi_pay:
            return True
        if 'surcharge' in self._fields and self.surcharge:
            return False
        return True

    @api.depends('opti_surcharge')
    def _compute_opti_surcharge_custom(self):
        custom = 'surcharge' not in self._fields
        for method in self:
            method.opti_surcharge_custom = custom

    @api.depends('opti_surcharge', 'name')
    def _compute_opti_surcharge_label(self):
        for method in self:
            percent = method._opti_effective_surcharge()
            if percent and not ('surcharge' in method._fields and method.surcharge):
                method.opti_surcharge_label = _(
                    '%(percent)s%% surcharge (%(method)s)',
                    percent=method._opti_surcharge_percent_label(),
                    method=method.name,
                )
            else:
                method.opti_surcharge_label = False
