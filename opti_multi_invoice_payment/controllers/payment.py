# -*- coding: utf-8 -*-
# Copyright 2026 optiOdoo Solutions
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request, route

from odoo.addons.account_payment.controllers.payment import PaymentPortal as AccountPaymentPortal


class PaymentPortal(AccountPaymentPortal):

    def _opti_payment_method_from_kwargs(self, kwargs):
        method_id = kwargs.get('payment_method_id')
        if not method_id and kwargs.get('token_id'):
            token = request.env['payment.token'].sudo().browse(int(kwargs['token_id'])).exists()
            method_id = token.payment_method_id.id
        if not method_id:
            return request.env['payment.method']
        return request.env['payment.method'].sudo().browse(int(method_id)).exists()

    @route()
    def invoice_transaction(self, invoice_id, access_token, **kwargs):
        """Add the payment-method surcharge, then create the transaction for the new total."""
        try:
            invoice_sudo = self._document_check_access('account.move', invoice_id, access_token)
        except MissingError as error:
            raise error
        except AccessError:
            raise ValidationError(_("The access token is invalid."))

        payment_method = self._opti_payment_method_from_kwargs(kwargs)
        if payment_method and invoice_sudo.move_type == 'out_invoice' and invoice_sudo.state == 'posted':
            kwargs['amount'] = invoice_sudo._opti_apply_surcharge_one(payment_method)
        return super().invoice_transaction(invoice_id, access_token, **kwargs)
