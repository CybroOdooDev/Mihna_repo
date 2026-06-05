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
                mrr_trend: 0,
                arr: 0,
                arr_trend: 0,
                active_subscriptions: 0,
                active_trend: 0,
                churn_rate: 0,
                churn_trend: 0,
                arpu: 0,
                forecast_revenue: 0,
            },
            charts: {
                revenue_breakdown: [],
                plan_distribution: [],
                new_vs_churned: []
            },
            widgets: {
                upcoming_renewals: [],
                recent_activity: [],
                top_customers: [],
                recent_payments: [],
                recovery_rate: 0
            },
            nav_counts: {
                subscriptions: 0,
                customers: 0,
                invoices: 0,
                dunning: 0
            },
            activeFilter: 'YTD',
            user_name: '',
            error: null,
            isLoading: true
        });
        
        this.chartInstances = {};
        
        // Chart Refs
        this.revenueBreakdownChartRef = useRef("revenueBreakdownChart");
        this.mrrDistributionChartRef = useRef("mrrDistributionChart");
        this.newVsChurnedChartRef = useRef("newVsChurnedChart");
        this.recoveryRateChartRef = useRef("recoveryRateChart");

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });

        onMounted(() => {
            this.processData();
            this.renderCharts();
        });
    }

    async fetchData() {
        try {
            const result = await this.orm.call("subscription.dashboard", "get_dashboard_data", [this.state.activeFilter]);
            if (result.error) {
                this.state.error = result.error;
                this.state.isLoading = false;
                return;
            }
            this.state.kpi = result.kpi;
            this.state.charts = result.charts;
            this.state.widgets = result.widgets;
            this.state.nav_counts = result.nav_counts;
            this.state.user_name = result.user_name;
            this.state.isLoading = false;
        } catch (error) {
            console.error("Error fetching dashboard data:", error);
        }
    }

    async setFilter(filter) {
        this.state.activeFilter = filter;
        // Don't set isLoading=true here to prevent OWL from destroying the canvas elements from the DOM
        await this.fetchData();
        this.processData();
        if (window.Chart) {
            // Give OWL a tick to patch any DOM changes before re-rendering charts
            setTimeout(() => {
                this.renderCharts();
            }, 10);
        }
    }

    openGlobalFilters() {
        this.actionService.doAction("advanced_subscription_management.action_subscription_subscriptions", {
            additionalContext: {
                search_default_in_progress: 1
            }
        });
    }

    processData() {
        if (!this.state.charts) return;
        
        // Add Cadence colors to plan distribution for custom HTML legend
        const colors = ['#C24A2A', '#207361', '#774B5C', '#AD7A1D', '#3B4E6B'];
        if (this.state.charts.plan_distribution) {
            this.state.charts.plan_distribution.forEach((plan, i) => {
                plan.color = colors[i % colors.length];
            });
        }
        
        // Calculate percentages for top customers horizontal bar
        if (this.state.widgets.top_customers && this.state.widgets.top_customers.length > 0) {
            const maxAmount = Math.max(...this.state.widgets.top_customers.map(c => c.amount));
            this.state.widgets.top_customers.forEach(cust => {
                cust.percent = maxAmount > 0 ? (cust.amount / maxAmount) * 100 : 0;
            });
        }
    }

    renderCharts() {
        if (!this.state.charts || !window.Chart) return;

        // Global Chart Defaults for Cadence Aesthetic
        window.Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
        window.Chart.defaults.color = '#888888';
        
        // 1. Revenue Breakdown (Area Chart)
        if (this.revenueBreakdownChartRef.el && this.state.charts.revenue_breakdown) {
            if (this.chartInstances.revenueBreakdown) {
                this.chartInstances.revenueBreakdown.destroy();
            }
            const ctx = this.revenueBreakdownChartRef.el.getContext('2d');
            const data = this.state.charts.revenue_breakdown;
            
            this.chartInstances.revenueBreakdown = new window.Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => d.label),
                    datasets: [
                        {
                            label: 'Existing MRR',
                            data: data.map(d => d.existing),
                            backgroundColor: '#e6ccc6',
                            borderColor: '#B84022',
                            borderWidth: 2,
                            fill: 'origin',
                            pointRadius: 0,
                            pointHoverRadius: 4
                        },
                        {
                            label: 'New business',
                            data: data.map(d => d.new),
                            backgroundColor: '#c7d9d1',
                            borderColor: '#196150',
                            borderWidth: 2,
                            fill: '-1',
                            pointRadius: 0,
                            pointHoverRadius: 4
                        },
                        {
                            label: 'Expansion',
                            data: data.map(d => d.expansion),
                            backgroundColor: '#e0cda8',
                            borderColor: '#9E6C14',
                            borderWidth: 2,
                            fill: '-1',
                            pointRadius: 0,
                            pointHoverRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { 
                        legend: { 
                            position: 'bottom',
                            align: 'start',
                            labels: { 
                                boxWidth: 12,
                                boxHeight: 12,
                                usePointStyle: true,
                                pointStyle: 'rect',
                                padding: 20,
                                color: '#666666'
                            }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(255,255,255,0.95)',
                            titleColor: '#000',
                            bodyColor: '#333',
                            borderColor: '#eee',
                            borderWidth: 1
                        }
                    },
                    scales: {
                        x: { 
                            grid: { display: false },
                            stacked: true,
                            ticks: { maxTicksLimit: 6 }
                        },
                        y: { 
                            stacked: true,
                            beginAtZero: true,
                            grid: { borderDashOffset: [0], color: '#f5f5f5', drawBorder: false },
                            ticks: {
                                callback: function(value) { return '$' + (value/1000) + 'K'; },
                                maxTicksLimit: 5
                            }
                        }
                    }
                }
            });
        }

        // 2. MRR Distribution (Doughnut)
        if (this.mrrDistributionChartRef.el && this.state.charts.plan_distribution) {
            if (this.chartInstances.mrrDistribution) {
                this.chartInstances.mrrDistribution.destroy();
            }
            const ctx = this.mrrDistributionChartRef.el.getContext('2d');
            const data = this.state.charts.plan_distribution;
            
            this.chartInstances.mrrDistribution = new window.Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.map(d => d.label),
                    datasets: [{
                        data: data.map(d => d.value),
                        backgroundColor: data.map(d => d.color),
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '75%',
                    plugins: {
                        legend: { display: false }, // Using custom HTML legend in XML
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return ' $' + context.parsed.toLocaleString('en-US');
                                }
                            }
                        }
                    }
                }
            });
        }

        // 3. New vs Churned (Bar Chart)
        if (this.newVsChurnedChartRef.el && this.state.charts.new_vs_churned) {
            if (this.chartInstances.newVsChurned) {
                this.chartInstances.newVsChurned.destroy();
            }
            const ctx = this.newVsChurnedChartRef.el.getContext('2d');
            const data = this.state.charts.new_vs_churned;
            
            this.chartInstances.newVsChurned = new window.Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.label),
                    datasets: [
                        {
                            label: 'New',
                            data: data.map(d => d.new),
                            backgroundColor: '#207361', // Cadence Green
                            borderRadius: 0,
                            barPercentage: 0.5
                        },
                        {
                            label: 'Churned',
                            data: data.map(d => d.churned), // Values are negative
                            backgroundColor: '#C24A2A', // Cadence Red
                            borderRadius: 0,
                            barPercentage: 0.5
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + Math.abs(context.parsed.y);
                                }
                            }
                        }
                    },
                    scales: {
                        x: { 
                            stacked: true,
                            grid: { display: false }
                        },
                        y: { 
                            stacked: true,
                            grid: { color: '#f5f5f5', drawBorder: false },
                            ticks: {
                                callback: function(value) { return Math.abs(value); },
                                maxTicksLimit: 5
                            }
                        }
                    }
                }
            });
        }

        // 4. Recovery Rate (Doughnut)
        if (this.recoveryRateChartRef.el) {
            if (this.chartInstances.recoveryRate) {
                this.chartInstances.recoveryRate.destroy();
            }
            const ctx = this.recoveryRateChartRef.el.getContext('2d');
            const rate = (this.state.widgets.recovery_details && this.state.widgets.recovery_details.rate) || 0;
            
            this.chartInstances.recoveryRate = new window.Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Recovered', 'Lost'],
                    datasets: [{
                        data: [rate, 100 - rate],
                        backgroundColor: ['#3C5846', '#F3EFE9'], 
                        borderWidth: 0,
                        borderRadius: 20
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '80%',
                    rotation: -90,
                    circumference: 180, // Half doughnut effect
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false }
                    }
                }
            });
        }
    }
    
    openSubscriptions() {
        this.actionService.doAction("advanced_subscription_management.action_subscription_subscriptions", {
            additionalContext: {
                search_default_in_progress: 1,
            }
        });
    }

    openRecentActivity() {
        this.actionService.doAction("advanced_subscription_management.action_subscription_subscriptions");
    }

    actionViewCustomers() {
        this.actionService.doAction("advanced_subscription_management.action_subscription_customers");
    }

    openCustomers() {
        this.actionService.doAction("advanced_subscription_management.action_subscription_customers");
    }

    openInvoices() {
        this.actionService.doAction("account.action_move_out_invoice_type");
    }

    openPlans() {
        this.actionService.doAction("advanced_subscription_management.action_subscription_plan");
    }

    actionNewSubscription() {
        this.actionService.doAction("advanced_subscription_management.action_new_subscription");
    }

    exportDashboard() {
        window.print();
    }

    openDunningQueue() {
        this.actionService.doAction("advanced_subscription_management.action_subscription_dunning_queue_list");
    }

    openDunningSettings() {
        this.actionService.doAction("advanced_subscription_management.action_subscription_dunning_plan");
    }
}

SubscriptionDashboard.template = "advanced_subscription_management.Dashboard";

registry.category("actions").add("subscription_dashboard_action", SubscriptionDashboard);
