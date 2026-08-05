# Part of Odoo. See LICENSE file for full copyright and licensing details.
import os
from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_ae_edi.lib import crypto
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nAeEdiCrypto(AccountTestInvoicingCommon):
    """ Tests the Fernet encryption/decryption helpers in lib/crypto.py, including the key source
    (database-generated vs. environment variable) and encrypted-at-rest storage on res.company. """

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ae')
    def setUpClass(cls):
        super().setUpClass()
        # Isolate every test in this class from whatever key a previous test/run may have generated.
        cls.env['ir.config_parameter'].sudo().set_param(crypto.CONFIG_PARAMETER_KEY, False)

    def test_round_trip_via_config_parameter_key(self):
        """ With no environment variable set, a key is generated once and reused. """
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(crypto.ENV_VAR_KEY, None)
            ciphertext = crypto.encrypt_secret(self.env, 'super-secret-value')
            self.assertTrue(ciphertext)
            self.assertNotIn('super-secret-value', ciphertext)
            self.assertEqual(crypto.decrypt_secret(self.env, ciphertext), 'super-secret-value')

    def test_round_trip_via_environment_variable_key(self):
        """ An environment-variable key takes priority over the database-stored one, and round-trips
        just as correctly - this is the recommended production posture (key never touches the DB). """
        from cryptography.fernet import Fernet
        env_key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {crypto.ENV_VAR_KEY: env_key}):
            ciphertext = crypto.encrypt_secret(self.env, 'super-secret-value')
            self.assertEqual(crypto.decrypt_secret(self.env, ciphertext), 'super-secret-value')

    def test_falsy_values_are_not_encrypted(self):
        """ Empty/False secrets pass through as-is instead of being wrapped in a Fernet token. """
        self.assertFalse(crypto.encrypt_secret(self.env, False))
        self.assertFalse(crypto.encrypt_secret(self.env, ''))
        self.assertFalse(crypto.decrypt_secret(self.env, False))

    def test_wrong_key_fails_closed_not_open(self):
        """ Decrypting under the wrong key must return False, not raise, and must never leak partial
        plaintext. """
        from cryptography.fernet import Fernet
        with patch.dict(os.environ, {crypto.ENV_VAR_KEY: Fernet.generate_key().decode()}):
            ciphertext = crypto.encrypt_secret(self.env, 'super-secret-value')
        with patch.dict(os.environ, {crypto.ENV_VAR_KEY: Fernet.generate_key().decode()}):
            self.assertFalse(crypto.decrypt_secret(self.env, ciphertext))

    def test_company_secret_fields_are_encrypted_at_rest_and_redacted(self):
        """ End-to-end: writing a secret through res.company never leaves the plaintext sitting in a
        readable column, and the stored ciphertext round-trips back through the computed field. """
        company = self.company_data['company']
        company.l10n_ae_edi_asp_client_secret = 'my-oauth-client-secret'

        self.assertNotEqual(company.l10n_ae_edi_asp_client_secret_encrypted, 'my-oauth-client-secret')
        self.assertNotIn('my-oauth-client-secret', company.l10n_ae_edi_asp_client_secret_encrypted or '')
        self.assertEqual(company.l10n_ae_edi_asp_client_secret, 'my-oauth-client-secret')
