# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# NOTE: these tests mock the HTTP layer - they verify our request-building/response-parsing logic is
# correct against Sovos's *documented* auth/status endpoints, not that Sovos's real servers behave
# exactly as documented. See lib/connectors/sovos.py for exactly what is and isn't confirmed.
from unittest.mock import MagicMock, patch

from odoo.addons.l10n_om_edi.lib.connectors.sovos import SovosConnector
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


def _fake_response(status_code=200, json_data=None, reason="OK", text=""):
    response = MagicMock()
    response.status_code = status_code
    response.reason = reason
    response.text = text or ""
    response.json.return_value = json_data or {}
    return response


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSovosConnector(TransactionCase):

    def setUp(self):
        super().setUp()
        self.connector = SovosConnector(
            base_url='https://api-test.sovos.com',
            client_id='fake-api-key',
            client_secret='fake-secret',
            environment='test',
        )

    def test_get_access_token_builds_correct_request(self):
        with patch.object(self.connector._session, 'request', return_value=_fake_response(
            json_data={'access_token': 'fake-token-123'},
        )) as mock_request:
            token = self.connector._get_access_token()

        self.assertEqual(token, 'fake-token-123')
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'POST')
        self.assertEqual(args[1], 'https://api-test.sovos.com/oauth/token')
        self.assertEqual(kwargs['data'], {'grant_type': 'client_credentials'})
        self.assertTrue(kwargs['headers']['Authorization'].startswith('Basic '))

    def test_get_access_token_missing_credentials_raises(self):
        connector = SovosConnector(base_url='https://api-test.sovos.com')
        with self.assertRaises(UserError):
            connector._get_access_token()

    def test_get_access_token_no_token_in_response_raises(self):
        with patch.object(self.connector._session, 'request', return_value=_fake_response(json_data={})):
            with self.assertRaises(UserError):
                self.connector._get_access_token()

    def test_test_connection_uses_bearer_token(self):
        responses = [
            _fake_response(json_data={'access_token': 'fake-token-123'}),
            _fake_response(json_data={'status': 'UP'}),
        ]
        with patch.object(self.connector._session, 'request', side_effect=responses) as mock_request:
            result = self.connector.test_connection('OM')

        self.assertEqual(result, {'status': 'UP'})
        self.assertEqual(mock_request.call_count, 2)
        args, kwargs = mock_request.call_args_list[1]
        self.assertEqual(args[0], 'GET')
        self.assertEqual(args[1], 'https://api-test.sovos.com/v1/status')
        self.assertEqual(kwargs['params'], {'countryCode': 'OM'})
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer fake-token-123')

    def test_authentication_failure_raises_clear_error(self):
        with patch.object(self.connector._session, 'request', return_value=_fake_response(
            status_code=401, text='{"error": "invalid_client"}',
        )):
            with self.assertRaises(UserError):
                self.connector._get_access_token()

    def test_submit_get_status_cancel_are_not_yet_implemented(self):
        # By design: endpoints are confirmed to exist, but the body schemas aren't, so these must
        # fail loudly with a specific reason rather than silently sending a guessed payload.
        with self.assertRaises(UserError):
            self.connector.submit_invoice(b'<xml/>', b'<xml/>')
        with self.assertRaises(UserError):
            self.connector.get_status('some-reference')
        with self.assertRaises(UserError):
            self.connector.cancel('some-reference', 'test reason')
