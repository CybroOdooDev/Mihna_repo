# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# NOTE: these tests mock the HTTP layer - they verify our request-building/response-parsing logic is
# correct against Flick Network's *documented* auth/status endpoints and JSON submission schema, not
# that their real servers behave exactly as documented. See lib/connectors/flick.py for exactly what
# is and isn't confirmed.
from unittest.mock import MagicMock, patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_om_edi.lib.connectors.flick import FlickNetworkConnector
from odoo.exceptions import UserError
from odoo.tests import tagged


def _fake_response(status_code=200, json_data=None, reason="OK", text=""):
    response = MagicMock()
    response.status_code = status_code
    response.reason = reason
    response.text = text or ""
    response.json.return_value = json_data or {}
    return response


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestFlickNetworkConnector(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('om')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].partner_id.write({
            'vat': 'OM1234567890',
            'l10n_om_cr_number': '1234567',
            'street': 'Way 2601, Building 15',
            'city': 'Muscat',
            'peppol_eas': '0248',
            'peppol_endpoint': 'OM1234567890',
        })
        cls.partner_a.write({
            'vat': 'OM1234567891',
            'country_id': cls.env.ref('base.om').id,
            'street': 'Way 3105, Building 8',
            'city': 'Muscat',
            'peppol_eas': '0248',
            'peppol_endpoint': 'OM1234567891',
        })
        cls.connector = FlickNetworkConnector(
            base_url='https://sb-om-api.flick.network',
            api_key='fake-flick-api-key',
            account_id='fake-participant-id',
            environment='test',
        )

    def _create_document(self):
        invoice = self.init_invoice(
            'out_invoice', products=self.product_a, partner=self.partner_a,
            taxes=self.company_data['default_tax_sale'],
        )
        invoice.action_post()
        return self.env['l10n.om.edi.document'].create({
            'move_id': invoice.id,
            'company_id': invoice.company_id.id,
        })

    def test_test_connection_uses_api_key_header(self):
        with patch.object(self.connector._session, 'request', return_value=_fake_response(
            json_data={'valid': True},
        )) as mock_request:
            result = self.connector.test_connection('OM')

        self.assertEqual(result, {'valid': True})
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertEqual(args[1], 'https://sb-om-api.flick.network/v1/auth/verify')
        self.assertEqual(kwargs['headers']['X-Flick-Auth-Key'], 'fake-flick-api-key')

    def test_test_connection_missing_api_key_raises(self):
        connector = FlickNetworkConnector(base_url='https://sb-om-api.flick.network')
        with self.assertRaises(UserError):
            connector.test_connection('OM')

    def test_authentication_failure_raises_clear_error(self):
        with patch.object(self.connector._session, 'request', return_value=_fake_response(
            status_code=401, text='{"error": "invalid or expired key"}',
        )):
            with self.assertRaises(UserError):
                self.connector.test_connection('OM')

    def test_build_flick_payload_maps_invoice_correctly(self):
        document = self._create_document()
        payload = self.connector._build_flick_payload(document)

        self.assertEqual(payload['uuid'], document.l10n_om_edi_uuid)
        self.assertEqual(payload['document_identifier'], document.move_id.name)
        self.assertEqual(payload['document_type'], '380')
        self.assertEqual(payload['document_currency'], document.move_id.currency_id.name)
        # Combined "scheme:value" string, matching Flick's documented JSON convention rather than the
        # standard Peppol/UBL schemeID-as-attribute approach their XML validator didn't seem to expect.
        # Key is "issuing_party", not "sending_party" as their written docs call it - confirmed by
        # every live validation error referencing the seller side as "issuing_party".
        self.assertEqual(payload['issuing_party']['peppol_id'], '0248:OM1234567890')
        self.assertEqual(payload['receiving_party']['peppol_id'], '0248:OM1234567891')
        self.assertEqual(payload['issuing_party']['vat_number'], 'OM1234567890')
        self.assertEqual(payload['receiving_party']['vat_number'], 'OM1234567891')
        self.assertEqual(len(payload['invoice_lines']), 1)
        self.assertEqual(payload['invoice_lines'][0]['item_type'], 'GS')
        self.assertEqual(payload['invoice_totals']['payable_amount'], "%.2f" % document.move_id.amount_total)

    def test_build_flick_payload_credit_note_uses_type_381(self):
        document = self._create_document()
        document.move_id.move_type = 'out_refund'  # not a realistic write path, only to check mapping
        payload = self.connector._build_flick_payload(document)
        self.assertEqual(payload['document_type'], '381')

    def test_submit_invoice_success_returns_document_id(self):
        document = self._create_document()
        with patch.object(self.connector._session, 'request', return_value=_fake_response(
            json_data={'status': 'success', 'data': {
                'document_id': '019534a1-b7be-7212-8c77-685b3edf267f',
                'status': 'processing', 'exchange_status': 'pending', 'reporting_status': 'pending',
            }},
        )) as mock_request:
            reference = self.connector.submit_invoice(b'<Invoice/>', b'<TaxDataDocument/>', document)

        self.assertEqual(reference, '019534a1-b7be-7212-8c77-685b3edf267f')
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'POST')
        self.assertEqual(args[1], 'https://sb-om-api.flick.network/v1/fake-participant-id/documents')
        # Payload must be wrapped in a top-level "document" key - confirmed only via a live rejection
        # ("`document` field is required"), not documented anywhere on Flick's side.
        self.assertEqual(kwargs['json']['document']['document_identifier'], document.move_id.name)
        self.assertEqual(len(kwargs['json']['document']['invoice_lines']), 1)
        self.assertEqual(kwargs['headers']['X-Flick-Auth-Key'], 'fake-flick-api-key')
        self.assertIsNone(kwargs['data'])

    def test_submit_invoice_validation_failure_surfaces_field_errors(self):
        document = self._create_document()
        with patch.object(self.connector._session, 'request', return_value=_fake_response(
            json_data={'status': 'failed', 'data': {'errors': [{
                'field_name': 'receiving_party.legal_name',
                'rule_code': 'ibr-001',
                'error_message': "An Invoice MUST have a Buyer name (IBT-044).",
                'error_level': 'fatal',
            }]}},
        )):
            with self.assertRaises(UserError) as cm:
                self.connector.submit_invoice(b'<Invoice/>', b'<TaxDataDocument/>', document)
        self.assertIn('receiving_party.legal_name', str(cm.exception))
        self.assertIn('Buyer name', str(cm.exception))

    def test_submit_invoice_errors_with_unknown_keys_show_raw_json(self):
        # The live sandbox returned an error list whose entries don't use the documented
        # 'field_name'/'error_message' keys at all - this must still surface the raw error content
        # rather than collapsing into "Unknown error" for every entry.
        document = self._create_document()
        with patch.object(self.connector._session, 'request', return_value=_fake_response(
            json_data={'status': 'failed', 'data': {'errors': [
                {'code': 'ERR_042', 'detail': "Something specific about a mismatched line total"},
            ]}},
        )):
            with self.assertRaises(UserError) as cm:
                self.connector.submit_invoice(b'<Invoice/>', b'<TaxDataDocument/>', document)
        self.assertIn('ERR_042', str(cm.exception))
        self.assertIn('mismatched line total', str(cm.exception))
        self.assertNotIn('Unknown error', str(cm.exception))

    def test_submit_invoice_failure_without_structured_errors_shows_raw_body(self):
        document = self._create_document()
        with patch.object(self.connector._session, 'request', return_value=_fake_response(
            status_code=400, json_data={'status': 'failed', 'message': "Invalid participant_id"},
        )):
            with self.assertRaises(UserError) as cm:
                self.connector.submit_invoice(b'<Invoice/>', b'<TaxDataDocument/>', document)
        self.assertIn('Invalid participant_id', str(cm.exception))

    def test_submit_invoice_auth_failure_raises_clear_error(self):
        document = self._create_document()
        with patch.object(self.connector._session, 'request', return_value=_fake_response(
            status_code=401, text='{"error": "invalid or expired key"}',
        )):
            with self.assertRaises(UserError):
                self.connector.submit_invoice(b'<Invoice/>', b'<TaxDataDocument/>', document)

    def test_submit_without_participant_id_raises_specific_error(self):
        document = self._create_document()
        connector = FlickNetworkConnector(
            base_url='https://sb-om-api.flick.network', api_key='fake-flick-api-key',
        )
        with self.assertRaises(UserError) as cm:
            connector.submit_invoice(b'<xml/>', b'<xml/>', document)
        self.assertIn('participant_id', str(cm.exception))

    def test_get_status_maps_flick_status_values(self):
        for flick_status, expected_state in (
            ('processing', 'in_progress'), ('completed', 'accepted'), ('failed', 'rejected'),
        ):
            with patch.object(self.connector._session, 'request', return_value=_fake_response(
                json_data={'status': 'success', 'data': {'status': flick_status}},
            )):
                self.assertEqual(self.connector.get_status('some-document-id'), expected_state)

    def test_cancel_not_yet_implemented(self):
        # No cancel/void endpoint is documented for Flick Network - see class docstring.
        with self.assertRaises(UserError):
            self.connector.cancel('some-reference', 'test reason')
