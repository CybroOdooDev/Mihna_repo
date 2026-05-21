/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

export class SubscriptionDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            kpi: {
                mrr: 0,
                arr: 0,
                active_subscriptions: 0,
                churn_rate: 0,
                arpu: 0
            },
            charts: null,
            isLoading: true
        });
        
        this.mrrChartRef = useRef("mrrChart");
        this.planChartRef = useRef("planChart");

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    async fetchData() {
        try {
            const result = await this.orm.call("subscription.dashboard", "get_dashboard_data", []);
            this.state.kpi = result.kpi;
            this.state.charts = result.charts;
            this.state.isLoading = false;
        } catch (error) {
            console.error("Error fetching dashboard data:", error);
        }
    }

    renderCharts() {
        if (!this.state.charts || !window.Chart) return;

        // MRR Growth Line Chart
        if (this.mrrChartRef.el) {
            new window.Chart(this.mrrChartRef.el, {
                type: 'line',
                data: {
                    labels: this.state.charts.mrr_growth.map(d => d.label),
                    datasets: [{
                        label: 'MRR Growth ($)',
                        data: this.state.charts.mrr_growth.map(d => d.value),
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
                        x: { grid: { display: false } }
                    }
                }
            });
        }

        // Plan Distribution Doughnut Chart
        if (this.planChartRef.el) {
            new window.Chart(this.planChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: this.state.charts.plan_distribution.map(d => d.label),
                    datasets: [{
                        data: this.state.charts.plan_distribution.map(d => d.value),
                        backgroundColor: ['#6366f1', '#a855f7', '#ec4899', '#3b82f6', '#10b981'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '75%',
                    plugins: {
                        legend: { position: 'right' }
                    }
                }
            });
        }
    }
    
    openSubscriptions() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Active Subscriptions",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: [['subscription_state', 'in', ['3_progress', '1_draft']]],
        });
    }
}

SubscriptionDashboard.template = "subscription_management.Dashboard";

registry.category("actions").add("subscription_dashboard_action", SubscriptionDashboard);
