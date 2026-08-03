# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, CONNECTOR_REGISTRY

# Importing each vendor module registers its connector class into CONNECTOR_REGISTRY (see base.py's
# @register_connector decorator). Add a new ASP by creating one file here + a matching Selection
# option on res.company.l10n_om_edi_asp_provider (see models/res_company.py).
#
# These 12 are the complete, official Oman Tax Authority Accredited Service Provider list (verified
# 2026-07-30, "Showing 1 - 12 of 12", no pagination beyond that -
# https://fawtara.taxoman.gov.om/accredited-service-providers). Only these are legally usable for
# real Oman e-invoicing compliance - do not add a connector here without checking that list first.
from . import cleartax
from . import jsr
from . import flick
from . import smarteis
from . import convergex
from . import bdo
from . import cygnet
from . import fynamics
from . import webtel
from . import faturathi
from . import marminai
from . import goroute


def get_connector_class(provider_code):
    """ Return the connector class registered for the given ASP provider code, or None. """
    return CONNECTOR_REGISTRY.get(provider_code)
