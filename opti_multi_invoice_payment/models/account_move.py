# -*- coding: utf-8 -*-
# Copyright 2026 optiOdoo Solutions
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import formatLang

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    opti_amount_surcharge = fields.Float(copy=False)
    opti_amount_total_without_surcharge = fields.Float(copy=False)
    opti_surcharge_label = fields.Char(copy=False)

    def _opti_epd_factor(self):
        """Share of the invoice that is still due after an early payment discount.

        Returns 1 when no discount applies. The surcharge itself is not discounted.
        """
        self.ensure_one()
        if self._is_eligible_for_early_payment_discount(self.currency_id, fields.Date.context_today(self)):
            return (100 - self.invoice_payment_term_id.discount_percentage) / 100
        return 1

    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for move in self:
            totals = move.tax_totals
            if not totals or not move.opti_amount_total_without_surcharge or not move.opti_surcharge_label:
                continue
            totals = dict(totals)
            totals.update({
                'formatted_amount_total_without_surcharge': formatLang(
                    self.env, move.opti_amount_total_without_surcharge, currency_obj=move.currency_id,
                ),
                'opti_surcharge_label': move.opti_surcharge_label,
            })
            move.tax_totals = totals

    def _opti_surcharge_product(self):
        product = self.env.ref(
            'opti_multi_invoice_payment.product_portal_card_surcharge',
            raise_if_not_found=False,
        )
        if product:
            return product
        vals = {
            'name': 'Surcharge',
            'list_price': 0.0,
            'sale_ok': False,
            'purchase_ok': False,
            'taxes_id': [(5, 0, 0)],
            'supplier_taxes_id': [(5, 0, 0)],
        }
        if 'detailed_type' in self.env['product.product']._fields:
            vals['detailed_type'] = 'service'
        else:
            vals['type'] = 'service'
        template_fields = self.env['product.template']._fields
        if 'sale_line_warn' in template_fields:
            vals['sale_line_warn'] = 'no-message'
        if 'purchase_line_warn' in template_fields:
            vals['purchase_line_warn'] = 'no-message'
        product = self.env['product.product'].sudo().create(vals)
        self.env['ir.model.data'].sudo().create({
            'module': 'opti_multi_invoice_payment',
            'name': 'product_portal_card_surcharge',
            'model': 'product.product',
            'res_id': product.id,
            'noupdate': True,
        })
        return product

    def _opti_surcharge_income_account(self, product):
        self.ensure_one()
        product = product.with_company(self.company_id)
        account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        if not account:
            account = self.invoice_line_ids.filtered(
                lambda line: line.display_type == 'product' and line.account_id and not line.opti_is_surcharge
            )[:1].account_id
        if not account:
            raise UserError(_(
                "Set an income account on the surcharge product %(product)s.",
                product=product.display_name,
            ))
        return account

    def _opti_surcharge_preview(self, payment_method):
        """Surcharge and payable total for these invoices and one payment method.

        Used on the payment form, before the line is created.
        """
        currency = self[:1].currency_id
        surcharge = 0.0
        payable = 0.0
        percent = payment_method._opti_effective_surcharge()
        for invoice in self:
            factor = invoice._opti_epd_factor()
            existing_amount = invoice._opti_existing_surcharge_amount()
            if existing_amount is not None:
                surcharge += existing_amount
                payable += invoice.amount_total
                continue
            part = 0.0
            if percent:
                part = currency.round(invoice.amount_untaxed * factor * percent / 100.0)
            surcharge += part
            payable += currency.round(invoice.amount_total * factor + part)
        if currency:
            surcharge = currency.round(surcharge)
            payable = currency.round(payable)
        return {'surcharge': surcharge, 'payable': payable}

    def _opti_create_surcharge_line(self, payment_method):
        """Add the payment-method surcharge and return the amount to charge.

        The percent is taken from the method. The base is the untaxed amount,
        reduced by an early payment discount when one still applies. A second
        call does not add another line.
        """
        self.ensure_one()
        payment_method = payment_method.sudo()
        if self._opti_existing_surcharge_amount() is not None or not payment_method.opti_surcharge:
            return self.amount_total

        currency = self.currency_id
        factor = self._opti_epd_factor()
        surcharge = currency.round(self.amount_untaxed * factor * payment_method.opti_surcharge / 100.0)
        if currency.is_zero(surcharge):
            return self.amount_total

        invoice = self.with_company(self.company_id).sudo()
        product = invoice._opti_surcharge_product()
        account = invoice._opti_surcharge_income_account(product)
        invoice.write({
            'opti_amount_surcharge': surcharge,
            'opti_amount_total_without_surcharge': invoice.amount_total,
            'opti_surcharge_label': payment_method.opti_surcharge_label,
        })
        sequences = invoice.invoice_line_ids.mapped('sequence')
        line_vals = {
            'product_id': product.id,
            'name': _('%(method)s %(percent)s%%', method=payment_method.name, percent=payment_method._opti_surcharge_percent_label()),
            'quantity': 1.0,
            'price_unit': surcharge,
            'account_id': account.id,
            'tax_ids': [Command.clear()],
            'display_type': 'product',
            'sequence': (max(sequences) if sequences else 0) + 1,
            'opti_is_surcharge': True,
        }
        try:
            with invoice.env.cr.savepoint():
                if invoice.state == 'posted':
                    if invoice.restrict_mode_hash_table:
                        raise UserError(_(
                            "Invoice %(invoice)s is in a locked journal, so the surcharge line cannot be added.",
                            invoice=invoice.display_name,
                        ))
                    invoice.button_draft()
                invoice.write({'invoice_line_ids': [Command.create(line_vals)]})
                line = invoice.invoice_line_ids.filtered('opti_is_surcharge')[-1:]
                if line.tax_ids:
                    line.write({'tax_ids': [Command.clear()]})
                if invoice.state == 'draft':
                    invoice.action_post()
                invoice._opti_drop_stale_invoice_pdf()
        except (UserError, ValidationError):
            _logger.exception("Could not add the payment surcharge on %s", invoice.display_name)
            raise

        return currency.round((invoice.amount_total - surcharge) * factor + surcharge)

    def _opti_existing_surcharge_amount(self):
        self.ensure_one()
        if 'is_surcharge' in self.env['account.move.line']._fields:
            lines = self.invoice_line_ids.filtered('is_surcharge')
            if lines:
                return self.amount_surcharge or sum(lines.mapped('price_unit'))
        lines = self.invoice_line_ids.filtered('opti_is_surcharge')
        if lines:
            return self.opti_amount_surcharge or sum(lines.mapped('price_unit'))
        return None

    def _opti_apply_surcharge_one(self, payment_method):
        """Add one surcharge line and return the amount to charge.

        When the payment method already has its own surcharge, that existing
        behavior is used so the invoice is not charged twice.
        """
        self.ensure_one()
        payment_method = payment_method.sudo()
        if (
            'surcharge' in payment_method._fields
            and payment_method.surcharge
            and hasattr(self, '_create_surcharge_line')
        ):
            return self._create_surcharge_line(payment_method.id)
        return self._opti_create_surcharge_line(payment_method)

    def _opti_apply_surcharge(self, payment_method):
        """Add the surcharge on every selected invoice and return the combined charge."""
        currency = self[:1].currency_id
        if len(self.currency_id) != 1:
            raise ValidationError(_("Select invoices that use the same currency."))
        total = 0.0
        for invoice in self:
            total += invoice._opti_apply_surcharge_one(payment_method)
        return currency.round(total) if currency else total

    def _opti_drop_stale_invoice_pdf(self):
        for move in self.filtered('invoice_pdf_report_id'):
            move.invoice_pdf_report_file = False

    def _get_invoice_next_payment_values(self, *args, **kwargs):
        values = super()._get_invoice_next_payment_values(*args, **kwargs)
        surcharge_lines = self.invoice_line_ids.filtered('opti_is_surcharge')
        if not surcharge_lines:
            return values
        currency = self.currency_id
        surcharge_amount = sum(surcharge_lines.mapped('price_unit'))
        next_amount = values['next_amount_to_pay']
        factor = self._opti_epd_factor()
        discount = currency.round((next_amount - surcharge_amount) * (1 - factor))
        values.update({
            'amount_due': currency.round((next_amount - surcharge_amount) * factor + surcharge_amount),
            'epd_discount_amount_currency': discount,
        })
        if not currency.is_zero(discount):
            values['epd_discount_msg'] = _(
                "Discount of %(amount)s if paid within the early payment period",
                amount=currency.format(discount),
            )
        return values

    def _opti_check_portal_payable(self):
        errors = []
        if not self:
            errors.append(_("Select at least one invoice that is waiting for payment."))
        if len(self.company_id) > 1:
            errors.append(_("Select invoices from the same company."))
        if len(self.currency_id) > 1:
            errors.append(_("Select invoices that use the same currency."))
        for invoice in self:
            if invoice.move_type != 'out_invoice' or not invoice._has_to_be_paid():
                errors.append(_("%s cannot be paid online.", invoice.display_name))
        if errors:
            raise ValidationError('\n'.join(dict.fromkeys(errors)))
