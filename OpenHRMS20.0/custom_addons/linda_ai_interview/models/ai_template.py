from odoo import api, fields, models
from odoo.exceptions import ValidationError

SECTION_TYPES = [
    ("written", "Written English"),
    ("coding", "Coding"),
    ("learn", "Learn and apply"),
    ("voice", "Voice interview"),
]
SECTION_ORDER = [s[0] for s in SECTION_TYPES]

TONES = [("friendly", "Friendly and encouraging"), ("neutral", "Calm and professional"), ("formal", "Formal")]

LANGUAGE_SELECTION = [("python", "Python"), ("c", "C"), ("cpp", "C++"), ("javascript", "JavaScript")]

DIMENSION_SELECTION = [
    ("coding", "Coding and problem solving"),
    ("learning", "Learning and adaptability"),
    ("attitude", "Attitude and workplace fit"),
    ("oral_english", "Oral English"),
    ("written_english", "Written English"),
]


class AiInterviewTemplate(models.Model):
    _name = "ai.interview.template"
    _description = "Linda – interview template"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    job_ids = fields.Many2many("hr.job", string="Job positions",
                               help="The template used when sending an AI interview for these jobs.")
    section_ids = fields.One2many("ai.interview.template.section", "template_id", copy=True)
    tone = fields.Selection(TONES, default="friendly", required=True, string="Interviewer tone")
    total_minutes = fields.Integer("Total time cap (min)", default=70, required=True)
    invite_hours = fields.Integer("Invite validity (hours)", default=72, required=True)
    lang_python = fields.Boolean("Python", default=True)
    lang_c = fields.Boolean("C", default=True)
    lang_cpp = fields.Boolean("C++", default=True)
    lang_javascript = fields.Boolean("JavaScript", default=True)

    weight_coding = fields.Integer("Coding %", default=30)
    weight_learning = fields.Integer("Learning %", default=20)
    weight_attitude = fields.Integer("Attitude %", default=20)
    weight_oral_english = fields.Integer("Oral English %", default=15)
    weight_written_english = fields.Integer("Written English %", default=15)
    band_strong = fields.Integer("Strong from (/100)", default=70)
    band_borderline = fields.Integer("Borderline from (/100)", default=50)

    auto_invite_stage_id = fields.Many2one(
        "hr.recruitment.stage", string="Auto-invite at stage",
        help="When automatic invites are enabled in settings, applicants entering this stage receive the invite.")
    max_resumes = fields.Integer(default=2, help="How many times a candidate may resume after a disconnect.")
    notes = fields.Html()

    @api.constrains("weight_coding", "weight_learning", "weight_attitude", "weight_oral_english",
                    "weight_written_english")
    def _check_weights(self):
        for rec in self:
            if sum(rec._weights().values()) != 100:
                raise ValidationError(self.env._("Dimension weights must add up to 100%."))

    @api.constrains("band_strong", "band_borderline")
    def _check_bands(self):
        for rec in self:
            if not 0 < rec.band_borderline < rec.band_strong <= 100:
                raise ValidationError(self.env._("Band thresholds must satisfy 0 < Borderline < Strong <= 100."))

    @api.constrains("section_ids", "total_minutes")
    def _check_sections(self):
        for rec in self:
            types = rec.section_ids.mapped("section_type")
            if len(types) != len(set(types)):
                raise ValidationError(self.env._("Each section type can appear only once in a template."))
            if sum(rec.section_ids.mapped("min_minutes")) > rec.total_minutes:
                raise ValidationError(self.env._("The minimum section times exceed the total time cap."))

    def _weights(self):
        self.ensure_one()
        return {
            "coding": self.weight_coding, "learning": self.weight_learning, "attitude": self.weight_attitude,
            "oral_english": self.weight_oral_english, "written_english": self.weight_written_english,
        }

    def _languages(self):
        """Languages allowed by the template AND enabled globally in settings."""
        self.ensure_one()
        enabled = self.env["res.config.settings"]._linda_enabled_languages()
        return [code for code, _label in LANGUAGE_SELECTION if self[f"lang_{code}"] and code in enabled]

    def _sections(self):
        """Active sections in the fixed FRD order."""
        self.ensure_one()
        return self.section_ids.filtered("active").sorted(lambda s: SECTION_ORDER.index(s.section_type))

    def _band_for(self, total):
        self.ensure_one()
        if total >= self.band_strong:
            return "strong"
        if total >= self.band_borderline:
            return "borderline"
        return "not_recommended"

    @api.model
    def _for_job(self, job):
        return self.search([("job_ids", "in", job.id)], limit=1) if job else self.browse()


class AiInterviewTemplateSection(models.Model):
    _name = "ai.interview.template.section"
    _description = "Linda – template section"
    _order = "template_id, sequence, id"

    template_id = fields.Many2one("ai.interview.template", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    section_type = fields.Selection(SECTION_TYPES, required=True)
    guidance = fields.Text("AI guidance", help="Topics to cover, target level, sample questions, style notes.")
    avoid = fields.Text("Things to avoid")
    difficulty = fields.Integer("Target difficulty (1-5)", default=2)
    min_minutes = fields.Integer("Min minutes", default=10)
    max_minutes = fields.Integer("Max minutes", default=15)
    question_count = fields.Integer("Questions", default=2,
                                    help="Written tasks, coding problems, learn tasks or voice questions.")
    followup_count = fields.Integer("Follow-ups per question", default=1,
                                    help="Coding: follow-up questions on the candidate's code (2-3). "
                                         "Voice: follow-ups per spoken question.")
    mandatory_question_ids = fields.Many2many(
        "ai.interview.question", "ai_template_section_mandatory_rel", "section_id", "question_id",
        string="Mandatory questions", help="Always asked (counted within the number of questions).")
    example_question_ids = fields.Many2many(
        "ai.interview.question", "ai_template_section_example_rel", "section_id", "question_id",
        string="Example questions", help="Shown to the AI as style examples; not asked verbatim.")

    @api.constrains("min_minutes", "max_minutes", "difficulty", "question_count")
    def _check_values(self):
        for rec in self:
            if rec.min_minutes < 0 or rec.max_minutes <= 0 or rec.min_minutes > rec.max_minutes:
                raise ValidationError(self.env._("Section minutes must satisfy 0 <= min <= max."))
            if not 1 <= rec.difficulty <= 5:
                raise ValidationError(self.env._("Difficulty must be between 1 and 5."))
            if rec.question_count < 1:
                raise ValidationError(self.env._("A section needs at least one question."))

    @api.depends("section_type", "template_id")
    def _compute_display_name(self):
        labels = dict(SECTION_TYPES)
        for rec in self:
            rec.display_name = labels.get(rec.section_type, "")
