# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from datetime import datetime, timezone

from odoo import _
from odoo.exceptions import UserError

from .base import L10nOmEdiConnector, register_connector


@register_connector('flick')
class FlickNetworkConnector(L10nOmEdiConnector):
    """ Flick Network connector.

    CONFIRMED OTA-ACCREDITED: listed on the Oman Tax Authority's official accredited-provider list
    (checked 2026-07-30, full list of 12): legal entity "Advanced Information Technology Company LLC",
    Solution Name "Flick Network", Data Residency Oman, contact ameen@flick.network -
    https://fawtara.taxoman.gov.om/accredited-service-providers

    CONFIRMED from their own dedicated Oman API reference (developer.flick.network/api-references/
    regional/om, "Flick Oman eInvoicing API" v1.0.0, OpenAPI 3.1.0 - resolves the earlier concern that
    their SDK's "EGS"/ZATCA-flavored terminology meant this was a Saudi-first product with no
    Oman-specific layer - it has its own) and their Oman developer guide
    (developer.flick.network/developer-guides/global-einvoicing/oman):

    - Sandbox server: https://sb-om-api.flick.network (production host not yet seen).
    - Auth: static API key via an `X-Flick-Auth-Key` header (implemented here), or OAuth2
      client_credentials (POST /v1/oauth/token, JSON body {client_id, client_secret,
      grant_type: "client_credentials"} -> {access_token, token_type: "Bearer", expires_in}) as an
      alternative not implemented here.
    - `GET /v1/auth/verify` -> {"status": "success", "message": "...", "data": null} - confirmed
      exact response shape, implemented below as test_connection().
    - IMPORTANT PREREQUISITE discovered from their Participants section: before any document can be
      submitted, the company must first be registered as a "Participant" on Flick's Peppol network
      (`POST /v1/participants`, with trade/legal name, VAT, address, and a Peppol ID; see
      `GET/PUT/DELETE /v1/participants/{participant_id}` and `.../activate`). The resulting
      `participant_id` is required on every document call below - mapped onto this module's generic
      `account_id` slot. This registration is treated as a one-time manual setup step (done via their
      dashboard or a separate call, not by this connector) rather than something Odoo re-does per
      invoice.
    - `POST /v1/{participant_id}/documents` - CONFIRMED: accepts either `application/json` (their own
      flattened PINT-OM field schema, fully documented with a required-fields table and a sample
      payload) or `application/xml` (a single undocumented line, no example ever shown). A real
      submission of our generic PINT-OM XML was tried first and came back with 5 validation errors -
      some pointed at genuine gaps in the generic XML (missing IssueTime/address-line-3, now fixed in
      l10n_om_ubl_pint), but one ("Buyer Peppol ID must be in format 0248:OM11XXXXXXXX") revealed their
      validator expects the *combined* scheme:value string their own JSON schema documents
      (`"peppol_id": "0248:OM1234567890"`), not the standard Peppol/UBL convention of `schemeID` as an
      XML attribute with the plain value as text. That's a real deviation from Peppol XML convention on
      their side - submitting their documented JSON instead of our generic XML sidesteps it entirely
      rather than guessing at further XML workarounds. Built here from the invoice record directly (see
      `_build_flick_payload`), not from the PINT-OM XML - `invoice_xml`/`tdd_xml` are still generated
      and kept as attachments regardless (Oman's 10-year self-archival requirement), just not what gets
      transmitted to Flick. Response: {"status": "success"|"failed", "data": {"document_id": ...,
      "status": "processing"|"completed"|"failed", "exchange_status": ..., "reporting_status": ...}} on
      success, or {"status": "failed", "data": {"errors": [...]}} on validation failure - the live
      sandbox's error entries did not use the documented 'field_name'/'error_message' keys, so
      `_format_flick_error` degrades to showing the raw error object rather than guessing further.
      `tdd_xml` is accepted (shared connector interface) but intentionally unused: Flick's platform
      performs Corner-5/OTA reporting itself once the invoice is submitted, matching the 5-corner
      model - there is no separate TDD upload endpoint in their documented API.
    - `item_type` (their invoice line field, Oman-specific business term BTOM-013, "MUST be provided
      except for simplified invoices" per the live validator) has only one example value in their docs
      ("GS") and no enum list - defaulted to "GS" for every line below, flagged as an assumption to
      revisit once Flick clarifies the real allowed values.
    - `GET /v1/{participant_id}/documents/{document_id}` - status-check endpoint, confirmed to reuse
      the identical status/exchange_status/reporting_status envelope described above - implemented
      below as get_status().
    - No dedicated cancel/void endpoint was found among their documented operations (only "Retry
      Document") - consistent with Peppol/Oman generally correcting via credit notes rather than true
      cancellation, which is already how this module's l10n.om.edi.document model works.
    - Also documented but not yet needed here: Network Lookup, Labels, Suppliers, Customers, Webhooks
      (could replace this module's cron-based polling with push notifications later), a
      Simulate/incoming endpoint useful for sandbox testing, bulk submission (up to 100/request), and
      a pre-submission /validate endpoint.
    """
    display_name = "Flick Network"
    OTA_ACCREDITED = True
    REQUIRED_CONFIG = ['api_key', 'account_id']
    CONFIG_STATUS = 'confirmed'
    DEFAULT_BASE_URL = {
        'test': 'https://sb-om-api.flick.network',
        # Production host not yet seen (their docs page may offer a server switcher) - leave unset
        # rather than guess a naming pattern (e.g. dropping the "sb-" prefix).
    }
    CONFIG_SOURCE = "https://developer.flick.network/api-references/regional/om"
    CONFIG_NOTES = ("Officially OTA-accredited for Oman (Data Residency: Oman; contact "
                     "ameen@flick.network). Confirmed: static API key via 'X-Flick-Auth-Key' (sandbox "
                     "server pre-filled above), plus an 'Account / Tenant / Company ID' field that "
                     "must hold your Flick 'participant_id' - you must first register as a Participant "
                     "via the Flick dashboard/API before any document call works. Authentication, "
                     "connectivity check, invoice submission and status polling are all implemented; "
                     "only cancellation has no documented endpoint yet.")

    # -------------------------------------------------------------------------
    # Real, confirmed calls
    # -------------------------------------------------------------------------

    def test_connection(self, country_code):
        """ GET /v1/auth/verify - confirmed side-effect-free way to check the configured API key is
        valid, without touching invoice submission at all. """
        if not self.api_key:
            raise self._not_configured_error()
        return self._request(
            'GET', '/v1/auth/verify',
            headers={'X-Flick-Auth-Key': self.api_key},
        )

    def submit_invoice(self, invoice_xml, tdd_xml, document):
        """ POST /v1/{participant_id}/documents, submitting Flick's own documented JSON schema built
        from the invoice record - see class docstring for why JSON was chosen over reusing the
        generic XML. `tdd_xml` is unused: Flick performs Corner-5/OTA reporting itself from the
        submitted invoice. """
        if not self.account_id:
            raise UserError(_(
                "No Flick 'participant_id' is configured (Account / Tenant / Company ID field). "
                "Register your company as a Participant via the Flick dashboard first, then enter "
                "the resulting participant_id in Settings > Accounting > Oman E-Invoicing."
            ))
        payload = self._build_flick_payload(document)
        response = self._request(
            'POST', f'/v1/{self.account_id}/documents',
            # A real submission confirmed the request body must be wrapped in a top-level "document"
            # key ({"document": {...}}) - their docs' sample payload showed the fields flat, without
            # this wrapper, so this was only discovered via a live rejection ("`document` field is
            # required"), not from the documentation itself.
            json={'document': payload},
            headers={'X-Flick-Auth-Key': self.api_key},
            handle_response=False,
        )
        return self._handle_submit_response(response)

    def _build_flick_payload(self, document):
        """ Maps `document`/`document.move_id` into Flick's documented JSON schema (developer.flick.
        network/developer-guides/global-einvoicing/oman) - see class docstring for why this is built
        directly rather than reusing the generic PINT-OM XML. Reuses the same tax-category and
        UN/ECE unit-code logic the generic XML builder already uses, via the pint_om EDI builder
        model, rather than re-deriving that logic here. """
        move = document.move_id
        builder = move.env['account.edi.xml.pint_om']
        supplier = move.company_id.partner_id.commercial_partner_id
        customer = move.partner_id.commercial_partner_id
        # In Odoo 19, a genuine product line has display_type == 'product' (not a falsy value as in
        # older versions) - section/note/tax/payment-term lines have their own distinct display_type.
        lines = move.invoice_line_ids.filtered(lambda l: l.display_type == 'product')

        def _party(partner):
            peppol_value = partner.peppol_endpoint or partner.vat
            return {
                'legal_name': partner.name,
                'trade_name': partner.name,
                'peppol_id': f"{partner.peppol_eas}:{peppol_value}" if partner.peppol_eas and peppol_value else None,
                'vat_number': partner.vat,
                'street_address': partner.street,
                'additional_street_address': partner.street2,
                'additional_address_lines': [partner.l10n_om_address_line3] if partner.l10n_om_address_line3 else [],
                'city_address': partner.city,
                'postal_zone': partner.zip,
                'country_subdivision_code': partner.state_id.code,
                'country_code': partner.country_id.code,
                'contact_name': partner.name,
                'contact_telephone': partner.phone,
                'contact_email': partner.email,
            }

        def _invoice_line(index, line):
            tax = line.tax_ids[:1]
            return {
                'id': str(index),
                'name': line.product_id.name or line.name,
                'description': line.name,
                'quantity': str(line.quantity),
                'uom': builder._get_uom_unece_code(line.product_uom_id),
                'unit_price': "%.2f" % line.price_unit,
                'base_quantity': "1",
                'line_extension_amount': "%.2f" % line.price_subtotal,
                'vat_category': builder._get_tax_category_code(customer, supplier, tax),
                'vat_percentage': "%.2f" % (tax.amount if tax else 0.0),
                # Only one example value ("GS") is shown in Flick's docs, no enum list - see class
                # docstring. Defaulted here for every line pending clarification from Flick.
                'item_type': "GS",
                'line_total_including_vat': "%.2f" % line.price_total,
            }

        now = datetime.now(timezone.utc)
        return {
            'uuid': document.l10n_om_edi_uuid,
            'document_identifier': move.name,
            'issue_date': move.invoice_date.isoformat() if move.invoice_date else None,
            'issue_time': now.strftime('%H:%M:%S'),
            'due_date': move.invoice_date_due.isoformat() if move.invoice_date_due else None,
            'document_type': '381' if move.move_type == 'out_refund' else '380',
            'document_currency': move.currency_id.name,
            'transaction_type_code': '0' * 20,
            # Their written docs call this "sending_party", but every single live validation error
            # (from the very first rejection) referenced the seller side as "issuing_party" instead -
            # the live validator does not recognize "sending_party" at all, so it reported everything
            # under it as missing regardless of content. "receiving_party" (buyer) matches the docs.
            'issuing_party': _party(supplier),
            'receiving_party': _party(customer),
            'invoice_lines': [_invoice_line(index, line) for index, line in enumerate(lines, start=1)],
            'invoice_totals': {
                'line_extension_amount': "%.2f" % move.amount_untaxed,
                'tax_exclusive_amount': "%.2f" % move.amount_untaxed,
                'tax_inclusive_amount': "%.2f" % move.amount_total,
                'payable_amount': "%.2f" % move.amount_total,
            },
        }

    def _handle_submit_response(self, response):
        """ Flick reports both transport-level failures (4xx/5xx) and business-validation failures
        (a "failed" status in an otherwise-200 JSON body) - handled here rather than via the shared
        `_handle_response()` so validation errors can be surfaced field-by-field instead of collapsing
        into a generic "could not process this request" message. """
        if response.status_code in (401, 403):
            raise UserError(_(
                "Authentication with Flick Network failed. Please check the API credentials configured "
                "in Settings > Accounting > Oman E-Invoicing."
            ))
        try:
            payload = response.json()
        except ValueError:
            raise UserError(_(
                "Flick Network returned an unexpected (non-JSON) response (%(status)s) while "
                "submitting this invoice:\n%(body)s",
                status=response.status_code, body=response.text[:2000],
            ))
        if payload.get('status') != 'success':
            # Documented shape is {"data": {"errors": [{"field_name", "error_message", ...}, ...]}},
            # but the live sandbox's actual error responses have not been fully confirmed against
            # that shape - fall back to showing the raw payload rather than hiding it behind a
            # generic message, so a real rejection is always self-diagnosing from the Odoo UI alone.
            errors = (payload.get('data') or {}).get('errors') or payload.get('errors') or []
            if errors:
                details = '\n'.join('- %s' % self._format_flick_error(error) for error in errors)
                raise UserError(_(
                    "Flick Network rejected this invoice:\n%(details)s", details=details,
                ))
            message = payload.get('message') or (payload.get('data') or {}).get('message') or payload.get('error')
            raise UserError(_(
                "Flick Network rejected this invoice submission (%(status)s):\n%(body)s",
                status=response.status_code, body=message or response.text[:2000],
            ))
        # A real submission confirmed the tracking identifier is returned as `data.id`, not the
        # documented `data.document_id` - kept as a fallback in case a future API revision changes this.
        document_id = (payload.get('data') or {}).get('id') or (payload.get('data') or {}).get('document_id')
        if not document_id:
            raise UserError(_(
                "Flick Network accepted the submission but did not return a document_id to track it."
            ))
        return document_id

    @staticmethod
    def _format_flick_error(error):
        """ Format one entry of Flick's error list without assuming their documented key names
        ('field_name'/'error_message') are exactly what the live sandbox actually returns - try the
        documented names and a couple of plausible alternates first, falling back to the raw error
        object as JSON so nothing is ever hidden behind a generic "Unknown error". """
        if not isinstance(error, dict):
            return str(error)
        field = error.get('field_name') or error.get('field') or error.get('path')
        message = error.get('error_message') or error.get('message') or error.get('description')
        if field or message:
            return "%s: %s" % (field or '?', message or json.dumps(error))
        return json.dumps(error)

    def get_status(self, asp_reference):
        """ GET /v1/{participant_id}/documents/{document_id} - confirmed to reuse the same
        status/exchange_status/reporting_status envelope as the Submit Document response. """
        payload = self._request(
            'GET', f'/v1/{self.account_id}/documents/{asp_reference}',
            headers={'X-Flick-Auth-Key': self.api_key},
        )
        document = payload.get('data') or {}
        return {
            'processing': 'in_progress',
            'completed': 'accepted',
            'failed': 'rejected',
        }.get(document.get('status'), 'in_progress')

    def cancel(self, asp_reference, reason):
        raise UserError(_(
            "No cancellation-specific endpoint was found among Flick Network's documented operations "
            "(only 'Retry Document') - Oman/Peppol e-invoicing generally corrects via credit notes "
            "rather than true cancellation, which this module already supports separately. Confirm "
            "with Flick directly whether any cancel/void operation exists before implementing this."
        ))
