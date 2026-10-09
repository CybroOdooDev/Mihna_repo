/**
 * Keystroke log for typing replay and integrity heuristics.
 *
 * Each event: [t_ms_epoch, kind, n, pos, text?]
 *   kind "i" = insert n chars at pos (text included, so the reviewer can replay),
 *   kind "d" = delete n chars at pos, kind "p" = blocked paste attempt.
 */
export class KeyLog {
    constructor(initial = "") {
        this.prev = initial || "";
        this.buffer = [];
    }

    record(value) {
        const prev = this.prev;
        if (value === prev) {
            return;
        }
        let start = 0;
        const max = Math.min(prev.length, value.length);
        while (start < max && prev[start] === value[start]) {
            start++;
        }
        let endPrev = prev.length;
        let endNew = value.length;
        while (endPrev > start && endNew > start && prev[endPrev - 1] === value[endNew - 1]) {
            endPrev--;
            endNew--;
        }
        const t = Date.now();
        if (endPrev > start) {
            this.buffer.push([t, "d", endPrev - start, start]);
        }
        if (endNew > start) {
            this.buffer.push([t, "i", endNew - start, start, value.slice(start, endNew)]);
        }
        this.prev = value;
    }

    paste() {
        this.buffer.push([Date.now(), "p", 0, 0]);
    }

    take() {
        const events = this.buffer;
        this.buffer = [];
        return events;
    }

    get dirty() {
        return this.buffer.length > 0;
    }
}

/** Rebuild the text at a given time from a keystroke log (used by the reviewer replay). */
export function replayText(events, untilT) {
    let text = "";
    for (const ev of events) {
        if (ev[0] > untilT) {
            break;
        }
        const [, kind, n, pos, ins] = ev;
        if (kind === "d") {
            text = text.slice(0, pos) + text.slice(pos + n);
        } else if (kind === "i") {
            text = text.slice(0, pos) + (ins || "") + text.slice(pos);
        }
    }
    return text;
}
