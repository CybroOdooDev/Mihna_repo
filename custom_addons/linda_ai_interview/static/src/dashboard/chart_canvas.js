import { Component, onMounted, onWillUnmount, onWillUpdateProps, useRef } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";

/** Palette roles (validated reference palette, light mode). Text never wears series colors. */
export const VIZ = {
    series1: "#2a78d6",
    series2: "#eb6834",
    grid: "#e1e0d9",
    axis: "#c3c2b7",
    muted: "#898781",
    textSecondary: "#52514e",
    // diverging blue <-> red with gray midpoint, for 1..5 rubric scores
    score: { 1: "#d03b3b", 2: "#ec9a9a", 3: "#c3c2b7", 4: "#86b6ef", 5: "#256abf" },
    status: { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" },
    ordinal: ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"],
};

export class ChartCanvas extends Component {
    static template = "linda_ai_interview.ChartCanvas";
    static props = { config: Object, height: { type: Number, optional: true } };
    static defaultProps = { height: 220 };

    setup() {
        this.canvas = useRef("canvas");
        this.chart = null;
        onMounted(async () => {
            await loadBundle("web.chartjs_lib");
            this.render_chart(this.props.config);
        });
        onWillUpdateProps((next) => this.render_chart(next.config));
        onWillUnmount(() => this.chart?.destroy());
    }

    render_chart(config) {
        if (!this.canvas.el || !window.Chart) {
            return;
        }
        this.chart?.destroy();
        const base = {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: { legend: { labels: { color: VIZ.textSecondary, boxWidth: 12 } } },
        };
        this.chart = new window.Chart(this.canvas.el, {
            ...config,
            options: { ...base, ...(config.options || {}), plugins: { ...base.plugins, ...(config.options?.plugins || {}) } },
        });
    }
}

export function axis(extra = {}) {
    return {
        grid: { color: VIZ.grid },
        border: { color: VIZ.axis },
        ticks: { color: VIZ.muted },
        ...extra,
    };
}
