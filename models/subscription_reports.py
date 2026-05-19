# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SubscriptionMrrBreakdown(models.Model):
    """MRR Breakdown Report model calculating and classifying recurring revenue fluctuations."""
    _name = 'subscription.mrr.breakdown'
    _description = 'MRR Breakdown Report'
    _order = 'event_date asc'

    event_date = fields.Date(string='Event Date')
    event_type = fields.Selection([
        ('new', 'New'),
        ('expansion', 'Expansion'),
        ('churn', 'Churn'),
        ('sum', 'Sum')
    ], string='Event Type')
    mrr_change = fields.Float(string='MRR Change')

    def init(self):
        """Initialize the MRR Breakdown table with enterprise mock dataset."""
        super().init()
        # Insert mock data if table is empty
        self.env.cr.execute("SELECT COUNT(*) FROM subscription_mrr_breakdown")
        if self.env.cr.fetchone()[0] == 0:
            query = """
                INSERT INTO subscription_mrr_breakdown (event_date, event_type, mrr_change) VALUES
                ('2026-01-01', 'new', 30.00),
                ('2026-02-01', 'new', 15.00),
                ('2026-02-01', 'expansion', 30.00),
                ('2026-03-01', 'new', 50.00),
                ('2026-04-01', 'churn', -15.00),
                ('2026-04-01', 'expansion', 40.00),
                ('2026-05-01', 'new', 40.00),
                ('2026-05-01', 'expansion', 40.00);
            """
            self.env.cr.execute(query)


class SubscriptionMrrAnalysis(models.Model):
    """MRR Analysis Report model tracking monthly recurring revenue progression."""
    _name = 'subscription.mrr.analysis'
    _description = 'MRR Analysis Report'
    _order = 'date asc'

    date = fields.Date(string='Date')
    mrr_change = fields.Float(string='MRR Change')

    def init(self):
        """Initialize the MRR Analysis table with enterprise mock dataset."""
        super().init()
        # Insert mock data if table is empty
        self.env.cr.execute("SELECT COUNT(*) FROM subscription_mrr_analysis")
        if self.env.cr.fetchone()[0] == 0:
            query = """
                INSERT INTO subscription_mrr_analysis (date, mrr_change) VALUES
                ('2026-01-01', 30.00),
                ('2026-02-01', 75.00),
                ('2026-03-01', 125.00),
                ('2026-04-01', 150.00),
                ('2026-05-01', 235.00);
            """
            self.env.cr.execute(query)


class SubscriptionAnalysisReport(models.Model):
    """Subscription Analysis Report model compiling total recurring contract valuations."""
    _name = 'subscription.analysis.report'
    _description = 'Subscriptions Analysis Report'

    monthly_recurring = fields.Float(string='Monthly Recurring')
    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('paused', 'Paused'),
    ], string='Status')
    is_recurring = fields.Boolean(string='Recurring', default=True)

    def init(self):
        """Initialize the Subscription Analysis table with enterprise mock dataset."""
        super().init()
        # Insert mock data if table is empty
        self.env.cr.execute("SELECT COUNT(*) FROM subscription_analysis_report")
        if self.env.cr.fetchone()[0] == 0:
            query = """
                INSERT INTO subscription_analysis_report (monthly_recurring, state, is_recurring) VALUES
                (1025.00, 'in_progress', true);
            """
            self.env.cr.execute(query)


class SubscriptionRetentionAnalysis(models.Model):
    """Subscription Retention Analysis model computing cohorts and customer churn rates."""
    _name = 'subscription.retention.analysis'
    _description = 'Retention Analysis'
    _order = 'first_contract_date asc'

    first_contract_date = fields.Date(string='First Contract Date')
    count = fields.Integer(string='Count')
    retention_rate = fields.Float(string='Retention Rate (%)')
    end_date_month = fields.Char(string='End Date - By Month')

    def init(self):
        """Initialize the Retention Analysis table with enterprise mock dataset."""
        super().init()
        # Insert mock data if table is empty
        self.env.cr.execute("SELECT COUNT(*) FROM subscription_retention_analysis")
        if self.env.cr.fetchone()[0] == 0:
            query = """
                INSERT INTO subscription_retention_analysis (first_contract_date, count, retention_rate, end_date_month) VALUES
                ('2026-05-01', 4, 75.0, '+0');
            """
            self.env.cr.execute(query)
