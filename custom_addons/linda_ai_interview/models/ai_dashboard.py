"""Data providers for the OWL dashboards (FRD §6). Access rights apply: reviewers only
get campaigns/sessions their record rules allow."""
from collections import Counter, defaultdict

from odoo import api, fields, models

from .ai_session import BANDS, DECISIONS, RISKS, SESSION_STATES
from .ai_template import DIMENSION_SELECTION, LANGUAGE_SELECTION, SECTION_TYPES


class AiInterviewCampaignDashboard(models.Model):
    _inherit = "ai.interview.campaign"

    @api.model
    def get_dashboard_data(self, campaign_id):
        campaign = self.browse(campaign_id).exists()
        campaign.check_access("read")
        sessions = campaign.session_ids.filtered(lambda s: s.state not in ("draft", "cancelled"))
        scored = sessions.filtered(lambda s: s.state in ("scored", "reviewed"))
        funnel = [
            ("invited", len(sessions)),
            ("started", len(sessions.filtered("started_at"))),
            ("submitted", len(sessions.filtered(lambda s: s.state in ("submitted", "scored", "reviewed")))),
            ("scored", len(scored)),
            ("reviewed", len(sessions.filtered(lambda s: s.state == "reviewed"))),
        ]
        dims = [d for d, _l in DIMENSION_SELECTION]
        spread = {}
        for dim in dims:
            values = [s[f"score_{dim}"] for s in scored if s[f"score_{dim}"]]
            spread[dim] = {str(v): values.count(v) for v in range(1, 6)}
            spread[dim]["avg"] = round(sum(values) / len(values), 2) if values else 0
        daily = defaultdict(int)
        for s in sessions.filtered("finished_at"):
            daily[fields.Date.to_string(s.finished_at.date())] += 1
        candidates = [{
            "id": s.id, "name": s.applicant_id.partner_name or s.applicant_id.display_name,
            "applicant_id": s.applicant_id.id, "state": s.state, "total": round(s.total_score, 1),
            "band": s.band or False, "risk": s.risk or False, "flags": s.integrity_signal_count,
            "red_flags": s.red_flag_count, "reviewer": s.reviewer_id.name or "",
            "decision": s.decision or False, "needs_review": s.needs_review,
            "language": s.language or False, "tokens": s.tokens_total, "cost": round(s.cost_total, 4),
            "scores": {d: s[f"score_{d}"] for d in dims},
        } for s in sessions]
        return {
            "campaign": {"id": campaign.id, "name": campaign.name, "job": campaign.job_id.name,
                         "state": campaign.state, "template": campaign.template_id.name,
                         "date_start": fields.Date.to_string(campaign.date_start),
                         "date_end": fields.Date.to_string(campaign.date_end) if campaign.date_end else False},
            "kpis": {
                "invited": campaign.invited_count, "started": campaign.started_count,
                "submitted": campaign.submitted_count, "expired": campaign.expired_count,
                "completion_rate": round(campaign.completion_rate, 1),
                "average_score": round(campaign.average_score, 1),
                "reviews_pending": campaign.review_pending_count,
            },
            "funnel": funnel,
            "bands": {k: len(scored.filtered(lambda s, k=k: s.band == k)) for k, _l in BANDS},
            "risks": {k: len(scored.filtered(lambda s, k=k: s.risk == k)) for k, _l in RISKS},
            "languages": dict(Counter(s.language for s in sessions if s.language)),
            "spread": spread,
            "daily": sorted(daily.items()),
            "candidates": candidates,
            "labels": {
                "dimensions": dict(DIMENSION_SELECTION), "bands": dict(BANDS), "risks": dict(RISKS),
                "states": dict(SESSION_STATES), "decisions": dict(DECISIONS),
                "languages": dict(LANGUAGE_SELECTION),
            },
            "can_manage": self.env.user.has_group("hr_recruitment.group_hr_recruitment_user"),
        }


