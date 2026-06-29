# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from odoo import fields

class TestHrResignation(TransactionCase):

    def setUp(self):
        super(TestHrResignation, self).setUp()
        
        self.company = self.env.company
        
        self.manager_user = self.env['res.users'].create({
            'name': 'Manager User',
            'login': 'manager_user',
        })
        
        self.manager = self.env['hr.employee'].create({
            'name': 'Test Manager',
            'user_id': self.manager_user.id
        })
        
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'joining_date': date.today() - timedelta(days=365),
            'parent_id': self.manager.id,
        })
        
        self.contract = self.env['hr.version'].create({
            'name': 'Test Contract',
            'employee_id': self.employee.id,
            'date_start': date.today() - timedelta(days=365),
            'notice_days': 30,
        })
        
        self.clearance_type_it = self.env['hr.clearance.type'].create({
            'name': 'IT',
            'default_responsible_id': self.manager_user.id,
        })
        self.clearance_type_hr = self.env['hr.clearance.type'].create({
            'name': 'HR',
            'default_responsible_id': self.env.user.id,
        })
        self.clearance_template = self.env['hr.clearance.template'].create({
            'name': 'Default Template',
            'clearance_type_ids': [(4, self.clearance_type_it.id), (4, self.clearance_type_hr.id)],
        })
        self.company.clearance_template_id = self.clearance_template.id

        if not self.env['hr.departure.reason'].search([('name', '=', 'Resigned')]):
            self.env['hr.departure.reason'].create({'name': 'Resigned'})
        if not self.env['hr.departure.reason'].search([('name', '=', 'Fired')]):
            self.env['hr.departure.reason'].create({'name': 'Fired'})
        
        self.departure_resigned = self.env['hr.departure.reason'].search([('name', '=', 'Resigned')], limit=1)

    def test_01_resignation_flow_manager_approval(self):
        self.company.enable_manager_approval = True
        
        resignation = self.env['hr.resignation'].create({
            'employee_id': self.employee.id,
            'expected_revealing_date': date.today() + timedelta(days=30),
            'reason': 'Better Opportunity',
            'reason_category_id': self.departure_resigned.id,
        })
        
        self.assertEqual(resignation.state, 'draft')
        
        # Confirm Resignation
        resignation.action_confirm_resignation()
        self.assertEqual(resignation.state, 'confirm')
        
        # Manager Approve
        resignation.action_manager_approve()
        self.assertEqual(resignation.state, 'manager_approved')
        
        # HR Approve
        resignation.action_approve_resignation()
        self.assertEqual(resignation.state, 'clearance')
        
        # Check clearance lines created
        self.assertEqual(len(resignation.clearance_line_ids), 2)
        
        # Check progress
        self.assertEqual(resignation.clearance_progress, 0.0)
        
        # Settle Clearance
        for line in resignation.clearance_line_ids:
            line.action_mark_cleared()
            
        self.assertEqual(resignation.clearance_progress, 100.0)
        
        # Settlement
        resignation.pending_salary = 1000
        resignation.action_compute_settlement()
        self.assertEqual(resignation.settlement_state, 'computed')
        
        resignation.action_approve_settlement()
        self.assertEqual(resignation.state, 'settlement')
        self.assertEqual(resignation.settlement_state, 'approved')
        self.assertTrue(resignation.payslip_id)
        
        # Relieve
        resignation.action_relieve()
        self.assertEqual(resignation.state, 'relieved')
        self.assertFalse(self.employee.active)

    def test_02_resignation_flow_no_manager_approval(self):
        self.company.enable_manager_approval = False
        
        resignation = self.env['hr.resignation'].create({
            'employee_id': self.employee.id,
            'expected_revealing_date': date.today() + timedelta(days=30),
            'reason': 'Personal Reasons',
            'reason_category_id': self.departure_resigned.id,
        })
        
        resignation.action_confirm_resignation()
        self.assertEqual(resignation.state, 'manager_approved')

    def test_03_custody_integration(self):
        property = self.env['custody.property'].create({'name': 'Laptop CR0015'})
        
        custody = self.env['hr.custody'].create({
            'employee_id': self.employee.id,
            'custody_property_id': property.id,
            'purpose': 'Work',
            'return_date': date.today() + timedelta(days=365),
        })
        custody.action_approve()
        
        resignation = self.env['hr.resignation'].create({
            'employee_id': self.employee.id,
            'expected_revealing_date': date.today() + timedelta(days=30),
            'reason': 'Moving',
            'reason_category_id': self.departure_resigned.id,
        })
        
        resignation.action_confirm_resignation()
        resignation.action_manager_approve()
        resignation.action_approve_resignation()
        
        admin_line = resignation.clearance_line_ids.filtered(lambda l: l.clearance_type_id.name == 'IT')
        self.assertEqual(admin_line.state, 'blocked')
        self.assertIn('Pending return', admin_line.remarks)
