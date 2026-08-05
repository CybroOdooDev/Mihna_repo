# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.addons.l10n_ae_edi.lib import crypto
from odoo.addons.l10n_ae_edi.lib.connectors import get_connector_class
from odoo.addons.l10n_ae_edi.lib.connectors.base import CONFIG_STATUS_SELECTION

# Deliberately a single entry: no named UAE Accredited Service Provider is hardcoded (see this
# module's description, and lib/connectors/base.py). A real provider is added by a small companion
# module contributing one more option here via `selection_add` plus its own connector file - this
# module's core code, views, and state machine never need to change for that.
ASP_PROVIDER_SELECTION = [
    ('reference', "Reference / Manual Integration (documentation only)"),
]


class ResCompany(models.Model):
    """ Stores this company's Accredited Service Provider (ASP) selection, connection settings, and
    encrypted credentials, and builds a ready-to-use connector instance from them. """
    _inherit = 'res.company'

    l10n_ae_edi_asp_provider = fields.Selection(
        selection=ASP_PROVIDER_SELECTION,
        string="ASP Provider",
        help="The Ministry of Finance-Accredited Service Provider (ASP) this company has contracted "
             "to submit e-invoices to the UAE Federal Tax Authority.",
    )
    # Provider-driven config metadata, computed from the selected connector class - NOT a single
    # hardcoded auth type. Each connector declares its own REQUIRED_CONFIG/CONFIG_STATUS/CONFIG_NOTES;
    # this just surfaces that metadata so the Settings view shows only the relevant fields.
    l10n_ae_edi_asp_required_config = fields.Json(
        string="ASP Required Configuration",
        compute='_compute_l10n_ae_edi_asp_config_meta',
    )
    l10n_ae_edi_asp_config_status = fields.Selection(
        selection=CONFIG_STATUS_SELECTION,
        string="ASP Config Confidence",
        compute='_compute_l10n_ae_edi_asp_config_meta',
    )
    l10n_ae_edi_asp_config_notes = fields.Char(
        string="ASP Config Notes",
        compute='_compute_l10n_ae_edi_asp_config_meta',
    )
    l10n_ae_edi_asp_mof_accredited = fields.Boolean(
        string="ASP is MoF-Accredited",
        compute='_compute_l10n_ae_edi_asp_config_meta',
        help="Whether the selected provider's connector was confirmed, by whoever built it, to "
             "actually appear on the Ministry of Finance's own published Accredited Service Provider "
             "list.",
    )

    l10n_ae_edi_asp_base_url = fields.Char(string="ASP API Base URL")
    l10n_ae_edi_asp_client_id = fields.Char(string="ASP Client ID")
    l10n_ae_edi_asp_username = fields.Char(string="ASP Username")
    l10n_ae_edi_asp_certificate_id = fields.Many2one(
        comodel_name='certificate.certificate', string="ASP Client Certificate",
    )
    l10n_ae_edi_asp_account_id = fields.Char(
        string="ASP Account / Tenant / Company ID",
        help="Some ASPs require a sub-account identifier alongside the credentials above.",
    )
    l10n_ae_edi_asp_redirect_url = fields.Char(
        string="ASP OAuth Redirect URL",
        help="Required by ASPs using an OAuth2 authorization_code flow - must be pre-registered with "
             "the provider.",
    )
    l10n_ae_edi_environment = fields.Selection(
        selection=[('sandbox', "Sandbox"), ('production', "Production")],
        string="ASP Environment",
        default='sandbox',
        required=True,
        help="Selects which of this company's ASP configuration applies. Kept independent of which "
             "ASP is chosen above, so switching a company from testing to going live is a one-field "
             "change, not a different module.",
    )

    # -------------------------------------------------------------------------
    # Encrypted credentials - see lib/crypto.py
    #
    # Each of these is a non-stored, admin-only, password-widget field backed by a genuine database
    # column holding nothing but a Fernet ciphertext token. The plaintext only ever exists transiently
    # in memory: while the compute method below is running (decrypting to show it back to an admin who
    # is allowed to see it) and while `_l10n_ae_edi_get_connector` is building a connector instance for
    # one outbound API call. It is never written to any log, and the `*_encrypted` column is never
    # exposed in any view.
    # -------------------------------------------------------------------------

    l10n_ae_edi_asp_client_secret_encrypted = fields.Char(string="ASP Client Secret (Encrypted)", groups='base.group_system')
    l10n_ae_edi_asp_client_secret = fields.Char(
        string="ASP Client Secret", groups='base.group_system',
        compute='_compute_l10n_ae_edi_asp_client_secret', inverse='_inverse_l10n_ae_edi_asp_client_secret',
    )
    l10n_ae_edi_asp_api_key_encrypted = fields.Char(string="ASP API Key (Encrypted)", groups='base.group_system')
    l10n_ae_edi_asp_api_key = fields.Char(
        string="ASP API Key", groups='base.group_system',
        compute='_compute_l10n_ae_edi_asp_api_key', inverse='_inverse_l10n_ae_edi_asp_api_key',
    )
    l10n_ae_edi_asp_password_encrypted = fields.Char(string="ASP Password (Encrypted)", groups='base.group_system')
    l10n_ae_edi_asp_password = fields.Char(
        string="ASP Password", groups='base.group_system',
        compute='_compute_l10n_ae_edi_asp_password', inverse='_inverse_l10n_ae_edi_asp_password',
    )

    def _compute_l10n_ae_edi_asp_client_secret(self):
        """ Decrypt the stored client secret into the transient, admin-only plaintext field. """
        for company in self:
            company.l10n_ae_edi_asp_client_secret = crypto.decrypt_secret(self.env, company.l10n_ae_edi_asp_client_secret_encrypted)

    def _inverse_l10n_ae_edi_asp_client_secret(self):
        """ Encrypt the plaintext client secret entered by an admin before storing it. """
        for company in self:
            company.l10n_ae_edi_asp_client_secret_encrypted = crypto.encrypt_secret(self.env, company.l10n_ae_edi_asp_client_secret)

    def _compute_l10n_ae_edi_asp_api_key(self):
        """ Decrypt the stored API key into the transient, admin-only plaintext field. """
        for company in self:
            company.l10n_ae_edi_asp_api_key = crypto.decrypt_secret(self.env, company.l10n_ae_edi_asp_api_key_encrypted)

    def _inverse_l10n_ae_edi_asp_api_key(self):
        """ Encrypt the plaintext API key entered by an admin before storing it. """
        for company in self:
            company.l10n_ae_edi_asp_api_key_encrypted = crypto.encrypt_secret(self.env, company.l10n_ae_edi_asp_api_key)

    def _compute_l10n_ae_edi_asp_password(self):
        """ Decrypt the stored password into the transient, admin-only plaintext field. """
        for company in self:
            company.l10n_ae_edi_asp_password = crypto.decrypt_secret(self.env, company.l10n_ae_edi_asp_password_encrypted)

    def _inverse_l10n_ae_edi_asp_password(self):
        """ Encrypt the plaintext password entered by an admin before storing it. """
        for company in self:
            company.l10n_ae_edi_asp_password_encrypted = crypto.encrypt_secret(self.env, company.l10n_ae_edi_asp_password)

    # -------------------------------------------------------------------------

    @api.depends('l10n_ae_edi_asp_provider')
    def _compute_l10n_ae_edi_asp_config_meta(self):
        """ Surface the selected connector class's own REQUIRED_CONFIG/CONFIG_STATUS/CONFIG_NOTES/
        MOF_ACCREDITED metadata, so the Settings view can show only the fields that ASP needs. """
        for company in self:
            connector_cls = company.l10n_ae_edi_asp_provider and get_connector_class(company.l10n_ae_edi_asp_provider)
            if connector_cls:
                company.l10n_ae_edi_asp_required_config = connector_cls.REQUIRED_CONFIG
                company.l10n_ae_edi_asp_config_status = connector_cls.CONFIG_STATUS
                company.l10n_ae_edi_asp_config_notes = connector_cls.CONFIG_NOTES
                company.l10n_ae_edi_asp_mof_accredited = connector_cls.MOF_ACCREDITED
            else:
                company.l10n_ae_edi_asp_required_config = []
                company.l10n_ae_edi_asp_config_status = False
                company.l10n_ae_edi_asp_config_notes = False
                company.l10n_ae_edi_asp_mof_accredited = False

    def _l10n_ae_edi_get_connector(self, timeout_limit=None):
        """ Return an instantiated connector for this company's configured ASP provider.

        This is the single seam a real ASP integration is wired in through: once a provider's
        connector (lib/connectors/<vendor>.py) implements `submit_invoice`/`get_status` for real, no
        other code in this module needs to change.
        """
        self.ensure_one()
        connector_cls = self.l10n_ae_edi_asp_provider and get_connector_class(self.l10n_ae_edi_asp_provider)
        if not connector_cls:
            raise UserError(_(
                "No Accredited Service Provider is configured for %(company)s. "
                "Go to Settings > Accounting > UAE E-Invoicing to select one.",
                company=self.display_name,
            ))

        return connector_cls(
            base_url=self.l10n_ae_edi_asp_base_url,
            client_id=self.l10n_ae_edi_asp_client_id,
            client_secret=self.l10n_ae_edi_asp_client_secret,
            api_key=self.l10n_ae_edi_asp_api_key,
            username=self.l10n_ae_edi_asp_username,
            password=self.l10n_ae_edi_asp_password,
            certificate_id=self.l10n_ae_edi_asp_certificate_id,
            account_id=self.l10n_ae_edi_asp_account_id,
            redirect_url=self.l10n_ae_edi_asp_redirect_url,
            environment=self.l10n_ae_edi_environment,
            timeout_limit=timeout_limit,
        )
