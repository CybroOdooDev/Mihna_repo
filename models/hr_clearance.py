# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrClearanceType(models.Model):
    _name = 'hr.clearance.type'
    _description = 'HR Clearance Type'

    name = fields.Char(string='Name', required=True)
    department_id = fields.Many2one('hr.department', string='Department')
    default_responsible_id = fields.Many2one('res.users', string='Default Responsible')


class HrClearanceTemplate(models.Model):
    _name = 'hr.clearance.template'
    _description = 'HR Clearance Template'

    name = fields.Char(string='Template Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    clearance_type_ids = fields.Many2many('hr.clearance.type', string='Clearance Types')


class HrResignationClearanceLine(models.Model):
    _name = 'hr.resignation.clearance.line'
    _description = 'Resignation Clearance Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    resignation_id = fields.Many2one('hr.resignation', string='Resignation', ondelete='cascade')
    clearance_type_id = fields.Many2one('hr.clearance.type', string='Clearance Type', required=True)
    department_id = fields.Many2one('hr.department', related='clearance_type_id.department_id', store=True)
    responsible_user_id = fields.Many2one('res.users', string='Responsible', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('cleared', 'Cleared'),
        ('blocked', 'Blocked')
    ], string='Status', default='pending', tracking=True)
    has_dues = fields.Boolean(string='Has Dues', compute='_compute_has_dues', store=True, tracking=True)
    due_amount = fields.Float(string='Due Amount', tracking=True)
    remarks = fields.Text(string='Remarks', tracking=True)
    cleared_date = fields.Datetime(string='Cleared Date')
    is_responsible = fields.Boolean(compute='_compute_is_responsible')

    @api.depends('due_amount')
    def _compute_has_dues(self):
        for rec in self:
            rec.has_dues = bool(rec.due_amount)

    @api.depends('responsible_user_id')
    def _compute_is_responsible(self):
        for rec in self:
            rec.is_responsible = (self.env.user == rec.responsible_user_id) or self.env.user.has_group('hr.group_hr_manager')

    def action_mark_cleared(self):
        for rec in self:
            rec.state = 'cleared'
            rec.cleared_date = fields.Datetime.now()
            # If all are cleared, we can trigger the resignation progress computation
            rec.resignation_id._compute_clearance_progress()

    def action_mark_blocked(self):
        for rec in self:
            rec.state = 'blocked'
