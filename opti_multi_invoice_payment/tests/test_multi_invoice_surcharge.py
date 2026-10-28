from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestMultiInvoiceSurcharge(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['account.move']._opti_surcharge_product()
        for product in cls.env['product.product'].search([('name', '=', 'Surcharge')]):
            product.with_company(cls.company_data['company']).property_account_income_id = cls.company_data['default_account_revenue']
        cls.card = cls.env['payment.method'].create({
            'name': 'Credit Card',
            'code': 'opti_multi_pay_card',
            'opti_surcharge': 3.0,
            'image': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
        })

    def _posted_invoice(self, amount):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1,
                'price_unit': amount,
                'tax_ids': [Command.clear()],
            })],
        })
        invoice.action_post()
        return invoice

    def test_surcharge_line_on_each_paid_invoice(self):
        if 'surcharge' in self.card._fields:
            self.card.surcharge = 0.0
        first = self._posted_invoice(92.80)
        second = self._posted_invoice(40.00)
        invoices = first + second
        currency = first.currency_id

        charged = invoices._opti_apply_surcharge(self.card)
        self.assertEqual(currency.compare_amounts(charged, 136.78), 0)
        for invoice, fee in ((first, 2.78), (second, 1.20)):
            line = invoice.invoice_line_ids.filtered('opti_is_surcharge')
            self.assertEqual(len(line), 1)
            self.assertEqual(currency.compare_amounts(line.price_unit, fee), 0)
            self.assertEqual(line.name, 'Credit Card 3%')
        self.assertEqual(currency.compare_amounts(invoices._opti_apply_surcharge(self.card), 136.78), 0)
        self.assertEqual(len(first.invoice_line_ids.filtered('opti_is_surcharge')), 1)

    def test_existing_method_surcharge_is_used_once(self):
        if 'surcharge' not in self.card._fields or not hasattr(self.env['account.move'], '_create_surcharge_line'):
            self.skipTest('This database has no payment-method surcharge yet.')
        self.card.write({'surcharge': 3.0, 'opti_surcharge': 9.0})
        first = self._posted_invoice(92.80)
        second = self._posted_invoice(40.00)
        invoices = first + second
        currency = first.currency_id

        charged = invoices._opti_apply_surcharge(self.card)
        self.assertEqual(currency.compare_amounts(charged, 136.78), 0)
        for invoice, fee in ((first, 2.78), (second, 1.20)):
            external_line = invoice.invoice_line_ids.filtered('is_surcharge')
            own_line = invoice.invoice_line_ids.filtered('opti_is_surcharge')
            self.assertEqual(len(external_line), 1)
            self.assertFalse(own_line)
            self.assertEqual(currency.compare_amounts(external_line.price_unit, fee), 0)
        self.assertEqual(len(first.invoice_line_ids.filtered('is_surcharge')), 1)
        self.assertEqual(currency.compare_amounts(invoices._opti_apply_surcharge(self.card), 136.78), 0)
