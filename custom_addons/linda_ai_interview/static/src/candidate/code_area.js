import { Component, useRef, useState, onMounted } from "@odoo/owl";

/**
 * Plain-textarea editor with line numbers and Tab indentation.
 * Paste is blocked (and reported) so the keystroke log stays meaningful (FRD §9).
 */
export class CodeArea extends Component {
    static template = "linda_ai_interview.CodeArea";
    static props = {
        value: { type: String, optional: true },
        keylog: Object,
        onChange: Function,
        onPaste: Function,
        readonly: { type: Boolean, optional: true },
        rows: { type: Number, optional: true },
        code: { type: Boolean, optional: true },
        placeholder: { type: String, optional: true },
    };
    static defaultProps = { value: "", rows: 18, code: true, placeholder: "" };

    setup() {
        this.textarea = useRef("textarea");
        this.gutter = useRef("gutter");
        this.state = useState({ lines: Math.max(1, (this.props.value || "").split("\n").length) });
        onMounted(() => {
            this.textarea.el.value = this.props.value || "";
        });
    }

    get lineNumbers() {
        return Array.from({ length: this.state.lines }, (_, i) => i + 1);
    }

    onInput(ev) {
        const value = ev.target.value;
        this.props.keylog.record(value);
        this.state.lines = Math.max(1, value.split("\n").length);
        this.props.onChange(value);
    }

    onKeydown(ev) {
        if (!this.props.code || ev.key !== "Tab" || this.props.readonly) {
            return;
        }
        ev.preventDefault();
        const el = ev.target;
        el.setRangeText("    ", el.selectionStart, el.selectionEnd, "end");
        this.onInput({ target: el });
    }

    onPaste(ev) {
        ev.preventDefault();
        this.props.keylog.paste();
        this.props.onPaste();
    }

    onDrop(ev) {
        ev.preventDefault();
        this.props.keylog.paste();
        this.props.onPaste();
    }

    onScroll(ev) {
        if (this.gutter.el) {
            this.gutter.el.scrollTop = ev.target.scrollTop;
        }
    }
}
