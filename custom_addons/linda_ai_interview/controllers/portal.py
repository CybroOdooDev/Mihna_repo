"""Public candidate routes. The browser only ever talks to Odoo; Odoo calls the AI,
speech and sandbox services server-side (FRD §8). Every route checks the signed token
and is rate-limited per IP."""
import base64
import logging

from werkzeug.exceptions import NotFound, TooManyRequests

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from ..services.tokens import limiter

_logger = logging.getLogger(__name__)

MOBILE_MARKERS = ("Android", "iPhone", "iPad", "iPod", "Mobile", "Opera Mini", "IEMobile")


class LindaPortal(http.Controller):

    def _limit(self, bucket, limit):
        ip = request.httprequest.remote_addr or "?"
        if not limiter.allow((ip, bucket), limit):
            raise TooManyRequests()

    def _session(self, token, bucket="api", limit=120):
        self._limit(bucket, limit)
        session = request.env["ai.interview.session"].sudo().search([("access_token", "=", token)], limit=1)
        if not session or not session._check_token(token):
            raise NotFound()
        return session

    def _guard(self, func):
        try:
            return {"ok": True, "result": func()}
        except UserError as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Page
    # ------------------------------------------------------------------

    @http.route("/linda/i/<string:token>", type="http", auth="public", website=True, sitemap=False)
    def interview_page(self, token, **kw):
        self._limit("page", 30)
        session = request.env["ai.interview.session"].sudo().search([("access_token", "=", token)], limit=1)
        if not session or not session.access_token:
            return request.render("linda_ai_interview.portal_message", {
                "title": "Link not valid", "message": "This interview link is not valid. Please contact HR."})
        if not session._check_token(token) or session.state == "expired":
            return request.render("linda_ai_interview.portal_message", {
                "title": "Link expired",
                "message": "This interview link has expired. Please contact HR if you need a new one."})
        user_agent = request.httprequest.headers.get("User-Agent", "")
        if any(marker in user_agent for marker in MOBILE_MARKERS):
            return request.render("linda_ai_interview.portal_message", {
                "title": "Please use a laptop or desktop",
                "message": "The interview needs a laptop or desktop computer with a microphone and the latest "
                           "Chrome, Edge or Firefox. Open this link on a computer to continue."})
        return request.render("linda_ai_interview.portal_interview", {"token": token, "session": session})

    # ------------------------------------------------------------------
    # JSON API
    # ------------------------------------------------------------------

    @http.route("/linda/api/<string:token>/state", type="jsonrpc", auth="public")
    def api_state(self, token, fresh_load=False):
        session = self._session(token)
        return self._guard(lambda: session._portal_state(fresh_load=bool(fresh_load)))

    @http.route("/linda/api/<string:token>/consent", type="jsonrpc", auth="public")
    def api_consent(self, token, accept):
        session = self._session(token, "consent", 10)
        return self._guard(lambda: (session._portal_consent(bool(accept), request.httprequest.remote_addr),
                                    session._portal_state())[1])

    @http.route("/linda/api/<string:token>/start", type="jsonrpc", auth="public")
    def api_start(self, token):
        session = self._session(token, "start", 30)
        return self._guard(lambda: {"started": session._portal_start(), "state": session._portal_state()})

    @http.route("/linda/api/<string:token>/tick", type="jsonrpc", auth="public")
    def api_tick(self, token, paused=None):
        session = self._session(token, "tick", 60)
        return self._guard(lambda: (session._tick(paused=paused), {
            "state": session.state, "current_section": session.current_section or False,
            "remaining": session._section_remaining() if session.current_section else 0,
            "paused": session.paused})[1])

    @http.route("/linda/api/<string:token>/save", type="jsonrpc", auth="public")
    def api_save(self, token, response_id, answer_text=None, code=None, language=None, keystrokes=None):
        session = self._session(token)
        return self._guard(lambda: session._portal_save(response_id, answer_text, code, language, keystrokes))

    @http.route("/linda/api/<string:token>/event", type="jsonrpc", auth="public")
    def api_event(self, token, etype, detail=""):
        session = self._session(token, "event", 60)
        return self._guard(lambda: session._portal_event(etype, detail))

    @http.route("/linda/api/<string:token>/submit_answer", type="jsonrpc", auth="public")
    def api_submit_answer(self, token, response_id, answer_text):
        session = self._session(token)
        return self._guard(lambda: session._portal_submit_answer(response_id, answer_text))

    @http.route("/linda/api/<string:token>/run_code", type="jsonrpc", auth="public")
    def api_run_code(self, token, response_id, code, language):
        session = self._session(token, "run", 30)
        return self._guard(lambda: session._portal_run_code(response_id, code, language))

    @http.route("/linda/api/<string:token>/submit_code", type="jsonrpc", auth="public")
    def api_submit_code(self, token, response_id, code, language):
        session = self._session(token, "llm", 30)
        return self._guard(lambda: session._portal_submit_code(response_id, code, language))

    @http.route("/linda/api/<string:token>/followup", type="jsonrpc", auth="public")
    def api_followup(self, token, response_id, index, text):
        session = self._session(token, "llm", 30)
        return self._guard(lambda: session._portal_followup_answer(response_id, index, text))

    @http.route("/linda/api/<string:token>/ask_doc", type="jsonrpc", auth="public")
    def api_ask_doc(self, token, response_id, question):
        session = self._session(token, "llm", 30)
        return self._guard(lambda: session._portal_ask_doc(response_id, question))

    @http.route("/linda/api/<string:token>/voice_text", type="jsonrpc", auth="public")
    def api_voice_text(self, token, response_id, text, index=-1):
        session = self._session(token, "llm", 30)
        return self._guard(lambda: session._portal_voice_text_answer(response_id, text, index))

    @http.route("/linda/api/<string:token>/submit_section", type="jsonrpc", auth="public")
    def api_submit_section(self, token):
        session = self._session(token, "section", 20)
        return self._guard(lambda: (session._portal_submit_section(), session._portal_state())[1])

    @http.route("/linda/api/<string:token>/withdraw", type="jsonrpc", auth="public")
    def api_withdraw(self, token):
        session = self._session(token, "consent", 10)
        return self._guard(session._portal_withdraw)

    @http.route("/linda/api/<string:token>/audio", type="http", auth="public", methods=["POST"], csrf=False)
    def api_audio(self, token, response_id, index="-1", silence_ms="0", audio=None, **kw):
        """Multipart upload of one recorded answer (turn-based voice, FRD §8)."""
        session = self._session(token, "llm", 30)
        if audio is None:
            return request.make_json_response({"ok": False, "error": "No audio received."}, status=400)
        data = audio.read()
        result = self._guard(lambda: session._portal_audio_answer(
            int(response_id), data, audio.mimetype, int(index), int(float(silence_ms or 0))))
        return request.make_json_response(result)

    @http.route("/linda/api/<string:token>/tts/<int:response_id>/<string:index>", type="http", auth="public")
    def api_tts(self, token, response_id, index="-1", **kw):
        session = self._session(token, "tts", 60)
        try:
            audio, mimetype = session._portal_tts(response_id, int(index))
        except Exception as exc:  # TTS is optional: the question is also shown as text
            _logger.warning("TTS failed: %s", exc)
            raise NotFound()
        return request.make_response(audio, headers=[("Content-Type", mimetype), ("Cache-Control", "no-store")])


