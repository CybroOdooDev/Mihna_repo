import { Component, markup, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";

import { CodeArea } from "./code_area";
import { KeyLog } from "./keylog";

const TICK_MS = 10000;
const AUTOSAVE_MS = 15000;

function fmt(seconds) {
    seconds = Math.max(0, Math.floor(seconds || 0));
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
}

export class CandidateApp extends Component {
    static template = "linda_ai_interview.CandidateApp";
    static components = { CodeArea };
    static props = { token: String };

    setup() {
        this.state = useState({
            screen: "loading",
            data: null,
            error: "",
            busy: false,
            remaining: 0,
            totalRemaining: 0,
            consentChecked: false,
            check: { mic: "pending", browser: "pending", level: 0 },
            fullscreenLost: false,
            edits: {}, // response id -> {answer_text, code, language}
            runResults: {},
            askText: {},
            followupText: {},
            voice: { recording: false, uploading: false, readyAt: 0, playing: false, thinking: false, textMode: false, typed: "" },
            notice: "",
        });
        this.keylogs = {};
        this.dirty = new Set();
        this.timers = [];
        this.recorder = null;
        this.audio = null;

        onWillStart(() => this.load(true));
        onMounted(() => {
            this.timers.push(setInterval(() => this.tick(), TICK_MS));
            this.timers.push(setInterval(() => this.autosave(), AUTOSAVE_MS));
            this.timers.push(setInterval(() => this.countdown(), 1000));
            this._onFullscreen = () => this.onFullscreenChange();
            this._onVisibility = () => this.onVisibility();
            this._onBlur = () => this.onWindowBlur();
            this._onBeforeUnload = () => this.autosave(true);
            document.addEventListener("fullscreenchange", this._onFullscreen);
            document.addEventListener("visibilitychange", this._onVisibility);
            window.addEventListener("blur", this._onBlur);
            window.addEventListener("beforeunload", this._onBeforeUnload);
        });
        onWillUnmount(() => {
            this.timers.forEach(clearInterval);
            document.removeEventListener("fullscreenchange", this._onFullscreen);
            document.removeEventListener("visibilitychange", this._onVisibility);
            window.removeEventListener("blur", this._onBlur);
            window.removeEventListener("beforeunload", this._onBeforeUnload);
            this.stopMicTest();
        });
    }

    // ------------------------------------------------------------------
    // Server calls
    // ------------------------------------------------------------------

    async call(route, params = {}) {
        const res = await rpc(`/linda/api/${this.props.token}/${route}`, params);
        if (!res.ok) {
            this.state.notice = res.error || "Something went wrong.";
            throw new Error(res.error);
        }
        return res.result;
    }

    async load(fresh = false) {
        try {
            const data = await this.call("state", { fresh_load: fresh });
            this.applyState(data);
        } catch (e) {
            if (!this.state.notice) {
                this.state.error = "We could not load your interview. Please refresh the page.";
                this.state.screen = "error";
            }
        }
    }

    applyState(data) {
        this.state.data = data;
        this.state.remaining = data.remaining;
        this.state.totalRemaining = data.total_remaining;
        for (const item of data.items || []) {
            if (!this.keylogs[item.id]) {
                this.keylogs[item.id] = new KeyLog(item.code || item.answer_text || "");
            }
            if (!this.state.edits[item.id]) {
                this.state.edits[item.id] = {
                    answer_text: item.answer_text,
                    code: item.code,
                    language: item.language || data.language || "",
                };
            }
        }
        const s = data.state;
        if (window.innerWidth < 900 || /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
            this.state.screen = "mobile";
        } else if (s === "invited") {
            if (!data.consented) {
                this.state.screen = "consent";
            } else if (this.state.screen !== "check" && this.state.screen !== "waiting") {
                this.state.screen = "check";
                this.runSystemCheck();
            }
        } else if (s === "in_progress") {
            if (this.state.screen !== "interview") {
                this.state.screen = "interview";
                this.state.fullscreenLost = !document.fullscreenElement;
            }
        } else if (["submitted", "scored", "reviewed"].includes(s)) {
            this.state.screen = "done";
            this.exitFullscreen();
        } else if (s === "cancelled") {
            this.state.screen = "cancelled";
        } else {
            this.state.screen = "expired";
        }
    }

    // ------------------------------------------------------------------
    // Consent and system check
    // ------------------------------------------------------------------

    get noticeHtml() {
        return markup(this.state.data?.notice?.html || "");
    }

    async onConsent(accept) {
        this.state.busy = true;
        try {
            const data = await this.call("consent", { accept });
            if (!accept) {
                this.state.screen = "declined";
                return;
            }
            this.applyState(data);
        } finally {
            this.state.busy = false;
        }
    }

    async runSystemCheck() {
        const check = this.state.check;
        const browserOk = !!(window.MediaRecorder && navigator.mediaDevices?.getUserMedia &&
            document.documentElement.requestFullscreen);
        check.browser = browserOk ? "ok" : "fail";
        if (!browserOk) {
            check.mic = "fail";
            return;
        }
        try {
            this.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const ctx = new AudioContext();
            const analyser = ctx.createAnalyser();
            ctx.createMediaStreamSource(this.micStream).connect(analyser);
            const buf = new Uint8Array(analyser.fftSize);
            this.micCtx = ctx;
            const loop = () => {
                if (!this.micCtx) {
                    return;
                }
                analyser.getByteTimeDomainData(buf);
                let peak = 0;
                for (const v of buf) {
                    peak = Math.max(peak, Math.abs(v - 128));
                }
                check.level = Math.min(100, Math.round((peak / 128) * 250));
                if (check.level > 8) {
                    check.mic = "ok";
                }
                requestAnimationFrame(loop);
            };
            check.mic = check.mic === "ok" ? "ok" : "listening";
            loop();
        } catch {
            check.mic = "fail";
        }
    }

    stopMicTest() {
        if (this.micCtx) {
            this.micCtx.close();
            this.micCtx = null;
        }
        if (this.micStream) {
            this.micStream.getTracks().forEach((t) => t.stop());
            this.micStream = null;
        }
    }

    get canStart() {
        const c = this.state.check;
        return c.browser === "ok" && c.mic === "ok";
    }

    async onStart() {
        this.state.busy = true;
        try {
            await this.enterFullscreen();
            const res = await this.call("start");
            if (!res.started) {
                this.state.screen = "waiting";
                setTimeout(() => this.state.screen === "waiting" && this.onStart(), 15000);
                return;
            }
            this.stopMicTest();
            this.applyState(res.state);
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------------
    // Time, autosave and integrity events
    // ------------------------------------------------------------------

    countdown() {
        if (this.state.screen !== "interview" || this.state.fullscreenLost) {
            return;
        }
        this.state.remaining = Math.max(0, this.state.remaining - 1);
        this.state.totalRemaining = Math.max(0, this.state.totalRemaining - 1);
        if (this.state.remaining === 0) {
            this.tick();
        }
    }

    async tick() {
        if (this.state.screen !== "interview" || this._ticking) {
            return;
        }
        this._ticking = true;
        try {
            const res = await this.call("tick", { paused: this.state.fullscreenLost });
            this.state.remaining = res.remaining;
            if (res.state !== "in_progress" || res.current_section !== this.state.data.current_section) {
                await this.autosave(false, true);
                await this.load();
                this.state.notice = res.state === "in_progress" ? "Time is up for that section. Moving on." : "";
            }
        } catch {
            // network blip: the server keeps time, we retry on the next tick
        } finally {
            this._ticking = false;
        }
    }

    markDirty(id) {
        this.dirty.add(id);
    }

    async autosave(beacon = false, force = false) {
        if (this.state.screen !== "interview") {
            return;
        }
        // A slow request (code submit, voice answer...) is updating the same answer: don't race it.
        if (this.state.busy && !force && !beacon) {
            return;
        }
        const ids = new Set([...this.dirty, ...Object.keys(this.keylogs).filter((id) => this.keylogs[id].dirty)]);
        for (const id of ids) {
            const item = (this.state.data.items || []).find((i) => String(i.id) === String(id));
            if (!item || (item.final && item.section !== "coding" && item.section !== "learn")) {
                continue;
            }
            const edit = this.state.edits[id] || {};
            const params = {
                response_id: Number(id),
                keystrokes: this.keylogs[id]?.take() || [],
            };
            if (!item.final) {
                if (item.section === "written") {
                    params.answer_text = edit.answer_text || "";
                } else if (item.section === "coding" || item.section === "learn") {
                    params.code = edit.code || "";
                    params.language = edit.language || null;
                }
            }
            if (beacon) {
                navigator.sendBeacon?.(`/linda/api/${this.props.token}/save`, new Blob(
                    [JSON.stringify({ jsonrpc: "2.0", method: "call", params })], { type: "application/json" }));
                continue;
            }
            try {
                await this.call("save", params);
                this.dirty.delete(id);
            } catch {
                // keep dirty; retried next autosave
                if (params.keystrokes.length) {
                    this.keylogs[id].buffer.unshift(...params.keystrokes);
                }
            }
        }
    }

    async event(etype, detail = "") {
        if (this.state.screen !== "interview") {
            return;
        }
        try {
            await this.call("event", { etype, detail });
        } catch {
            // best effort
        }
    }

    onFullscreenChange() {
        if (this.state.screen !== "interview") {
            return;
        }
        if (!document.fullscreenElement) {
            this.state.fullscreenLost = true;
            this.event("fullscreen_exit", "Left full-screen mode");
        }
    }

    onVisibility() {
        if (document.visibilityState === "hidden") {
            this._hiddenAt = Date.now();
            this.event("tab_switch", "Tab or window hidden");
        }
    }

    onWindowBlur() {
        if (this._hiddenAt && Date.now() - this._hiddenAt < 1000) {
            return;
        }
        if (this.state.voice.recording) {
            return;
        }
        this.event("blur", "Interview window lost focus");
    }

    onPasteBlocked() {
        this.state.notice = "Pasting is disabled during the interview.";
        this.event("paste", "Paste attempt blocked");
    }

    onBlockedPaste(ev) {
        ev.preventDefault();
        this.onPasteBlocked();
    }

    itemNumber(item) {
        return this.items.findIndex((i) => i.id === item.id) + 1;
    }

    blockCopy(ev) {
        ev.preventDefault();
    }

    async enterFullscreen() {
        try {
            if (!document.fullscreenElement) {
                await document.documentElement.requestFullscreen();
            }
        } catch {
            // some browsers refuse without a gesture; the overlay asks again
        }
    }

    exitFullscreen() {
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
        }
    }

    async resumeFullscreen() {
        await this.enterFullscreen();
        if (document.fullscreenElement) {
            this.state.fullscreenLost = false;
            await this.call("tick", { paused: false }).catch(() => {});
        }
    }

    // ------------------------------------------------------------------
    // Sections
    // ------------------------------------------------------------------

    get section() {
        return this.state.data?.current_section;
    }

    get sectionInfo() {
        return (this.state.data?.sections || []).find((s) => s.type === this.section) || {};
    }

    get items() {
        return this.state.data?.items || [];
    }

    get currentItem() {
        // coding / learn / voice: one item at a time
        return this.items.find((i) => !this.itemDone(i)) || null;
    }

    itemDone(item) {
        if (item.section === "coding") {
            return item.final && item.followups.every((f) => f.a);
        }
        return item.final;
    }

    get progress() {
        const sections = this.state.data?.sections || [];
        return sections.map((s) => ({ ...s, current: s.type === this.section }));
    }

    fmt(seconds) {
        return fmt(seconds);
    }

    get timeWarning() {
        return this.state.remaining < 120;
    }

    replaceItem(item) {
        const items = this.state.data.items;
        const idx = items.findIndex((i) => i.id === item.id);
        if (idx >= 0) {
            items[idx] = item;
        }
    }

    onText(item, value) {
        this.state.edits[item.id].answer_text = value;
        this.markDirty(item.id);
    }

    onCode(item, value) {
        this.state.edits[item.id].code = value;
        this.markDirty(item.id);
    }

    wordCount(text) {
        return (text || "").trim().split(/\s+/).filter(Boolean).length;
    }

    languageLocked(item) {
        return !!(item.language && (this.state.edits[item.id].code || "").trim());
    }

    onLanguage(item, ev) {
        this.state.edits[item.id].language = ev.target.value;
        this.markDirty(item.id);
    }

    async submitWritten(item) {
        if (!(this.state.edits[item.id].answer_text || "").trim()) {
            this.state.notice = "Please write your answer first.";
            return;
        }
        this.state.busy = true;
        try {
            await this.autosave(false, true);
            const updated = await this.call("submit_answer", {
                response_id: item.id,
                answer_text: this.state.edits[item.id].answer_text || "",
            });
            this.replaceItem(updated);
        } finally {
            this.state.busy = false;
        }
    }

    async runCode(item) {
        const edit = this.state.edits[item.id];
        if (!edit.language) {
            this.state.notice = "Choose a programming language first.";
            return;
        }
        this.state.busy = true;
        try {
            await this.autosave(false, true);
            this.state.runResults[item.id] = await this.call("run_code", {
                response_id: item.id, code: edit.code || "", language: edit.language,
            });
        } finally {
            this.state.busy = false;
        }
    }

    async submitCode(item) {
        const edit = this.state.edits[item.id];
        if (!edit.language) {
            this.state.notice = "Choose a programming language first.";
            return;
        }
        if (!confirm("Submit your solution? You won't be able to change the code afterwards.")) {
            return;
        }
        this.state.busy = true;
        try {
            await this.autosave(false, true);
            const updated = await this.call("submit_code", {
                response_id: item.id, code: edit.code || "", language: edit.language,
            });
            this.replaceItem(updated);
        } finally {
            this.state.busy = false;
        }
    }

    pendingFollowup(item) {
        return item.followups.find((f) => !f.a);
    }

    async answerFollowup(item, followup) {
        const key = `${item.id}_${followup.index}`;
        const text = (this.state.followupText[key] || "").trim();
        if (!text) {
            this.state.notice = "Please type your answer.";
            return;
        }
        this.state.busy = true;
        try {
            const updated = await this.call("followup", { response_id: item.id, index: followup.index, text });
            this.state.followupText[key] = "";
            this.replaceItem(updated);
        } finally {
            this.state.busy = false;
        }
    }

    async askDoc(item) {
        const question = (this.state.askText[item.id] || "").trim();
        if (!question) {
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.call("ask_doc", { response_id: item.id, question });
            item.doc_questions.push({ q: question, a: res.answer });
            this.state.askText[item.id] = "";
        } finally {
            this.state.busy = false;
        }
    }

    get canFinishSection() {
        if (this.section === "written") {
            return true;
        }
        return !this.currentItem;
    }

    async finishSection(force = false) {
        const unfinished = this.items.filter((i) => !this.itemDone(i)).length;
        const msg = unfinished && !force
            ? "Some answers are not submitted yet. They will be saved as they are. Finish this section? You cannot come back to it."
            : "Finish this section? You cannot come back to it.";
        if (!confirm(msg)) {
            return;
        }
        this.state.busy = true;
        try {
            await this.autosave(false, true);
            const data = await this.call("submit_section");
            this.state.runResults = {};
            this.applyState(data);
            window.scrollTo(0, 0);
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------------
    // Voice (turn-based)
    // ------------------------------------------------------------------

    voiceTurn(item) {
        if (!item) {
            return null;
        }
        if (!item.answered) {
            return { index: -1, text: item.prompt };
        }
        const pending = this.pendingFollowup(item);
        return pending ? { index: pending.index, text: pending.q } : null;
    }

    ttsUrl(item, turn) {
        return `/linda/api/${this.props.token}/tts/${item.id}/${turn.index}`;
    }

    playQuestion(item, turn) {
        if (this.audio) {
            this.audio.pause();
        }
        this.state.voice.readyAt = Date.now();
        const audio = new Audio(this.ttsUrl(item, turn));
        this.audio = audio;
        // The speech is generated on request, so answering stays blocked until it starts playing.
        this.state.voice.thinking = true;
        this.state.voice.playing = false;
        clearTimeout(this.thinkingTimer);
        this.thinkingTimer = setTimeout(() => this.audio === audio && this.stopThinking(), 30000);
        // A replaced clip is paused, which rejects its play(); only the current clip may change the state.
        audio.onplaying = () => {
            if (this.audio === audio) {
                this.stopThinking();
                this.state.voice.playing = true;
            }
        };
        audio.onended = audio.onerror = () => {
            if (this.audio === audio) {
                this.stopThinking();
                this.state.voice.playing = false;
                this.state.voice.readyAt = Date.now();
            }
        };
        audio.play().catch(() => {
            if (this.audio === audio) {
                this.stopThinking();
                this.state.voice.playing = false;
            }
        });
    }

    stopThinking() {
        clearTimeout(this.thinkingTimer);
        this.state.voice.thinking = false;
    }

    async startRecording() {
        if (this.state.voice.thinking) {
            return;
        }
        if (this.audio) {
            this.audio.pause();
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
            this.recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
            this.chunks = [];
            this.recorder.ondataavailable = (e) => e.data.size && this.chunks.push(e.data);
            this.recordStartedAt = Date.now();
            this.recorder.start();
            this.state.voice.recording = true;
        } catch {
            this.state.notice = "We can't access your microphone. You can type this answer instead.";
            this.state.voice.textMode = true;
        }
    }

    async stopRecording(item, turn) {
        if (!this.recorder) {
            return;
        }
        const recorder = this.recorder;
        const stopped = new Promise((resolve) => (recorder.onstop = resolve));
        recorder.stop();
        recorder.stream.getTracks().forEach((t) => t.stop());
        await stopped;
        this.recorder = null;
        this.state.voice.recording = false;
        const blob = new Blob(this.chunks, { type: recorder.mimeType || "audio/webm" });
        const silence = Math.max(0, this.recordStartedAt - (this.state.voice.readyAt || this.recordStartedAt));
        const form = new FormData();
        form.append("response_id", item.id);
        form.append("index", turn.index);
        form.append("silence_ms", silence);
        form.append("audio", blob, "answer.webm");
        this.state.voice.uploading = true;
        try {
            const resp = await fetch(`/linda/api/${this.props.token}/audio`, { method: "POST", body: form });
            const res = await resp.json();
            if (!res.ok) {
                this.state.notice = res.error || "Upload failed, please record again.";
                return;
            }
            this.replaceItem(res.result);
            this.state.voice.readyAt = Date.now();
            this.autoPlayNext();
        } catch {
            this.state.notice = "Upload failed, please record your answer again.";
        } finally {
            this.state.voice.uploading = false;
        }
    }

    async submitTypedVoice(item, turn) {
        const text = (this.state.voice.typed || "").trim();
        if (!text) {
            return;
        }
        this.state.busy = true;
        try {
            const updated = await this.call("voice_text", { response_id: item.id, text, index: turn.index });
            this.state.voice.typed = "";
            this.replaceItem(updated);
            this.autoPlayNext();
        } finally {
            this.state.busy = false;
        }
    }

    autoPlayNext() {
        const item = this.currentItem;
        const turn = this.voiceTurn(item);
        if (item && turn && item.section === "voice") {
            this.state.voice.thinking = true;
            setTimeout(() => this.playQuestion(item, turn), 400);
        }
    }

    async withdraw() {
        if (!confirm("Withdraw your consent? The interview stops and your interview data is deleted.")) {
            return;
        }
        await this.call("withdraw");
        this.exitFullscreen();
        this.state.screen = "cancelled";
    }

    dismissNotice() {
        this.state.notice = "";
    }
}

registry.category("public_components").add("linda_ai_interview.CandidateApp", CandidateApp);
