from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged
from .common import TestAccountAvataxCommon


@tagged("-at_install", "post_install")
class TestAccountAvalaraInternal(TestAccountAvataxCommon):
    def assertInvoice(self, invoice, test_exact_response):
        self.assertEqual(
            len(invoice.invoice_line_ids.tax_ids),
            0,
            "There should be no tax rate on the line."
        )

        self.assertRecordValues(invoice, [{
            'amount_total': 90.0,
            'amount_untaxed': 90.0,
            'amount_tax': 0.0,
        }])
        invoice.action_post()

        if test_exact_response:
            self.assertRecordValues(invoice, [{
                'amount_total': 96.54,
                'amount_untaxed': 90.0,
                'amount_tax': 6.54,
            }])

            avatax_mapping = {avatax_line['lineNumber']: avatax_line for avatax_line in test_exact_response['lines']}
            for line in invoice.invoice_line_ids:
                line_number = f'account.move.line,{line.id}'
                self.assertIn(line_number, avatax_mapping)
                avatax_line = avatax_mapping[line_number]
                self.assertEqual(
                    line.price_total,
                    avatax_line['tax'] + avatax_line['lineAmount'],
                    f"Tax-included price doesn't match tax returned by Avatax for line {line.id} (product: {line.product_id.display_name})."
                )
                self.assertEqual(
                    line.price_subtotal,
                    avatax_line['lineAmount'],
                    f"Wrong Avatax amount for {line.id} (product: {line.product_id.display_name}), there is probably a mismatch between the test SO and the mocked response."
                )

        else:
            for line in invoice.invoice_line_ids:
                product_name = line.product_id.display_name
                self.assertGreater(len(line.tax_ids), 0, "Line with %s did not get any taxes set." % product_name)

            self.assertGreater(invoice.amount_tax, 0.0, "Invoice has a tax_amount of 0.0.")

    def test_01_odoo_invoice(self):
        invoice, response = self._create_invoice_01_and_expected_response()
        with self._capture_request(return_value=response):
            self.assertInvoice(invoice, test_exact_response=response)

        # verify transactions are uncommitted
        with patch('odoo.addons.account_avatax.models.account_avatax.AccountAvatax._uncommit_avatax_transaction') as mocked_commit:
            invoice.button_draft()
            mocked_commit.assert_called()

    def test_integration_01_odoo_invoice(self):
        with self._skip_no_credentials():
            invoice, _ = self._create_invoice_01_and_expected_response()
            self.assertInvoice(invoice, test_exact_response=False)
            invoice.button_draft()

    def test_02_odoo_invoice(self):
        invoice, response = self._create_invoice_02_and_expected_response()
        with self._capture_request(return_value=response):
            self.assertInvoice(invoice, test_exact_response=response)

        # verify transactions are uncommitted
        with patch('odoo.addons.account_avatax.models.account_avatax.AccountAvatax._uncommit_avatax_transaction') as mocked_commit:
            invoice.button_draft()
            mocked_commit.assert_called()

    def test_integration_02_odoo_invoice(self):
        with self._skip_no_credentials():
            invoice, _ = self._create_invoice_02_and_expected_response()
            self.assertInvoice(invoice, test_exact_response=False)
            invoice.button_draft()

    def test_01_odoo_refund(self):
        invoice, response = self._create_invoice_01_and_expected_response()

        with self._capture_request(return_value=response):
            invoice.action_post()

        move_reversal = self.env['account.move.reversal'] \
            .with_context(active_model='account.move', active_ids=invoice.ids) \
            .create({'refund_method': 'refund'})
        refund = self.env['account.move'].browse(move_reversal.reverse_moves()['res_id'])

        # Amounts should be sent as negative for refunds:
        # https://developer.avalara.com/erp-integration-guide/sales-tax-badge/transactions/test-refunds/
        for line in refund._get_avatax_invoice_lines():
            if 'Discount' in line['description']:
                self.assertGreater(line['amount'], 0)
            else:
                self.assertLess(line['amount'], 0)

    def test_unlink(self):
        invoice, _ = self._create_invoice_01_and_expected_response()

        mock_response = {'error': {'code': 'EntityNotFoundError',
           'details': [{'code': 'EntityNotFoundError',
                        'description': "The Document with code 'Journal Entry "
                                       "2180' was not found.",
                        'faultCode': 'Client',
                        'helpLink': 'http://developer.avalara.com/avatax/errors/EntityNotFoundError',
                        'message': 'Document not found.',
                        'number': 4,
                        'severity': 'Error'}],
           'message': 'Document not found.',
           'target': 'HttpRequest'}}

        with self._capture_request(return_value=mock_response) as capture:
            invoice.unlink()

        self.assertEqual(capture.val['json']['code'], 'DocVoided', 'Should have tried to void without raising on EntityNotFoundError.')

    def test_journal_entry(self):
        entry, _ = self._create_invoice_01_and_expected_response()
        entry.move_type = 'entry'

        with self._capture_request(return_value={'lines': [], 'summary': []}) as capture:
            entry.action_post()

        self.assertIsNone(capture.val, "Journal entries should not be sent to Avatax.")

    def test_posted_invoice(self):
        invoice, _ = self._create_invoice_01_and_expected_response()

        with self._capture_request(return_value={'lines': [], 'summary': []}):
            invoice.action_post()

        with self._capture_request(return_value={'lines': [], 'summary': []}) as capture:
            invoice.button_update_avatax()

        self.assertIsNone(capture.val, "Should not update taxes of posted invoices.")

    def test_check_address_constraint(self):
        invoice, _ = self._create_invoice_01_and_expected_response()
        partner_no_zip = self.env["res.partner"].create({
            "name": "Test no zip",
            "state_id": self.env.ref("base.state_us_5").id,
            "country_id": self.env.ref("base.us").id,
            "zip": False,
        })

        with self.assertRaises(ValidationError):
            invoice.partner_id = partner_no_zip

    def test_negative_quantities(self):
        """ The quantity field sent to Avatax should always be positive. From the Avatax documentation:
        'Quantity of items in this line. This quantity value should always be a positive value representing the quantity
        of product that changed hands, even when handling returns or refunds.'
        """
        res = self.env['account.avatax']._get_avatax_invoice_line(self.product_accounting, None, -1, None)
        self.assertEqual(res['quantity'], 1, 'Quantities sent to Avatax should always be positive.')

    def test_multi_currency_exempted_tax(self):
        """ Test an invoice in another currency having 2 taxes computed from AvaTax whose one is exempted"""
        # create an invoice of 100 in a currency with a rate of 2.0
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'fiscal_position_id': self.fp_avatax.id,
            'currency_id': self.currency_data['currency'].id,
            'invoice_date': '2021-01-01',
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product_user.id,
                    'tax_ids': None,
                    'price_unit': 100.00,
                }),
            ]
        })
        # Taxes from AvaTax:
        # - "CA STATE TAX" (4%)
        # - "CA COUNTY TAX" (6%) [exempted]
        lines = [{
            'details': [{
                'jurisCode': '06',
                'nonTaxableAmount': 0.0,
                'rate': 0.04,
                'taxableAmount': 100.0,
                'taxName': 'CA STATE TAX',
            }, {
                'jurisCode': '075',
                'nonTaxableAmount': 100.0,
                'rate': 0.06,
                'taxableAmount': 0.0,
                'taxName': 'CA COUNTY TAX',
            }],
            'lineAmount': 100.0,
            'lineNumber': 'account.move.line,' + str(invoice.invoice_line_ids.id),
            'tax': 4.0,
        }]
        summary = [{
            'jurisCode': '06',
            'nonTaxable': 0.0,
            'rate': 0.04,
            'tax': 4.0,
            'taxCalculated': 4.0,
            'taxName': 'CA STATE TAX',
            'taxable': 100.0,
        }, {
            'country': 'US',
            'jurisCode': '075',
            'nonTaxable': 100.0,
            'rate': 0.06,
            'tax': 0.0,
            'taxCalculated': 0.0,
            'taxName': 'CA COUNTY TAX',
            'taxable': 0.0,
        }]
        with self._capture_request(return_value={'lines': lines, 'summary': summary}):
            invoice.action_post()
        self.assertRecordValues(invoice, [{'amount_tax': 4.0, 'amount_total': 104.0, 'amount_untaxed': 100.0}])
        # The tax lines should be:
        # ________________________________________________________________________________
        #              Label              | Amount in Currency | Balance | Debit | Credit
        # --------------------------------------------------------------------------------
        #  CA STATE TAX [06] (4.0000 %)   |        -4.0        |   -2.0  |  0.0  |  2.0
        #  CA COUNTY TAX [075] (6.0000 %) |         0.0        |    0.0  |  0.0  |  0.0
        tax_line = invoice.line_ids.filtered(lambda l: l.tax_line_id.name == 'CA STATE TAX [06] (4.0000 %)')
        self.assertRecordValues(tax_line, [{'quantity': 1.0, 'amount_currency': -4.0, 'balance': -2.0, 'debit': 0.0, 'credit': 2.0}])
        exempted_tax_line = invoice.line_ids.filtered(lambda l: l.tax_line_id.name == 'CA COUNTY TAX [075] (6.0000 %)')
        self.assertRecordValues(exempted_tax_line, [{'quantity': 1.0, 'amount_currency': 0.0, 'balance': 0.0, 'debit': 0.0, 'credit': 0.0}])

