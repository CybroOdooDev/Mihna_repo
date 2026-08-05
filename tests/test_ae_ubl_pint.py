# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# NOTE: these tests validate that the generated XML is *stable* and *structurally sane* (correct
# CustomizationID/ProfileID, TIN-based EndpointID, round-trips on import, etc). They do not - and
# cannot yet - validate regulatory correctness against an official PINT-AE schematron/test suite,
# which was not publicly available at the time this module was written.
from datetime import datetime

from freezegun import freeze_time

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestAeUblPint(AccountTestInvoicingCommon):
    """ Tests the PINT AE XML builder (account.edi.xml.pint_ae): generated structure, scenario-flag
    encoding, export constraints, and round-trip import. """

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ae')
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].partner_id.write({
            'vat': 'AE123456789012345',
            'l10n_ae_tin': '1234567890',
            'l10n_ae_legal_registration_type': 'TL',
            'l10n_ae_legal_registration_number': '1122334455',
            'street': 'Sheikh Zayed Road',
            'city': 'Dubai',
            'phone': '+97141234500',
            'peppol_eas': '0235',
        })
        cls.partner_a.write({
            'vat': 'AE123456789012346',
            'l10n_ae_tin': '2233445566',
            'country_id': cls.env.ref('base.ae').id,
            'street': 'Sheikh Zayed Road',
            'city': 'Dubai',
            'phone': '+97141234501',
            'peppol_eas': '0235',
        })

        cls.fakenow = datetime(2026, 8, 1, 10, 0, 0)
        cls.startClassPatcher(freeze_time(cls.fakenow))

    def test_invoice_domestic_b2b(self):
        """ A plain domestic B2B invoice generates a PINT AE XML with the correct CustomizationID/
        ProfileID and a TIN-based (not VAT-based) supplier EndpointID. """
        invoice = self.init_invoice('out_invoice', products=self.product_a, taxes=self.company_data['default_tax_sale'])
        invoice.action_post()

        actual_xml, errors = self.env['account.edi.xml.pint_ae']._export_invoice(invoice)
        self.assertFalse(errors)

        tree = self.get_xml_tree_from_string(actual_xml)
        self.assertEqual(tree.findtext('{*}CustomizationID'), 'urn:peppol:pint:billing-1@ae-1')
        self.assertEqual(tree.findtext('{*}ProfileID'), 'urn:peppol:bis:billing')

        # Seller electronic address must be the TIN (not the full 15-digit VAT/TRN).
        endpoint_ids = tree.findall('.//{*}AccountingSupplierParty//{*}EndpointID')
        self.assertTrue(endpoint_ids)
        self.assertEqual(endpoint_ids[0].text, '1234567890')
        self.assertEqual(endpoint_ids[0].get('schemeID'), '0235')

        # The Invoice transaction type code bitstring is embedded in the Note pending an official
        # PINT-AE schema location for it (see account_edi_xml_pint_ae.py).
        self.assertIn('AE-TRANSACTION-TYPE-CODE:00000000', tree.findtext('{*}Note') or '')

    def test_credit_note_domestic_b2b(self):
        """ A credit note exports as a UBL CreditNote document with the correct type code. """
        invoice = self.init_invoice('out_refund', products=self.product_a, taxes=self.company_data['default_tax_sale'])
        invoice.action_post()

        actual_xml, errors = self.env['account.edi.xml.pint_ae']._export_invoice(invoice)
        self.assertFalse(errors)

        tree = self.get_xml_tree_from_string(actual_xml)
        self.assertEqual(tree.tag, '{urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2}CreditNote')
        self.assertEqual(tree.findtext('{*}CreditNoteTypeCode'), '381')

    def test_transaction_type_code_reflects_scenario_flags(self):
        """ Ticking scenario flags sets the matching bits of the transaction type code. """
        invoice = self.init_invoice('out_invoice', products=self.product_a, taxes=self.company_data['default_tax_sale'])
        invoice.l10n_ae_flag_free_zone = True
        invoice.l10n_ae_flag_summary_invoice = True
        self.assertEqual(invoice.l10n_ae_transaction_type_code, '10010000')

    def test_export_flag_auto_detected_from_buyer_country(self):
        """ The Export flag is computed automatically when the buyer is outside the UAE. """
        foreign_partner = self.partner_a.copy({'country_id': self.env.ref('base.fr').id, 'vat': False, 'l10n_ae_tin': False})
        invoice = self.init_invoice('out_invoice', partner=foreign_partner, products=self.product_a)
        self.assertTrue(invoice.l10n_ae_flag_export)

    def test_missing_tin_raises_constraint(self):
        """ XML generation reports an export constraint (rather than a hard crash) when the
        supplier's TIN is missing. """
        invoice = self.init_invoice('out_invoice', products=self.product_a, taxes=self.company_data['default_tax_sale'])
        invoice.action_post()
        self.company_data['company'].l10n_ae_tin = False

        _actual_xml, errors = self.env['account.edi.xml.pint_ae']._export_invoice(invoice)
        self.assertTrue(any('Tax Identification Number' in error for error in errors))

    def test_invoice_import(self):
        """ A previously exported PINT AE XML can be recognized and re-imported as an invoice. """
        invoice = self.init_invoice('out_invoice', products=self.product_a, taxes=self.company_data['default_tax_sale'])
        invoice.action_post()
        xml_content, errors = self.env['account.edi.xml.pint_ae']._export_invoice(invoice)
        self.assertFalse(errors)

        xml_attachment = self.env['ir.attachment'].create({
            'mimetype': 'application/xml',
            'name': 'test_invoice.xml',
            'raw': xml_content,
        })
        imported_invoice = self.env['account.move'] \
            .with_context(default_move_type='out_invoice') \
            ._create_records_from_attachments(xml_attachment)

        self.assertEqual(imported_invoice.move_type, 'out_invoice')
        self.assertEqual(imported_invoice.partner_id, self.partner_a)

    def test_check_l10n_ae_tin_format(self):
        """ The TIN must be exactly 10 digits - too short, too long, and non-digit values all raise. """
        partner = self.partner_a
        partner.l10n_ae_tin = '1234567890'  # 10 digits: ok
        with self.assertRaises(ValidationError):
            partner.l10n_ae_tin = '123456789'  # 9 digits: too short
        with self.assertRaises(ValidationError):
            partner.l10n_ae_tin = '12345678901'  # 11 digits: too long
        with self.assertRaises(ValidationError):
            partner.l10n_ae_tin = '123456789A'  # non-digit
