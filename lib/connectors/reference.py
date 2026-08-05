# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _
from odoo.exceptions import UserError

from .base import L10nAeEdiConnector, register_connector


@register_connector('reference')
class ReferenceConnector(L10nAeEdiConnector):
    """ Documentation-only reference implementation of a UAE e-invoicing ASP connector.

    This is NOT a real Accredited Service Provider and issues no live HTTP request under any
    circumstance - every method below simply explains, in comments, what a real connector for a real
    MoF-accredited ASP would do at that point, then raises a clear error saying so.

    To integrate a real ASP: copy this file to `<provider>.py`, change the `@register_connector(...)`
    code and `display_name`, fill in `REQUIRED_CONFIG`/`CONFIG_STATUS`/`CONFIG_SOURCE`/`CONFIG_NOTES`
    from that vendor's own published documentation, replace the method bodies below with real calls
    (the `_request`/`_handle_response` helpers on the base class are there to help), then add a
    matching Selection option in `models/res_company.py` and import your new module from
    `lib/connectors/__init__.py`. Nothing else in this module needs to change.
    """
    display_name = "Reference / Manual Integration (documentation only)"
    MOF_ACCREDITED = False
    REQUIRED_CONFIG = ['api_key']  # example only - a real ASP's actual auth fields go here
    CONFIG_STATUS = 'unconfirmed'
    CONFIG_NOTES = ("This is a documentation-only template, not a real Accredited Service Provider. "
                    "Until a real ASP's connector is implemented, generate the PINT AE XML from the "
                    "invoice and submit it to your contracted ASP by whatever channel they provide "
                    "(portal upload, email, etc).")

    def submit_invoice(self, invoice_xml):
        """ Documentation-only override of `L10nAeEdiConnector.submit_invoice` - always refuses. """
        # A real connector would typically, at this point:
        #   1. Authenticate (e.g. `self._request('POST', '/oauth/token', data={...})` for OAuth2
        #      client-credentials, or simply set a bearer/API-key header from `self.api_key`).
        #   2. POST `invoice_xml` (or a base64-encoded copy of it, per that ASP's API contract) to
        #      their invoice-submission endpoint, e.g.:
        #      response = self._request('POST', '/v1/invoices', data=invoice_xml,
        #                                headers={'Content-Type': 'application/xml'})
        #   3. Return whatever reference/ID field that ASP's response uses to identify the submission,
        #      e.g. `return response['submissionId']`.
        raise UserError(_(
            "%(provider)s is a documentation-only template, not a real Accredited Service Provider. "
            "Configure a real MoF-accredited ASP's connector before submitting invoices "
            "automatically - see Settings > Accounting > UAE E-Invoicing.",
            provider=self.display_name,
        ))

    def get_status(self, asp_reference):
        """ Documentation-only override of `L10nAeEdiConnector.get_status` - always refuses. """
        # A real connector would typically GET a status endpoint keyed by `asp_reference` and map that
        # ASP's own status vocabulary onto 'in_progress' / 'accepted' / 'rejected' / 'error', e.g.:
        #   response = self._request('GET', f'/v1/invoices/{asp_reference}')
        #   return {'PENDING': 'in_progress', 'ACK': 'accepted', 'NACK': 'rejected'}.get(response['status'], 'error')
        raise UserError(_(
            "%(provider)s is a documentation-only template, not a real Accredited Service Provider.",
            provider=self.display_name,
        ))
