# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_manager_approval = fields.Boolean(string="Enable Manager Approval for Resignation", default=True)
    clearance_template_id = fields.Many2one('hr.clearance.template', string="Default Clearance Template")

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_manager_approval = fields.Boolean(
        related='company_id.enable_manager_approval',
        readonly=False,
        string="Enable Manager Approval"
    )
    clearance_template_id = fields.Many2one(
        related='company_id.clearance_template_id',
        readonly=False,
        string="Default Clearance Template"
    )
