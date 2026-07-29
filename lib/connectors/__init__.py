# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, CONNECTOR_REGISTRY

# Importing each vendor module registers its connector class into CONNECTOR_REGISTRY (see base.py's
# @register_connector decorator). Add a new ASP by creating one file here + a matching Selection
# option on res.company.l10n_om_edi_asp_provider (see models/res_company.py).
from . import cleartax
from . import pagero
from . import edicom
from . import sovos
from . import comarch
from . import opentext
from . import sap
from . import basware
from . import vertex
from . import unifiedpost
from . import fawtarax


def get_connector_class(provider_code):
    """ Return the connector class registered for the given ASP provider code, or None. """
    return CONNECTOR_REGISTRY.get(provider_code)