@tagged("-at_install", "post_install")
class TestAccountAvalaraSalesTaxAdministration(TestAccountAvataxCommon):
    """https://developer.avalara.com/certification/avatax/sales-tax-badge/"""

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        res = super().setUpClass(chart_template_ref)
        cls.config = cls.env['res.config.settings'].create({})
        return res

    def test_disable_document_recording(self):
        """In order for this connector to be used in conjunction with other integrations to AvaTax,
        the user must be able to control which connector is used for recording documents to AvaTax.

        From a technical standpoint, simply use DocType: 'SalesOrder' on all calls
        and suppress any non-getTax calls (i.e. cancelTax, postTax).
        """
        self.env.company.avalara_commit = False
        invoice, response = self._create_invoice_01_and_expected_response()
        with self._capture_request(return_value=response), patch('odoo.addons.account_avatax.lib.avatax_client.AvataxClient.commit_transaction') as mocked_commit:
            invoice.action_post()
            mocked_commit.assert_not_called()

    def test_disable_avatax(self):
        """The user must have an option to turn on or off the AvaTax Calculation service
        independent of any other Avalara product or service.
        """
        self.fp_avatax.is_avatax = False
        with patch('odoo.addons.account_avatax.lib.avatax_client.AvataxClient.request') as mocked_request:
            self._create_invoice()
            mocked_request.assert_not_called()

    def test_integration_connect_button(self):
        """Test the connection to the AvaTax service and verify the AvaTax credentials."""
        with self._skip_no_credentials(), self.assertRaisesRegex(UserError, "'version'"):
            self.config.avatax_ping()
