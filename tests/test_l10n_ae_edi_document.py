# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# NOTE: these tests exercise the l10n.ae.edi.document state machine against a mock connector - they
# do not and cannot validate a real ASP integration, since no connector shipped in this module is
# backed by a real API (see lib/connectors/reference.py, which is documentation-only by design).
from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_ae_edi.lib.connectors.base import L10nAeEdiConnector
from odoo.exceptions import UserError
from odoo.tests import tagged


class MockConnector(L10nAeEdiConnector):
    """ Fake ASP connector that always accepts a submission, standing in for a real ASP in tests. """
    display_name = "Mock ASP"

    def submit_invoice(self, invoice_xml):
        """ Pretend to submit and return a fixed ASP reference. """
        return 'MOCK-REF-001'

    def get_status(self, asp_reference):
        """ Pretend the submission was acknowledged. """
        return 'accepted'


class FailingMockConnector(L10nAeEdiConnector):
    """ Fake ASP connector that always fails, to exercise the error/retry-count path. """
    display_name = "Failing Mock ASP"

    def submit_invoice(self, invoice_xml):
        """ Simulate an ASP-side submission failure. """
        raise UserError("Simulated ASP failure")


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nAeEdiDocument(AccountTestInvoicingCommon):
    """ Tests the l10n.ae.edi.document submission state machine (submit/retry/status-poll) against
    the shipped reference connector and mock connectors standing in for a real ASP. """

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ae')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].write({
            'vat': 'AE123456789012345',
            'l10n_ae_tin': '1234567890',
            'l10n_ae_legal_registration_type': 'TL',
            'l10n_ae_legal_registration_number': '1122334455',
            'l10n_ae_edi_asp_provider': 'reference',
        })
        cls.partner_a.write({
            'vat': 'AE123456789012346',
            'l10n_ae_tin': '2233445566',
            'country_id': cls.env.ref('base.ae').id,
            'peppol_eas': '0235',
        })

    def test_required_config_follows_selected_provider(self):
        """ The company's config-metadata fields mirror the selected connector class's own
        REQUIRED_CONFIG/CONFIG_STATUS/MOF_ACCREDITED attributes. """
        company = self.company_data['company']
        self.assertEqual(company.l10n_ae_edi_asp_required_config, ['api_key'])
        self.assertEqual(company.l10n_ae_edi_asp_config_status, 'unconfirmed')
        self.assertFalse(company.l10n_ae_edi_asp_mof_accredited)

    def test_reference_connector_refuses_to_submit(self):
        """ The shipped reference connector is documentation-only: it must never make a live call, and
        must say so clearly rather than silently succeed. """
        invoice = self.init_invoice('out_invoice', products=self.product_a, taxes=self.company_data['default_tax_sale'])
        invoice.action_post()
        invoice.action_l10n_ae_edi_submit()

        document = invoice.l10n_ae_edi_document_ids
        self.assertEqual(document.l10n_ae_edi_state, 'error')
        self.assertIn("documentation-only template", document.error_message)

    def test_submission_success_with_mock_connector(self):
        """ A successful submit moves the document to 'in_progress' with the ASP reference and XML
        stored, and a later status poll advances it to 'accepted'. """
        invoice = self.init_invoice('out_invoice', products=self.product_a, taxes=self.company_data['default_tax_sale'])
        invoice.action_post()

        with patch(
            'odoo.addons.l10n_ae_edi.models.res_company_edi.get_connector_class',
            return_value=MockConnector,
        ):
            invoice.action_l10n_ae_edi_submit()

        document = invoice.l10n_ae_edi_document_ids
        self.assertEqual(document.l10n_ae_edi_state, 'in_progress')
        self.assertEqual(document.asp_reference, 'MOCK-REF-001')
        self.assertTrue(document.invoice_xml)

        with patch(
            'odoo.addons.l10n_ae_edi.models.res_company_edi.get_connector_class',
            return_value=MockConnector,
        ):
            self.env['l10n.ae.edi.document']._cron_poll_submission_status()
        self.assertEqual(document.l10n_ae_edi_state, 'accepted')

    def test_submission_failure_records_error_and_retry_count(self):
        """ A failed submit leaves the document in 'error' with the failure message and an
        incremented retry count. """
        invoice = self.init_invoice('out_invoice', products=self.product_a, taxes=self.company_data['default_tax_sale'])
        invoice.action_post()

        with patch(
            'odoo.addons.l10n_ae_edi.models.res_company_edi.get_connector_class',
            return_value=FailingMockConnector,
        ):
            invoice.action_l10n_ae_edi_submit()

        document = invoice.l10n_ae_edi_document_ids
        self.assertEqual(document.l10n_ae_edi_state, 'error')
        self.assertEqual(document.error_message, "Simulated ASP failure")
        self.assertEqual(document.retry_count, 1)

    def test_direction_defaults_to_outbound(self):
        """ A newly created document defaults to 'outbound' - this module only implements Corner 1. """
        invoice = self.init_invoice('out_invoice', products=self.product_a, taxes=self.company_data['default_tax_sale'])
        invoice.action_post()
        document = invoice._l10n_ae_edi_get_or_create_document()
        self.assertEqual(document.direction, 'outbound')
