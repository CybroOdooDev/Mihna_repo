"""Single entry point for every external service call.

All calls are made server-side (API keys never reach the browser) and each one is
written to ``ai.interview.call.log`` with tokens and cost (FRD §8, §11 audit/cost).
"""
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from odoo import api, models

from ..services import llm as llm_service
from ..services import sandbox as sandbox_service
from ..services import speech as speech_service

_logger = logging.getLogger(__name__)

MOCK_PROVIDER = {"kind": "mock", "model": "mock"}

# Which section a call belongs to when the task alone says it. Scoring calls are named score_<dimension>_runN;
# attitude is scored mainly from the voice interview, so it is counted there.
TASK_SECTION = {"interviewer_turn": "voice", "code_followups": "coding", "ask_doc": "learn",
                "reference_answer": "written", "written_spoken_gap": "general"}
DIMENSION_SECTION = {"coding": "coding", "learning": "learn", "written_english": "written",
                     "oral_english": "voice", "attitude": "voice"}
SCORING_STATES = ("submitted", "scored", "reviewed")


class AiInterviewEngine(models.AbstractModel):
    _name = "ai.interview.engine"
    _description = "Linda – service gateway"

    def _provider(self, role, provider=None):
        provider = provider or self.env["ai.interview.provider"]._get_for_role(role)
        return provider, (provider._config() if provider else dict(MOCK_PROVIDER))

    def _usage_tags(self, session, task):
        """Section and phase of a session call, for token usage per section."""
        section = self.env.context.get("linda_section") or TASK_SECTION.get(task)
        if not section and task.startswith("score_"):
            section = DIMENSION_SECTION.get(task[len("score_"):].rsplit("_run", 1)[0])
        if not section and session.state == "in_progress":
            section = session.current_section
        return {"section": section or "general",
                "phase": "scoring" if session.state in SCORING_STATES else "interview"}

    def _log(self, vals):
        if vals.get("session_id") and "section" not in vals:
            session = self.env["ai.interview.session"].sudo().browse(vals["session_id"])
            vals = dict(vals, **self._usage_tags(session, vals.get("task") or ""))
        try:
            self.env["ai.interview.call.log"].sudo().create(vals)
        except Exception:  # never let logging break the interview
            _logger.exception("Could not write AI call log")

    @api.model
    def _llm_call(self, role, task, system, messages, schema=None, session=None, question=None,
                  provider=None, max_tokens=4000):
        provider, config = self._provider(role, provider)
        adapter = llm_service.get_llm(config)
        log = {"session_id": session.id if session else False, "question_id": question.id if question else False,
               "role": role, "task": task, "provider_id": provider.id if provider else False,
               "kind": config["kind"], "model": config.get("model"),
               "request": json.dumps({"system": system, "messages": messages}, ensure_ascii=False)[:100000]}
        started = time.time()
        try:
            result = adapter.complete(system, messages, schema=schema, max_tokens=max_tokens)
        except llm_service.LLMError as exc:
            self._log(dict(log, status="error", error=str(exc), latency_ms=int((time.time() - started) * 1000)))
            raise
        except Exception as exc:
            self._log(dict(log, status="error", error=repr(exc), latency_ms=int((time.time() - started) * 1000)))
            raise llm_service.LLMError(str(exc)) from exc
        cost = 0.0
        if provider:
            cost = (result.input_tokens * provider.price_input + result.output_tokens * provider.price_output) / 1e6
        self._log(dict(log, response=result.text[:100000], input_tokens=result.input_tokens,
                       output_tokens=result.output_tokens, cost=cost, model=result.model or config.get("model"),
                       latency_ms=int((time.time() - started) * 1000)))
        return result

    @api.model
    def _llm_batch(self, role, calls, session=None, max_workers=6):
        """Run independent LLM calls concurrently (scoring makes ~10), so a session scores within
        the cron time limit. Threads only do HTTP through the adapters; all ORM work (provider
        lookup, logging) stays in this thread. ``calls``: list of (task, system, messages, schema,
        max_tokens). Returns results in the same order; raises the first error after logging all."""
        if not calls:
            return []
        provider, config = self._provider(role)

        def run(call):
            _task, system, messages, schema, max_tokens = call
            started = time.time()
            try:
                # one adapter per call: adapters may adjust their config after a rejected request
                res = llm_service.get_llm(dict(config)).complete(system, messages, schema=schema,
                                                                 max_tokens=max_tokens)
                return res, None, started
            except Exception as exc:  # collected and re-raised below
                return None, exc, started

        with ThreadPoolExecutor(max_workers=min(max_workers, len(calls))) as pool:
            outcomes = list(pool.map(run, calls))
        results, first_error = [], None
        for (task, system, messages, _schema, _max), (res, exc, started) in zip(calls, outcomes):
            log = {"session_id": session.id if session else False, "role": role, "task": task,
                   "provider_id": provider.id if provider else False, "kind": config["kind"],
                   "model": config.get("model"),
                   "request": json.dumps({"system": system, "messages": messages}, ensure_ascii=False)[:100000]}
            if exc is not None:
                self._log(dict(log, status="error", error=str(exc), latency_ms=int((time.time() - started) * 1000)))
                first_error = first_error or (exc if isinstance(exc, llm_service.LLMError)
                                              else llm_service.LLMError(str(exc)))
                results.append(None)
                continue
            cost = 0.0
            if provider:
                cost = (res.input_tokens * provider.price_input + res.output_tokens * provider.price_output) / 1e6
            self._log(dict(log, response=res.text[:100000], input_tokens=res.input_tokens,
                           output_tokens=res.output_tokens, cost=cost, model=res.model or config.get("model"),
                           latency_ms=res.latency_ms))
            results.append(res)
        if first_error:
            raise first_error
        return results

    @api.model
    def _run_code(self, language, code, tests, session=None, provider=None):
        provider, config = self._provider("sandbox", provider)
        started = time.time()
        try:
            results = sandbox_service.get_sandbox(config).run(language, code, tests)
        except sandbox_service.SandboxError as exc:
            self._log({"session_id": session.id if session else False, "role": "sandbox", "task": "run_code",
                       "kind": config["kind"], "status": "error", "error": str(exc),
                       "provider_id": provider.id if provider else False})
            raise
        self._log({"session_id": session.id if session else False, "role": "sandbox", "task": "run_code",
                   "kind": config["kind"], "provider_id": provider.id if provider else False,
                   "request": json.dumps({"language": language, "tests": len(tests)}),
                   "response": json.dumps([{k: r[k] for k in ("passed", "status", "time_ms")} for r in results]),
                   "latency_ms": int((time.time() - started) * 1000)})
        return results

    @api.model
    def _stt(self, audio, role="stt_fast", filename="answer.webm", mimetype="audio/webm", session=None,
             provider=None):
        provider, config = self._provider(role, provider)
        try:
            result = speech_service.transcribe(config, audio, filename, mimetype)
        except speech_service.SpeechError as exc:
            self._log({"session_id": session.id if session else False, "role": role, "task": "transcribe",
                       "kind": config["kind"], "status": "error", "error": str(exc),
                       "provider_id": provider.id if provider else False})
            raise
        self._log({"session_id": session.id if session else False, "role": role, "task": "transcribe",
                   "kind": config["kind"], "model": config.get("model"),
                   "provider_id": provider.id if provider else False,
                   "response": result["text"][:5000], "latency_ms": result["latency_ms"]})
        return result

    @api.model
    def _tts(self, text, session=None, provider=None):
        provider, config = self._provider("tts", provider)
        voice = self.env["ir.config_parameter"].sudo().get_str("linda_ai_interview.tts_voice")
        started = time.time()
        audio, mime = speech_service.synthesize(config, text, voice=voice or None)
        self._log({"session_id": session.id if session else False, "role": "tts", "task": "synthesize",
                   "kind": config["kind"], "provider_id": provider.id if provider else False,
                   "request": text[:2000], "latency_ms": int((time.time() - started) * 1000)})
        return audio, mime
