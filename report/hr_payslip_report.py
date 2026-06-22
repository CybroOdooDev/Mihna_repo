# -*- coding: utf-8 -*-
import time
from calendar import monthrange

from odoo import fields, models, tools


class HrPayslipReport(models.Model):
    """Create a new model for getting monthly report"""
    _name = 'hr.payslip.report'
    _auto = False

    now = fields.Date.today()
    month_day = monthrange(now.year, now.month)
    start_date = fields.Date(string="Start Date",
                             default=time.strftime('%Y-%m-01'),
                             help="Start Date for Report")
    end_date = fields.Date(string="End Date", default=time.strftime(
        '%Y-%m-' + str(month_day[1]) + ''),
                           help="End Date for Report")
    name = fields.Many2one('hr.employee', string='Employee',
                           help="Choose Employee")
    date_from = fields.Date(string='From', help="Starting Date for Report")
    date_to = fields.Date(string='To', help="Ending Date for Report")
    state = fields.Selection(
        [('draft', 'Draft'), ('verify', 'Waiting'), ('done', 'Done'),
         ('cancel', 'Rejected')],
        string='Status', help="Select Status for Report")
    job_id = fields.Many2one('hr.job', string='Job Title',
                             help="Choose Hr Job")
    company_id = fields.Many2one('res.company', string='Company',
                                 help="Choose Company")
    department_id = fields.Many2one('hr.department',
                                    string='Department',
                                    help="Choose Hr Department")
    rule_name_id = fields.Many2one('hr.salary.rule.category',
                                string="Rule Category",
                                help="Choose Salary Rule Category")
    rule_amount = fields.Float(string="Amount", help="Set Amount")
    struct_id = fields.Many2one('hr.payroll.structure',
                                string="Salary Structure",
                                help="Choose Hr Payroll Structure")
    rule_id = fields.Many2one('hr.salary.rule',
                              string="Salary Rule", help="Choose Salary Rule")

    def _select(self):
        select_str = """
            min(psl.id),ps.id,ps.number,emp.id as name,dp.id as 
            department_id,jb.id as job_id,cmp.id as company_id,ps.date_from, 
            ps.date_to, ps.state as state ,rl.id as rule_name_id, 
            psl.total as rule_amount,ps.struct_id as struct_id,rlu.id as rule_id
            """
        return select_str

    def _from(self):
        from_str = """
                hr_payslip_line psl
                join hr_payslip ps on ps.id=psl.slip_id
                join hr_salary_rule rlu on rlu.id = psl.salary_rule_id
                join hr_employee emp on ps.employee_id=emp.id
                left join hr_version ver on ver.id=ps.contract_id
                join hr_salary_rule_category rl on rl.id = psl.category_id
                left join hr_department dp on dp.id = ver.department_id
                left join hr_job jb on jb.id = ver.job_id
                join res_company cmp on cmp.id=ps.company_id
             """
        return from_str

    def _group_by(self):
        group_by_str = """group by ps.number,ps.id,emp.id,dp.id,jb.id,cmp.id,
        ps.date_from,ps.date_to,ps.state,
            psl.total,psl.name,psl.category_id,rl.id,rlu.id"""
        return group_by_str

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as ( SELECT
                   %s
                   FROM %s
                   %s
                   )""" % (
            self._table, self._select(), self._from(), self._group_by()))
