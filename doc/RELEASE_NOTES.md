## Module <l10n_om_convergex>

#### 01.10.2026
#### Version 19.0.1.1.0
#### UPDATE

- Aligned with Peppol PINT OM compliance:
  - Added 12-digit Oman HS Code (`item_classification_identifier` / IBT-158) on products and invoice lines.
  - Added 6-digit Oman ISIC Code (`industrial_classification_code` / BTOM-033) on company, products, and invoice lines.
  - Added UN/ECE Rec 20 Unit of Measure mapping (`unit_of_measure` / IBT-130).
- Fixed 404 non-JSON error during invoice / credit note submission by aligning with official ConvergeX Customer Master sync and create workflow (`POST /api/invoices/create/`).
- Added automatic resolution of `preceding_invoice_uuid` (BTOM-031) from compliance evidence for credit notes.
- Added recovery of internal invoice UUID in `_recover_existing_invoice`.

#### 14.08.2026
#### Version 19.0.1.0.0
#### ADD

- Initial commit for Oman E-Invoicing - ConvergeX

