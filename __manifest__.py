# -*- coding: utf-8 -*-
{
    'name': "UAE E-Invoicing - Aigentrix",
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': "Submit UAE Peppol e-invoices and credit notes to the Aigentrix External Gateway, "
               "with validation and status tracking",
    'description': """
    UAE E-Invoicing - Aigentrix
    ============================

    A standalone connector to the Aigentrix E-Invoice External Gateway (X-API-KEY auth, base
    port 8095) for UAE Peppol e-invoicing, built strictly against the "Aigentrix E-Invoice API -
    External Gateway Reference Guide":

    * Builds the documented EInvoiceCreateRequestDTO JSON payload directly from the customer
      invoice/credit note already in Odoo (header, line items, and - where a credit-transfer bank
      account is set - payment means) and submits it via POST /eInvoiceEntry/createFull.
    * Pre-flight validation via POST /eInvoiceEntry/validate (no database write on the Aigentrix
      side) before committing.
    * Tracks each submission as its own document record, refreshed from GET /eInvoiceEntry/{id}
      with the exact EInvoiceEntryStatus/EInvoiceEntryTaxStatus values the API returns - not
      remapped to a local vocabulary.
    * Status timeline (GET .../statusTimeline), stored validation errors
      (GET .../validationErrors), advancing an entry to SUBMITTED (PUT .../{id}), deleting an
      entry (DELETE /eInvoiceEntry), and downloading the Peppol PDF/raw XML
      (GET /print/xml/{id}, GET /print/orgxml/{id}).

    SCOPE: this covers the per-invoice JSON flow only (Sections 4.1, 4.2, 4.4-4.8, 4.12, 4.15 of
    the API guide). The bulk Excel upload/template/error-log endpoints (4.9-4.11, 4.13-4.14) and
    the Peppol raw/multipart-XML endpoints (4.16-4.17) are not implemented - this module always
    submits invoices that already exist in Odoo one at a time via the documented JSON endpoints,
    so the Excel-bulk-import and externally-built-XML endpoints are out of scope here.

    Every request/response field name, endpoint path, enum value, and validation rule used by
    this module is taken directly from the API guide and the accompanying Postman collection -
    nothing is invented. Where the guide has no corresponding Odoo field (e.g. the Peppol VAT
    category S/Z/E/O per tax, or delivery/tax-representative details), this module adds an
    explicit configuration field for the accountant to fill in, rather than guessing.

    On install, this module also creates a ready-to-use "UAE Company (Aigentrix)" company
    (country United Arab Emirates, a sample VAT/TRN, added to the Administrator's allowed
    companies) purely so the module can be tried out immediately - the Aigentrix API
    Key/Base URL/Company ID/Peppol Participant ID still have to be entered by hand under that
    company's "Aigentrix E-Invoice" tab, since those are real credentials this module has no way
    to know in advance. Delete or repurpose that company for a production deployment.
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'data/res_company_data.xml',
        'views/l10n_ae_aigentrix_document_views.xml',
        'views/account_move_views.xml',
        'views/account_tax_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
