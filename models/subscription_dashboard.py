# -*- coding: utf-8 -*-
from odoo import models, api, fields
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

class SubscriptionDashboard(models.AbstractModel):
    """Subscription Dashboard abstract model computing high-level MRR, ARR, and active KPI stats for visual charts."""
    _name = 'subscription.dashboard'
    _description = 'Subscription Dashboard Analytics'

    @api.model
    def get_dashboard_data(self):
        """Fetch and compute all key KPI metrics and chart distributions for the main dashboard widget."""
        # Active Subscriptions
        active_subs = self.env['subscription.subscription'].search([('state', 'in', ['in_progress', 'in_trial'])])
        
        # Calculate MRR using Odoo's native computed mrr field
        mrr = sum(active_subs.mapped('mrr'))
        
        arr = mrr * 12
        active_count = len(active_subs)
        arpu = mrr / active_count if active_count else 0.0

        # Calculate Churn Rate (closed/cancelled subs in last 30 days)
        thirty_days_ago = date.today() - timedelta(days=30)
        churned_subs = self.env['subscription.subscription'].search_count([
            ('state', 'in', ['closed', 'cancelled']),
            ('write_date', '>=', thirty_days_ago)
        ])
        
        total_subs_30d = active_count + churned_subs
        churn_rate = (churned_subs / total_subs_30d * 100) if total_subs_30d > 0 else 0.0
        
        # Chart data: Active subs by plan
        plans = self.env['subscription.plan'].search([])
        plan_distribution = []
        for plan in plans:
            count = self.env['subscription.subscription'].search_count([
                ('state', 'in', ['in_progress', 'in_trial']),
                ('plan_id', '=', plan.id)
            ])
            if count > 0:
                plan_distribution.append({
                    'label': plan.name,
                    'value': count
                })
                
        # Chart data: Recent MRR growth (last 6 months approximation)
        mrr_growth = []
        for i in range(5, -1, -1):
            month_date = date.today() - relativedelta(months=i)
            month_label = month_date.strftime("%b %Y")
            
            mrr_record = self.env['subscription.mrr.analysis'].search([
                ('date', '<=', month_date)
            ], order='date desc', limit=1)
            
            val = mrr_record.mrr_change if mrr_record else (mrr * (1 - (i*0.05)))
            
            mrr_growth.append({
                'label': month_label,
                'value': round(val, 2)
            })

        return {
            'kpi': {
                'mrr': round(mrr, 2),
                'arr': round(arr, 2),
                'active_subscriptions': active_count,
                'churn_rate': round(churn_rate, 2),
                'arpu': round(arpu, 2),
            },
            'charts': {
                'plan_distribution': plan_distribution,
                'mrr_growth': mrr_growth,
            }
        }
