import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import prompts
from ..services.llm import LLMError

_logger = logging.getLogger(__name__)


class AiInterviewQuestionGenerate(models.TransientModel):
    _name = "ai.interview.question.generate"
    _description = "Linda – generate pool questions"

    qtype = fields.Selection([("coding", "Coding problems"), ("learn", "Learn-and-apply tasks")],
                             required=True, default="coding")
    count = fields.Integer(default=5, required=True)
    difficulty = fields.Integer(default=2, required=True)
    guidance = fields.Text(help="Topics, constraints and style for the generated questions.")
    validate_now = fields.Boolean(default=False,
                                  help="Validate in the sandbox immediately instead of in the background job.")
    pool_status = fields.Html(compute="_compute_pool_status")

    @api.depends("qtype")
    def _compute_pool_status(self):
        status = self.env["ai.interview.question"]._pool_status()
        labels = dict(self.env["ai.interview.question"]._fields["qtype"].selection)
        rows = "".join(f"<tr><td>{labels[k]}</td><td>{v['approved']} / {v['target']}</td></tr>"
                       for k, v in status.items())
        for rec in self:
            rec.pool_status = f"<table class='table table-sm'><tr><th>Type</th><th>Approved / target</th></tr>{rows}</table>"

    def action_generate(self):
        self.ensure_one()
        if not 1 <= self.count <= 20:
            raise UserError(self.env._("Generate between 1 and 20 questions at a time."))
        Question = self.env["ai.interview.question"]
        engine = self.env["ai.interview.engine"]
        existing = Question.search([("qtype", "=", self.qtype)], limit=200).mapped("name")
        created = Question
        errors = []
        for _i in range(self.count):
            builder = prompts.generate_coding_problem if self.qtype == "coding" else prompts.generate_learn_doc
            schema = prompts.CODING_PROBLEM_SCHEMA if self.qtype == "coding" else prompts.LEARN_DOC_SCHEMA
            system, messages = builder(self.guidance, self.difficulty, existing + created.mapped("name"))
            try:
                res = engine._llm_call("llm_generator", f"generate_{self.qtype}", system, messages,
                                       schema=schema, max_tokens=8000)
            except LLMError as exc:
                errors.append(str(exc))
                continue
            created |= Question._create_from_generated(self.qtype, res.data, self.difficulty)
        if self.validate_now:
            created.action_validate()
        else:
            self.env.ref("linda_ai_interview.ir_cron_validate_questions")._trigger()
        if not created:
            raise UserError(self.env._("No question could be generated:\n%s", "\n".join(errors[:3])))
        action = self.env["ir.actions.act_window"]._for_xml_id("linda_ai_interview.action_ai_interview_question")
        action.update(domain=[("id", "in", created.ids)], context={})
        return action