class LindaBackend(http.Controller):

    @http.route("/linda/backend/audio/<int:attachment_id>", type="http", auth="user")
    def backend_audio(self, attachment_id, **kw):
        """Recordings are only streamed to Recruitment users (FRD §10)."""
        if not request.env.user.has_group("hr_recruitment.group_hr_recruitment_interviewer"):
            raise NotFound()
        att = request.env["ir.attachment"].sudo().browse(attachment_id).exists()
        if not att or att.res_model != "ai.interview.response":
            raise NotFound()
        response = request.env["ai.interview.response"].browse(att.res_id).exists()
        if not response:
            raise NotFound()
        content = bytes(att.raw) if getattr(att, "raw", None) else (base64.b64decode(att.datas) if getattr(att, "datas", None) else b"")
        return request.make_response(content, headers=[
            ("Content-Type", att.mimetype or "audio/webm"), ("Cache-Control", "private, no-store")])

    @http.route("/linda/backend/campaign/<int:campaign_id>/export", type="http", auth="user")
    def campaign_export(self, campaign_id, ids=None, **kw):
        import io

        import xlsxwriter

        data = request.env["ai.interview.campaign"].get_dashboard_data(campaign_id)
        rows = data["candidates"]
        if ids:
            wanted = {int(i) for i in ids.split(",") if i}
            rows = [r for r in rows if r["id"] in wanted]
        labels = data["labels"]
        dims = list(labels["dimensions"].keys())
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {"in_memory": True})
        sheet = book.add_worksheet("Candidates")
        bold = book.add_format({"bold": True})
        header = ["Candidate", "Status", "Total /100", "Band"] + [labels["dimensions"][d] for d in dims] + [
            "AI-assistance risk", "Integrity signals", "Red flags", "Language", "Reviewer", "Decision"]
        sheet.write_row(0, 0, header, bold)
        for i, r in enumerate(rows, start=1):
            sheet.write_row(i, 0, [
                r["name"], labels["states"].get(r["state"], r["state"]), r["total"],
                labels["bands"].get(r["band"], "") if r["band"] else ""] + [r["scores"][d] or "" for d in dims] + [
                labels["risks"].get(r["risk"], "") if r["risk"] else "", r["flags"], r["red_flags"],
                labels["languages"].get(r["language"], "") if r["language"] else "", r["reviewer"],
                labels["decisions"].get(r["decision"], "") if r["decision"] else ""])
        sheet.set_column(0, 0, 28)
        sheet.set_column(1, len(header), 14)
        book.close()
        name = f"linda_{data['campaign']['name']}.xlsx".replace(" ", "_").replace("/", "_")
        return request.make_response(buf.getvalue(), headers=[
            ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", f'attachment; filename="{name}"')])
