import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..services.sandbox import DEFAULT_TIME_LIMITS

from .ai_template import SECTION_TYPES

ROLES = [
    ("llm_interviewer", "LLM – Interviewer (low latency)"),
    ("llm_scorer", "LLM – Scorer (strong model)"),
    ("llm_generator", "LLM – Question & reference-answer generator"),
    ("stt_fast", "Speech-to-text – fast (during interview)"),
    ("stt_accurate", "Speech-to-text – accurate (after submission)"),
    ("tts", "Text-to-speech"),
    ("sandbox", "Code sandbox"),
]

KINDS = [
    ("anthropic", "Anthropic API"),
    ("openai", "OpenAI-compatible API (OpenAI, Azure, OpenRouter, vLLM, Ollama)"),
    ("whisper", "Whisper (OpenAI-compatible /audio/transcriptions)"),
    ("kokoro", "Kokoro (OpenAI-compatible /audio/speech)"),
    ("judge0", "Judge0"),
    ("dev_local", "Local subprocess (DEVELOPMENT ONLY)"),
    ("mock", "Mock (offline, for testing)"),
]

ROLE_KINDS = {
    "llm": {"anthropic", "openai", "mock"},
    "stt": {"whisper", "mock"},
    "tts": {"kokoro", "mock"},
    "sandbox": {"judge0", "dev_local", "mock"},
}


class AiInterviewProvider(models.Model):
    _name = "ai.interview.provider"
    _description = "Linda – AI / speech / sandbox provider"
    _order = "role, sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    role = fields.Selection(ROLES, required=True)
    kind = fields.Selection(KINDS, required=True, default="mock")
    base_url = fields.Char(help="Leave empty for the provider default (e.g. https://api.anthropic.com).")
    api_key = fields.Char(groups="hr_recruitment.group_hr_recruitment_manager", copy=False)
    workspace_id = fields.Char(
        "Workspace ID", groups="hr_recruitment.group_hr_recruitment_manager",
        help="Anthropic: required when the API key is not scoped to a workspace (e.g. sk-ant-usr… keys). "
             "Sent as the anthropic-workspace-id header. Looks like wrkspc_…")
    model = fields.Char(help="Any model name the provider accepts, e.g. claude-sonnet-5-5, claude-haiku-4-5, "
                             "gpt-4.1-mini, llama3.1:8b, Systran/faster-whisper-large-v3.")
    effort = fields.Selection([("low", "Low"), ("medium", "Medium"), ("high", "High"), ("xhigh", "Extra high"),
                               ("max", "Max")],
                              help="Anthropic effort level. Leave empty for models that do not support it "
                                   "(e.g. claude-haiku-4-5).")
    refusal_fallback = fields.Boolean(
        default=True, help="Anthropic: enable the server-side refusal fallback on models that support it.")
    timeout = fields.Integer(default=60, help="Request timeout in seconds.")
    voice = fields.Char(help="TTS voice name (Kokoro), e.g. af_heart.")
    price_input = fields.Float("Price / 1M input tokens", digits=(12, 4))
    price_output = fields.Float("Price / 1M output tokens", digits=(12, 4))
    time_limits = fields.Char(
        default=lambda self: json.dumps(DEFAULT_TIME_LIMITS),
        help='Sandbox per-test time limits (seconds) per language as JSON, e.g. {"python": 2, "c": 1}.')
    language_ids = fields.Char(help='Judge0 language ids override as JSON, e.g. {"python": 71}.')
    allow_dev_local = fields.Boolean(
        "I understand this runs candidate code on the Odoo server",
        help="Required to use the local subprocess sandbox. Never enable in production.")
    notes = fields.Text()

    @api.constrains("role", "kind")
    def _check_kind(self):
        for rec in self:
            family = rec.role.split("_")[0] if rec.role != "sandbox" else "sandbox"
            if rec.kind not in ROLE_KINDS[family]:
                raise ValidationError(self.env._("Provider type %(kind)s cannot be used for role %(role)s.",
                                                 kind=rec.kind, role=rec.role))

    @api.constrains("time_limits", "language_ids")
    def _check_json(self):
        for rec in self:
            for value in (rec.time_limits, rec.language_ids):
                if value:
                    try:
                        json.loads(value)
                    except ValueError:
                        raise ValidationError(self.env._("Invalid JSON: %s", value))

    def _config(self):
        """Plain dict handed to the service adapters (read with sudo: api_key is admin-only)."""
        self.ensure_one()
        rec = self.sudo()
        return {
            "kind": rec.kind, "base_url": rec.base_url, "api_key": rec.api_key, "model": rec.model,
            "workspace_id": (rec.workspace_id or "").strip() or None,
            "effort": rec.effort, "refusal_fallback": rec.refusal_fallback, "timeout": rec.timeout,
            "voice": rec.voice, "allow_dev_local": rec.allow_dev_local,
            "time_limits": json.loads(rec.time_limits) if rec.time_limits else {},
            "language_ids": json.loads(rec.language_ids) if rec.language_ids else {},
        }

    @api.model
    def _get_for_role(self, role):
        return self.sudo().search([("role", "=", role)], limit=1)

    def action_test_connection(self):
        """Send a tiny request to check the configuration."""
        self.ensure_one()
        engine = self.env["ai.interview.engine"]
        if self.role.startswith("llm"):
            text = engine._llm_call(self.role, "ping", "TASK: ping\nReply with the single word OK.",
                                    [{"role": "user", "content": "ping"}], provider=self, max_tokens=20).text
            message = self.env._("Model replied: %s", (text or "")[:100])
        elif self.role == "sandbox":
            res = engine._run_code("python", 'print(input())', [{"stdin": "ok\n", "stdout": "ok"}], provider=self)
            message = self.env._("Sandbox result: %s", res[0]["status"])
        elif self.role == "tts":
            audio, mime = engine._tts("Hello from Linda.", provider=self)
            message = self.env._("Received %(n)s bytes of %(m)s", n=len(audio), m=mime)
        else:
            from ..services import speech
            audio, _mime = speech.synthesize({"kind": "mock"}, "test")
            res = engine._stt(audio, self.role, filename="test.wav", mimetype="audio/wav", provider=self)
            message = self.env._("Transcript: %s", res["text"][:100] or "(empty)")
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": self.env._("Connection OK"), "message": message, "type": "success"}}


class AiInterviewCallLog(models.Model):
    _name = "ai.interview.call.log"
    _description = "Linda – external service call log"
    _order = "id desc"

    session_id = fields.Many2one("ai.interview.session", index=True, ondelete="cascade")
    question_id = fields.Many2one("ai.interview.question", index=True, ondelete="set null")
    role = fields.Selection(ROLES)
    task = fields.Char()
    section = fields.Selection(SECTION_TYPES + [("general", "Whole interview")], index=True,
                               help="Interview section the call was made for (token usage per section).")
    phase = fields.Selection([("interview", "During the interview"), ("scoring", "Scoring")])
    provider_id = fields.Many2one("ai.interview.provider", ondelete="set null")
    kind = fields.Char()
    model = fields.Char()
    request = fields.Text()
    response = fields.Text()
    status = fields.Selection([("ok", "OK"), ("error", "Error")], default="ok")
    error = fields.Text()
    input_tokens = fields.Integer()
    output_tokens = fields.Integer()
    cost = fields.Float(digits=(12, 6))
    latency_ms = fields.Integer("Latency (ms)")
