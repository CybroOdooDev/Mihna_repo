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
                total_customers: 0,
                mrr: 0,
                arr: 0,
                active_subscriptions: 0,
                churn_rate: 0,
                arpu: 0,
                forecast_revenue: 0,
            },
            charts: null,
            widgets: {
                upcoming_renewals: [],
                recent_activity: [],
                top_customers: [],
                recent_payments: []
            },
            user_name: '',
            error: null,
            isLoading: true
        });
        
        this.mrrChartRef = useRef("mrrChart");
        
        // Sparkline Refs
        this.sparkMrrRef = useRef("sparkMrr");
        this.sparkArrRef = useRef("sparkArr");
        this.sparkActiveRef = useRef("sparkActive");
        this.sparkChurnRef = useRef("sparkChurn");
        this.sparkArpuRef = useRef("sparkArpu");

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
            if (result.error) {
                this.state.error = result.error;
                this.state.isLoading = false;
                return;
            }
            this.state.kpi = result.kpi;
            this.state.charts = result.charts;
            this.state.widgets = result.widgets;
            this.state.user_name = result.user_name;
            this.state.isLoading = false;
        } catch (error) {
            console.error("Error fetching dashboard data:", error);
        }
    }

    renderCharts() {
        if (!this.state.charts || !window.Chart) return;

        // MRR Growth Line Chart
        if (this.mrrChartRef.el) {
            const ctx = this.mrrChartRef.el.getContext('2d');
            let gradient = ctx.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
            gradient.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

            new window.Chart(ctx, {
                type: 'line',
                data: {
                    labels: this.state.charts.mrr_growth.map(d => d.label),
                    datasets: [{
                        label: 'MRR Growth ($)',
                        data: this.state.charts.mrr_growth.map(d => d.value),
                        borderColor: '#6366f1',
                        backgroundColor: gradient,
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#ffffff',
                        pointBorderColor: '#6366f1',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { 
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: '#111827',
                            padding: 12,
                            titleFont: { size: 13, family: 'Inter' },
                            bodyFont: { size: 14, family: 'Inter', weight: 'bold' },
                            displayColors: false,
                            callbacks: {
                                label: function(context) {
                                    return '$' + context.parsed.y;
                                }
                            }
                        }
                    },
                    scales: {
                        y: { 
                            beginAtZero: true, 
                            grid: { color: 'rgba(0,0,0,0.04)', drawBorder: false },
                            ticks: { callback: function(value) { return '$' + value; }, font: { family: 'Inter' } }
                        },
                        x: { 
                            grid: { display: false, drawBorder: false },
                            ticks: { font: { family: 'Inter' } }
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index',
                    },
                }
            });
        }

        // Helper to render sparklines
        const renderSparkline = (ref, data, color) => {
            if (ref.el) {
                new window.Chart(ref.el, {
                    type: 'line',
                    data: {
                        labels: ['1', '2', '3', '4', '5', '6', '7'],
                        datasets: [{
                            data: data,
                            borderColor: color,
                            borderWidth: 2,
                            tension: 0.4,
                            pointRadius: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false }, tooltip: { enabled: false } },
                        scales: { x: { display: false }, y: { display: false } },
                        animation: { duration: 1000 }
                    }
                });
            }
        };

        renderSparkline(this.sparkMrrRef, this.state.kpi.mrr_sparkline, '#4F46E5');
        renderSparkline(this.sparkArrRef, this.state.kpi.arr_sparkline, '#16A34A');
        renderSparkline(this.sparkActiveRef, this.state.kpi.active_sparkline, '#0284C7');
        renderSparkline(this.sparkChurnRef, this.state.kpi.churn_sparkline, '#DC2626');
        renderSparkline(this.sparkArpuRef, this.state.kpi.arpu_sparkline, '#D97706');
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

    actionCreateSubscription() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Create Subscription",
            res_model: "sale.order",
            views: [[false, "form"]],
            context: { 'default_plan_id': true }
        });
    }

    actionManagePlans() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Subscription Plans",
            res_model: "subscription.plan",
            views: [[false, "list"], [false, "form"]],
        });
    }

    actionViewCustomers() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Customers",
            res_model: "res.partner",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain: [['customer_rank', '>', 0]]
        });
    }

    actionGenerateInvoices() {
        // Simple quick link to out_invoices
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Invoices",
            res_model: "account.move",
            views: [[false, "list"], [false, "form"]],
            domain: [['move_type', '=', 'out_invoice']]
        });
    }

    actionRevenueReports() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "MRR Analysis",
            res_model: "subscription.mrr.analysis",
            views: [[false, "graph"], [false, "pivot"]],
        });
    }

    actionAddCustomer() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "New Customer",
            res_model: "res.partner",
            views: [[false, "form"]],
            context: { 'default_customer_rank': 1 }
        });
    }
}

SubscriptionDashboard.template = "subscription_management.Dashboard";

registry.category("actions").add("subscription_dashboard_action", SubscriptionDashboard);
