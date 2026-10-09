import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { replayText } from "../candidate/keylog";
import { ChartCanvas, VIZ, axis } from "./chart_canvas";

const STATUS = {
    band: { strong: "good", borderline: "warning", not_recommended: "critical" },
    risk: { low: "good", medium: "warning", high: "critical" },
};

export class ReplayPlayer extends Component {
    static template = "linda_ai_interview.ReplayPlayer";
    static props = { sessionId: Number, responseId: Number };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loaded: false, log: [], t: 0, playing: false, speed: 10 });
        onWillUnmount(() => clearInterval(this.timer));
    }

    async load() {
        const res = await this.orm.call("ai.interview.session", "get_keystroke_log", [[this.props.sessionId], this.props.responseId]);
        this.state.log = res.log || [];
        this.state.loaded = true;
        this.state.t = this.start;
    }

    get start() {
        return this.state.log.length ? this.state.log[0][0] : 0;
    }

    get end() {
        return this.state.log.length ? this.state.log[this.state.log.length - 1][0] : 0;
    }

    get text() {
        return replayText(this.state.log, this.state.t);
    }

    get elapsed() {
        return Math.round((this.state.t - this.start) / 1000);
    }

    get stats() {
        const ins = this.state.log.filter((e) => e[1] === "i").reduce((a, e) => a + e[2], 0);
        const del = this.state.log.filter((e) => e[1] === "d").reduce((a, e) => a + e[2], 0);
        const pastes = this.state.log.filter((e) => e[1] === "p").length;
        return { ins, del, pastes, minutes: Math.round((this.end - this.start) / 6000) / 10 };
    }

    onSlide(ev) {
        this.state.t = Number(ev.target.value);
    }

    play() {
        if (this.state.playing) {
            clearInterval(this.timer);
            this.state.playing = false;
            return;
        }
        if (this.state.t >= this.end) {
            this.state.t = this.start;
        }
        this.state.playing = true;
        this.timer = setInterval(() => {
            this.state.t = Math.min(this.end, this.state.t + 100 * this.state.speed);
            if (this.state.t >= this.end) {
                clearInterval(this.timer);
                this.state.playing = false;
            }
        }, 100);
    }
}

export class CandidateDashboard extends Component {
    static template = "linda_ai_interview.CandidateDashboard";
    static components = { ChartCanvas, ReplayPlayer };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.sessionId = this.props.action.params?.session_id || this.props.action.context?.active_id;
        this.state = useState({ data: null, tab: "", review: { overrides: {}, notes: "", decision: "" }, saving: false });
        onWillStart(() => this.load());
    }

    async load() {
        const data = await this.orm.call("ai.interview.session", "get_dashboard_data", [[this.sessionId]]);
        this.state.data = data;
        this.state.tab = this.state.tab || data.sections[0]?.type || "";
        const overrides = {};
        for (const s of data.scores) {
            overrides[s.id] = { human_score: s.human_score || "", reason: s.reason || "" };
        }
        this.state.review = {
            overrides,
            notes: (data.session.review_notes || "").replace(/<[^>]+>/g, "\n").replace(/\n{2,}/g, "\n").trim(),
            decision: data.session.decision || "",
        };
    }

    get s() {
        return this.state.data.session;
    }

    num(value) {
        return (value || 0).toLocaleString();
    }

    get usageTotal() {
        const sum = (k) => this.state.data.usage.reduce((t, r) => t + r[k], 0);
        return { interview: sum("interview"), scoring: sum("scoring"), total: sum("total"),
                 cost: Math.round(sum("cost") * 10000) / 10000 };
    }

    statusColor(kind, value) {
        return value ? VIZ.status[STATUS[kind][value]] : "transparent";
    }

    get chartConfig() {
        const scores = this.state.data.scores;
        const datasets = [{
            label: _t("This candidate"), data: scores.map((s) => s.final), backgroundColor: VIZ.series1,
            borderRadius: 4, maxBarThickness: 28,
        }];
        if (this.s.campaign_id) {
            datasets.push({
                label: _t("Campaign average"), data: scores.map((s) => s.campaign_avg), backgroundColor: VIZ.series2,
                borderRadius: 4, maxBarThickness: 28,
            });
        }
        return {
            type: "bar",
            data: { labels: scores.map((s) => s.label), datasets },
            options: {
                scales: { y: axis({ min: 0, max: 5, ticks: { stepSize: 1, color: VIZ.muted } }), x: axis({ grid: { display: false } }) },
                plugins: { tooltip: { mode: "index", intersect: false } },
            },
        };
    }

    get signals() {
        return this.state.data.flags.filter((f) => f.signal);
    }

    get section() {
        return this.state.data.sections.find((x) => x.type === this.state.tab);
    }

    setTab(tab) {
        this.state.tab = tab;
    }

    audioUrl(id) {
        return `/linda/backend/audio/${id}`;
    }

    weightClass(weight) {
        return { high: "text-danger", medium: "text-warning", low: "text-muted", event: "text-muted" }[weight];
    }

    async save(confirmReview = false) {
        const overrides = Object.entries(this.state.review.overrides).map(([id, o]) => ({
            id: Number(id), human_score: Number(o.human_score) || 0, reason: o.reason,
        }));
        for (const o of overrides) {
            if (o.human_score && !(o.reason || "").trim()) {
                this.notification.add(_t("Every score override needs a reason."), { type: "danger" });
                return;
            }
        }
        this.state.saving = true;
        try {
            const notes = this.state.review.notes
                ? `<p>${this.state.review.notes.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/\n/g, "<br/>")}</p>`
                : false;
            await this.orm.call("ai.interview.session", "save_review", [[this.sessionId], {
                overrides, review_notes: notes, decision: this.state.review.decision || false, confirm: confirmReview,
            }]);
            this.notification.add(confirmReview ? _t("Review confirmed.") : _t("Review saved."), { type: "success" });
            await this.load();
        } finally {
            this.state.saving = false;
        }
    }

    async print() {
        const action = await this.orm.call("ai.interview.session", "action_print_scorecard", [[this.sessionId]]);
        this.action.doAction(action);
    }

    openForm() {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "ai.interview.session", res_id: this.sessionId,
                               views: [[false, "form"]] });
    }

    openApplicant() {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.applicant", res_id: this.s.applicant_id,
                               views: [[false, "form"]] });
    }

    openCampaign() {
        this.action.doAction({ type: "ir.actions.client", tag: "linda_campaign_dashboard", name: this.s.campaign,
                               params: { campaign_id: this.s.campaign_id } });
    }
}

registry.category("actions").add("linda_candidate_dashboard", CandidateDashboard);
