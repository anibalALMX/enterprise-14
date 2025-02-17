# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import fields
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestNlXafExport(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref='l10n_nl.l10nnl_chart_template'):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.env.company.write({
            'vat': 'NL123456782B90',
            'country_id': cls.env.ref('base.nl').id,
        })

        products = [cls.product_a, cls.product_b]

        # Create three invoices, one refund and one bill in 2019
        partner_a_invoice1 = cls.init_invoice('out_invoice', products=products)
        partner_a_invoice2 = cls.init_invoice('out_invoice', products=products)
        partner_a_invoice3 = cls.init_invoice('out_invoice', products=products)
        partner_a_refund = cls.init_invoice('out_refund', products=products)

        partner_b_bill = cls.init_invoice('in_invoice', products=products, partner=cls.partner_b)

        # Create one invoice for partner B in 2018
        partner_b_invoice1 = cls.init_invoice('out_invoice', products=products, partner=cls.partner_b, invoice_date=fields.Date.from_string('2018-01-01'))

        # Create one MISC entry in 2018
        bank_account_id = cls.company_data['default_journal_bank'].default_account_id.id
        receivable_account_id = cls.company_data['default_account_receivable'].id
        partner_a_misc = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2018-01-01'),
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 100.0, 'credit': 0.0, 'account_id': receivable_account_id, 'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0, 'credit': 100.0, 'account_id': bank_account_id, 'partner_id': cls.partner_a.id}),
            ],
        })

        # init_invoice has hardcoded 2019 year's date, we are resetting it to current year's one.
        (partner_a_invoice1 + partner_a_invoice2 + partner_a_invoice3 + partner_b_invoice1 + partner_a_refund + partner_b_bill + partner_a_misc).action_post()

    @freeze_time('2019-12-31')
    def test_xaf_export(self):
        # Only run the test if the new (v2) template has been installed
        if not self.env.ref('l10n_nl_reports.xaf_audit_file_v2', raise_if_not_found=False):
            return True
        report = self.env['account.general.ledger']
        options = self._init_options(report, fields.Date.from_string('2019-01-01'), fields.Date.from_string('2019-12-31'))

        generated_xaf = self.get_xml_tree_from_string(report.get_xaf(options).decode("utf-8"))
        expected_xaf = self.get_xml_tree_from_string('''
            <auditfile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.auditfiles.nl/XAF/3.2">
                <header>
                    <fiscalYear>2019</fiscalYear>
                    <startDate>2019-01-01</startDate>
                    <endDate>2019-12-31</endDate>
                    <curCode>EUR</curCode>
                    <dateCreated>2019-12-31</dateCreated>
                    <softwareDesc>Odoo</softwareDesc>
                    <softwareVersion>___ignore___</softwareVersion>
                </header>
                <company>
                    <companyName>company_1_data</companyName>
                    <taxRegistrationCountry>NL</taxRegistrationCountry>
                    <taxRegIdent>NL123456782B90</taxRegIdent>
                    <streetAddress>
                        <country>NL</country>
                    </streetAddress>
                    <customersSuppliers>
                        <customerSupplier>
                            <custSupID>___ignore___</custSupID>
                            <custSupName>partner_a</custSupName>
                            <custSupTp>S</custSupTp>
                            <streetAddress>
                            </streetAddress>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </customerSupplier><customerSupplier>
                            <custSupID>___ignore___</custSupID>
                            <custSupName>partner_b</custSupName>
                            <custSupTp>B</custSupTp>
                            <streetAddress>
                            </streetAddress>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </customerSupplier>
                    </customersSuppliers>
                    <generalLedger>
                        <ledgerAccount>
                            <accID>152000</accID>
                            <accDesc>Voorbelasting hoog</accDesc>
                            <accTp>M</accTp>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </ledgerAccount><ledgerAccount>
                            <accID>800100</accID>
                            <accDesc>Omzet NL handelsgoederen 1</accDesc>
                            <accTp>M</accTp>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </ledgerAccount><ledgerAccount>
                            <accID>103002</accID>
                            <accDesc>Bank</accDesc>
                            <accTp>M</accTp>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </ledgerAccount><ledgerAccount>
                            <accID>150000</accID>
                            <accDesc>Af te dragen BTW hoog tarief</accDesc>
                            <accTp>M</accTp>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </ledgerAccount><ledgerAccount>
                            <accID>800100 (1)</accID>
                            <accDesc>Omzet NL handelsgoederen 1</accDesc>
                            <accTp>M</accTp>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </ledgerAccount><ledgerAccount>
                            <accID>400100 (1)</accID>
                            <accDesc>Bruto lonen</accDesc>
                            <accTp>M</accTp>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </ledgerAccount><ledgerAccount>
                            <accID>130010</accID>
                            <accDesc>Crediteuren (copy)</accDesc>
                            <accTp>M</accTp>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </ledgerAccount><ledgerAccount>
                            <accID>110010</accID>
                            <accDesc>Debiteuren (copy)</accDesc>
                            <accTp>M</accTp>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </ledgerAccount><ledgerAccount>
                            <accID>110000</accID>
                            <accDesc>Debiteuren</accDesc>
                            <accTp>M</accTp>
                            <changeInfo>
                                <userID>___ignore___</userID>
                                <changeDateTime>___ignore___</changeDateTime>
                                <changeDescription>___ignore___</changeDescription>
                            </changeInfo>
                        </ledgerAccount>
                    </generalLedger>
                    <vatCodes>
                        <vatCode>
                            <vatID>___ignore___</vatID>
                            <vatDesc>Verkopen/omzet hoog</vatDesc>
                        </vatCode><vatCode>
                            <vatID>___ignore___</vatID>
                            <vatDesc>Verkopen/omzet hoog (Copy)</vatDesc>
                        </vatCode><vatCode>
                            <vatID>___ignore___</vatID>
                            <vatDesc>BTW te vorderen hoog (inkopen) (Copy)</vatDesc>
                        </vatCode>
                    </vatCodes>
                    <periods>
                        <period>
                            <periodNumber>901</periodNumber>
                            <periodDesc>January 2019</periodDesc>
                            <startDatePeriod>2019-01-01</startDatePeriod>
                            <endDatePeriod>2019-01-31</endDatePeriod>
                        </period><period>
                            <periodNumber>902</periodNumber>
                            <periodDesc>February 2019</periodDesc>
                            <startDatePeriod>2019-02-01</startDatePeriod>
                            <endDatePeriod>2019-02-28</endDatePeriod>
                        </period><period>
                            <periodNumber>903</periodNumber>
                            <periodDesc>March 2019</periodDesc>
                            <startDatePeriod>2019-03-01</startDatePeriod>
                            <endDatePeriod>2019-03-31</endDatePeriod>
                        </period><period>
                            <periodNumber>904</periodNumber>
                            <periodDesc>April 2019</periodDesc>
                            <startDatePeriod>2019-04-01</startDatePeriod>
                            <endDatePeriod>2019-04-30</endDatePeriod>
                        </period><period>
                            <periodNumber>905</periodNumber>
                            <periodDesc>May 2019</periodDesc>
                            <startDatePeriod>2019-05-01</startDatePeriod>
                            <endDatePeriod>2019-05-31</endDatePeriod>
                        </period><period>
                            <periodNumber>906</periodNumber>
                            <periodDesc>June 2019</periodDesc>
                            <startDatePeriod>2019-06-01</startDatePeriod>
                            <endDatePeriod>2019-06-30</endDatePeriod>
                        </period><period>
                            <periodNumber>907</periodNumber>
                            <periodDesc>July 2019</periodDesc>
                            <startDatePeriod>2019-07-01</startDatePeriod>
                            <endDatePeriod>2019-07-31</endDatePeriod>
                        </period><period>
                            <periodNumber>908</periodNumber>
                            <periodDesc>August 2019</periodDesc>
                            <startDatePeriod>2019-08-01</startDatePeriod>
                            <endDatePeriod>2019-08-31</endDatePeriod>
                        </period><period>
                            <periodNumber>909</periodNumber>
                            <periodDesc>September 2019</periodDesc>
                            <startDatePeriod>2019-09-01</startDatePeriod>
                            <endDatePeriod>2019-09-30</endDatePeriod>
                        </period><period>
                            <periodNumber>910</periodNumber>
                            <periodDesc>October 2019</periodDesc>
                            <startDatePeriod>2019-10-01</startDatePeriod>
                            <endDatePeriod>2019-10-31</endDatePeriod>
                        </period><period>
                            <periodNumber>911</periodNumber>
                            <periodDesc>November 2019</periodDesc>
                            <startDatePeriod>2019-11-01</startDatePeriod>
                            <endDatePeriod>2019-11-30</endDatePeriod>
                        </period><period>
                            <periodNumber>912</periodNumber>
                            <periodDesc>December 2019</periodDesc>
                            <startDatePeriod>2019-12-01</startDatePeriod>
                            <endDatePeriod>2019-12-31</endDatePeriod>
                        </period>
                    </periods>
                    <openingBalance>
                        <opBalDate>2019-01-01</opBalDate>
                        <linesCount>5</linesCount>
                        <totalDebit>1552.0</totalDebit>
                        <totalCredit>352.0</totalCredit>
                        <obLine>
                            <nr>___ignore___</nr>
                            <accID>110000</accID>
                            <amnt>100.0</amnt>
                            <amntTp>D</amntTp>
                        </obLine><obLine>
                            <nr>___ignore___</nr>
                            <accID>150000</accID>
                            <amnt>252.0</amnt>
                            <amntTp>C</amntTp>
                        </obLine><obLine>
                            <nr>___ignore___</nr>
                            <accID>103002</accID>
                            <amnt>100.0</amnt>
                            <amntTp>C</amntTp>
                        </obLine><obLine>
                            <nr>___ignore___</nr>
                            <accID>110010</accID>
                            <amnt>1452.0</amnt>
                            <amntTp>D</amntTp>
                        </obLine>
                    </openingBalance>
                    <transactions>
                        <linesCount>25</linesCount>
                        <totalDebit>7137.6</totalDebit>
                        <totalCredit>7137.6</totalCredit>
                        <journal>
                            <jrnID>INV</jrnID>
                            <desc>Customer Invoices</desc>
                            <jrnTp>S</jrnTp>
                            <transaction>
                                <nr>___ignore___</nr>
                                <desc>INV/2019/01/0001</desc>
                                <periodNumber>901</periodNumber>
                                <trDt>2019-01-01</trDt>
                                <amnt>1494.0</amnt>
                                <trLine>
                                    <nr>___ignore___</nr>
                                    <accID>150000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>Verkopen/omzet hoog</desc>
                                    <amnt>252.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-252.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>110000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>INV/2019/01/0001</desc>
                                    <amnt>1494.0</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>1494.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>800100</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_a</desc>
                                    <amnt>1000.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-1000.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>800100 (1)</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_b</desc>
                                    <amnt>200.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-200.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>150000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>Verkopen/omzet hoog (Copy)</desc>
                                    <amnt>42.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-42.0</curAmnt>
                                    </currency>
                                </trLine>
                            </transaction><transaction>
                                <nr>___ignore___</nr>
                                <desc>INV/2019/01/0002</desc>
                                <periodNumber>901</periodNumber>
                                <trDt>2019-01-01</trDt>
                                <amnt>1494.0</amnt>
                                <trLine>
                                    <nr>___ignore___</nr>
                                    <accID>150000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>Verkopen/omzet hoog</desc>
                                    <amnt>252.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0002</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-252.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>110000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>INV/2019/01/0002</desc>
                                    <amnt>1494.0</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0002</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>1494.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>800100</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_a</desc>
                                    <amnt>1000.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0002</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-1000.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>800100 (1)</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_b</desc>
                                    <amnt>200.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0002</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-200.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>150000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>Verkopen/omzet hoog (Copy)</desc>
                                    <amnt>42.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0002</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-42.0</curAmnt>
                                    </currency>
                                </trLine>
                            </transaction><transaction>
                                <nr>___ignore___</nr>
                                <desc>INV/2019/01/0003</desc>
                                <periodNumber>901</periodNumber>
                                <trDt>2019-01-01</trDt>
                                <amnt>1494.0</amnt>
                                <trLine>
                                    <nr>___ignore___</nr>
                                    <accID>150000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>Verkopen/omzet hoog</desc>
                                    <amnt>252.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0003</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-252.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>110000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>INV/2019/01/0003</desc>
                                    <amnt>1494.0</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0003</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>1494.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>800100</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_a</desc>
                                    <amnt>1000.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0003</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-1000.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>800100 (1)</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_b</desc>
                                    <amnt>200.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0003</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-200.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>150000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>Verkopen/omzet hoog (Copy)</desc>
                                    <amnt>42.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>INV/2019/01/0003</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-42.0</curAmnt>
                                    </currency>
                                </trLine>
                            </transaction><transaction>
                                <nr>___ignore___</nr>
                                <desc>RINV/2019/01/0001</desc>
                                <periodNumber>901</periodNumber>
                                <trDt>2019-01-01</trDt>
                                <amnt>1494.0</amnt>
                                <trLine>
                                    <nr>___ignore___</nr>
                                    <accID>150000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>Verkopen/omzet hoog</desc>
                                    <amnt>252.0</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>RINV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>252.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>110000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc></desc>
                                    <amnt>1494.0</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>RINV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-1494.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>800100</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_a</desc>
                                    <amnt>1000.0</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>RINV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>1000.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>800100 (1)</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_b</desc>
                                    <amnt>200.0</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>RINV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>200.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>150000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>Verkopen/omzet hoog (Copy)</desc>
                                    <amnt>42.0</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>RINV/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>42.0</curAmnt>
                                    </currency>
                                </trLine>
                            </transaction>
                        </journal><journal>
                            <jrnID>BILL</jrnID>
                            <desc>Vendor Bills</desc>
                            <jrnTp>P</jrnTp>
                            <transaction>
                                <nr>___ignore___</nr>
                                <desc>BILL/2019/01/0001</desc>
                                <periodNumber>901</periodNumber>
                                <trDt>2019-01-01</trDt>
                                <amnt>1161.6</amnt>
                                <trLine>
                                    <nr>___ignore___</nr>
                                    <accID>152000</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>BTW te vorderen hoog (inkopen) (Copy)</desc>
                                    <amnt>201.6</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>BILL/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>201.6</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>130010</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc></desc>
                                    <amnt>348.48</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>BILL/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-348.48</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>130010</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc></desc>
                                    <amnt>813.12</amnt>
                                    <amntTp>C</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>BILL/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>-813.12</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>400100 (1)</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_a</desc>
                                    <amnt>800.0</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>BILL/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>800.0</curAmnt>
                                    </currency>
                                </trLine><trLine>
                                    <nr>___ignore___</nr>
                                    <accID>400100 (1)</accID>
                                    <docRef>/</docRef>
                                    <effDate>2019-01-01</effDate>
                                    <desc>product_b</desc>
                                    <amnt>160.0</amnt>
                                    <amntTp>D</amntTp>
                                    <custSupID>___ignore___</custSupID>
                                    <invRef>BILL/2019/01/0001</invRef>
                                    <currency>
                                        <curCode>EUR</curCode>
                                        <curAmnt>160.0</curAmnt>
                                    </currency>
                                </trLine>
                            </transaction>
                        </journal>
                    </transactions>
                </company>
            </auditfile>
        ''')
        self.assertXmlTreeEqual(generated_xaf, expected_xaf)