class AiInterviewSessionDashboard(models.Model):
    _inherit = "ai.interview.session"

    def get_dashboard_data(self):
        self.ensure_one()
        self.check_access("read")
        s = self
        peers = s.campaign_id.session_ids.filtered(lambda x: x.state in ("scored", "reviewed")) if s.campaign_id \
            else self.browse()
        dims = [d for d, _l in DIMENSION_SELECTION]
        campaign_avg = {d: round(sum(p[f"score_{d}"] for p in peers) / len(peers), 2) if peers else 0 for d in dims}
        sections = []
        for stype, label in SECTION_TYPES:
            responses = s.response_ids.filtered(lambda r, st=stype: r.section == st)
            if not responses:
                continue
            sections.append({"type": stype, "label": label, "responses": [{
                "id": r.id, "prompt": r.prompt_text, "answer": r.answer_text or "", "code": r.code or "",
                "language": dict(LANGUAGE_SELECTION).get(r.language, ""), "title": r.question_id.name or "",
                "doc": (r.question_id.reference_doc or "") if stype == "learn" else "",
                "tests_passed": r.tests_passed, "tests_total": r.tests_total,
                "test_results": [{k: t.get(k) for k in ("status", "passed", "hidden", "time_ms", "stdin",
                                                         "expected", "stdout", "stderr")}
                                 for t in (r.test_results or [])],
                "followups": [{"q": f.get("q"), "a": f.get("a_final") or f.get("a"),
                               "audio_id": f.get("audio_id")} for f in (r.followups or [])],
                "doc_questions": r.doc_questions or [], "run_log": r.run_log or [],
                "transcript": r._final_transcript(), "time_spent": r.time_spent,
                "audio": [{"id": a.id, "name": a.name} for a in r.audio_attachment_ids],
                "has_keystrokes": bool(r.keystroke_log),
            } for r in responses]})
        return {
            "session": {
                "id": s.id, "name": s.name, "candidate": s.applicant_id.partner_name or "",
                "applicant_id": s.applicant_id.id, "job": s.job_id.name or "", "state": s.state,
                "campaign": s.campaign_id.name or "", "campaign_id": s.campaign_id.id,
                "template": s.template_id.name, "total": round(s.total_score, 1), "band": s.band or False,
                "risk": s.risk or False, "duration": s.duration_minutes, "reviewer": s.reviewer_id.name or "",
                "reviewer_id": s.reviewer_id.id, "decision": s.decision or False, "band_confirmed": s.band_confirmed,
                "review_notes": str(s.review_notes or ""), "needs_review": s.needs_review,
                "red_flags": s.red_flag_count, "live_recheck": s.live_recheck_required,
                "started_at": fields.Datetime.to_string(s.started_at) if s.started_at else "",
                "finished_at": fields.Datetime.to_string(s.finished_at) if s.finished_at else "",
                "consent_at": fields.Datetime.to_string(s.consent_at) if s.consent_at else "",
                "consent_version": s.consent_version, "resume_count": s.resume_count,
                "cost": round(s.cost_total, 4), "tokens": s.tokens_total,
                "language": dict(LANGUAGE_SELECTION).get(s.language, ""),
                "scoring_state": s.scoring_state, "scoring_error": s.scoring_error or "",
            },
            "scores": [{
                "id": sc.id, "dimension": sc.dimension, "label": dict(DIMENSION_SELECTION)[sc.dimension],
                "ai_score": sc.ai_score, "run1": sc.ai_score_run1, "run2": sc.ai_score_run2,
                "human_score": sc.human_score, "final": sc.final_score, "reason": sc.override_reason or "",
                "evidence": sc.evidence or [], "criteria": sc.criteria or [], "rationale": sc.rationale or "",
                "needs_review": sc.needs_review, "red_flag": sc.is_red_flag, "weight": sc.weight,
                "campaign_avg": campaign_avg.get(sc.dimension, 0),
            } for sc in s.score_ids],
            "flags": [{"id": f.id, "type": f.type, "label": dict(f._fields["type"].selection)[f.type],
                       "weight": f.weight, "signal": f.is_signal, "detail": f.detail or "",
                       "timestamp": fields.Datetime.to_string(f.timestamp), "response_id": f.response_id.id}
                      for f in s.flag_ids],
            "sections": sections,
            "usage": s._token_usage(),
            "labels": {"bands": dict(BANDS), "risks": dict(RISKS), "states": dict(SESSION_STATES),
                       "decisions": dict(DECISIONS)},
            "can_review": self.env.user.has_group("hr_recruitment.group_hr_recruitment_interviewer"),
        }

    def get_keystroke_log(self, response_id):
        self.ensure_one()
        self.check_access("read")
        resp = self.response_ids.filtered(lambda r: r.id == response_id)
        return {"log": resp.keystroke_log or [], "final": resp.code or resp.answer_text or ""}

    def save_review(self, vals):
        """Review panel: overrides, notes, decision (and optional confirmation)."""
        self.ensure_one()
        self.check_access("write")
        for item in vals.get("overrides", []):
            score = self.score_ids.filtered(lambda sc: sc.id == item["id"])
            if score:
                score.write({"human_score": int(item.get("human_score") or 0),
                             "override_reason": item.get("reason") or False})
        update = {k: vals[k] for k in ("decision", "review_notes") if k in vals}
        if update:
            self.write(update)
        if vals.get("confirm"):
            self.action_confirm_review()
        return True
