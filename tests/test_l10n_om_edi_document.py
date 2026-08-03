# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# NOTE: these tests exercise the l10n.om.edi.document state machine against a mock connector -
# they do not and cannot validate a real ASP integration, since no ASP connector shipped in this
# module is backed by a real, confirmed API at the time of writing (see lib/connectors/*.py).
from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_om_edi.lib.connectors.base import L10nOmEdiConnector
from odoo.exceptions import UserError
from odoo.tests import tagged


class MockConnector(L10nOmEdiConnector):
    display_name = "Mock ASP"

    def submit_invoice(self, invoice_xml, tdd_xml, document):
        return 'MOCK-REF-001'

    def get_status(self, asp_reference):
        return 'accepted'

    def cancel(self, asp_reference, reason):
        return True


class FailingMockConnector(L10nOmEdiConnector):
    display_name = "Failing Mock ASP"

    def submit_invoice(self, invoice_xml, tdd_xml, document):
        raise UserError("Simulated ASP failure")


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nOmEdiDocument(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('om')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].write({
            'vat': 'OM1234567890',
            'l10n_om_cr_number': '1234567',
            'l10n_om_edi_asp_provider': 'cleartax',
        })
        cls.partner_a.write({
            'vat': 'OM1234567891',
            'country_id': cls.env.ref('base.om').id,
            'peppol_eas': '0248',
            'peppol_endpoint': 'OM1234567891',
        })

    def test_required_config_follows_selected_provider(self):
        company = self.company_data['company']
        # setUpClass configures 'cleartax', whose REQUIRED_CONFIG is a single API key (per their
        # published KSA e-invoicing docs), not a client_id/client_secret pair.
        self.assertEqual(company.l10n_om_edi_asp_required_config, ['api_key'])
        self.assertEqual(company.l10n_om_edi_asp_config_status, 'partial')

        company.l10n_om_edi_asp_provider = 'jsr'
        # Odoo's Json field normalizes an empty list to False on read-back (see
        # odoo/orm/fields_misc.py Json.convert_to_cache: `if not value: return None`), so an "empty"
        # REQUIRED_CONFIG reads as False here, not []. The Settings view's `invisible` expressions are
        # written to handle that (`not required_config or 'x' not in required_config`).
        self.assertFalse(company.l10n_om_edi_asp_required_config)
        self.assertEqual(company.l10n_om_edi_asp_config_status, 'unconfirmed')

        company.l10n_om_edi_asp_provider = False
        self.assertFalse(company.l10n_om_edi_asp_required_config)
        self.assertFalse(company.l10n_om_edi_asp_config_status)

    def test_ota_accredited_flag_matches_official_list(self):
        """ Verified 2026-07-30 against https://fawtara.taxoman.gov.om/accredited-service-providers
        ("Showing 1 - 12 of 12" - the complete list, no pagination beyond that). Every provider
        currently shipped in this module is one of those 12, so all should report as accredited -
        this test exists to catch a future connector being added without checking that list first
        (the exact mistake that happened with this module's first version). """
        company = self.company_data['company']

        for provider in ('cleartax', 'jsr', 'flick', 'smarteis', 'convergex', 'bdo', 'cygnet',
                         'fynamics', 'webtel', 'faturathi', 'marminai', 'goroute'):
            company.l10n_om_edi_asp_provider = provider
            self.assertTrue(company.l10n_om_edi_asp_ota_accredited, f"{provider} should be OTA-accredited")

    def test_submit_without_asp_provider_raises(self):
        self.company_data['company'].l10n_om_edi_asp_provider = False
        invoice = self.init_invoice('out_invoice', products=self.product_a, partner=self.partner_a,
                                     taxes=self.company_data['default_tax_sale'])
        invoice.action_post()

        with self.assertRaises(UserError):
            self.company_data['company']._l10n_om_edi_get_connector()

    def test_submit_success_transitions_to_in_progress(self):
        invoice = self.init_invoice('out_invoice', products=self.product_a, partner=self.partner_a,
                                     taxes=self.company_data['default_tax_sale'])
        invoice.action_post()

        with patch(
            'odoo.addons.l10n_om_edi.models.res_company.get_connector_class',
            return_value=MockConnector,
        ):
            invoice.action_l10n_om_edi_submit()

        document = invoice.l10n_om_edi_document_ids
        self.assertEqual(len(document), 1)
        self.assertEqual(document.l10n_om_edi_state, 'in_progress')
        self.assertEqual(document.asp_reference, 'MOCK-REF-001')
        self.assertTrue(document.invoice_xml)
        self.assertTrue(document.tdd_xml)
        self.assertTrue(document.l10n_om_edi_uuid)

    def test_submit_failure_transitions_to_error(self):
        invoice = self.init_invoice('out_invoice', products=self.product_a, partner=self.partner_a,
                                     taxes=self.company_data['default_tax_sale'])
        invoice.action_post()

        with patch(
            'odoo.addons.l10n_om_edi.models.res_company.get_connector_class',
            return_value=FailingMockConnector,
        ):
            invoice.action_l10n_om_edi_submit()

        document = invoice.l10n_om_edi_document_ids
        self.assertEqual(document.l10n_om_edi_state, 'error')
        self.assertIn('Simulated ASP failure', document.error_message)

    def test_cron_poll_updates_state(self):
        invoice = self.init_invoice('out_invoice', products=self.product_a, partner=self.partner_a,
                                     taxes=self.company_data['default_tax_sale'])
        invoice.action_post()

        with patch(
            'odoo.addons.l10n_om_edi.models.res_company.get_connector_class',
            return_value=MockConnector,
        ):
            invoice.action_l10n_om_edi_submit()
            self.env['l10n.om.edi.document']._cron_poll_submission_status()

        document = invoice.l10n_om_edi_document_ids
        self.assertEqual(document.l10n_om_edi_state, 'accepted')
