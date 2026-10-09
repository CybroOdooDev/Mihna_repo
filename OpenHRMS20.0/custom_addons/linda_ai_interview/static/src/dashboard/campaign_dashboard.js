import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { ChartCanvas, VIZ, axis } from "./chart_canvas";

const BAND_STATUS = { strong: "good", borderline: "warning", not_recommended: "critical" };
const RISK_STATUS = { low: "good", medium: "warning", high: "critical" };
const BAND_ICON = { strong: "fa-arrow-up", borderline: "fa-minus", not_recommended: "fa-arrow-down" };
const RISK_ICON = { low: "fa-check", medium: "fa-exclamation", high: "fa-exclamation-triangle" };

export class CompareDialog extends Component {
    static template = "linda_ai_interview.CompareDialog";
    static components = { Dialog };
    static props = { rows: Array, labels: Object, close: Function };

    get dims() {
        return Object.keys(this.props.labels.dimensions);
    }

    best(dim) {
        return Math.max(...this.props.rows.map((r) => r.scores[dim] || 0));
    }
}

export class CampaignDashboard extends Component {
    static template = "linda_ai_interview.CampaignDashboard";
    static components = { ChartCanvas };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        const params = this.props.action.params || {};
        this.state = useState({
            campaignId: params.campaign_id || this.props.action.context?.active_id || false,
            campaigns: [],
            data: null,
            sort: { key: "total", asc: false },
            filters: { band: "", state: "", risk: "", search: "" },
            selected: new Set(),
        });
        onWillStart(() => this.load());
    }

    async load() {
        if (!this.state.campaignId) {
            this.state.campaigns = await this.orm.searchRead("ai.interview.campaign", [],
                ["name", "job_id", "state", "invited_count", "submitted_count", "review_pending_count"],
                { order: "date_start desc" });
            return;
        }
        this.state.data = await this.orm.call("ai.interview.campaign", "get_dashboard_data", [this.state.campaignId]);
        this.state.selected = new Set();
    }

    async pickCampaign(id) {
        this.state.campaignId = id;
        await this.load();
    }

    async backToList() {
        this.state.campaignId = false;
        this.state.data = null;
        await this.load();
    }

    get labels() {
        return this.state.data.labels;
    }

    // ---------------- charts ----------------

    get funnel() {
        const f = this.state.data.funnel;
        const max = Math.max(1, f[0][1]);
        return f.map(([stage, n], i) => ({
            stage, n, pct: (100 * n) / max,
            drop: i > 0 && f[i - 1][1] ? Math.round(100 - (100 * n) / f[i - 1][1]) : null,
            color: VIZ.ordinal[Math.min(i, VIZ.ordinal.length - 1)],
        }));
    }

    split(obj, labels, statusMap, iconMap) {
        const total = Object.values(obj).reduce((a, b) => a + b, 0) || 1;
        return Object.entries(labels).map(([key, label]) => ({
            key, label, n: obj[key] || 0, pct: (100 * (obj[key] || 0)) / total,
            color: statusMap ? VIZ.status[statusMap[key]] : VIZ.series1, icon: iconMap ? iconMap[key] : "",
        }));
    }

    get bandSplit() {
        return this.split(this.state.data.bands, this.labels.bands, BAND_STATUS, BAND_ICON);
    }

    get riskSplit() {
        return this.split(this.state.data.risks, this.labels.risks, RISK_STATUS, RISK_ICON);
    }

    get languageSplit() {
        return this.split(this.state.data.languages, this.labels.languages);
    }

    get spreadConfig() {
        const dims = Object.keys(this.labels.dimensions);
        const spread = this.state.data.spread;
        return {
            type: "bar",
            data: {
                labels: dims.map((d) => `${this.labels.dimensions[d]} (avg ${spread[d].avg || "–"})`),
                datasets: [1, 2, 3, 4, 5].map((score) => ({
                    label: `Score ${score}`,
                    data: dims.map((d) => spread[d][String(score)] || 0),
                    backgroundColor: VIZ.score[score],
                    borderColor: "#fcfcfb",
                    borderWidth: 2,
                    borderSkipped: false,
                })),
            },
            options: {
                indexAxis: "y",
                scales: { x: axis({ stacked: true, ticks: { color: VIZ.muted, precision: 0 } }), y: axis({ stacked: true, grid: { display: false } }) },
                plugins: { tooltip: { mode: "index" } },
            },
        };
    }

    get dailyConfig() {
        const daily = this.state.data.daily;
        return {
            type: "line",
            data: {
                labels: daily.map((d) => d[0]),
                datasets: [{ label: _t("Completed interviews"), data: daily.map((d) => d[1]), borderColor: VIZ.series1,
                             backgroundColor: VIZ.series1, borderWidth: 2, pointRadius: 4, tension: 0 }],
            },
            options: {
                scales: { x: axis({ grid: { display: false } }), y: axis({ beginAtZero: true, ticks: { color: VIZ.muted, precision: 0 } }) },
                plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
                interaction: { mode: "index", intersect: false },
            },
        };
    }

    // ---------------- table ----------------

    get rows() {
        const { band, state, risk, search } = this.state.filters;
        let rows = this.state.data.candidates.filter((r) =>
            (!band || r.band === band) && (!state || r.state === state) && (!risk || r.risk === risk) &&
            (!search || (r.name || "").toLowerCase().includes(search.toLowerCase())));
        const { key, asc } = this.state.sort;
        const val = (r) => (key.startsWith("dim:") ? r.scores[key.slice(4)] : r[key]) ?? "";
        rows = [...rows].sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * (asc ? 1 : -1));
        return rows;
    }

    num(value) {
        return (value || 0).toLocaleString();
    }

    sortBy(key) {
        this.state.sort = { key, asc: this.state.sort.key === key ? !this.state.sort.asc : false };
    }

    sortIcon(key) {
        if (this.state.sort.key !== key) {
            return "";
        }
        return this.state.sort.asc ? "fa fa-caret-up" : "fa fa-caret-down";
    }

    toggle(id) {
        const sel = new Set(this.state.selected);
        sel.has(id) ? sel.delete(id) : sel.add(id);
        this.state.selected = sel;
    }

    toggleAll(ev) {
        this.state.selected = ev.target.checked ? new Set(this.rows.map((r) => r.id)) : new Set();
    }

    get selectedIds() {
        return [...this.state.selected];
    }

    bandColor(band) {
        return band ? VIZ.status[BAND_STATUS[band]] : "transparent";
    }

    riskColor(risk) {
        return risk ? VIZ.status[RISK_STATUS[risk]] : "transparent";
    }

    scoreClass(score) {
        if (!score) {
            return "text-muted";
        }
        return score <= 2 ? "o_linda_score_low" : score >= 4 ? "o_linda_score_high" : "";
    }

    // ---------------- actions ----------------

    openCandidate(row) {
        this.action.doAction({
            type: "ir.actions.client", tag: "linda_candidate_dashboard", name: row.name,
            params: { session_id: row.id },
        });
    }

    compare() {
        const ids = this.selectedIds;
        if (ids.length < 2 || ids.length > 4) {
            this.notification.add(_t("Select 2 to 4 candidates to compare."), { type: "warning" });
            return;
        }
        const rows = this.state.data.candidates.filter((r) => ids.includes(r.id));
        this.dialog.add(CompareDialog, { rows, labels: this.labels });
    }

    async remind() {
        const ids = this.selectedIds;
        if (!ids.length) {
            return this.notification.add(_t("Select candidates first."), { type: "warning" });
        }
        const res = await this.orm.call("ai.interview.session", "action_send_reminder", [ids]);
        await this.action.doAction(res);
        await this.load();
    }

    async nextStage() {
        const ids = this.selectedIds;
        if (!ids.length) {
            return this.notification.add(_t("Select reviewed candidates first."), { type: "warning" });
        }
        const res = await this.orm.call("ai.interview.session", "action_move_next_stage", [ids]);
        await this.action.doAction(res);
        await this.load();
    }

    exportXlsx() {
        const ids = this.selectedIds.join(",");
        window.location = `/linda/backend/campaign/${this.state.campaignId}/export${ids ? "?ids=" + ids : ""}`;
    }

    openAnalysis() {
        this.action.doAction({
            type: "ir.actions.act_window", name: _t("AI interviews"), res_model: "ai.interview.session",
            views: [[false, "pivot"], [false, "graph"], [false, "list"], [false, "form"]],
            domain: [["campaign_id", "=", this.state.campaignId]], context: { create: false },
        });
    }

    openCampaign() {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "ai.interview.campaign", res_id: this.state.campaignId,
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("linda_campaign_dashboard", CampaignDashboard);
