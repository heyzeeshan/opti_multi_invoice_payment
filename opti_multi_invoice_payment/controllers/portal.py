# -*- coding: utf-8 -*-
# Copyright 2026 optiOdoo Solutions
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _
from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.http import request, route

from odoo.addons.account_payment.controllers.portal import PortalAccount
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.controllers.portal import PaymentPortal


class OptiPortalAccount(PortalAccount):

    def _invoice_get_page_view_values(self, invoice, access_token, **kwargs):
        values = super()._invoice_get_page_view_values(invoice, access_token, **kwargs)
        values['opti_surcharge_invoices'] = invoice
        return values

    def _opti_payment_values(self, invoices, partner, access_token, transaction_route, landing_route):
        company = invoices.company_id
        currency = invoices.currency_id
        amount = currency.round(sum(invoices.mapped('amount_residual')))
        providers_sudo = request.env['payment.provider'].sudo()._get_compatible_providers(
            company.id, partner.id, amount, currency_id=currency.id,
        )
        payment_methods_sudo = request.env['payment.method'].sudo()._get_compatible_payment_methods(
            providers_sudo.ids, partner.id, currency_id=currency.id,
        )
        tokens_sudo = request.env['payment.token'].sudo()._get_available_tokens(
            providers_sudo.ids, partner.id,
        )
        return {
            'page_name': 'invoice',
            'invoices': invoices,
            'opti_surcharge_invoices': invoices,
            'opti_multi_pay': True,
            'company_mismatch': not PaymentPortal._can_partner_pay_in_company(partner, company),
            'expected_company': company,
            'amount': amount,
            'currency': currency,
            'partner_id': partner.id,
            'providers_sudo': providers_sudo,
            'payment_methods_sudo': payment_methods_sudo,
            'tokens_sudo': tokens_sudo,
            'transaction_route': transaction_route,
            'landing_route': landing_route,
            'access_token': access_token,
            'show_tokenize_input_mapping': PaymentPortal._compute_show_tokenize_input_mapping(providers_sudo),
        }

    def _opti_selected_invoices(self, invoice_ids):
        if isinstance(invoice_ids, (list, tuple)):
            raw_ids = invoice_ids
        else:
            raw_ids = str(invoice_ids or '').split(',')
        ids = []
        for raw_id in raw_ids:
            try:
                ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue
        if not ids:
            raise ValidationError(_("Select at least one invoice."))
        invoices = request.env['account.move'].search([('id', 'in', ids)])
        if set(invoices.ids) != set(ids):
            raise ValidationError(_("One or more selected invoices cannot be paid."))
        invoices._opti_check_portal_payable()
        return invoices

    @route(['/my/invoices/pay'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_pay_invoices(self, invoice_ids=None, **kwargs):
        try:
            invoices = self._opti_selected_invoices(invoice_ids)
        except ValidationError as error:
            return request.render('opti_multi_invoice_payment.portal_multi_invoice_pay', {
                'page_name': 'invoice',
                'opti_error': error.args[0],
                'invoices': request.env['account.move'],
            })
        partner = request.env.user.partner_id
        id_path = ','.join(str(invoice_id) for invoice_id in invoices.ids)
        access_token = payment_utils.generate_access_token(partner.id, id_path, invoices.currency_id.id)
        values = self._opti_payment_values(
            invoices,
            partner,
            access_token,
            f'/my/invoices/pay/transaction/{id_path}',
            '/my/invoices',
        )
        return request.render('opti_multi_invoice_payment.portal_multi_invoice_pay', values)

    @route('/my/invoices/pay/transaction/<string:invoice_ids>', type='json', auth='user')
    def portal_pay_invoices_transaction(self, invoice_ids, access_token, **kwargs):
        try:
            invoices = self._opti_selected_invoices(invoice_ids)
        except ValidationError as error:
            raise ValidationError(error.args[0]) from error

        partner = request.env.user.partner_id
        id_path = ','.join(str(invoice_id) for invoice_id in invoices.ids)
        if not payment_utils.check_access_token(access_token, partner.id, id_path, invoices.currency_id.id):
            raise ValidationError(_("The access token is invalid."))

        payment_method = request.env['payment.method']
        method_id = kwargs.get('payment_method_id')
        if not method_id and kwargs.get('token_id'):
            token = request.env['payment.token'].sudo().browse(int(kwargs['token_id'])).exists()
            method_id = token.payment_method_id.id
        if method_id:
            payment_method = request.env['payment.method'].sudo().browse(int(method_id)).exists()
        if not payment_method:
            raise ValidationError(_("Select a payment method."))
        amount = invoices.sudo()._opti_apply_surcharge(payment_method)

        self._validate_transaction_kwargs(kwargs)
        names = invoices.mapped('name')
        reference_prefix = names[0] if len(names) == 1 else f"{names[0]}+{len(names) - 1}"
        kwargs.update({
            'amount': amount,
            'currency_id': invoices.currency_id.id,
            'partner_id': partner.id,
        })
        tx_sudo = self._create_transaction(
            reference_prefix=reference_prefix[:40],
            custom_create_values={'invoice_ids': [Command.set(invoices.ids)]},
            **kwargs,
        )
        return tx_sudo._get_processing_values()
