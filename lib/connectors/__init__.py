# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nAeEdiConnector, CONNECTOR_REGISTRY

# Importing each vendor module registers its connector class into CONNECTOR_REGISTRY (see base.py's
# @register_connector decorator).
#
# Only the documentation-only reference connector ships here - see reference.py and this module's
# description for why no real ASP is hardcoded. Add a real provider by creating one file here + a
# matching Selection option on res.company.l10n_ae_edi_asp_provider (see models/res_company.py).
from . import reference


def get_connector_class(provider_code):
    """ Return the connector class registered for the given ASP provider code, or None. """
    return CONNECTOR_REGISTRY.get(provider_code)
