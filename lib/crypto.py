# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Symmetric encryption at rest for ASP credentials (API keys, client secrets, passwords, ...).

Secret values are never stored in the clear: `res.company` exposes plain-looking fields (e.g.
`l10n_ae_edi_asp_client_secret`) that are actually non-stored computed fields, backed by a hidden
`*_encrypted` Char column holding a Fernet token (AES-128-CBC + HMAC-SHA256, authenticated symmetric
encryption). Decryption only ever happens transiently, in memory, at the point a connector needs the
value to build an outbound API call - see `models/res_company.py::_l10n_ae_edi_get_connector`.

No `key_version` column is kept on purpose: today's key lives in exactly one place (see
`get_encryption_key` below), so a future key-rotation wizard can re-encrypt every stored credential in
a single all-or-nothing transaction (decrypt-all-under-old-key, re-encrypt-under-new-key, swap the
parameter) without ever needing a schema change.
"""
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

_logger = logging.getLogger(__name__)

# Server-wide environment variable checked first. Setting this keeps the encryption key out of the
# database entirely (it never sits alongside the ciphertext it protects) - the recommended posture in
# production. Not required: the module works out of the box without it (see the ir.config_parameter
# fallback below), which matters for a quick dev/sandbox install.
ENV_VAR_KEY = 'ODOO_L10N_AE_EDI_KEY'

# Fallback storage: generated once, the first time any credential is encrypted, and reused after that.
CONFIG_PARAMETER_KEY = 'l10n_ae_edi.credential_key'


def get_encryption_key(env):
    """ Return the Fernet key used to encrypt/decrypt ASP credentials for this database.

    This is the single indirection point every encrypt/decrypt call goes through - nothing else in
    this module ever reads the environment variable or the config parameter directly, which is what
    makes future key rotation a pure data operation (see the module docstring).
    """
    env_key = os.environ.get(ENV_VAR_KEY)
    if env_key:
        return env_key.encode()

    IrConfigParameter = env['ir.config_parameter'].sudo()
    key = IrConfigParameter.get_param(CONFIG_PARAMETER_KEY)
    if not key:
        key = Fernet.generate_key().decode()
        IrConfigParameter.set_param(CONFIG_PARAMETER_KEY, key)
        _logger.info("Generated a new UAE e-invoicing credential encryption key (%s).", CONFIG_PARAMETER_KEY)
    return key.encode()


def encrypt_secret(env, plaintext):
    """ Encrypt `plaintext`, returning a Fernet token string, or False if there's nothing to encrypt. """
    if not plaintext:
        return False
    return Fernet(get_encryption_key(env)).encrypt(plaintext.encode()).decode()


def decrypt_secret(env, ciphertext):
    """ Decrypt a Fernet token string previously produced by `encrypt_secret`, or False if there's
    nothing to decrypt or the token can no longer be decrypted with the current key (e.g. the
    environment variable was unset after being used to encrypt, or the database parameter was lost). """
    if not ciphertext:
        return False
    try:
        return Fernet(get_encryption_key(env)).decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        _logger.warning("Could not decrypt a stored UAE e-invoicing ASP credential with the current "
                         "encryption key - it may have been encrypted under a different key.")
        return False
