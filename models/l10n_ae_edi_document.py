# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class L10nAeEdiDocument(models.Model):
    """ Tracks the submission of one invoice/credit note to the UAE's e-invoicing 5-corner Peppol
    network through the company's configured Accredited Service Provider (ASP).

    Unlike a clearance model (e.g. Saudi ZATCA), the Federal Tax Authority does not validate/clear the
    invoice itself - Corner 2 (the supplier's ASP) reports Tax Data to Corner 5 (the FTA) and relays
    back a confirmation. `l10n_ae_edi_state` reflects that: 'accepted' means the ASP/FTA acknowledged
    the Tax Data report, not that the invoice content was "approved". """
    _name = 'l10n.ae.edi.document'
    _inherit = ['mail.thread', 'sequence.mixin']
    _description = "UAE E-Invoicing Document"
    _order = 'l10n_ae_edi_issuance_date desc, id desc'
    _check_company_auto = True
    _sequence_date_field = 'l10n_ae_edi_issuance_date'

    name = fields.Char(compute='_compute_name', store=True, copy=False, index='trigram')
    company_id = fields.Many2one(comodel_name='res.company', required=True, readonly=True,
                                  default=lambda self: self.env.company)
    move_id = fields.Many2one(comodel_name='account.move', string="Invoice/Credit Note", required=True,
                               readonly=True, index=True, check_company=True)
    l10n_ae_edi_issuance_date = fields.Date(related='move_id.invoice_date', store=True, readonly=True)

    # Fixed to 'outbound' for now: this module implements Corner 1 (issuing) only. Kept as an explicit
    # field, rather than assumed, so a future inbound (Corner 4, receiving) module can reuse this same
    # tracking model for inbound documents without an schema change to this one.
    direction = fields.Selection(
        selection=[('outbound', "Outbound"), ('inbound', "Inbound")],
        default='outbound',
        required=True,
        readonly=True,
    )

    l10n_ae_edi_state = fields.Selection(
        string="Submission State",
        selection=[
            ('to_send', "To Send"),
            ('in_progress', "Submission In Progress"),
            ('accepted', "Acknowledged"),
            ('rejected', "Rejected"),
            ('error', "Error"),
            ('cancelled', "Cancelled"),
        ],
        default='to_send',
        copy=False,
        readonly=True,
        tracking=True,
        help="'Acknowledged' means the ASP/Federal Tax Authority has acknowledged receipt of the Tax "
             "Data report - the UAE model has no separate invoice clearance/validation step.",
    )
    asp_reference = fields.Char(string="ASP Reference", copy=False, readonly=True,
                                 help="Reference assigned by the Accredited Service Provider to this submission.")
    error_message = fields.Text(string="Error Message", copy=False, readonly=True)
    retry_count = fields.Integer(default=0, copy=False, readonly=True)

    invoice_xml = fields.Binary(string="Invoice XML", copy=False, readonly=True, attachment=True,
                                 export_string_translation=False)
    invoice_xml_fname = fields.Char(compute='_compute_invoice_xml_fname')

    @api.depends('l10n_ae_edi_issuance_date')
    def _compute_name(self):
        """ Assign the next sequence number in `document.l10n_ae_edi_issuance_date`'s year, once that
        date is known and the document doesn't already hold a name matching it. """
        for document in self.sorted(key=lambda d: (d.l10n_ae_edi_issuance_date, d._origin.id)):
            document_has_name = document.name and document.name != '/'
            if document_has_name:
                if not document._sequence_matches_date():
                    document.name = False
                    continue
            if document.l10n_ae_edi_issuance_date and not document_has_name:
                document._set_next_sequence()
        self.filtered(lambda d: not d.name).name = '/'

    def _compute_invoice_xml_fname(self):
        """ Build the invoice XML attachment's filename from the linked move's name. """
        for document in self:
            document.invoice_xml_fname = document.move_id.name and f"{document.move_id.name.replace('/', '_')}_pint_ae.xml"

    def _get_starting_sequence(self):
        """ Return the first sequence value for a new year, e.g. "AEEDI/2026/00000". """
        self.ensure_one()
        return "AEEDI/%04d/00000" % (self.l10n_ae_edi_issuance_date or fields.Date.context_today(self)).year

    def _get_last_sequence_domain(self, relaxed=False):
        """ Returns the SQL WHERE statement to use when fetching the latest record with the same
        sequence, and its params. Required override: the sequence.mixin base returns an empty ("",
        {}) domain, which is not valid SQL on its own. """
        self.ensure_one()
        if not self.l10n_ae_edi_issuance_date:
            return "WHERE FALSE", {}
        where_string = "WHERE name != '/'"
        param = {}

        if not relaxed:
            domain = [('id', '!=', self.id or self._origin.id), ('name', 'not in', ('/', '', False))]
            reference_name = self.sudo().search(domain + [('l10n_ae_edi_issuance_date', '<=', self.l10n_ae_edi_issuance_date)], limit=1).name
            if not reference_name:
                reference_name = self.sudo().search(domain, order='l10n_ae_edi_issuance_date asc', limit=1).name
            sequence_number_reset = self._deduce_sequence_number_reset(reference_name)
            date_start, date_end, *_ = self._get_sequence_date_range(sequence_number_reset)
            where_string += " AND l10n_ae_edi_issuance_date BETWEEN %(date_start)s AND %(date_end)s"
            param['date_start'] = date_start
            param['date_end'] = date_end

        return where_string, param

    # -------------------------------------------------------------------------
    # XML generation
    # -------------------------------------------------------------------------

    def _generate_invoice_xml(self):
        """ Generate the PINT AE Invoice/CreditNote XML for `self.move_id` (Corners 1-4). """
        self.ensure_one()
        builder = self.env['account.edi.xml.pint_ae']
        xml_content, errors = builder._export_invoice(self.move_id)
        if errors:
            raise UserError(_("Could not generate the PINT AE invoice XML:\n%s", '\n'.join(errors)))
        self.invoice_xml = base64.b64encode(xml_content)
        return xml_content

    # -------------------------------------------------------------------------
    # Submission
    # -------------------------------------------------------------------------

    def action_retry_submission(self):
        """ Public wrapper around `_action_submit`, callable from view buttons. """
        self._action_submit()

    def _action_submit(self):
        """ Submit the invoice XML to the company's configured ASP. """
        for document in self:
            try:
                invoice_xml = document._generate_invoice_xml()
                connector = document.company_id._l10n_ae_edi_get_connector()
                reference = connector.submit_invoice(invoice_xml)
            except UserError as e:
                document.l10n_ae_edi_state = 'error'
                document.error_message = str(e)
                document.retry_count += 1
                continue

            document.write({
                'l10n_ae_edi_state': 'in_progress',
                'asp_reference': reference,
                'error_message': False,
            })

    def _cron_poll_submission_status(self):
        """ Poll the ASP for documents still 'in_progress'. Degrades to a no-op for companies without
        a configured connector, so this cron is safe to run even before an ASP is wired in. """
        documents = self.search([
            ('direction', '=', 'outbound'),
            ('l10n_ae_edi_state', '=', 'in_progress'),
            ('asp_reference', '!=', False),
        ])
        for company, company_documents in documents.grouped('company_id').items():
            if not company.l10n_ae_edi_asp_provider:
                continue
            connector = company._l10n_ae_edi_get_connector()
            for document in company_documents:
                try:
                    state = connector.get_status(document.asp_reference)
                except UserError as e:
                    _logger.warning("Error polling UAE e-invoicing status for %s: %s", document.name, e)
                    continue
                if state in dict(self._fields['l10n_ae_edi_state'].selection):
                    document.l10n_ae_edi_state = state
