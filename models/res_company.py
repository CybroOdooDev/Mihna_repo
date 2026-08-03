# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.addons.l10n_om_edi.lib.connectors import get_connector_class
from odoo.addons.l10n_om_edi.lib.connectors.base import CONFIG_STATUS_SELECTION

# Keep in sync with the connector modules registered in lib/connectors/__init__.py. Oman's e-invoicing
# mandate allows multiple Accredited Service Providers (unlike e.g. Malaysia's single MyInvois portal),
# so this is a plain per-company choice rather than a hardcoded single integration.
#
# This is the complete, official Oman Tax Authority Accredited Service Provider list (verified
# 2026-07-30, "Showing 1 - 12 of 12" - https://fawtara.taxoman.gov.om/accredited-service-providers).
# An earlier version of this module also shipped 10 additional connectors built from general vendor
# research before that official list was checked (Pagero, EDICOM, Sovos, Comarch, OpenText, SAP,
# Basware, Vertex, Unifiedpost, FawtaraX) - none of them were on the real list, so they were removed
# rather than kept as a confusing "unofficial" option alongside the real 12.
ASP_PROVIDER_SELECTION = [
    ('cleartax', "ClearTax"),
    ('jsr', "JSR Tax Advisors"),
    ('flick', "Flick Network"),
    ('smarteis', "SMARTeIS"),
    ('convergex', "ConvergeX"),
    ('bdo', "BDO"),
    ('cygnet', "Cygnet"),
    ('fynamics', "Fynamics"),
    ('webtel', "Webtel"),
    ('faturathi', "Faturathi"),
    ('marminai', "Marmin AI"),
    ('goroute', "GoRoute"),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_om_edi_asp_provider = fields.Selection(
        selection=ASP_PROVIDER_SELECTION,
        string="ASP Provider",
        help="The Accredited Service Provider (ASP) this company has contracted, via the Fawtara "
             "Portal, to submit e-invoices to the Oman Tax Authority.",
    )
    # Provider-driven config metadata, computed from the selected connector class - NOT a single
    # hardcoded auth type. Each connector declares its own REQUIRED_CONFIG/CONFIG_STATUS/CONFIG_NOTES
    # from that vendor's own public documentation (see lib/connectors/<vendor>.py); this just surfaces
    # that metadata so the Settings view can show only the relevant fields plus an honest confidence
    # indicator, rather than assuming every ASP authenticates the same way.
    l10n_om_edi_asp_required_config = fields.Json(
        string="ASP Required Configuration",
        compute='_compute_l10n_om_edi_asp_config_meta',
    )
    l10n_om_edi_asp_config_status = fields.Selection(
        selection=CONFIG_STATUS_SELECTION,
        string="ASP Config Confidence",
        compute='_compute_l10n_om_edi_asp_config_meta',
        help="How well the shown configuration fields are actually verified against the selected "
             "provider's own documentation - see the note below the ASP Provider field.",
    )
    l10n_om_edi_asp_config_notes = fields.Char(
        string="ASP Config Notes",
        compute='_compute_l10n_om_edi_asp_config_meta',
    )
    l10n_om_edi_asp_ota_accredited = fields.Boolean(
        string="ASP is OTA-Accredited",
        compute='_compute_l10n_om_edi_asp_config_meta',
        help="Whether the selected provider actually appears on the Oman Tax Authority's own "
             "published accredited-provider list - the real, legal answer to whether this ASP can be "
             "used for Oman e-invoicing at all, independent of how well its API happens to be "
             "documented.",
    )

    l10n_om_edi_asp_base_url = fields.Char(string="ASP API Base URL")
    l10n_om_edi_asp_client_id = fields.Char(string="ASP Client ID")
    l10n_om_edi_asp_client_secret = fields.Char(string="ASP Client Secret", groups='base.group_system')
    l10n_om_edi_asp_api_key = fields.Char(string="ASP API Key", groups='base.group_system')
    l10n_om_edi_asp_username = fields.Char(string="ASP Username")
    l10n_om_edi_asp_password = fields.Char(string="ASP Password", groups='base.group_system')
    l10n_om_edi_asp_certificate_id = fields.Many2one(
        comodel_name='certificate.certificate', string="ASP Client Certificate",
    )
    l10n_om_edi_asp_account_id = fields.Char(
        string="ASP Account / Tenant / Company ID",
        help="Some ASPs require a sub-account identifier alongside the credentials above "
             "(e.g. Pagero's 'companyId').",
    )
    l10n_om_edi_asp_redirect_url = fields.Char(
        string="ASP OAuth Redirect URL",
        help="Required by ASPs using an OAuth2 authorization_code flow - must be pre-registered with "
             "the provider.",
    )
    l10n_om_edi_environment = fields.Selection(
        selection=[('test', "Sandbox"), ('production', "Production")],
        string="ASP Environment",
        default='test',
        required=True,
    )

    @api.depends('l10n_om_edi_asp_provider')
    def _compute_l10n_om_edi_asp_config_meta(self):
        for company in self:
            connector_cls = company.l10n_om_edi_asp_provider and get_connector_class(company.l10n_om_edi_asp_provider)
            if connector_cls:
                company.l10n_om_edi_asp_required_config = connector_cls.REQUIRED_CONFIG
                company.l10n_om_edi_asp_config_status = connector_cls.CONFIG_STATUS
                company.l10n_om_edi_asp_config_notes = connector_cls.CONFIG_NOTES
                company.l10n_om_edi_asp_ota_accredited = connector_cls.OTA_ACCREDITED
            else:
                company.l10n_om_edi_asp_required_config = []
                company.l10n_om_edi_asp_config_status = False
                company.l10n_om_edi_asp_config_notes = False
                company.l10n_om_edi_asp_ota_accredited = False

    def _l10n_om_edi_get_connector(self, timeout_limit=None):
        """ Return an instantiated connector for this company's configured ASP provider.

        This is the single seam a real ASP integration is wired in through: once a provider's
        connector (lib/connectors/<vendor>.py) implements `submit_invoice`/`get_status`/`cancel` for
        real, no other code in this module needs to change.
        """
        self.ensure_one()
        connector_cls = self.l10n_om_edi_asp_provider and get_connector_class(self.l10n_om_edi_asp_provider)
        if not connector_cls:
            raise UserError(_(
                "No Accredited Service Provider is configured for %(company)s. "
                "Go to Settings > Accounting > Oman E-Invoicing to select one.",
                company=self.display_name,
            ))

        return connector_cls(
            base_url=self.l10n_om_edi_asp_base_url,
            client_id=self.l10n_om_edi_asp_client_id,
            client_secret=self.l10n_om_edi_asp_client_secret,
            api_key=self.l10n_om_edi_asp_api_key,
            username=self.l10n_om_edi_asp_username,
            password=self.l10n_om_edi_asp_password,
            certificate_id=self.l10n_om_edi_asp_certificate_id,
            account_id=self.l10n_om_edi_asp_account_id,
            redirect_url=self.l10n_om_edi_asp_redirect_url,
            environment=self.l10n_om_edi_environment,
            timeout_limit=timeout_limit,
        )
