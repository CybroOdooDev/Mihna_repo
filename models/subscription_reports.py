# -*- coding: utf-8 -*-
from odoo import models, fields


# Shared MRR formula snippet (used as a Python f-string fragment in SQL)
MRR_EXPR = """
    CASE
        WHEN p.billing_period = 'daily'        THEN (l.price_unit * l.product_uom_qty * (1.0 - COALESCE(l.discount, 0.0) / 100.0)) * 30.0
        WHEN p.billing_period = 'weekly'       THEN (l.price_unit * l.product_uom_qty * (1.0 - COALESCE(l.discount, 0.0) / 100.0)) * 4.33
        WHEN p.billing_period = 'monthly'      THEN (l.price_unit * l.product_uom_qty * (1.0 - COALESCE(l.discount, 0.0) / 100.0))
        WHEN p.billing_period = 'quarterly'    THEN (l.price_unit * l.product_uom_qty * (1.0 - COALESCE(l.discount, 0.0) / 100.0)) / 3.0
        WHEN p.billing_period = 'semi_annually'THEN (l.price_unit * l.product_uom_qty * (1.0 - COALESCE(l.discount, 0.0) / 100.0)) / 6.0
        WHEN p.billing_period = 'yearly'       THEN (l.price_unit * l.product_uom_qty * (1.0 - COALESCE(l.discount, 0.0) / 100.0)) / 12.0
        WHEN p.billing_period = 'custom' AND p.custom_days > 0
                                               THEN (l.price_unit * l.product_uom_qty * (1.0 - COALESCE(l.discount, 0.0) / 100.0)) * (30.0 / p.custom_days)
        ELSE (l.price_unit * l.product_uom_qty * (1.0 - COALESCE(l.discount, 0.0) / 100.0))
    END
"""


class SubscriptionMrrBreakdown(models.Model):
    """MRR Breakdown Report: classifies MRR changes as New (activation) or Churn (cancellation)."""
    _name = 'subscription.mrr.breakdown'
    _description = 'MRR Breakdown Report'
    _auto = False
    _order = 'event_date asc'

    event_date = fields.Date(string='Event Date', readonly=True)
    event_type = fields.Selection([
        ('new', 'New'),
        ('churn', 'Churn'),
    ], string='Event Type', readonly=True)
    mrr_change = fields.Float(string='MRR Change', readonly=True)
    new_mrr = fields.Float(string='New MRR', readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    def init(self):
        """Create live SQL view for MRR Breakdown from real subscription data."""
        from odoo.tools import drop_view_if_exists
        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'DROP TABLE IF EXISTS {self._table} CASCADE')

        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                -- NEW MRR: from subscriptions that became active
                SELECT
                    l.id AS id,
                    DATE_TRUNC('month', so.date_order)::date AS event_date,
                    'new' AS event_type,
                    ({MRR_EXPR}) AS mrr_change,
                    ({MRR_EXPR}) AS new_mrr,
                    so.id AS sale_order_id,
                    so.user_id AS user_id,
                    so.team_id AS team_id,
                    so.company_id AS company_id,
                    so.currency_id AS currency_id
                FROM sale_order_line l
                JOIN sale_order so ON so.id = l.order_id
                JOIN product_product pp ON pp.id = l.product_id
                JOIN product_template t ON t.id = pp.product_tmpl_id
                JOIN subscription_plan p ON p.id = so.plan_id
                WHERE so.date_order IS NOT NULL
                  AND t.recurring_ok = true
                  AND so.subscription_state NOT IN ('1_draft')

                UNION ALL

                -- CHURN MRR: from subscriptions that were cancelled (negative value)
                SELECT
                    l.id + 10000000 AS id,
                    DATE_TRUNC('month', COALESCE(so.write_date, so.date_order))::date AS event_date,
                    'churn' AS event_type,
                    -({MRR_EXPR}) AS mrr_change,
                    0.0 AS new_mrr,
                    so.id AS sale_order_id,
                    so.user_id AS user_id,
                    so.team_id AS team_id,
                    so.company_id AS company_id,
                    so.currency_id AS currency_id
                FROM sale_order_line l
                JOIN sale_order so ON so.id = l.order_id
                JOIN product_product pp ON pp.id = l.product_id
                JOIN product_template t ON t.id = pp.product_tmpl_id
                JOIN subscription_plan p ON p.id = so.plan_id
                WHERE so.subscription_state = '6_churn'
                  AND t.recurring_ok = true
            )
        """)


class SubscriptionMrrAnalysis(models.Model):
    """MRR Timeline: cumulative Monthly Recurring Revenue growth over time."""
    _name = 'subscription.mrr.analysis'
    _description = 'MRR Analysis Report'
    _auto = False
    _order = 'date asc'

    date = fields.Date(string='Date', readonly=True)
    mrr_change = fields.Float(string='Cumulative MRR', readonly=True)

    def init(self):
        """Create live SQL view for cumulative MRR Timeline from real subscription data."""
        from odoo.tools import drop_view_if_exists
        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'DROP TABLE IF EXISTS {self._table} CASCADE')

        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY month_date) AS id,
                    month_date AS date,
                    SUM(monthly_mrr) OVER (ORDER BY month_date) AS mrr_change
                FROM (
                    SELECT
                        DATE_TRUNC('month', so.date_order)::date AS month_date,
                        SUM({MRR_EXPR}) AS monthly_mrr
                    FROM sale_order_line l
                    JOIN sale_order so ON so.id = l.order_id
                    JOIN product_product pp ON pp.id = l.product_id
                    JOIN product_template t ON t.id = pp.product_tmpl_id
                    JOIN subscription_plan p ON p.id = so.plan_id
                    WHERE so.date_order IS NOT NULL
                      AND t.recurring_ok = true
                      AND so.subscription_state NOT IN ('1_draft')
                    GROUP BY DATE_TRUNC('month', so.date_order)
                ) monthly_totals
            )
        """)


