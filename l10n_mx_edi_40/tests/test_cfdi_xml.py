# -*- coding: utf-8 -*-
from .common import TestMxEdiCommon
from odoo.tests import tagged
from odoo.exceptions import ValidationError

from freezegun import freeze_time


@tagged('post_install', '-at_install')
class TestEdiResults(TestMxEdiCommon):

    # -------------------------------------------------------------------------
    # INVOICES
    # -------------------------------------------------------------------------

    def test_invoice_cfdi_no_external_trade(self):
        # company = MXN, invoice = Gol
        with freeze_time(self.frozen_today):
            self.invoice.action_post()

            # Change the currency to prove that the rate is computed based on the invoice
            self.currency_data['rates'].rate = 10

            generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.get_xml_tree_from_string(self.expected_invoice_cfdi_values)
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_no_tax_breakdown(self):
        with freeze_time(self.frozen_today):
            self.invoice.commercial_partner_id.l10n_mx_edi_no_tax_breakdown = True
            self.invoice.action_post()

            generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_invoice_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="SubTotal">10600.000</attribute>
                        <attribute name="Descuento">2120.000</attribute>
                    </xpath>
                    <xpath expr="//Concepto" position="replace">
                        <Concepto
                            ClaveProdServ="01010101"
                            Cantidad="5.000000"
                            Descripcion="product_mx"
                            ValorUnitario="2120.000"
                            Importe="10600.000"
                            ObjetoImp="03"
                            Descuento="2120.000"/>
                    </xpath>
                    <xpath expr="//Comprobante/Impuestos" position="replace">
                    </xpath>
                ''')
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_mixed_tax_breakdown(self):
        with freeze_time(self.frozen_today):
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
                'currency_id': self.company_data['currency'].id,
                'invoice_incoterm_id': self.env.ref('account.incoterm_FCA').id,
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 100.0,
                        'quantity': 1,
                        'tax_ids': [(6, 0, self.tax_16.ids)],
                    }),
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 100.0,
                        'quantity': 1,
                        'tax_ids': [],
                    }),
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 100.0,
                        'quantity': 1,
                        'tax_ids': [(6, 0, self.tax_16.ids)],
                        'discount': 100,
                    }),
                ]
            })

            invoice.commercial_partner_id.l10n_mx_edi_no_tax_breakdown = False
            invoice.action_post()

            generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_invoice_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Moneda">MXN</attribute>
                        <attribute name="Folio">2</attribute>
                        <attribute name="Descuento">100.00</attribute>
                        <attribute name="SubTotal">300.00</attribute>
                        <attribute name="Total">216.00</attribute>
                        <attribute name="TipoCambio" delete="true"/>
                    </xpath>
                    <xpath expr="//Concepto" position="replace">
                        <Concepto
                            Cantidad="1.000000"
                            ClaveProdServ="01010101"
                            Descripcion="product_mx"
                            ObjetoImp="02"
                            Importe="100.00"
                            ValorUnitario="100.00">
                            <Impuestos>
                                <Traslados>
                                    <Traslado
                                        Base="100.00"
                                        Importe="16.00"
                                        TasaOCuota="0.160000"
                                        TipoFactor="Tasa"/>
                                </Traslados>
                            </Impuestos>
                        </Concepto>
                        <Concepto
                            Cantidad="1.000000"
                            ClaveProdServ="01010101"
                            Descripcion="product_mx"
                            ObjetoImp="01"
                            Importe="100.00"
                            ValorUnitario="100.00">
                        </Concepto>
                        <Concepto
                            Cantidad="1.000000"
                            ClaveProdServ="01010101"
                            Descripcion="product_mx"
                            ObjetoImp="01"
                            Importe="100.00"
                            Descuento="100.00"
                            ValorUnitario="100.00">
                        </Concepto>
                    </xpath>
                    <xpath expr="/Comprobante/Impuestos" position="replace">
                        <Impuestos
                            TotalImpuestosTrasladados="16.00">
                            <Traslados>
                                <Traslado
                                    Base="100.00"
                                    Importe="16.00"
                                    TasaOCuota="0.160000"
                                    TipoFactor="Tasa"/>
                            </Traslados>
                        </Impuestos>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

            invoice.commercial_partner_id.l10n_mx_edi_no_tax_breakdown = True
            invoice_2 = invoice.copy({
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
            })
            invoice_2.action_post()

            generated_files = self._process_documents_web_services(invoice_2, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                expected_etree,
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Moneda">MXN</attribute>
                        <attribute name="Folio">3</attribute>
                        <attribute name="Descuento">100.00</attribute>
                        <attribute name="SubTotal">316.00</attribute>
                        <attribute name="Total">216.00</attribute>
                        <attribute name="TipoCambio" delete="true"/>
                    </xpath>
                    <xpath expr="(//Concepto)[1]" position="attributes">
                        <attribute name="ObjetoImp">03</attribute>
                        <attribute name="Importe">116.00</attribute>
                        <attribute name="ValorUnitario">116.00</attribute>
                    </xpath>
                    <xpath expr="(//Concepto)[1]/Impuestos" position="replace">
                    </xpath>
                    <xpath expr="(//Concepto)[2]" position="attributes">
                        <attribute name="ObjetoImp">01</attribute>
                    </xpath>
                    <xpath expr="(//Concepto)[2]" position="attributes">
                        <attribute name="ObjetoImp">01</attribute>
                    </xpath>
                    <xpath expr="/Comprobante/Impuestos" position="replace">
                    </xpath>
                '''
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_group_of_taxes(self):
        # company = MXN, invoice = Gol
        with freeze_time(self.frozen_today):
            self.invoice.write({
                'invoice_line_ids': [(1, self.invoice.invoice_line_ids.id, {'tax_ids': [(6, 0, self.tax_group.ids)]})],
            })
            self.invoice.action_post()

            generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.get_xml_tree_from_string(self.expected_invoice_cfdi_values)
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_fixed_negative_tax(self):
        with freeze_time(self.frozen_today):
            fixed_tax = self.env['account.tax'].create({
                'name': 'fixed_tax',
                'amount_type': 'fixed',
                'amount': -2.0,
                'type_tax_use': 'sale',
                'l10n_mx_tax_type': 'Cuota',
            })

            self.invoice.write({
                'invoice_line_ids': [(1, self.invoice.invoice_line_ids.id, {'tax_ids': [(6, 0, fixed_tax.ids)]})],
            })
            self.invoice.action_post()

            generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_invoice_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                      <attribute name="Total">7990.000</attribute>
                    </xpath>
                    <xpath expr="//Concepto/Impuestos" position="replace">
                      <Impuestos>
                        <Retenciones>
                          <Retencion
                            Base="8000.000"
                            Importe="10.00"
                            TasaOCuota="0.001250"
                            TipoFactor="Cuota"/>
                        </Retenciones>
                      </Impuestos>
                    </xpath>
                    <xpath expr="//Comprobante/Impuestos" position="replace">
                      <Impuestos TotalImpuestosRetenidos="10.000">
                        <Retenciones>
                          <Retencion
                            Importe="10.000"/>
                        </Retenciones>
                      </Impuestos>
                    </xpath>
                ''',
            )

            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_tax_price_included(self):
        # company = MXN, invoice = Gol
        with freeze_time(self.frozen_today):
            tax_16_incl = self.env['account.tax'].create({
                'name': 'tax_16',
                'amount_type': 'percent',
                'amount': 16,
                'type_tax_use': 'sale',
                'l10n_mx_tax_type': 'Tasa',
                'price_include': True,
                'include_base_amount': True,
            })

            self.invoice.write({
                'invoice_line_ids': [(1, self.invoice.invoice_line_ids.id, {'tax_ids': [(6, 0, tax_16_incl.ids)]})],
            })
            self.invoice.action_post()

            generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_invoice_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                      <attribute name="SubTotal">8620.690</attribute>
                    </xpath>
                    <xpath expr="//Comprobante" position="attributes">
                      <attribute name="Descuento">1724.138</attribute>
                    </xpath>
                    <xpath expr="//Comprobante" position="attributes">
                      <attribute name="Total">8000.000</attribute>
                    </xpath>
                    <xpath expr="//Concepto" position="attributes">
                      <attribute name="ValorUnitario">1724.138</attribute>
                    </xpath>
                    <xpath expr="//Concepto" position="attributes">
                      <attribute name="Importe">8620.690</attribute>
                    </xpath>
                    <xpath expr="//Concepto" position="attributes">
                      <attribute name="Descuento">1724.138</attribute>
                    </xpath>
                    <xpath expr="//Concepto/Impuestos" position="replace">
                      <Impuestos>
                        <Traslados>
                          <Traslado
                            Base="6896.552"
                            Importe="1103.45"
                            TasaOCuota="0.160000"
                            TipoFactor="Tasa"/>
                        </Traslados>
                      </Impuestos>
                    </xpath>
                    <xpath expr="//Comprobante/Impuestos" position="replace">
                      <Impuestos TotalImpuestosTrasladados="1103.448">
                        <Traslados>
                          <Traslado
                            Base="6896.552"
                            Importe="1103.448"
                            TasaOCuota="0.160000"
                            TipoFactor="Tasa"/>
                        </Traslados>
                      </Impuestos>
                    </xpath>
                ''',
            )

            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_full_discount_line(self):
        # company = MXN, invoice = Gol
        with freeze_time(self.frozen_today):
            self.invoice.write({
                'invoice_line_ids': [(1, self.invoice.invoice_line_ids.id, {'discount': 100.0})],
            })
            self.invoice.action_post()

            generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_invoice_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                      <attribute name="SubTotal">10000.000</attribute>
                    </xpath>
                    <xpath expr="//Comprobante" position="attributes">
                      <attribute name="TipoCambio">1.000000</attribute>
                    </xpath>
                    <xpath expr="//Comprobante" position="attributes">
                      <attribute name="Descuento">10000.000</attribute>
                    </xpath>
                    <xpath expr="//Comprobante" position="attributes">
                      <attribute name="Total">0.000</attribute>
                    </xpath>
                    <xpath expr="//Concepto" position="attributes">
                      <attribute name="ValorUnitario">2000.000</attribute>
                      <attribute name="ObjetoImp">01</attribute>
                    </xpath>
                    <xpath expr="//Concepto" position="attributes">
                      <attribute name="Importe">10000.000</attribute>
                    </xpath>
                    <xpath expr="//Concepto" position="attributes">
                      <attribute name="Descuento">10000.000</attribute>
                    </xpath>
                    <xpath expr="//Concepto/Impuestos" position="replace">
                    </xpath>
                    <xpath expr="//Comprobante/Impuestos" position="replace">
                    </xpath>
                ''',
            )

            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_addenda(self):
        # company = MXN, invoice = Gol
        with freeze_time(self.frozen_today):

            # Setup an addenda on the partner.
            self.invoice.partner_id.l10n_mx_edi_addenda = self.env['ir.ui.view'].create({
                'name': 'test_invoice_cfdi_addenda',
                'type': 'qweb',
                'arch': """
                    <t t-name="l10n_mx_edi.test_invoice_cfdi_addenda">
                        <test info="this is an addenda"/>
                    </t>
                """
            })

            self.invoice.action_post()

            generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_invoice_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="inside">
                        <Addenda>
                            <test info="this is an addenda"/>
                        </Addenda>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_mxn(self):
        # invoice = MXN, company = MXN
        with freeze_time(self.frozen_today):
            self.invoice.currency_id = self.invoice.company_id.currency_id
            self.invoice.action_post()

            generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_invoice_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name='Descuento'>2000.00</attribute>
                        <attribute name='Moneda'>MXN</attribute>
                        <attribute name='SubTotal'>10000.00</attribute>
                        <attribute name='Total'>8480.00</attribute>
                        <attribute name='TipoCambio' />
                    </xpath>
                    <xpath expr="//Concepto" position="attributes">
                        <attribute name='Descuento'>2000.00</attribute>
                        <attribute name='Importe'>10000.00</attribute>
                        <attribute name='ValorUnitario'>2000.00</attribute>
                    </xpath>
                    <xpath expr="//Conceptos//Traslado" position="attributes">
                        <attribute name='Base'>8000.00</attribute>
                    </xpath>
                    <xpath expr="//Conceptos//Retencion" position="attributes">
                        <attribute name='Base'>8000.00</attribute>
                    </xpath>
                    <xpath expr="//Comprobante/Impuestos" position="attributes">
                        <attribute name='TotalImpuestosRetenidos'>800.00</attribute>
                        <attribute name='TotalImpuestosTrasladados'>1280.00</attribute>
                    </xpath>
                    <xpath expr="//Comprobante/Impuestos//Retencion" position="attributes">
                        <attribute name='Importe'>800.00</attribute>
                    </xpath>
                    <xpath expr="//Comprobante/Impuestos//Traslado" position="attributes">
                        <attribute name='Importe'>1280.00</attribute>
                        <attribute name='Base'>8000.00</attribute>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_tax_rounding(self):
        '''
        To pass validation by the PAC, the tax amounts reported for each invoice
        line need to fulfil the following two conditions:
        (1) The total tax amount must be equal to the sum of the tax amounts
            reported for each invoice line.
        (2) The tax amount reported for each line must be equal to
            (tax rate * base amount), rounded either up or down.
        For example, for the line with base = MXN 398.28, the exact tax amount
        would be 0.16 * 398.28 = 63.7248, so the acceptable values for the tax
        amount on that line are 63.72 and 63.73.
        For the line with base = 108.62, acceptable values are 17.37 and 17.38.
        For the line with base = 362.07, acceptable values are 57.93 and 57.94.
        For the lines with base = 31.9, acceptable values are 5.10 and 5.11.
        This test is deliberately crafted (thanks to the lines with base = 31.9)
        to introduce rounding errors which can fool some naive algorithms for
        allocating the total tax amount among tax lines (such as algorithms
        which allocate the total tax amount proportionately to the base amount).
        '''
        with freeze_time(self.frozen_today):

            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
                'currency_id': self.company_data['currency'].id,
                'invoice_incoterm_id': self.env.ref('account.incoterm_FCA').id,
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 398.28,
                        'quantity': 1,
                        'tax_ids': [(6, 0, self.tax_16.ids)],
                    }),
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 108.62,
                        'quantity': 1,
                        'tax_ids': [(6, 0, self.tax_16.ids)],
                    }),
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 362.07,
                        'quantity': 1,
                        'tax_ids': [(6, 0, self.tax_16.ids)],
                    })] + [
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 31.9,
                        'quantity': 1,
                        'tax_ids': [(6, 0, self.tax_16.ids)],
                    }),
                ] * 12,
            })
            invoice.action_post()

            generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_invoice_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Moneda">MXN</attribute>
                        <attribute name="Folio">2</attribute>
                        <attribute name="Descuento"/>
                        <attribute name="SubTotal">1251.77</attribute>
                        <attribute name="Total">1452.00</attribute>
                        <attribute name="TipoCambio" delete="true"/>
                    </xpath>
                    <xpath expr="//Concepto" position="replace">
                        <Concepto
                            Cantidad="1.000000"
                            ClaveProdServ="01010101"
                            Descripcion="product_mx"
                            ObjetoImp="02"
                            Importe="398.28"
                            ValorUnitario="398.28">
                            <Impuestos>
                                <Traslados>
                                    <Traslado
                                        Base="398.28"
                                        Importe="63.72"
                                        TasaOCuota="0.160000"
                                        TipoFactor="Tasa"/>
                                </Traslados>
                            </Impuestos>
                        </Concepto>
                        <Concepto
                            Cantidad="1.000000"
                            ClaveProdServ="01010101"
                            Descripcion="product_mx"
                            ObjetoImp="02"
                            Importe="108.62"
                            ValorUnitario="108.62">
                            <Impuestos>
                                <Traslados>
                                    <Traslado
                                        Base="108.62"
                                        Importe="17.38"
                                        TasaOCuota="0.160000"
                                        TipoFactor="Tasa"/>
                                </Traslados>
                            </Impuestos>
                        </Concepto>
                        <Concepto
                            Cantidad="1.000000"
                            ClaveProdServ="01010101"
                            Descripcion="product_mx"
                            ObjetoImp="02"
                            Importe="362.07"
                            ValorUnitario="362.07">
                            <Impuestos>
                                <Traslados>
                                    <Traslado
                                        Base="362.07"
                                        Importe="57.93"
                                        TasaOCuota="0.160000"
                                        TipoFactor="Tasa"/>
                                </Traslados>
                            </Impuestos>
                        </Concepto>
                        ''' + '''<Concepto
                            Cantidad="1.000000"
                            ClaveProdServ="01010101"
                            Descripcion="product_mx"
                            ObjetoImp="02"
                            Importe="31.90"
                            ValorUnitario="31.90">
                            <Impuestos>
                                <Traslados>
                                    <Traslado
                                        Base="31.90"
                                        Importe="5.10"
                                        TasaOCuota="0.160000"
                                        TipoFactor="Tasa"/>
                                </Traslados>
                            </Impuestos>
                        </Concepto>
                        ''' * 12 + '''
                    </xpath>
                    <xpath expr="/Comprobante/Impuestos" position="replace">
                        <Impuestos
                            TotalImpuestosTrasladados="200.23">
                            <Traslados>
                                <Traslado
                                    Base="1251.77"
                                    Importe="200.23"
                                    TasaOCuota="0.160000"
                                    TipoFactor="Tasa"/>
                            </Traslados>
                        </Impuestos>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cfdi_fixed_tax(self):
        with freeze_time(self.frozen_today):
            fixed_tax = self.env['account.tax'].create({
                'name': 'fixed_tax',
                'amount_type': 'fixed',
                'amount': 200,
                'type_tax_use': 'sale',
                'l10n_mx_tax_type': 'Cuota',
                'price_include': False,
                'include_base_amount': False,
            })

            self.invoice.write({
                'invoice_line_ids': [(1, self.invoice.invoice_line_ids.id, {'tax_ids': [(6, 0, fixed_tax.ids)]})],
            })
            self.invoice.action_post()

            generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_invoice_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                      <attribute name="Total">9000.000</attribute>
                    </xpath>
                    <xpath expr="//Concepto/Impuestos" position="replace">
                      <Impuestos>
                        <Traslados>
                          <Traslado
                            Base="8000.000"
                            Importe="1000.00"
                            TasaOCuota="0.125000"
                            TipoFactor="Cuota"/>
                        </Traslados>
                      </Impuestos>
                    </xpath>
                    <xpath expr="//Comprobante/Impuestos" position="replace">
                      <Impuestos TotalImpuestosTrasladados="1000.000">
                        <Traslados>
                          <Traslado
                            Base="8000.000"
                            Importe="1000.000"
                            TasaOCuota="0.125000"
                            TipoFactor="Cuota"/>
                        </Traslados>
                      </Impuestos>
                    </xpath>
                ''',
            )

            self.assertXmlTreeEqual(current_etree, expected_etree)

    # -------------------------------------------------------------------------
    # PAYMENTS
    # -------------------------------------------------------------------------

    def test_payment_cfdi(self):
        self.env['res.partner.bank'].create({
            'acc_number': "0123456789",
            'partner_id': self.partner_a.id,
            'acc_type': 'bank',
        })
        self.env['res.partner.bank'].create({
            'acc_number': "9876543210",
            'partner_id': self.partner_a.id,
            'acc_type': 'bank',
        })
        self.partner_a.l10n_mx_edi_no_tax_breakdown = True

        with freeze_time(self.frozen_today):
            self.payment.payment_id.action_l10n_mx_edi_force_generate_cfdi()
            self.invoice.action_post()
            self.payment.action_post()

            (self.invoice.line_ids + self.payment.line_ids)\
                .filtered(lambda line: line.account_internal_type == 'receivable')\
                .reconcile()

            # Fake the fact the invoice is signed.
            self._process_documents_web_services(self.invoice)
            self.invoice.l10n_mx_edi_cfdi_uuid = '123456789'

            generated_files = self._process_documents_web_services(self.payment.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Complemento/Pagos/Pago" position="attributes">
                        <attribute name="CtaOrdenante">0123456789</attribute>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_payment_cfdi_tax(self):
        self.env['res.partner.bank'].create({
            'acc_number': "0123456789",
            'partner_id': self.partner_a.id,
            'acc_type': 'bank',
        })
        self.env['res.partner.bank'].create({
            'acc_number': "9876543210",
            'partner_id': self.partner_a.id,
            'acc_type': 'bank',
        })

        with freeze_time(self.frozen_today):
            self.payment.payment_id.action_l10n_mx_edi_force_generate_cfdi()
            self.invoice.action_post()
            self.payment.action_post()

            (self.invoice.line_ids + self.payment.line_ids)\
                .filtered(lambda line: line.account_internal_type == 'receivable')\
                .reconcile()

            # Fake the fact the invoice is signed.
            self._process_documents_web_services(self.invoice)
            self.invoice.l10n_mx_edi_cfdi_uuid = '123456789'

            generated_files = self._process_documents_web_services(self.payment.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Complemento/Pagos/Pago" position="attributes">
                        <attribute name="CtaOrdenante">0123456789</attribute>
                    </xpath>
                    <xpath expr="//DoctoRelacionado" position="replace">
                        <DoctoRelacionado
                            IdDocumento="123456789"
                            Folio="1" Serie="INV/2017/01/"
                            MonedaDR="Gol"
                            EquivalenciaDR="1"
                            NumParcialidad="1"
                            ImpSaldoAnt="8480.000"
                            ImpPagado="8480.000"
                            ObjetoImpDR="02"
                            ImpSaldoInsoluto="0.000">
                            <ImpuestosDR>
                                <RetencionesDR>
                                    <RetencionDR
                                        BaseDR="8000.000"
                                        TipoFactorDR="Tasa"
                                        TasaOCuotaDR="0.100000"
                                        ImporteDR="800.000"/>
                                </RetencionesDR>
                                <TrasladosDR>
                                    <TrasladoDR
                                        BaseDR="8000.000"
                                        TipoFactorDR="Tasa"
                                        TasaOCuotaDR="0.160000"
                                        ImporteDR="1280.000"/>
                                </TrasladosDR>
                            </ImpuestosDR>
                        </DoctoRelacionado>
                        <ImpuestosP>
                            <RetencionesP>
                                <RetencionP
                                    ImporteP="800.000"/>
                            </RetencionesP>
                            <TrasladosP>
                                <TrasladoP
                                    BaseP="8000.000"
                                    TipoFactorP="Tasa"
                                    TasaOCuotaP="0.160000"
                                    ImporteP="1280.000"/>
                            </TrasladosP>
                        </ImpuestosP>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_payment_cfdi_another_currency_invoice(self):
        self.partner_a.l10n_mx_edi_no_tax_breakdown = True
        with freeze_time(self.frozen_today):
            invoice = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_usd_data['currency'].id,
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 1200.0})],
            })

            self.payment.action_l10n_mx_edi_force_generate_cfdi()
            invoice.action_post()
            self.payment.action_post()

            (invoice.line_ids + self.payment.line_ids)\
                .filtered(lambda line: line.account_internal_type == 'receivable')\
                .reconcile()

            # Fake the fact the invoice is signed.
            self._process_documents_web_services(invoice)
            invoice.l10n_mx_edi_cfdi_uuid = '123456789'

            generated_files = self._process_documents_web_services(self.payment.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos
                                Version="2.0">
                                <Totales
                                    MontoTotalPagos="4240.00"/>
                                <Pago
                                    FechaPago="2017-01-01T12:00:00"
                                    MonedaP="Gol"
                                    Monto="8480.000"
                                    FormaDePagoP="99"
                                    TipoCambioP="0.500000">
                                    <DoctoRelacionado
                                        Folio="2"
                                        IdDocumento="123456789"
                                        ImpPagado="1200.00"
                                        ImpSaldoAnt="1200.00"
                                        ImpSaldoInsoluto="0.00"
                                        MonedaDR="USD"
                                        EquivalenciaDR="2.0000000000"
                                        NumParcialidad="1"
                                        ObjetoImpDR="03"
                                        Serie="INV/2017/01/"/>
                                </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_payment_cfdi_multi_currency_invoice_positive_rate(self):
        ''' Test the following payment:
        - Invoice1 & invoice2 of 750 GOL / 250 MXN in 2016.
        - Payment of 750 MXN fully paying invoice1 & invoice2 with a write-off because 1500 GOL = 750 MXN in
        2017.
        '''
        self.partner_a.l10n_mx_edi_no_tax_breakdown = True
        with freeze_time(self.frozen_today):

            invoice1 = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.currency_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 750.0})],
            })
            invoice2 = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.currency_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 750.0})],
            })
            (invoice1 + invoice2).action_post()

            payment = self.env['account.payment.register']\
                .with_context(
                    active_model='account.move',
                    active_ids=(invoice1 + invoice2).ids,
                    default_l10n_mx_edi_force_generate_cfdi=True,
                )\
                .create({
                    'amount': 750.0,
                    'payment_date': '2017-01-01',
                    'currency_id': self.env.company.currency_id.id,
                    'group_payment': True,
                    'payment_difference_handling': 'reconcile',
                    'writeoff_account_id': self.company_data['default_account_revenue'].id,
                    'writeoff_label': 'writeoff',
                    'payment_method_id': self.env.ref('account.account_payment_method_manual_out').id,
                })\
                ._create_payments()

            receivable_lines = (payment.move_id + invoice1 + invoice2).line_ids\
                .filtered(lambda x: x.account_id.internal_type == 'receivable')
            self.assertRecordValues(receivable_lines, [{'reconciled': True}] * 3)

            self._process_documents_web_services(invoice1)
            invoice1.l10n_mx_edi_cfdi_uuid = '123456789'
            self._process_documents_web_services(invoice2)
            invoice2.l10n_mx_edi_cfdi_uuid = '987654321'

            generated_files = self._process_documents_web_services(payment.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">2</attribute>
                    </xpath>
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos
                                Version="2.0">
                                <Totales
                                    MontoTotalPagos="750.00"/>
                                <Pago
                                    FechaPago="2017-01-01T12:00:00"
                                    MonedaP="MXN"
                                    Monto="750.00"
                                    NumOperacion="INV/2016/12/0001 INV/2016/12/0002"
                                    FormaDePagoP="99"
                                    TipoCambioP="1">
                                    <DoctoRelacionado
                                        Folio="1"
                                        IdDocumento="123456789"
                                        ImpPagado="750.000"
                                        ImpSaldoAnt="750.000"
                                        ImpSaldoInsoluto="0.000"
                                        MonedaDR="Gol"
                                        EquivalenciaDR="2.0000000000"
                                        NumParcialidad="1"
                                        ObjetoImpDR="03"
                                        Serie="INV/2016/12/"/>
                                    <DoctoRelacionado
                                        Folio="2"
                                        IdDocumento="987654321"
                                        ImpPagado="750.000"
                                        ImpSaldoAnt="750.000"
                                        ImpSaldoInsoluto="0.000"
                                        MonedaDR="Gol"
                                        EquivalenciaDR="2.0000000000"
                                        NumParcialidad="1"
                                        ObjetoImpDR="03"
                                        Serie="INV/2016/12/"/>
                                </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_payment_cfdi_multi_currency_invoice_negative_rate(self):
        ''' Test the following payment:
        - Invoice1 & invoice2 of 750 GOL / 375 MXN in 2017.
        - Payment of 500 MXN paying not completely invoice1 & invoice2 because 1500 GOL = 500 MXN in 2017.
        '''
        self.partner_a.l10n_mx_edi_no_tax_breakdown = True
        with freeze_time(self.frozen_today):

            invoice1 = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.currency_data['currency'].id,
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 750.0})],
            })
            invoice2 = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.currency_data['currency'].id,
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 750.0})],
            })
            (invoice1 + invoice2).action_post()

            payment = self.env['account.payment.register']\
                .with_context(
                    active_model='account.move',
                    active_ids=(invoice1 + invoice2).ids,
                    default_l10n_mx_edi_force_generate_cfdi=True,
                )\
                .create({
                    'amount': 500.0,
                    'payment_date': '2016-12-31',
                    'currency_id': self.env.company.currency_id.id,
                    'group_payment': True,
                    'payment_difference_handling': 'reconcile',
                    'writeoff_account_id': self.company_data['default_account_revenue'].id,
                    'writeoff_label': 'writeoff',
                    'payment_method_id': self.env.ref('account.account_payment_method_manual_out').id,
                })\
                ._create_payments()

            receivable_lines = (payment.move_id + invoice1 + invoice2).line_ids\
                .filtered(lambda x: x.account_id.internal_type == 'receivable')
            self.assertRecordValues(receivable_lines, [
                {'reconciled': True},
                {'reconciled': True},
                {'reconciled': True},
            ])

            self._process_documents_web_services(invoice1)
            invoice1.l10n_mx_edi_cfdi_uuid = '123456789'
            self._process_documents_web_services(invoice2)
            invoice2.l10n_mx_edi_cfdi_uuid = '987654321'

            generated_files = self._process_documents_web_services(payment.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">1</attribute>
                        <attribute name="Serie">BNK1/2016/12/</attribute>
                    </xpath>
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos
                                Version="2.0">
                                <Totales
                                    MontoTotalPagos="500.00"/>
                                <Pago
                                    FechaPago="2016-12-31T12:00:00"
                                    MonedaP="MXN"
                                    Monto="500.00"
                                    NumOperacion="INV/2017/01/0002 INV/2017/01/0003"
                                    FormaDePagoP="99"
                                    TipoCambioP="1">
                                    <DoctoRelacionado
                                        Folio="2"
                                        IdDocumento="123456789"
                                        ImpPagado="750.000"
                                        ImpSaldoAnt="750.000"
                                        ImpSaldoInsoluto="0.000"
                                        MonedaDR="Gol"
                                        EquivalenciaDR="3.0000000000"
                                        NumParcialidad="1"
                                        ObjetoImpDR="03"
                                        Serie="INV/2017/01/"/>
                                    <DoctoRelacionado
                                        Folio="3"
                                        IdDocumento="987654321"
                                        ImpPagado="750.000"
                                        ImpSaldoAnt="750.000"
                                        ImpSaldoInsoluto="0.000"
                                        MonedaDR="Gol"
                                        EquivalenciaDR="3.0000000000"
                                        NumParcialidad="1"
                                        ObjetoImpDR="03"
                                        Serie="INV/2017/01/"/>
                                </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_payment_cfdi_multi_currency_invoice_partial_payment(self):
        ''' Test the following partial payment:
        - Invoice of 750 GOL / 250 MXN in 2016.
        - Payment of 100 MXN partially paying invoice without write-off in 2017.
        '''
        self.partner_a.l10n_mx_edi_no_tax_breakdown = True
        with freeze_time(self.frozen_today):

            invoice = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.currency_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 750.0})],
            })
            invoice.action_post()

            payment = self.env['account.payment.register']\
                .with_context(
                    active_model='account.move',
                    active_ids=invoice.ids,
                    default_l10n_mx_edi_force_generate_cfdi=True,
                )\
                .create({
                    'amount': 100.0,
                    'payment_date': '2017-01-01',
                    'currency_id': invoice.company_currency_id.id,
                    'payment_difference_handling': 'open',
                })\
                ._create_payments()

            receivable_lines = (payment.move_id + invoice).line_ids\
                .filtered(lambda x: x.account_id.internal_type == 'receivable')
            self.assertEqual(len(receivable_lines.filtered(lambda r: r.reconciled)), 1)
            self.assertEqual(len(receivable_lines.filtered(lambda r: not r.reconciled)), 1)

            self._process_documents_web_services(invoice)
            invoice.l10n_mx_edi_cfdi_uuid = '123456789'

            generated_files = self._process_documents_web_services(payment.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">2</attribute>
                    </xpath>
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos
                                Version="2.0">
                                <Totales
                                    MontoTotalPagos="100.00"/>
                                <Pago
                                    FechaPago="2017-01-01T12:00:00"
                                    MonedaP="MXN"
                                    Monto="100.00"
                                    NumOperacion="INV/2016/12/0001"
                                    FormaDePagoP="99"
                                    TipoCambioP="1">
                                    <DoctoRelacionado
                                        Folio="1"
                                        IdDocumento="123456789"
                                        ImpPagado="300.000"
                                        ImpSaldoAnt="750.000"
                                        ImpSaldoInsoluto="450.000"
                                        MonedaDR="Gol"
                                        EquivalenciaDR="3.0000000000"
                                        NumParcialidad="1"
                                        ObjetoImpDR="03"
                                        Serie="INV/2016/12/"/>
                                </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_payment_cfdi_rate(self):
        self.partner_a.l10n_mx_edi_no_tax_breakdown = True
        with freeze_time(self.frozen_today):
            self.fake_usd_data['rates'][0].rate = 0.050498164392
            self.fake_usd_data['rates'][1].rate = 0.050465035300

            invoice1 = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_usd_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 81.20})],
            })
            invoice2 = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_usd_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 81.20})],
            })
            (invoice1 + invoice2).action_post()

            payment = self.env['account.payment.register']\
                .with_context(
                    active_model='account.move',
                    active_ids=(invoice1 + invoice2).ids,
                    default_l10n_mx_edi_force_generate_cfdi=True,
                )\
                .create({
                    'amount': 3215.96,
                    'payment_date': '2017-01-01',
                    'currency_id': self.env.company.currency_id.id,
                    'group_payment': True,
                    'payment_method_id': self.env.ref('account.account_payment_method_manual_out').id,
                })\
                ._create_payments()

            receivable_lines = (payment.move_id + invoice1 + invoice2).line_ids\
                .filtered(lambda x: x.account_id.internal_type == 'receivable')
            self.assertRecordValues(receivable_lines, [
                {'reconciled': True},
                {'reconciled': True},
                {'reconciled': True},
            ])

            self._process_documents_web_services(invoice1)
            invoice1.l10n_mx_edi_cfdi_uuid = '123456789'
            self._process_documents_web_services(invoice2)
            invoice2.l10n_mx_edi_cfdi_uuid = '987654321'

            generated_files = self._process_documents_web_services(payment.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">2</attribute>
                        <attribute name="Serie">BNK1/2017/01/</attribute>
                    </xpath>
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos
                                Version="2.0">
                                <Totales
                                    MontoTotalPagos="3215.96"/>
                                <Pago
                                    FechaPago="2017-01-01T12:00:00"
                                    MonedaP="MXN"
                                    Monto="3215.96"
                                    NumOperacion="INV/2016/12/0001 INV/2016/12/0002"
                                    FormaDePagoP="99"
                                    TipoCambioP="1">
                                    <DoctoRelacionado
                                        Folio="1"
                                        IdDocumento="123456789"
                                        ImpPagado="81.20"
                                        ImpSaldoAnt="81.20"
                                        ImpSaldoInsoluto="0.00"
                                        MonedaDR="USD"
                                        EquivalenciaDR="0.0504981406"
                                        NumParcialidad="1"
                                        ObjetoImpDR="03"
                                        Serie="INV/2016/12/"/>
                                    <DoctoRelacionado
                                        Folio="2"
                                        IdDocumento="987654321"
                                        ImpPagado="81.20"
                                        ImpSaldoAnt="81.20"
                                        ImpSaldoInsoluto="0.00"
                                        MonedaDR="USD"
                                        EquivalenciaDR="0.0504981406"
                                        NumParcialidad="1"
                                        ObjetoImpDR="03"
                                        Serie="INV/2016/12/"/>
                                </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    # -------------------------------------------------------------------------
    # STATEMENT LINES
    # -------------------------------------------------------------------------

    def test_statement_line_cfdi(self):
        self.partner_a.l10n_mx_edi_no_tax_breakdown = True
        with freeze_time(self.frozen_today):
            self.statement_line.action_l10n_mx_edi_force_generate_cfdi()
            self.invoice.action_post()
            self.statement.button_post()

            receivable_line = self.invoice.line_ids.filtered(lambda line: line.account_internal_type == 'receivable')
            self.statement_line.reconcile([{'id': receivable_line.id}])

            # Fake the fact the invoice is signed.
            self._process_documents_web_services(self.invoice)
            self.invoice.l10n_mx_edi_cfdi_uuid = '123456789'

            generated_files = self._process_documents_web_services(self.statement_line.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">2</attribute>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)