class SubscriptionAnalysisReport(models.Model):
    """Subscription Analysis Report: per-line view of all active subscription revenue."""
    _name = 'subscription.analysis.report'
    _description = 'Subscriptions Analysis Report'
    _auto = False

    name = fields.Char(string='Order Reference', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    plan_id = fields.Many2one('subscription.plan', string='Subscription Template', readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    monthly_recurring = fields.Float(string='Monthly Recurring', readonly=True)
    state = fields.Selection([
        ('1_draft', 'Draft'),
        ('2_renewal', 'Renewal'),
        ('3_progress', 'In Progress'),
        ('4_paused', 'Paused'),
        ('5_renewed', 'Renewed'),
        ('6_churn', 'Churned'),
        ('7_upsell', 'Upsell'),
    ], string='Subscription State', readonly=True)
    is_recurring = fields.Boolean(string='Recurring', default=True, readonly=True)

    def init(self):
        """Create live SQL view for Subscriptions Analysis from real subscription data."""
        from odoo.tools import drop_view_if_exists
        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'DROP TABLE IF EXISTS {self._table} CASCADE')

        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    l.id                AS id,
                    so.name             AS name,
                    so.partner_id       AS partner_id,
                    t.categ_id          AS categ_id,
                    so.plan_id          AS plan_id,
                    so.user_id          AS user_id,
                    so.team_id          AS team_id,
                    so.company_id       AS company_id,
                    so.currency_id      AS currency_id,
                    so.subscription_state AS state,
                    true                AS is_recurring,
                    ({MRR_EXPR})        AS monthly_recurring
                FROM sale_order_line l
                JOIN sale_order so ON so.id = l.order_id
                JOIN product_product pp ON pp.id = l.product_id
                JOIN product_template t ON t.id = pp.product_tmpl_id
                JOIN subscription_plan p ON p.id = so.plan_id
                WHERE t.recurring_ok = true
                  AND so.subscription_state NOT IN ('1_draft', '6_churn')
            )
        """)


class SubscriptionRetentionAnalysis(models.Model):
    """Retention Analysis: cohort-based view showing how many customers remain active per start month."""
    _name = 'subscription.retention.analysis'
    _description = 'Retention Analysis'
    _auto = False
    _order = 'first_contract_date asc'

    first_contract_date = fields.Date(string='First Contract Date', readonly=True)
    count = fields.Integer(string='Total Subscribers', readonly=True)
    active_count = fields.Integer(string='Still Active', readonly=True)
    retention_rate = fields.Float(string='Retention Rate (%)', readonly=True)
    end_date_month = fields.Char(string='Cohort Month Offset', readonly=True)

    def init(self):
        """Create live SQL view for Retention Analysis from real subscription cohort data."""
        from odoo.tools import drop_view_if_exists
        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'DROP TABLE IF EXISTS {self._table} CASCADE')

        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY cohort_month) AS id,
                    cohort_month        AS first_contract_date,
                    total_count         AS count,
                    active_count        AS active_count,
                    ROUND(
                        CASE WHEN total_count > 0
                             THEN (active_count::numeric / total_count * 100.0)
                             ELSE 0.0
                        END, 2
                    )                   AS retention_rate,
                    '+0'                AS end_date_month
                FROM (
                    SELECT
                        DATE_TRUNC('month', so.date_order)::date AS cohort_month,
                        COUNT(*)                                 AS total_count,
                        COUNT(CASE WHEN so.subscription_state NOT IN ('6_churn') THEN 1 END) AS active_count
                    FROM sale_order so
                    WHERE so.date_order IS NOT NULL
                      AND so.subscription_state IS NOT NULL
                    GROUP BY DATE_TRUNC('month', so.date_order)
                ) cohorts
            )
        """)
